#!/usr/bin/env bash
# ==============================================================================
# AI Research Assistant — Backend Test Runner Script (Unix / macOS)
# ==============================================================================

set -e

echo "[*] Running backend Pytest test suite..."
if command -v uv >/dev/null 2>&1; then
    uv run --directory backend pytest
else
    cd backend
    python -m pytest
fi
