/**
 * k6 Load Test for mostlylucid-nmt GPU Translation API
 *
 * This test simulates realistic load patterns to determine maximum throughput
 * and identify bottlenecks for the GPU-accelerated translation service.
 *
 * Installation:
 *   Download k6: https://k6.io/docs/get-started/installation/
 *
 * Usage:
 *   # Smoke test (quick validation)
 *   k6 run --vus 1 --duration 30s tests/k6-load-test.js
 *
 *   # Load test (find capacity limits)
 *   k6 run --vus 10 --duration 2m tests/k6-load-test.js
 *
 *   # Stress test (push beyond limits)
 *   k6 run --vus 50 --duration 5m tests/k6-load-test.js
 *
 *   # Spike test (sudden traffic burst)
 *   k6 run --stage 0s:1,10s:50,20s:50,30s:1 tests/k6-load-test.js
 *
 * Environment Variables:
 *   BASE_URL: API base URL (default: http://localhost:8000)
 *
 * Metrics to watch:
 *   - http_req_duration: Request latency (p95 should be <2s for single sentence)
 *   - http_req_failed: Error rate (should be <1%)
 *   - http_reqs: Requests per second (GPU should handle 5-10 rps with beam_size=5)
 *   - vus: Virtual users (concurrent requests)
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const translationErrors = new Rate('translation_errors');
const translationDuration = new Trend('translation_duration_ms');
const translatedChars = new Counter('translated_chars');
const pivotTranslations = new Counter('pivot_translations');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Test data: variety of languages and text lengths
const TEST_SENTENCES = [
  { src: 'en', tgt: 'de', text: 'Hello world' },
  { src: 'en', tgt: 'fr', text: 'The quick brown fox jumps over the lazy dog' },
  { src: 'en', tgt: 'es', text: 'Machine translation has come a long way in recent years' },
  { src: 'de', tgt: 'en', text: 'Guten Morgen, wie geht es Ihnen heute?' },
  { src: 'fr', tgt: 'en', text: 'Bonjour, comment allez-vous?' },
  { src: 'es', tgt: 'de', text: 'La inteligencia artificial está transformando el mundo' },
  { src: 'it', tgt: 'en', text: 'Buongiorno a tutti' },
  { src: 'en', tgt: 'ja', text: 'This is a test of the translation system' },
  // Longer text for stress testing
  {
    src: 'en',
    tgt: 'de',
    text: 'Artificial intelligence and machine learning have revolutionized the field of natural language processing. Modern neural machine translation systems can now produce translations that rival human quality for many language pairs. However, challenges remain for low-resource languages and domain-specific terminology.'
  },
];

// Default test options (can be overridden by CLI flags)
export const options = {
  // Stages define the load profile
  stages: [
    { duration: '30s', target: 5 },  // Ramp up to 5 users
    { duration: '1m', target: 10 },  // Increase to 10 users
    { duration: '30s', target: 15 }, // Spike to 15 users
    { duration: '1m', target: 10 },  // Drop back to 10
    { duration: '30s', target: 0 },  // Ramp down
  ],

  // Thresholds define success criteria
  thresholds: {
    'http_req_duration': ['p95<5000'],  // 95% of requests under 5s
    'http_req_failed': ['rate<0.05'],   // Error rate under 5%
    'translation_errors': ['rate<0.05'], // Translation errors under 5%
  },
};

/**
 * Setup function - runs once before test starts
 */
export function setup() {
  // Check if API is available
  const healthCheck = http.get(`${BASE_URL}/healthz`);
  if (healthCheck.status !== 200) {
    throw new Error(`API not available at ${BASE_URL}. Start the server first.`);
  }

  console.log(`API is available at ${BASE_URL}`);

  // Get model info
  const modelInfo = http.get(`${BASE_URL}/model_name`);
  if (modelInfo.status === 200) {
    const info = modelInfo.json();
    console.log(`Model: ${info.model_name}, Device: ${info.device}`);
  }

  return { baseUrl: BASE_URL };
}

/**
 * Main test function - runs for each virtual user iteration
 */
export default function (data) {
  // Select random test case
  const testCase = TEST_SENTENCES[Math.floor(Math.random() * TEST_SENTENCES.length)];

  // Prepare request
  const payload = JSON.stringify({
    text: [testCase.text],
    source_lang: testCase.src,
    target_lang: testCase.tgt,
    beam_size: 5,
    perform_sentence_splitting: true
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: '30s', // Individual request timeout
  };

  // Make translation request
  const startTime = new Date().getTime();
  const response = http.post(`${data.baseUrl}/translate`, payload, params);
  const endTime = new Date().getTime();
  const duration = endTime - startTime;

  // Record metrics
  translationDuration.add(duration);

  // Validate response
  const success = check(response, {
    'status is 200': (r) => r.status === 200,
    'has translated field': (r) => {
      try {
        const json = r.json();
        return 'translated' in json;
      } catch {
        return false;
      }
    },
    'translation not empty': (r) => {
      try {
        const json = r.json();
        return json.translated && json.translated.length > 0 && json.translated[0] !== '';
      } catch {
        return false;
      }
    },
    'response time < 10s': (r) => r.timings.duration < 10000,
  });

  if (response.status === 200) {
    try {
      const result = response.json();

      // Track translation errors
      if (!result.translated || result.translated[0] === '') {
        translationErrors.add(1);
      } else {
        translationErrors.add(0);

        // Count translated characters
        translatedChars.add(result.translated[0].length);

        // Track pivot translations
        if (result.pivot_path) {
          pivotTranslations.add(1);
        }
      }
    } catch (e) {
      translationErrors.add(1);
    }
  } else {
    translationErrors.add(1);
  }

  // Think time: simulate realistic user behavior (1-3 seconds between requests)
  sleep(Math.random() * 2 + 1);
}

/**
 * Teardown function - runs once after test completes
 */
export function teardown(data) {
  console.log('\nLoad test completed');
}

/**
 * Custom summary handler - runs after test to generate report
 */
export function handleSummary(data) {
  const summary = {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
  };

  // Also write JSON summary to file
  summary['tests/k6-summary.json'] = JSON.stringify(data);

  return summary;
}

// Helper function for text summary (basic version, k6 has built-in)
function textSummary(data, options) {
  return ''; // k6 will use its built-in summary
}
