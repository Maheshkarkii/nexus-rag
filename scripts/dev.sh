#!/usr/bin/env bash
# ==============================================================================
# AI Research Assistant — Development Startup Script (Unix / macOS)
# ==============================================================================

set -e

echo "================================================================================"
echo " Starting AI Research Assistant Development Environment"
echo "================================================================================"

# Check for .env file
if [ ! -f .env ]; then
    echo "[!] .env not found. Copying .env.example to .env..."
    cp .env.example .env
fi

# Launch Docker Compose
echo "[*] Building and starting all services (Frontend, Backend, Postgres, Qdrant)..."
docker compose up --build
