# Production Hardening + Benchmarking

## Purpose

Operational readiness for production-quality evaluation: reliability,
observability, and measurable performance. No business features.

## Model warmup

`app/infrastructure/warmup.py` loads singleton AI models at worker boot via
the Celery `worker_ready` signal (`app/infrastructure/celery/signals.py`).
Load time per model is logged (`model_warmup_completed`) and tracked in
`ModelWarmupState`, which feeds `model_loaded` in health and system metrics.
Disable with `PERFORMANCE_MODEL_WARMUP=false`.

## Pipeline profiling + timing

`app/shared/profiling.py` (`PipelineProfiler`) records per-stage
`start_time` / `end_time` / `duration_ms` / `status` for:
preprocessing, analysis, technical, acoustic, speech, prediction.

- Per-audio timings persist to `audio_assets.timing_json`
  (`*_duration_ms` + `total_pipeline_duration_ms` + `stages`).
- The full profile is stored in the internal prediction metadata under
  `profile` (R2 + `internal_prediction_json`).
- Per-batch `batch_duration_ms` persists to `batch_metrics`.

## Worker resiliency

- Heartbeats refresh `worker:{hostname}` keys (TTL-bounded).
- `JobProgressCache.list_workers` + `is_worker_stale` power
  `/api/v1/system/workers` stale detection.
- `JobService.recover_orphaned_jobs` runs at worker boot: RUNNING jobs
  older than the threshold without a fresh heartbeat are failed, their
  PROCESSING assets reset, and the job is requeued.
- Graceful shutdown is logged via the `worker_shutdown` signal.
- Retries log `audio_task_retrying`; Celery `task_time_limit` /
  `task_soft_time_limit` bound task runtimes.

## R2 resiliency

`CloudflareR2Storage` now provides:

- Exponential-backoff retry (`R2_RETRY_COUNT`, base/max backoff) for
  transient failures; 4xx errors (except 429) are never retried.
- Connect/read timeouts via botocore `Config`.
- Connection reuse (single cached client).
- `upload_stream` / `download_stream` for chunked I/O.

## Performance configuration

`PERFORMANCE_WORKER_CONCURRENCY`, `PERFORMANCE_BATCH_SIZE`,
`PERFORMANCE_PREFETCH_MULTIPLIER`, `PERFORMANCE_MODEL_WARMUP`,
`PERFORMANCE_PIPELINE_PROFILING`, `PERFORMANCE_R2_RETRY_COUNT`,
`PERFORMANCE_TASK_TIMEOUT`, plus R2 resiliency knobs (`R2_*`).

## Health + system API

- `/health/ready` additionally returns `model_loaded`, `worker_count`,
  `system_version`.
- `GET /api/v1/system/metrics` — database/redis/r2/celery/model_loaded/
  worker_count/system_version.
- `GET /api/v1/system/workers` — worker registry with stale flags.
- `GET /api/v1/system/benchmark?batch_id=...` — latency average/P50/P95/P99,
  throughput (files/minute), average confidence, failure rate.

## Benchmarking

`app/system/benchmark.py` (`BenchmarkRunner`) computes benchmarks from
persisted per-audio timing metadata (wall-time fallback) and job duration.
