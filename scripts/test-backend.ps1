# ==============================================================================
# AI Research Assistant — Backend Test Runner Script (Windows PowerShell)
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "[*] Running backend Pytest test suite..." -ForegroundColor Cyan

if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv run --directory backend pytest
} else {
    Set-Location backend
    python -m pytest
    Set-Location ..
}
