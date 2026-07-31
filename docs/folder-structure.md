# Folder Structure

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml
├── backend/
│   ├── alembic/
│   │   ├── versions/
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── alembic.ini
│   ├── app/
│   │   ├── ai/
│   │   │   ├── acoustic/
│   │   │   ├── aggregation/
│   │   │   ├── confidence/
│   │   │   ├── emotion/
│   │   │   └── technical/
│   │   ├── audio/
│   │   ├── auth/
│   │   ├── config/
│   │   ├── health/
│   │   ├── infrastructure/
│   │   │   ├── celery/
│   │   │   ├── database/
│   │   │   ├── r2/
│   │   │   └── redis/
│   │   ├── jobs/
│   │   ├── prediction/
│   │   ├── shared/
│   │   │   ├── database/
│   │   │   ├── exceptions/
│   │   │   ├── logging/
│   │   │   ├── middleware/
│   │   │   ├── response/
│   │   │   ├── security/
│   │   │   ├── storage/
│   │   │   └── types/
│   │   ├── upload/
│   │   ├── dependencies.py
│   │   └── main.py
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── requirements-dev.txt
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── Dockerfile.worker
├── docs/
│   ├── architecture.md
│   ├── development.md
│   ├── folder-structure.md
│   └── setup.md
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   └── lib/
│   ├── components.json
│   ├── next.config.ts
│   ├── package.json
│   └── tsconfig.json
├── scripts/
├── tests/
│   ├── api/
│   ├── integration/
│   └── unit/
├── .editorconfig
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── CLAUDE.md
├── docker-compose.yml
└── README.md
```

## Ownership Rules

| Path | Owns |
| --- | --- |
| `backend/app/<feature>/` | One business capability |
| `backend/app/shared/` | Cross-cutting primitives only |
| `backend/app/infrastructure/` | External system adapters |
| `backend/app/config/` | Typed settings |
| `tests/` | Automated verification |
| `docs/` | Engineering documentation |
| `docker/` | Container build definitions |
| `scripts/` | Operational helper scripts |
