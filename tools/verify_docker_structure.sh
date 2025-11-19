#!/bin/bash
# Verify Docker image structure
# Usage: docker run --rm --entrypoint /bin/sh IMAGE_NAME /app/tools/verify_docker_structure.sh

echo "=== Docker Image Structure Verification ==="
echo ""
echo "Working directory:"
pwd
echo ""
echo "PYTHONPATH:"
echo "$PYTHONPATH"
echo ""
echo "Contents of /app:"
ls -la /app
echo ""
echo "Contents of /app/src:"
ls -la /app/src 2>&1
echo ""
echo "app.py exists?"
test -f /app/app.py && echo "YES" || echo "NO"
echo ""
echo "src/__init__.py exists?"
test -f /app/src/__init__.py && echo "YES" || echo "NO"
echo ""
echo "src/app.py exists?"
test -f /app/src/app.py && echo "YES" || echo "NO"
echo ""
echo "Testing Python import:"
cd /app
python3 -c "import sys; print('sys.path:', sys.path); from src.app import app; print('SUCCESS: app imported')" 2>&1
