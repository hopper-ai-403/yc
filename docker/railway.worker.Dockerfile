# syntax=docker/dockerfile:1
# Railway Celery worker — build context = repository root.
# Dockerfile path in Railway: docker/railway.worker.Dockerfile
# Includes ffmpeg (required for preprocessing).

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    PERFORMANCE_MODEL_WARMUP=false \
    AI_MODEL_CACHE_DIR=/tmp/model_cache \
    HF_HOME=/tmp/model_cache \
    TRANSFORMERS_CACHE=/tmp/model_cache \
    TORCH_HOME=/tmp/model_cache \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    TOKENIZERS_PARALLELISM=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential libpq-dev ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /tmp/model_cache

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY config/ ./config/

# concurrency=1 keeps Redis Cloud client usage low.
# max-tasks-per-child recycles the process to limit long-run RSS growth.
CMD ["celery", "-A", "app.infrastructure.celery.app.celery_app", "worker", "--loglevel=INFO", "--concurrency=1", "-Q", "default", "--max-tasks-per-child=20"]
