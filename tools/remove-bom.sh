#!/bin/bash
# Remove BOM (Byte Order Mark) from all text files in the project
# BOMs can cause issues with Docker builds, Python imports, and shell scripts

set -e

echo "=== BOM Removal Tool ==="
echo ""

# File patterns to check
patterns=(
    "*.py"
    "*.sh"
    "*.md"
    "*.txt"
    "*.yml"
    "*.yaml"
    ".dockerignore"
    ".gitignore"
)

files_with_bom=()
files_fixed=()

# Find all files with BOM
for pattern in "${patterns[@]}"; do
    while IFS= read -r -d '' file; do
        # Read first 3 bytes
        if [ -f "$file" ]; then
            head_bytes=$(head -c 3 "$file" | od -An -tx1 | tr -d ' ')
            # Check for UTF-8 BOM (efbbbf)
            if [ "$head_bytes" = "efbbbf" ]; then
                files_with_bom+=("$file")
                echo "[BOM] $file"
            fi
        fi
    done < <(find . -type f -name "$pattern" -print0 2>/dev/null)
done

echo ""

if [ ${#files_with_bom[@]} -eq 0 ]; then
    echo "No files with BOM found!"
    exit 0
fi

echo "Found ${#files_with_bom[@]} file(s) with BOM"
echo ""
echo "Removing BOMs..."

for file in "${files_with_bom[@]}"; do
    # Remove BOM using sed (portable across Linux/Mac)
    if sed -i '1s/^\xEF\xBB\xBF//' "$file" 2>/dev/null || sed -i '' '1s/^\xEF\xBB\xBF//' "$file" 2>/dev/null; then
        files_fixed+=("$file")
        echo "[FIXED] $file"
    else
        # Fallback: use tail to skip BOM
        if tail -c +4 "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"; then
            files_fixed+=("$file")
            echo "[FIXED] $file"
        else
            echo "[ERROR] $file"
        fi
    fi
done

echo ""
echo "=== Summary ==="
echo "Files with BOM: ${#files_with_bom[@]}"
echo "Files fixed: ${#files_fixed[@]}"
echo ""

if [ ${#files_fixed[@]} -gt 0 ]; then
    echo "BOM removal complete! Files are now safe for Docker builds."
else
    echo "No files were fixed (they may already be clean)."
fi
