# Audio Intelligence Platform

Production-grade modular monolith for **batch analysis of customer call recordings**.  
Upload a ZIP of audio files → Celery workers run a multi-stage AI pipeline → structured predictions + CSV/JSON export.

This README is the **primary local setup guide** for reviewers evaluating the project on their own machines.

---

## What it does

Given call recordings (`.wav` / `.mp3` / `.ogg`), the platform produces:

| Field | Description |
| --- | --- |
| `emotional_tone` | SER-mapped tone (e.g. NEUTRAL, FRUSTRATED, SATISFIED) |
| `emotional_intensity` | LOW / MEDIUM / HIGH |
| `background_noise_present` | Boolean |
| `background_noise_type` | Classified noise category |
| `background_noise_severity` | Severity score / band |
| `audio_quality` | Technical quality assessment |
| `speaker_overlap` | Overlap detection |
| `long_silence` | Long-silence / pacing flags |
| `confidence` | Aggregated confidence |

### Pipeline

```text
Upload (ZIP)
  → Preprocessing (ffmpeg normalize)
  → Analysis (VAD + features)
  → Technical Intelligence (quality, silence, overlap)
  → Acoustic Intelligence (noise / audio-event model)
  → Speech Emotion Recognition (HuBERT SER)
  → Prediction aggregation + confidence
  → CSV / JSON export (R2)
```

---

## Stack

| Layer | Technology |
| --- | --- |
| API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic |
| Workers | Celery (`--pool=solo`), Redis |
| Database | Neon (serverless PostgreSQL) |
| Storage | Cloudflare R2 (`StorageProvider`) |
| AI | Silero VAD, pyannote overlap, AST audio-event, HuBERT SER |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind, TanStack Query |

Architecture rules live in [`CLAUDE.md`](CLAUDE.md). Do not redesign or simplify the module layout.

---

## Prerequisites

| Requirement | Notes |
| --- | --- |
| **Python 3.12+** | Backend + worker |
| **Node.js 20+** (22 recommended) | Frontend |
| **ffmpeg** + **ffprobe** | On `PATH` (worker preprocessing) |
| **Docker** (optional but recommended) | Local Redis via Compose |
| **RAM ≥ 16 GB** recommended | Full AI (Torch + HuBERT-large + AST + pyannote). **≥ 8 GB** absolute minimum for the worker process |
| **Disk ~5–10 GB** | Hugging Face model cache on first run |

### External accounts / credentials

You need all of these before the full pipeline works:

1. **[Neon](https://neon.tech)** — PostgreSQL (`DATABASE_URL` pooled + `DATABASE_DIRECT_URL` direct)
2. **[Cloudflare R2](https://developers.cloudflare.com/r2/)** — S3-compatible bucket + API tokens
3. **[Hugging Face](https://huggingface.co/)** — token with access to:
   - [`superb/hubert-large-superb-er`](https://huggingface.co/superb/hubert-large-superb-er) (SER)
   - [`MIT/ast-finetuned-audioset-10-10-0.4593`](https://huggingface.co/MIT/ast-finetuned-audioset-10-10-0.4593) (noise events)
   - [`pyannote/overlapped-speech-detection`](https://huggingface.co/pyannote/overlapped-speech-detection) (gated — accept the model license on HF)
4. **Redis** — Docker Compose below, or any Redis 7 URL

---

## Recommended local setup (host processes + Docker Redis)

This is the path reviewers should use. It keeps models/cache on the host, matches day-to-day development, and avoids packaging surprises.

### 1. Clone and environment file

```bash
git clone <this-repo-url>
cd "Audio Intelligence Platform"   # or your checkout directory

cp .env.example .env
```

Edit `.env` with real values (see [Configuration checklist](#configuration-checklist) below).

**Critical for host-based Redis** — `.env.example` defaults use the Compose hostname `redis`. On your machine, override to `localhost`:

```env
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

### 2. Start Redis

```bash
docker compose up -d redis
```

### 3. Backend install

```bash
cd backend
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements-dev.txt
pip install -e .
```

Confirm `ffmpeg` / `ffprobe`:

```bash
ffmpeg -version
ffprobe -version
```

### 4. Database migrations

Uses `DATABASE_DIRECT_URL` (Neon direct endpoint):

```bash
# from backend/ with venv active; loads repo-root .env
alembic upgrade head
alembic current
```

### 5. Frontend install

```bash
cd frontend
cp .env.example .env.local
```

`.env.local` should contain:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

```bash
npm install
```

### 6. Run the three processes

Open **three terminals** (venv activated for API + worker).

**API**

```bash
cd backend
# activate .venv
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Worker** (required for batch processing)

```bash
cd backend
# activate .venv
celery -A app.infrastructure.celery.app.celery_app worker --loglevel=INFO --pool=solo --concurrency=1 -Q default
```

First worker boot downloads/loads models when `PERFORMANCE_MODEL_WARMUP=true` (default). Expect several minutes and significant RAM/disk use.

**Frontend**

```bash
cd frontend
npm run dev -- --port 3100
```

| Service | URL |
| --- | --- |
| UI | http://localhost:3100 |
| API | http://localhost:8000 |
| OpenAPI | http://localhost:8000/docs |
| Health | http://localhost:8000/health |

`APP_ALLOWED_ORIGINS` in `.env` already includes `http://localhost:3000` and `http://localhost:3100`.

---

## Configuration checklist

Copy from `.env.example`, then set at least:

```env
# App / CORS
APP_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3100,http://127.0.0.1:3000,http://127.0.0.1:3100

# Neon
DATABASE_URL=postgresql://...@ep-XXX-pooler....neon.tech/neondb?sslmode=require
DATABASE_DIRECT_URL=postgresql://...@ep-XXX....neon.tech/neondb?sslmode=require

# Redis (host)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# JWT (any long random string for local)
JWT_SECRET_KEY=local-dev-change-me

# Cloudflare R2
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=...
R2_ENDPOINT_URL=https://<accountid>.r2.cloudflarestorage.com

# Full AI (do not disable for the assessment)
ANALYSIS_VAD_BACKEND=silero
TECHNICAL_OVERLAP_BACKEND=pyannote
TECHNICAL_OVERLAP_HF_TOKEN=<hf_token_with_pyannote_access>
ACOUSTIC_CLASSIFIER_BACKEND=audio_event
SPEECH_ENABLED=true
SPEECH_MODEL_NAME=superb/hubert-large-superb-er
PERFORMANCE_MODEL_WARMUP=true
PERFORMANCE_WORKER_CONCURRENCY=1
```

Also export a Hugging Face token in the worker shell (used by `transformers` / hub downloads):

```bash
# Windows PowerShell
$env:HF_TOKEN="hf_..."

# macOS / Linux
export HF_TOKEN=hf_...
```

You may set the same value in `TECHNICAL_OVERLAP_HF_TOKEN`.

Label maps ship in repo `config/` (`speech_label_mapping.json`, `noise_label_mapping.json`). Keep paths pointing at those files.

---

## Smoke test (end-to-end)

1. Open http://localhost:3100 → **Upload**.
2. Upload a small ZIP of short `.wav` / `.mp3` / `.ogg` calls (1–3 files recommended for first run).
3. Start / open the batch and wait for status **Completed**.
4. Confirm:
   - Worker logs show stages: preprocessing → analysis → technical → acoustic → speech → prediction → finalize
   - Batch detail shows processed files and predictions (not “No results”)
   - CSV/JSON export download works
   - R2 prefix `uploads/<batch_id>/` contains `normalized/`, `predictions/`, `exports/`

Health probes:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/database
curl http://localhost:8000/health/redis
curl http://localhost:8000/health/storage
curl http://localhost:8000/health/worker
```

---

## Alternative: full Docker Compose

```bash
cp .env.example .env
# Fill Neon + R2 (+ HF tokens). Keep REDIS_* as redis://redis:6379/... for Compose.
docker compose up --build
```

| Service | Port |
| --- | --- |
| frontend | http://localhost:3000 |
| backend | http://localhost:8000 |
| flower | http://localhost:5555 |
| redis | 6379 |
| worker | (internal) |

**Notes for reviewers**

- Compose builds from `docker/Dockerfile.*` with context `backend/` — ensure `config/` mappings are available to the container (repo-root `config/` is required for correct SER/noise labels; Railway images copy it explicitly).
- Worker containers need **large memory limits** (≥8 GB) for full AI warmup.
- Prefer the **host-based** setup above if Compose OOMs or models fail to download.

Postgres is **never** run in Compose — Neon is required.

---

## Tests

```bash
cd backend
# activate .venv
pytest ../tests -q
```

Quality tools (optional):

```bash
ruff check app ../tests
black --check app ../tests
pyright app
```

---

## Project layout

```text
.
├── backend/                 # FastAPI app, Celery, Alembic
│   └── app/
│       ├── ai/              # technical / acoustic / speech / …
│       ├── audio/           # preprocessing + analysis
│       ├── jobs/            # batch orchestration
│       ├── prediction/      # aggregation + export
│       ├── upload/
│       ├── infrastructure/  # Celery, R2, Redis
│       └── shared/
├── frontend/                # Next.js UI
├── config/                  # speech + noise label mappings
├── docker/                  # Dockerfiles (local + Railway)
├── docs/                    # Architecture & deployment
├── tests/
├── .env.example
└── CLAUDE.md                # Engineering constitution
```

---

## Documentation

| Doc | Purpose |
| --- | --- |
| [`CLAUDE.md`](CLAUDE.md) | Engineering constitution (must follow) |
| [`docs/architecture.md`](docs/architecture.md) | Architecture overview |
| [`docs/architecture/DOMAIN_MODEL.md`](docs/architecture/DOMAIN_MODEL.md) | Domain model |
| [`docs/setup.md`](docs/setup.md) | Setup notes (companion to this README) |
| [`docs/development.md`](docs/development.md) | Contributor conventions |
| [`docs/deployment.md`](docs/deployment.md) | Railway + Vercel production deploy |
| [`docs/folder-structure.md`](docs/folder-structure.md) | Folder map |

---

## Notes for assessment reviewers

- **Prediction quality > infra cost.** Run the **full** AI stack (Silero, pyannote, AST, HuBERT). Do not switch to heuristic-only / disabled-SER modes for evaluation.
- **Memory:** if the worker is killed during warmup, raise available RAM (or use a larger machine). Do not disable `PERFORMANCE_MODEL_WARMUP` or stub emotion output for the assessment.
- **First run** downloads multi‑GB HF weights; subsequent runs reuse the cache (`AI_MODEL_CACHE_DIR` / Hugging Face home).
- **Auth:** uploads use a system uploader identity for batch ingestion; JWT settings exist for the platform security model.
- **Windows workers:** always use `--pool=solo` with PyTorch (as shown above).

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Jobs stay queued | Worker not running or Redis URL mismatch (`localhost` vs `redis`) |
| `max number of clients reached` | Too many Redis connections (free Redis Cloud); use local Docker Redis |
| Preprocess fails | Install ffmpeg/ffprobe on `PATH` |
| SER / AST / pyannote errors | Set `HF_TOKEN`, accept gated model licenses, check disk/RAM |
| CORS in browser | Add your UI origin to `APP_ALLOWED_ORIGINS` |
| Empty / wrong labels | Ensure `config/*.json` paths resolve from the process cwd |
| Worker OOM | Need ≥8 GB for the worker; 16 GB machine recommended |

---

## License

Proprietary — submitted for engineering assessment evaluation.
