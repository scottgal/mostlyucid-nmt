#!/bin/bash
# build_exe.sh - Build standalone executable for MostlyLucid-NMT (Linux/Mac)
#
# Usage:
#   ./build_exe.sh           # Build with default settings
#   ./build_exe.sh --clean   # Clean build (remove dist/build first)
#   ./build_exe.sh --no-upx  # Skip UPX compression

set -e

CLEAN=false
NO_UPX=false
DEBUG=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --clean|-c)
            CLEAN=true
            shift
            ;;
        --no-upx)
            NO_UPX=true
            shift
            ;;
        --debug|-d)
            DEBUG=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "========================================"
echo "MostlyLucid-NMT Executable Builder"
echo "========================================"
echo ""

# Check Python
echo "[1/5] Checking Python environment..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 not found in PATH"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo "       Found: $PYTHON_VERSION"

# Check PyInstaller
echo "[2/5] Checking PyInstaller..."
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "       Installing PyInstaller..."
    pip3 install pyinstaller
fi
PYINSTALLER_VERSION=$(python3 -c "import PyInstaller; print(PyInstaller.__version__)")
echo "       Found: PyInstaller $PYINSTALLER_VERSION"

# Check UPX (optional)
UPX_AVAILABLE=false
if [ "$NO_UPX" = false ]; then
    echo "[2.5/5] Checking UPX (optional compression)..."
    if command -v upx &> /dev/null; then
        UPX_AVAILABLE=true
        echo "       Found: UPX available"
    else
        echo "       UPX not found (optional - exe will be larger)"
    fi
fi

# Clean if requested
if [ "$CLEAN" = true ]; then
    echo "[3/5] Cleaning previous builds..."
    rm -rf dist build
    echo "       Cleaned dist/ and build/"
else
    echo "[3/5] Skipping clean (use --clean to force)"
fi

# Build
echo "[4/5] Building executable..."
echo "       This may take several minutes..."

BUILD_ARGS="mostlylucid_nmt.spec"
if [ "$DEBUG" = true ]; then
    BUILD_ARGS="$BUILD_ARGS --log-level=DEBUG"
fi
if [ "$NO_UPX" = true ] || [ "$UPX_AVAILABLE" = false ]; then
    BUILD_ARGS="$BUILD_ARGS --noupx"
fi

START_TIME=$(date +%s)
pyinstaller $BUILD_ARGS
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Verify output
echo "[5/5] Verifying build..."
EXE_PATH="dist/mostlylucid-nmt"
if [ ! -f "$EXE_PATH" ]; then
    echo "ERROR: Executable not found at $EXE_PATH"
    exit 1
fi

EXE_SIZE=$(du -h "$EXE_PATH" | cut -f1)
echo ""
echo "========================================"
echo "BUILD SUCCESSFUL"
echo "========================================"
echo ""
echo "Output:   $EXE_PATH"
echo "Size:     $EXE_SIZE"
echo "Time:     ${DURATION} seconds"
echo ""
echo "Usage:"
echo "  ./dist/mostlylucid-nmt              # Start server"
echo "  ./dist/mostlylucid-nmt --help       # Show help"
echo "  ./dist/mostlylucid-nmt --check      # Check if running"
echo "  ./dist/mostlylucid-nmt --translate 'Hello' -s en -t de"
echo ""

# Make executable
chmod +x "$EXE_PATH"
