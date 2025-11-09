#!/bin/bash
# API Validation Script
# Runs automated tests against a live running instance
# Bash script for Linux/Mac

BASE_URL="${BASE_URL:-http://localhost:8000}"
SMOKE_ONLY=false
VERBOSE="-v"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --base-url)
            BASE_URL="$2"
            shift 2
            ;;
        --smoke-only)
            SMOKE_ONLY=true
            shift
            ;;
        --verbose)
            VERBOSE="-vv"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "=== API VALIDATION ==="
echo "Testing API at: $BASE_URL"
echo ""

# Check if API is reachable
echo "Checking API availability..."
if curl -sf "$BASE_URL/healthz" > /dev/null 2>&1; then
    echo "✓ API is reachable"
else
    echo "✗ API not reachable at $BASE_URL"
    echo ""
    echo "Make sure the API is running:"
    echo "  docker run -p 8000:8000 dev:latest"
    echo ""
    echo "Or specify a different URL:"
    echo "  BASE_URL=http://localhost:8001 ./validate-api.sh"
    exit 1
fi

echo ""

# Export for pytest
export BASE_URL

# Build pytest command
PYTEST_ARGS="tests/test_api_live.py $VERBOSE"

if [ "$SMOKE_ONLY" = true ]; then
    echo "Running smoke tests only (health checks + basic translation)..."
    PYTEST_ARGS="$PYTEST_ARGS -m smoke"
else
    echo "Running full validation suite..."
    PYTEST_ARGS="$PYTEST_ARGS -m 'not slow'"
fi

echo ""

# Run tests
python -m pytest $PYTEST_ARGS

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ All validation tests passed!"
else
    echo "✗ Some tests failed"
fi

echo ""
echo "OPTIONS:"
echo "  ./validate-api.sh                               # Full validation"
echo "  ./validate-api.sh --smoke-only                  # Quick smoke test"
echo "  ./validate-api.sh --base-url http://localhost:8001  # Custom URL"
echo "  ./validate-api.sh --verbose                     # More verbose output"

exit $EXIT_CODE
