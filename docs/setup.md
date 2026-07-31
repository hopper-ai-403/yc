# Setup Guide

## Prerequisites

- Docker Desktop / Docker Engine + Compose
- Python 3.12+
- Node.js 22+
- Git

## Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Key variable groups:

| Prefix | Purpose |
| --- | --- |
| `APP_` | Application runtime |
| `DATABASE_` | PostgreSQL |
| `REDIS_` | Redis |
| `JWT_` | Auth tokens (Sprint 1) |
| `R2_` | Cloudflare R2 |
| `LOGGING_` | Structlog |
| `AI_` | Inference (later) |
| `CELERY_` | Workers |

Never call `os.getenv()` from business logic. Use `get_settings()`.

## Docker Compose (recommended)

From the repository root:

```bash
docker compose up --build
```

Services:

| Service | Port | URL |
| --- | --- | --- |
| backend | 8000 | http://localhost:8000 |
| frontend | 3000 | http://localhost:3000 |
| postgres | 5432 | internal / localhost |
| redis | 6379 | internal / localhost |
| flower | 5555 | http://localhost:5555 |
| worker | — | Celery worker |

Health probes:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/database
curl http://localhost:8000/health/redis
curl http://localhost:8000/health/storage
curl http://localhost:8000/health/worker
```

## Backend (host machine)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e .
cp ../.env.example ../.env
uvicorn app.main:app --reload --port 8000
```

Ensure Postgres and Redis are reachable (Compose or local installs).

## Frontend (host machine)

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

## Alembic

Migrations toolchain is configured. No models exist in Sprint 0.

```bash
cd backend
alembic current
alembic history
```

## Cloudflare R2

Provide credentials in `.env` when ready:

```env
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=audio-intelligence
R2_ENDPOINT_URL=
```

Until Sprint 1, storage methods raise `NotImplementedError`. The health probe only verifies configuration presence.
