#!/usr/bin/env powershell
# Remove BOM (Byte Order Mark) from all text files in the project
# BOMs can cause issues with Docker builds, Python imports, and shell scripts

$ErrorActionPreference = "Stop"

Write-Host "=== BOM Removal Tool ===" -ForegroundColor Cyan
Write-Host ""

# File patterns to check
$patterns = @(
    "*.py",
    "*.sh",
    "*.md",
    "*.txt",
    "*.yml",
    "*.yaml",
    ".dockerignore",
    ".gitignore"
)

$filesWithBOM = @()
$filesFixed = @()

# Find all files with BOM
foreach ($pattern in $patterns) {
    Get-ChildItem -Recurse -Include $pattern -File -ErrorAction SilentlyContinue | ForEach-Object {
        $file = $_.FullName

        # Read first 3 bytes
        try {
            $bytes = Get-Content $file -Encoding Byte -TotalCount 3 -ErrorAction Stop

            # Check for UTF-8 BOM (EF BB BF)
            if ($bytes.Count -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
                $filesWithBOM += $file
                Write-Host "[BOM] $file" -ForegroundColor Yellow
            }
        } catch {
            # Skip files that can't be read
        }
    }
}

Write-Host ""

if ($filesWithBOM.Count -eq 0) {
    Write-Host "No files with BOM found!" -ForegroundColor Green
    exit 0
}

Write-Host "Found $($filesWithBOM.Count) file(s) with BOM" -ForegroundColor Yellow
Write-Host ""
Write-Host "Removing BOMs..." -ForegroundColor Cyan

foreach ($file in $filesWithBOM) {
    try {
        # Read content without BOM
        $content = Get-Content $file -Raw

        # Remove BOM if present
        if ($content.StartsWith([char]0xFEFF)) {
            $content = $content.Substring(1)
        }

        # Write back without BOM
        [System.IO.File]::WriteAllText($file, $content, (New-Object System.Text.UTF8Encoding $false))

        $filesFixed += $file
        Write-Host "[FIXED] $(Resolve-Path -Relative $file)" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] $file : $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
Write-Host "Files checked: $(Get-ChildItem -Recurse -Include $patterns -File | Measure-Object | Select-Object -ExpandProperty Count)"
Write-Host "Files with BOM: $($filesWithBOM.Count)" -ForegroundColor Yellow
Write-Host "Files fixed: $($filesFixed.Count)" -ForegroundColor Green
Write-Host ""

if ($filesFixed.Count -gt 0) {
    Write-Host "BOM removal complete! Files are now safe for Docker builds." -ForegroundColor Green
} else {
    Write-Host "No files were fixed (they may already be clean)." -ForegroundColor Gray
}
