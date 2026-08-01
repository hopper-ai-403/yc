# syntax=docker/dockerfile:1
# Railway Celery worker — build context = repository root.
# Dockerfile path in Railway: docker/railway.worker.Dockerfile
# Includes ffmpeg (required for preprocessing).

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential libpq-dev ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY config/ ./config/

# concurrency=1 keeps Redis Cloud client usage low.
CMD ["celery", "-A", "app.infrastructure.celery.app.celery_app", "worker", "--loglevel=INFO", "--concurrency=1", "-Q", "default"]
