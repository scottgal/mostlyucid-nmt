#!/bin/bash

# Quick API test script for mostlylucid-nmt v3.1
# Tests various translation pairs including fallback scenarios

set -e

BASE_URL="${1:-http://localhost:8000}"

echo "========================================================================"
echo "  mostlylucid-nmt v3.1 - Quick API Test"
echo "========================================================================"
echo ""
echo "Testing API at: $BASE_URL"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print test header
test_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Function to test translation
test_translate() {
    local text="$1"
    local src="$2"
    local tgt="$3"
    local family="${4:-}"

    echo -e "${GREEN}🧪 Testing: $src → $tgt${NC}"
    echo "   Text: '$text'"

    if [ -z "$family" ]; then
        BODY=$(jq -n \
            --arg text "$text" \
            --arg src "$src" \
            --arg tgt "$tgt" \
            '{text: [$text], source_lang: $src, target_lang: $tgt, beam_size: 1}')
    else
        echo "   Model family: $family"
        BODY=$(jq -n \
            --arg text "$text" \
            --arg src "$src" \
            --arg tgt "$tgt" \
            --arg family "$family" \
            '{text: [$text], source_lang: $src, target_lang: $tgt, beam_size: 1, model_family: $family}')
    fi

    RESPONSE=$(curl -s -X POST "$BASE_URL/translate" \
        -H "Content-Type: application/json" \
        -H "X-Enable-Metadata: 1" \
        -d "$BODY")

    # Extract translation
    TRANSLATION=$(echo "$RESPONSE" | jq -r '.translated[0] // "ERROR"')

    if [ "$TRANSLATION" = "ERROR" ]; then
        echo -e "   ${RED}✗ Translation failed${NC}"
        echo "$RESPONSE" | jq '.'
    else
        echo -e "   ${GREEN}✓ Translation: '$TRANSLATION'${NC}"

        # Show model info if available
        MODEL_FAMILY=$(echo "$RESPONSE" | jq -r '.metadata.model_family // empty')
        if [ -n "$MODEL_FAMILY" ]; then
            echo -e "   ${YELLOW}ℹ Model family: $MODEL_FAMILY${NC}"
        fi

        # Show pivot if used
        PIVOT=$(echo "$RESPONSE" | jq -r '.pivot_path // empty')
        if [ -n "$PIVOT" ]; then
            echo -e "   ${YELLOW}ℹ Pivot: $PIVOT${NC}"
        fi
    fi

    echo ""
}

# Check health
echo "Checking service health..."
if curl -s "$BASE_URL/healthz" | grep -q "ok"; then
    echo -e "${GREEN}✓ Service is healthy${NC}"
else
    echo -e "${RED}✗ Service is not responding${NC}"
    exit 1
fi

# Test Set 1: Basic pairs (opus-mt)
test_header "TEST SET 1: Basic Translation Pairs (Opus-MT)"

test_translate "Hello world" "en" "de"
test_translate "Guten Tag" "de" "en"
test_translate "Bonjour le monde" "fr" "en"
test_translate "Hola mundo" "es" "en"

# Test Set 2: Fallback pairs
test_header "TEST SET 2: Automatic Fallback (Opus-MT → mBART50/M2M100)"

test_translate "Hello" "en" "bn"
test_translate "Hello" "en" "ur"
test_translate "Good morning" "en" "ta"

# Test Set 3: Explicit model families
test_header "TEST SET 3: Explicit Model Family Selection"

test_translate "Hello world" "en" "de" "opus-mt"
test_translate "Hello world" "en" "de" "mbart50"
test_translate "Hello world" "en" "de" "m2m100"

# Test Set 4: Multiple pairs to test cache
test_header "TEST SET 4: Cache Behavior (Multiple Pairs)"

test_translate "Hello" "en" "fr"
test_translate "World" "en" "fr"  # Should hit cache
test_translate "Bonjour" "fr" "de"
test_translate "Hola" "es" "fr"

# Show cache status
test_header "CACHE STATUS"

echo "Current cache status:"
curl -s "$BASE_URL/cache" | jq '.'

echo ""
echo "========================================================================"
echo -e "${GREEN}Test suite complete!${NC}"
echo "========================================================================"
echo ""
echo "Check server logs to see:"
echo "  • Download progress banners with sizes and device info"
echo "  • Cache HIT/MISS indicators (✓/✗/💾/⚠️)"
echo "  • Model family fallback decisions"
echo "  • Intelligent pivot selection logic"
echo ""
