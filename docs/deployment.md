# Deployment Guide — Railway (Backend) + Vercel (Frontend)

Target repo: `https://github.com/hopper-ai-403/yc`

| Layer | Host | Role |
| --- | --- | --- |
| API | Railway service `api` | FastAPI (`uvicorn`) |
| Worker | Railway service `worker` | Celery + ffmpeg + HF models |
| Frontend | Vercel | Next.js 15 (`frontend/`) |
| Postgres | Neon (external) | Already configured |
| Redis | Redis Cloud (external) | Broker + result + progress |
| Object storage | Cloudflare R2 | Uploads / normalized / exports |

Do **not** run Postgres in Railway. Do **not** deploy Flower unless you need it.

Secrets live only in Railway / Vercel dashboards. Never commit `.env`.

---

## 0. Repo layout (what to select where)

```
yc/                              ← Railway Root Directory = repo root (/)
├── backend/                     ← Python app (copied into API + worker images)
│   ├── app/
│   ├── requirements.txt
│   └── alembic/
├── config/                      ← REQUIRED in images (noise + speech mappings)
│   ├── noise_label_mapping.json
│   └── speech_label_mapping.json
├── docker/
│   ├── railway.api.Dockerfile   ← use this for Railway API
│   └── railway.worker.Dockerfile← use this for Railway worker
├── frontend/                    ← Vercel Root Directory = frontend
└── .env.example
```

Local `docker/Dockerfile.backend` and `docker/Dockerfile.worker` assume build context `backend/` only and **omit** `config/`. Prefer the `railway.*.Dockerfile` files below for production.

---

## 1. One-time prep (local)

### 1.1 Confirm migrations on Neon

From your machine (with local `.env` loaded):

```powershell
cd backend
.\.venv\Scripts\activate
alembic upgrade head
```

### 1.2 Confirm Redis client headroom

Redis Cloud free tier is often **max 30 clients**. Production needs:

- 1× API process
- 1× Celery worker (several Redis connections)

Kill idle clients or upgrade Redis before deploy if you still hit `max number of clients reached`.

### 1.3 Hugging Face

Accept model licenses / grant token access for:

- `superb/hubert-large-superb-er` (SER)
- `MIT/ast-finetuned-audioset-10-10-0.4593` (noise events)
- `pyannote/overlapped-speech-detection` (optional; gated)

If pyannote is not ready, set `TECHNICAL_OVERLAP_BACKEND=heuristic` for first deploy.

---

## 2. Railway — create project

1. [Railway](https://railway.app) → **New Project** → **Deploy from GitHub**.
2. Select `hopper-ai-403/yc`.
3. You will create **two services** from the same repo: `api` and `worker`.

---

## 3. Railway service: `api`

### 3.1 Settings

| Setting | Value |
| --- | --- |
| Service name | `api` |
| Source repo | `hopper-ai-403/yc` |
| Branch | `main` |
| **Root Directory** | leave empty / `/` (repo root) |
| **Builder** | Dockerfile |
| **Dockerfile path** | `docker/railway.api.Dockerfile` |
| Public networking | Generate domain |
| Health check path | `/health` |

Railway injects `PORT`. The API Dockerfile listens on `$PORT`.

### 3.2 Environment variables — `api`

Paste these into Railway → `api` → Variables.

**Copy secret values from your local `.env`** (Neon, Redis, R2, JWT). Override the production-specific rows below.

#### App (override for prod)

```env
APP_NAME=Audio Intelligence Platform
APP_VERSION=0.1.0
APP_ENVIRONMENT=production
APP_DEBUG=false
APP_API_PREFIX=/api/v1
APP_HOST=0.0.0.0
APP_ALLOWED_ORIGINS=https://YOUR_VERCEL_DOMAIN.vercel.app
```

After Vercel deploy, replace `YOUR_VERCEL_DOMAIN` and redeploy `api`.  
Include preview URLs if needed, comma-separated.

#### Database (from local `.env`)

```env
DATABASE_URL=<Neon pooled URL — host contains -pooler — sslmode=require>
DATABASE_DIRECT_URL=<Neon direct URL — no -pooler — sslmode=require>
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=5
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=300
DATABASE_ECHO=false
```

#### Redis + Celery (from local `.env`)

Use your Redis Cloud URL. Prefer **one logical DB** for all three if your plan is small:

```env
REDIS_URL=<redis://default:****@****.db.redis.io:****/0>
REDIS_HEALTH_CHECK_INTERVAL=30
CELERY_BROKER_URL=<same Redis URL>
CELERY_RESULT_BACKEND=<same Redis URL>
CELERY_TASK_ALWAYS_EAGER=false
CELERY_TASK_TRACK_STARTED=true
CELERY_WORKER_PREFETCH_MULTIPLIER=1
CELERY_TASK_ACKS_LATE=true
```

#### JWT (from local `.env` — or generate a new secret for prod)

```env
JWT_SECRET_KEY=<long random secret>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

#### Cloudflare R2 (from local `.env`)

```env
R2_ACCOUNT_ID=<from .env>
R2_ACCESS_KEY_ID=<from .env>
R2_SECRET_ACCESS_KEY=<from .env>
R2_BUCKET_NAME=ycaudiointelligence
R2_ENDPOINT_URL=https://<accountid>.r2.cloudflarestorage.com
R2_REGION=auto
R2_SIGNED_URL_EXPIRY_SECONDS=3600
R2_RETRY_COUNT=3
R2_BACKOFF_BASE_SECONDS=0.5
R2_BACKOFF_MAX_SECONDS=8.0
R2_CONNECT_TIMEOUT_SECONDS=10
R2_READ_TIMEOUT_SECONDS=60
R2_STREAMING_CHUNK_SIZE=1048576
```

#### Upload / logging / jobs

```env
UPLOAD_MAX_FILE_SIZE_BYTES=104857600
UPLOAD_MAX_ZIP_SIZE_BYTES=524288000
UPLOAD_MAX_FILES_PER_BATCH=500
UPLOAD_MAX_UNCOMPRESSED_ZIP_BYTES=1073741824
UPLOAD_ALLOWED_EXTENSIONS=.wav,.mp3,.ogg
UPLOAD_SYSTEM_UPLOADER_EMAIL=system.upload@audio-intelligence.local
LOGGING_LEVEL=INFO
LOGGING_JSON_LOGS=true
LOGGING_SERVICE_NAME=audio-intelligence-platform
JOB_MAX_RETRIES=3
JOB_RETRY_BACKOFF_BASE_SECONDS=2
JOB_SIMULATE_PROCESSING_MS=100
JOB_HEARTBEAT_TTL_SECONDS=60
JOB_PROGRESS_TTL_SECONDS=86400
```

#### Preprocessing (keep trim off)

```env
PREPROCESS_TRIM_SILENCE=false
PREPROCESS_MAX_DURATION_DELTA_RATIO=0.02
PREPROCESS_TARGET_SAMPLE_RATE=16000
PREPROCESS_TARGET_CHANNELS=1
PREPROCESS_TARGET_LUFS=-23.0
PREPROCESS_TARGET_TRUE_PEAK_DB=-1.5
PREPROCESS_LOUDNESS_RANGE=11.0
PREPROCESS_SILENCE_THRESHOLD_DB=-50.0
PREPROCESS_SILENCE_MIN_DURATION_SECONDS=0.1
PREPROCESS_FFMPEG_TIMEOUT_SECONDS=120
PREPROCESS_FFPROBE_TIMEOUT_SECONDS=30
```

Leave `PREPROCESS_FFMPEG_PATH` / `PREPROCESS_FFPROBE_PATH` empty (PATH ffmpeg on worker).

#### Analysis / technical / acoustic / speech / prediction

Copy the remaining calibrated blocks from local `.env` (or `.env.example`), including:

- `ANALYSIS_*`
- `TECHNICAL_*` (see overlap note below)
- `ACOUSTIC_*`
- `SPEECH_*`
- `PREDICTION_*`
- `PERFORMANCE_*`
- `AI_*`

**Production overrides recommended:**

```env
AI_ENABLED=false
AI_MODEL_CACHE_DIR=/tmp/model_cache
TECHNICAL_OVERLAP_BACKEND=heuristic
TECHNICAL_OVERLAP_DEVICE=cpu
TECHNICAL_OVERLAP_HF_TOKEN=
ACOUSTIC_CLASSIFIER_BACKEND=audio_event
ACOUSTIC_EVENT_DEVICE=cpu
ACOUSTIC_EVENT_LABEL_MAPPING_PATH=config/noise_label_mapping.json
SPEECH_ENABLED=true
SPEECH_DEVICE=cpu
SPEECH_LABEL_MAPPING_PATH=config/speech_label_mapping.json
PERFORMANCE_WORKER_CONCURRENCY=1
PERFORMANCE_PREFETCH_MULTIPLIER=1
PERFORMANCE_MODEL_WARMUP=false
PERFORMANCE_TASK_TIMEOUT=900
PERFORMANCE_BATCH_SIZE=10
```

When pyannote is ready:

```env
TECHNICAL_OVERLAP_BACKEND=pyannote
TECHNICAL_OVERLAP_MODEL_NAME=pyannote/overlapped-speech-detection
TECHNICAL_OVERLAP_HF_TOKEN=<hf_token_with_model_access>
TECHNICAL_OVERLAP_DEVICE=cpu
TECHNICAL_OVERLAP_THRESHOLD=0.62
```

### 3.3 Verify API

```text
https://<railway-api-domain>/health
https://<railway-api-domain>/docs
```

Save the public API base URL (no trailing slash), e.g. `https://aip-api-production.up.railway.app`.

---

## 4. Railway service: `worker`

### 4.1 Settings

| Setting | Value |
| --- | --- |
| Service name | `worker` |
| Same GitHub repo / branch | `main` |
| **Root Directory** | empty / `/` |
| **Builder** | Dockerfile |
| **Dockerfile path** | `docker/railway.worker.Dockerfile` |
| Public networking | **Off** (no domain) |
| **Memory** | **≥ 8 GB** (HuBERT-large ≈ 1.3 GB weights + Torch + AST) |

Worker image installs **ffmpeg** (required for preprocessing).

The Railway worker Dockerfile sets `PERFORMANCE_MODEL_WARMUP=false` so the
process does **not** download HuBERT at boot. Eager warmup on a small plan
OOMs the container; Railway restarts it → crash loop every few minutes.

### 4.2 Environment variables — `worker`

**Duplicate all variables from `api`** (Railway: “Shared variable” / copy service variables).

**Required / strongly recommended for stability:**

```env
PERFORMANCE_MODEL_WARMUP=false
PERFORMANCE_WORKER_CONCURRENCY=1
CELERY_WORKER_PREFETCH_MULTIPLIER=1
HF_TOKEN=<optional but recommended — higher HF rate limits>
AI_MODEL_CACHE_DIR=/tmp/model_cache
```

Leave `PREPROCESS_FFMPEG_PATH` / `PREPROCESS_FFPROBE_PATH` empty.

If you still OOM on the **first** audio job after warmup is disabled, raise
Railway memory to 8 GB (or temporarily set
`SPEECH_MODEL_NAME` to a smaller public SER checkpoint).

### 4.3 Verify worker

In Railway logs you should see:

- `celery@… ready`
- `model_warmup_skipped` / `warmup_enabled=false` (expected on Railway image)
- **no** restart loop

Then enqueue one batch and confirm models load during the first task without
the service crashing.
---

## 5. Vercel — frontend

### 5.1 Settings

| Setting | Value |
| --- | --- |
| Import | `hopper-ai-403/yc` |
| **Root Directory** | `frontend` |
| Framework preset | Next.js |
| Build command | `npm run build` (default) |
| Output | Next default (standalone is for Docker only; Vercel ignores it) |
| Install command | `npm install` |

### 5.2 Environment variables — Vercel

Project → Settings → Environment Variables → Production (+ Preview if desired):

| Name | Value |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | `https://<railway-api-domain>` (no trailing slash) |

That is the **only** required frontend env var (`frontend/.env.example`).

### 5.3 Deploy

Deploy → open `https://YOUR_PROJECT.vercel.app`.

### 5.4 Fix CORS

Update Railway `api` variable:

```env
APP_ALLOWED_ORIGINS=https://YOUR_PROJECT.vercel.app
```

Redeploy `api`. Soft refresh the Vercel app.

---

## 6. End-to-end smoke test

1. Open Vercel URL.
2. Upload a small ZIP (`.wav` / `.mp3` / `.ogg`).
3. Run the batch.
4. Watch Railway **worker** logs: preprocessing → analysis → technical → acoustic → speech → prediction → finalize.
5. Confirm CSV/JSON export downloads.
6. Confirm R2 prefix `uploads/<batch_id>/` has `normalized/`, `predictions/`, `exports/`.

---

## 7. Variable checklist (quick)

| Variable group | `api` | `worker` | Vercel |
| --- | --- | --- | --- |
| `APP_*` | yes | yes | no |
| `DATABASE_*` | yes | yes | no |
| `REDIS_*` / `CELERY_*` | yes | yes | no |
| `JWT_*` | yes | yes | no |
| `R2_*` | yes | yes | no |
| Preprocess / AI / Technical / Acoustic / Speech / Prediction / Performance | yes | yes | no |
| `NEXT_PUBLIC_API_URL` | no | no | **yes** |

---

## 8. Common failures

| Symptom | Fix |
| --- | --- |
| CORS errors in browser | Set `APP_ALLOWED_ORIGINS` to exact Vercel origin; redeploy `api` |
| API up, jobs never process | Worker not deployed or not sharing Redis URL |
| `max number of clients reached` | Free Redis quota; one worker only; kill idle clients |
| Worker crash-loops every few minutes | OOM during HuBERT warmup — set `PERFORMANCE_MODEL_WARMUP=false`, size worker ≥8GB, redeploy `docker/railway.worker.Dockerfile` |
| Preprocess fails / ffmpeg missing | Use `docker/railway.worker.Dockerfile` (has ffmpeg) |
| Noise/SER labels wrong / empty mapping | Ensure image includes repo `config/` (railway Dockerfiles do) |
| Port bind errors on Railway | API must listen on `$PORT` (railway API Dockerfile does) |
| HuggingFace / pyannote auth errors | Set HF token or `TECHNICAL_OVERLAP_BACKEND=heuristic` |
| Vercel calls localhost | `NEXT_PUBLIC_API_URL` must be Railway HTTPS URL |

---

## 9. Resource sizing (starting point)

| Service | RAM | Notes |
| --- | --- | --- |
| `api` | 512 MB–1 GB | Light; mostly I/O |
| `worker` | 4–8 GB | Torch + HuBERT + AST; start at 8 GB if OOM |
| Vercel | Hobby/Pro | Frontend only |

---

## 10. Deploy order (summary)

1. Neon migrations (`alembic upgrade head`)
2. Railway `api` + env + public domain
3. Railway `worker` + same env
4. Vercel `frontend` + `NEXT_PUBLIC_API_URL`
5. Set `APP_ALLOWED_ORIGINS` → redeploy `api`
6. Smoke-test one batch
