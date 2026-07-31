# Architecture Overview

## Purpose

The Audio Intelligence Platform is a modular monolith SaaS system that processes batches of customer call recordings and produces structured predictions.

Sprint 0 establishes the engineering foundation. Business capabilities are added as isolated feature modules in later sprints.

## Style

- Modular monolith
- Domain-driven feature modules
- Service layer + repository pattern
- Dependency injection via FastAPI `Depends`
- Infrastructure adapters behind interfaces

## Runtime Topology

```
┌────────────┐     ┌────────────┐     ┌──────────────────┐
│  Frontend  │────▶│  Backend   │────▶│ Neon PostgreSQL  │
│  Next.js   │     │  FastAPI   │     └──────────────────┘
└────────────┘     └─────┬──────┘
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
        ┌──────┐   ┌──────────┐   ┌─────────┐
        │Redis │   │  Celery  │   │   R2    │
        └──────┘   │  Worker  │   │ Storage │
                   └────┬─────┘   └─────────┘
                        ▼
                   ┌─────────┐
                   │ Flower  │
                   └─────────┘
```

PostgreSQL is provided by [Neon](https://neon.tech) (serverless). Redis and workers remain in Docker Compose.
## Backend Layers

| Layer | Location | Responsibility |
| --- | --- | --- |
| API | `app/*/api.py`, `app/health` | HTTP adapters only |
| Services | `app/*/service.py` | Business orchestration |
| Repositories | `app/*/repository.py` | Persistence |
| Shared | `app/shared` | Cross-cutting primitives |
| Infrastructure | `app/infrastructure` | External systems |
| Config | `app/config` | Typed settings |

## Feature Modules (scaffolded)

- `auth` — authentication (Sprint 1+)
- `upload` — audio upload pipeline (Sprint 1+)
- `jobs` — batch job orchestration
- `prediction` — prediction persistence/API
- `audio` — audio domain operations
- `ai/` — emotion, acoustic, technical, aggregation, confidence

## AI Separation Rules

- Emotion never classifies noise
- Noise/acoustic never computes confidence
- Aggregation combines predictions
- Confidence is an independent concern

## API Contract

Success:

```json
{
  "success": true,
  "message": "",
  "data": {}
}
```

Error:

```json
{
  "success": false,
  "error": {
    "code": "",
    "message": "",
    "details": {}
  }
}
```

## Extension Points

- New feature modules under `backend/app/<feature>/`
- New AI engines under `backend/app/ai/<engine>/`
- New infrastructure adapters under `backend/app/infrastructure/`
- Storage remains behind `StorageProvider`

## Domain documentation

- [Domain Model](architecture/DOMAIN_MODEL.md)
- [Database Schema](architecture/DATABASE_SCHEMA.md)
- [ER Diagram](architecture/ER_DIAGRAM.md)
- [Repository Dependencies](architecture/REPOSITORY_DEPENDENCIES.md)
- [Upload Flow](architecture/UPLOAD_FLOW.md)
- [R2 Folder Structure](architecture/R2_FOLDER_STRUCTURE.md)
