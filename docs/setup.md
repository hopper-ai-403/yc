# Setup Guide

## Prerequisites

- Docker Desktop / Docker Engine + Compose
- Python 3.12+
- Node.js 22+
- Git
- A [Neon](https://neon.tech) project (PostgreSQL)

## Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Key variable groups:

| Prefix | Purpose |
| --- | --- |
| `APP_` | Application runtime |
| `DATABASE_` | Neon PostgreSQL |
| `REDIS_` | Redis |
| `JWT_` | Auth tokens (Sprint 1) |
| `R2_` | Cloudflare R2 |
| `LOGGING_` | Structlog |
| `AI_` | Inference (later) |
| `CELERY_` | Workers |

Never call `os.getenv()` from business logic. Use `get_settings()`.

## Neon PostgreSQL

1. Create a Neon project and database.
2. From the Neon console, copy:
   - **Pooled** connection string → `DATABASE_URL` (host includes `-pooler`)
   - **Direct** connection string → `DATABASE_DIRECT_URL` (no `-pooler`; used by Alembic)
3. Keep `sslmode=require` (added automatically for `neon.tech` hosts if missing).
4. Neon URLs starting with `postgresql://` or `postgres://` are normalized to `postgresql+psycopg://`.

Example:

```env
DATABASE_URL=postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require
DATABASE_DIRECT_URL=postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require
```

Verify connectivity after the API is up:

```bash
curl http://localhost:8000/health/database
```

## Docker Compose

Compose runs application services only. Postgres is **not** containerized — Neon is the database.

```bash
docker compose up --build
```

Services:

| Service | Port | URL |
| --- | --- | --- |
| backend | 8000 | http://localhost:8000 |
| frontend | 3000 | http://localhost:3000 |
| redis | 6379 | internal / localhost |
| flower | 5555 | http://localhost:5555 |
| worker | — | Celery worker |
| Neon | — | External PostgreSQL |

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
# Paste Neon URLs into ../.env
uvicorn app.main:app --reload --port 8000
```

Ensure Neon and Redis are reachable.

## Frontend (host machine)

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

## Alembic

Migrations use `DATABASE_DIRECT_URL` when set (Neon direct endpoint), otherwise `DATABASE_URL`.

```bash
cd backend
alembic current
alembic history
```

No models exist in Sprint 0.

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
