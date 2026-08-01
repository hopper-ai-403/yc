# Setup Guide

For the full **assessment / reviewer** walkthrough, start with the root [`README.md`](../README.md).

This page is a short companion checklist.

## Prerequisites

- Python 3.12+
- Node.js 20+ (22 recommended)
- ffmpeg + ffprobe on `PATH`
- Docker (recommended for local Redis)
- Neon PostgreSQL, Cloudflare R2, Hugging Face token
- **≥ 8 GB RAM for the worker** (16 GB machine recommended for full AI)

## Environment

```bash
cp .env.example .env
```

When running API/worker on the **host** (recommended):

```env
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

When using **Docker Compose** for app services, keep the Compose hostname:

```env
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
```

Never call `os.getenv()` from business logic — use `get_settings()`.

## Neon

1. Create a Neon project.
2. Pooled URL → `DATABASE_URL` (host contains `-pooler`).
3. Direct URL → `DATABASE_DIRECT_URL` (Alembic).
4. Keep `sslmode=require`.

```bash
cd backend
# venv active
alembic upgrade head
curl http://localhost:8000/health/database
```

## Redis

```bash
docker compose up -d redis
```

## Backend + worker + frontend

See [README — Recommended local setup](../README.md#recommended-local-setup-host-processes--docker-redis).

Quick commands:

```bash
# API
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Worker (solo pool required with PyTorch)
celery -A app.infrastructure.celery.app.celery_app worker --loglevel=INFO --pool=solo --concurrency=1 -Q default

# Frontend
cd frontend && cp .env.example .env.local && npm install && npm run dev -- --port 3100
```

## Cloudflare R2

```env
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_ENDPOINT_URL=https://<accountid>.r2.cloudflarestorage.com
```

```bash
curl http://localhost:8000/health/storage
```

## Full AI backends (assessment)

```env
ANALYSIS_VAD_BACKEND=silero
TECHNICAL_OVERLAP_BACKEND=pyannote
ACOUSTIC_CLASSIFIER_BACKEND=audio_event
SPEECH_ENABLED=true
SPEECH_MODEL_NAME=superb/hubert-large-superb-er
PERFORMANCE_MODEL_WARMUP=true
```

Accept Hugging Face licenses for HuBERT, AST, and pyannote. Set `HF_TOKEN` / `TECHNICAL_OVERLAP_HF_TOKEN`.

## Docker Compose (optional)

```bash
docker compose up --build
```

Postgres is **not** in Compose — Neon only. Worker needs a high memory limit for model warmup.

## Health

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/database
curl http://localhost:8000/health/redis
curl http://localhost:8000/health/storage
curl http://localhost:8000/health/worker
```
