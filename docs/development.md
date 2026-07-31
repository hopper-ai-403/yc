# Development Guide

## Principles

Follow `CLAUDE.md` strictly:

- SOLID, clean code, separation of concerns
- Dependency injection
- Repository + service layers
- No business logic in API routes
- No direct SQLAlchemy / R2 / Redis access from routes
- Typed everything
- Structured logging only (no `print`)

## Feature Module Pattern

When adding a capability (Sprint 1+), create:

```
backend/app/<feature>/
  api.py
  service.py
  repository.py
  schemas.py
  models.py
  exceptions.py
  dependencies.py
```

Keep tests beside the feature or under `tests/`.

## Adding an Endpoint

1. Define Pydantic schemas in the feature module
2. Implement service methods
3. Persist via repository (never from routes)
4. Inject dependencies with `Depends`
5. Return the standard success/error envelopes
6. Add API tests under `tests/api/`

## Logging

Use:

```python
from app.shared.logging import get_logger, bind_context

logger = get_logger(__name__)
bind_context(job_id=str(job_id))
logger.info("job_started", status="ok")
```

Include `request_id`, `job_id`, `audio_id`, `user_id`, `service`, `latency`, and `status` when available.

## Exceptions

Raise specific exceptions from `app.shared.exceptions`:

- `ValidationException`
- `StorageException`
- `AuthenticationException`
- `InferenceException`
- `QueueException`

## Quality Gate (local)

```bash
cd backend
ruff check app ../tests
black app ../tests
pyright app
pytest ../tests -q
pre-commit run --all-files
```

## Worker Development

Celery app:

```text
app.infrastructure.celery.app.celery_app
```

Sample task (Sprint 0 only):

```text
app.infrastructure.celery.tasks.heartbeat
```

Run worker:

```bash
celery -A app.infrastructure.celery.app.celery_app worker --loglevel=INFO
```

## Frontend Notes

- App Router under `frontend/src/app`
- TanStack Query provider already wired
- shadcn/ui configured via `components.json` (add components as needed)
- API client helper: `frontend/src/lib/api.ts`

## What Not To Do in Sprint 0 Follow-ups

- Do not invent alternate response formats
- Do not put business logic in `shared/`
- Do not import `boto3` outside `infrastructure/`
- Do not create `misc.py` or dump utilities
- Do not assume `localhost` inside containers — use Compose service names
