# Audio Intelligence Platform

Production-grade SaaS platform for batch analysis of customer call recordings with structured AI predictions.

## Sprint 0 Status

This repository currently contains the **engineering foundation only**:

- Modular monolith backend (FastAPI)
- Async SQLAlchemy + Alembic (no models yet)
- Redis client + Celery worker + Flower
- Cloudflare R2 `StorageProvider` interface
- Structured JSON logging (structlog)
- Health endpoints
- Next.js 15 frontend shell
- Docker Compose stack
- CI quality gates

Authentication, uploads, database models, and AI inference are intentionally deferred.

## Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic |
| Workers | Celery, Redis, Flower |
| Storage | Cloudflare R2 (via `StorageProvider`) |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind, TanStack Query |
| Infra | Docker Compose, Neon PostgreSQL, Redis |
| Quality | Ruff, Black, Pyright, Pytest, Pre-commit, GitHub Actions |

## Quick Start

```bash
# 1. Copy environment
cp .env.example .env

# 2. Start infrastructure + services
docker compose up --build

# 3. Verify health
curl http://localhost:8000/health
```

Frontend: http://localhost:3000  
API docs: http://localhost:8000/docs  
Flower: http://localhost:5555

## Local Backend Development

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Local Frontend Development

```bash
cd frontend
npm install
npm run dev
```

## Quality Checks

```bash
cd backend
ruff check app ../tests
black --check app ../tests
pyright app
pytest ../tests -q
```

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Setup Guide](docs/setup.md)
- [Development Guide](docs/development.md)
- [Folder Structure](docs/folder-structure.md)

## Project Constitution

All contributors must follow [`CLAUDE.md`](CLAUDE.md). Do not redesign or simplify the architecture.
