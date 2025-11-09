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

// Test data
const TEST_SENTENCES = [
  { src: 'en', tgt: 'de', text: 'Hello world' },
  { src: 'en', tgt: 'fr', text: 'The quick brown fox jumps over the lazy dog' },
  { src: 'en', tgt: 'es', text: 'Machine translation has come a long way in recent years' },
  { src: 'de', tgt: 'en', text: 'Guten Morgen, wie geht es Ihnen heute?' },
  { src: 'fr', tgt: 'en', text: 'Bonjour, comment allez-vous?' },
  { src: 'es', tgt: 'de', text: 'La inteligencia artificial está transformando el mundo' },
  { src: 'it', tgt: 'en', text: 'Buongiorno a tutti' },
  { src: 'en', tgt: 'ja', text: 'This is a test of the translation system' },
  {
    src: 'en',
    tgt: 'de',
    text: 'Artificial intelligence and machine learning have revolutionized the field of natural language processing. Modern neural machine translation systems can now produce translations that rival human quality for many language pairs. However, challenges remain for low-resource languages and domain-specific terminology.'
  },
];

// Default test options
export const options = {
  stages: [
    { duration: '30s', target: 5 },
    { duration: '1m', target: 10 },
    { duration: '30s', target: 15 },
    { duration: '1m', target: 10 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p95 < 5000'],
    http_req_failed: ['rate < 0.05'],
    translation_errors: ['rate < 0.05'],
  },
};

// Setup
export function setup() {
  const healthCheck = http.get(`${BASE_URL}/healthz`);
  if (healthCheck.status !== 200) {
    throw new Error(`API not available at ${BASE_URL}. Start the server first.`);
  }
  console.log(`API is available at ${BASE_URL}`);

  const modelInfo = http.get(`${BASE_URL}/model_name`);
  if (modelInfo.status === 200) {
    const info = modelInfo.json();
    console.log(`Model: ${info.model_name}, Device: ${info.device}`);
  }
}

// Main test
export default function () {
  const testCase = TEST_SENTENCES[Math.floor(Math.random() * TEST_SENTENCES.length)];

  const payload = JSON.stringify({
    text: [testCase.text],
    source_lang: testCase.src,
    target_lang: testCase.tgt,
    beam_size: 5,
    perform_sentence_splitting: true,
  });

  const params = {
    headers: { 'Content-Type': 'application/json' },
    timeout: '30s',
  };

  const response = http.post(`${BASE_URL}/translate`, payload, params);

  // Record duration
  translationDuration.add(response.timings.duration);

  // Validate response
  check(response, {
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

  // Error tracking
  let errorFlag = 0;
  if (response.status !== 200) {
    errorFlag = 1;
  } else {
    try {
      const result = response.json();
      if (!result.translated || !result.translated[0]) {
        errorFlag = 1;
      } else {
        translatedChars.add(result.translated[0].length);
        if (result.pivot_path) pivotTranslations.add(1);
      }
    } catch {
      errorFlag = 1;
    }
  }
  translationErrors.add(errorFlag);

  // Think time
  sleep(Math.random() * 2 + 1);
}

// Teardown
export function teardown() {
  console.log('\nLoad test completed');
}

// Summary
export function handleSummary(data) {
  return {
    'k6-summary.json': JSON.stringify(data, null, 2),
  };
}