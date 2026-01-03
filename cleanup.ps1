# Cleanup script for PyInstaller build
$ErrorActionPreference = 'SilentlyContinue'

# Kill any related processes
Get-Process | Where-Object { $_.Path -like '*mostlylucid*' } | Stop-Process -Force

# Remove build artifacts
Remove-Item -Path 'E:\source\mostlylucid-nmt\dist' -Recurse -Force
Remove-Item -Path 'E:\source\mostlylucid-nmt\build' -Recurse -Force

Write-Host "Cleanup completed"
