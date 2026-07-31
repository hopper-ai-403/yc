# Database Schema

## Overview

Initial domain schema for the Audio Intelligence Platform (Alembic revision `ce21a1451fc6`).

Provider: Neon PostgreSQL.

## Tables

### users

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID PK | |
| email | VARCHAR(320) | unique, indexed |
| password_hash | VARCHAR(255) | |
| role | user_role enum | ADMIN, EVALUATOR |
| is_active | BOOLEAN | default true |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### audio_batches

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID PK | |
| original_filename | VARCHAR(512) | |
| total_files | INTEGER | |
| uploaded_by | UUID FK → users.id | RESTRICT |
| status | batch_status enum | indexed |
| created_at / updated_at | TIMESTAMPTZ | |

### audio_assets

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID PK | |
| batch_id | UUID FK → audio_batches.id | CASCADE, indexed |
| filename | VARCHAR(512) | |
| format | VARCHAR(32) | |
| duration | FLOAT | nullable |
| sample_rate | INTEGER | nullable |
| channels | INTEGER | nullable |
| storage_key | VARCHAR(1024) | unique |
| processing_status | audio_status enum | indexed |
| created_at / updated_at | TIMESTAMPTZ | |

### jobs

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID PK | |
| batch_id | UUID FK → audio_batches.id | unique (one job per batch) |
| status | job_status enum | indexed |
| progress | INTEGER | 0–100 check |
| retry_count | INTEGER | ≥ 0 check |
| started_at / completed_at | TIMESTAMPTZ | nullable |
| created_at / updated_at | TIMESTAMPTZ | |

### predictions

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID PK | |
| audio_asset_id | UUID FK → audio_assets.id | unique (one prediction per asset) |
| emotional_tone | emotion_tone enum | |
| emotional_intensity | emotion_intensity enum | |
| background_noise_present | BOOLEAN | |
| background_noise_type | VARCHAR(128) | empty when no noise |
| background_noise_severity | noise_severity enum | NONE when no noise |
| audio_quality | audio_quality enum | |
| speaker_overlap | BOOLEAN | |
| long_silence | BOOLEAN | |
| confidence | FLOAT | 0–1 check |
| is_persisted | BOOLEAN | immutability flag |
| created_at / updated_at | TIMESTAMPTZ | |

### audit_logs

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID PK | |
| actor_id | UUID FK → users.id | SET NULL |
| action | VARCHAR(128) | indexed |
| resource_type | VARCHAR(128) | indexed |
| resource_id | UUID | indexed, nullable |
| details | JSONB | |
| created_at / updated_at | TIMESTAMPTZ | |

## Invariants enforced in schema

- One `Job` per `AudioBatch` (`uq_jobs_batch_id`)
- One `Prediction` per `AudioAsset` (`uq_predictions_audio_asset_id`)
- Unique `users.email`, unique `audio_assets.storage_key`
- Job progress 0–100; prediction confidence 0–1

## ER Diagram

See [ER_DIAGRAM.md](./ER_DIAGRAM.md).
