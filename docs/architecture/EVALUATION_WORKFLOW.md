# Evaluation Workflow

## Purpose

End-to-end batch execution workflow for reviewers:

Upload ZIP → Start Job → Monitor Progress → Download assessment CSV.

## Components

| File | Responsibility |
| --- | --- |
| `runner.py` | Validate batch and queue its job; prevent duplicate execution |
| `service.py` | Reviewer-facing workflow: run, status, metrics, exports |
| `pipeline.py` | Finalize a completed batch: metrics + export artifacts |
| `metrics.py` | Deterministic per-batch metric computation |
| `exporter.py` | CSV/JSON generation and R2 artifact management |
| `repository.py` | `BatchMetricsRepository` persistence contract |
| `models.py` | `BatchMetrics` entity (one row per batch) |
| `factory.py` | Construct `EvaluationService` outside FastAPI DI |
| `api.py` | HTTP routes (no business logic) |
| `schemas.py` | Request/response DTOs |

## Endpoints

- `POST /api/v1/batches/{batch_id}/run` — queue the batch job; idempotent.
- `GET /api/v1/batches/{batch_id}/status` — progress + `estimated_remaining_seconds`.
- `GET /api/v1/batches/{batch_id}/export/csv` — `filename,result_json` CSV download.
- `GET /api/v1/batches/{batch_id}/export/json` — public assessment fields only.
- `GET /api/v1/batches/{batch_id}/metrics` — persisted batch metrics.
- `GET /api/v1/batches/{batch_id}/exports` — signed R2 URLs for export artifacts.

## Worker integration

When `finalize_job` completes a job, the evaluation pipeline runs
(non-fatally): metrics are computed and persisted, and
`uploads/{batch_id}/exports/results.csv` + `results.json` are uploaded to R2.

## Business rules

- Batch completes even if some files fail.
- Exports include only successfully predicted files.
- Metrics include failed files.
- Export generation is idempotent (existing R2 artifacts are reused unless
  `regenerate=True`).

## Metric computation

Processing time per asset is the wall time from `uploaded_at` to
`prediction_completed_at`. Confidence is averaged over successful
predictions. `success_rate = successful / total_audio` (0 when empty).

## Extension points

- Additional export formats: extend `BatchExporter`.
- Additional metric dimensions: extend `BatchMetricsCalculator` and
  `BatchMetrics`.
