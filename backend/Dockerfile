# ==============================================================================
# AI Research Assistant — FastAPI Backend Dockerfile
# ==============================================================================
# Base Image: Python 3.13 Slim (Debian based, minimal attack surface)
# ==============================================================================
FROM python:3.13-slim AS base

# Environment variables to optimize Python runtime in Docker
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system utilities needed for health checks & minimal build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for optimal Docker layer caching
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy backend application source code
COPY app/ ./app/

# Create a non-privileged user for security compliance
RUN useradd -u 1000 -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose FastAPI development / production port
EXPOSE 8000

# Health check configuration inside the container
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/liveness || exit 1

# Launch FastAPI using Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
