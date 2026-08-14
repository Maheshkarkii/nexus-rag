# ==============================================================================
# AI Research Assistant — Development Startup Script (Windows PowerShell)
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " Starting AI Research Assistant Development Environment" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

# Check for .env file
if (-not (Test-Path -Path ".env")) {
    Write-Host "[!] .env not found. Copying .env.example to .env..." -ForegroundColor Yellow
    Copy-Item -Path ".env.example" -Destination ".env"
}

# Launch Docker Compose
Write-Host "[*] Building and starting all services (Frontend, Backend, Postgres, Qdrant)..." -ForegroundColor Green
docker compose up --build
