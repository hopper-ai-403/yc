# DOMAIN_MODEL.md

# Audio Intelligence Platform

Version: 1.0

---

# Purpose

This document defines the business domain.

It intentionally contains **no implementation details**.

It does not describe:

- FastAPI
- SQLAlchemy
- Celery
- Redis
- PostgreSQL
- Cloudflare R2

It only defines the business model.

---

# Ubiquitous Language

Throughout the codebase these words have fixed meanings.

Audio Batch

A collection of uploaded audio files processed together.

Audio Asset

A single audio recording.

Job

An asynchronous processing task.

Prediction

The final structured analysis for one audio file.

Pipeline

The ordered stages required to transform raw audio into predictions.

Analyzer

A component responsible for one type of analysis.

Storage

Persistent storage for uploaded files.

Manifest

CSV describing uploaded files.

Inference

Running an AI model.

---

# Bounded Contexts

The system consists of these business domains.

Authentication

Audio Management

Storage

Job Processing

Prediction

AI Analysis

Export

Administration

These contexts communicate through services.

---

# Domain Entities

## User

Represents a person using the platform.

Fields

- id
- email
- password_hash
- role
- is_active
- created_at
- updated_at

Roles

ADMIN

EVALUATOR

---

## AudioBatch

Represents one uploaded ZIP.

Fields

- id
- original_filename
- total_files
- uploaded_by
- status
- created_at

Relationships

One batch

↓

Many AudioAssets

---

## AudioAsset

Represents one uploaded audio file.

Fields

- id
- batch_id
- filename
- format
- duration
- sample_rate
- channels
- storage_key
- processing_status

Relationships

One AudioAsset

↓

One Prediction

---

## Job

Represents one asynchronous processing job.

Fields

- id
- batch_id
- status
- progress
- retry_count
- started_at
- completed_at

---

## Prediction

Represents the final AI output.

Fields

- id
- audio_asset_id
- emotion
- emotion_intensity
- noise
- quality
- overlap
- silence
- confidence

Prediction is immutable after completion.

---

## AuditLog

Represents important system actions.

Examples

Upload

Delete

Login

Download

Failure

---

# Value Objects

Unlike entities, value objects have no identity.

EmotionResult

- tone
- intensity

NoiseResult

- present
- type
- severity

QualityResult

- quality

OverlapResult

- present

SilenceResult

- present

ConfidenceScore

- value

Metadata

- duration
- sample_rate
- channels
- bitrate

---

# Aggregates

AudioBatch

Owns

AudioAssets

Job

Owns

Processing lifecycle

Prediction

Owns

All analyzer outputs

---

# Repository Contracts

UserRepository

create()

find_by_email()

find_by_id()

JobRepository

create()

update_status()

find()

find_active()

AudioRepository

create()

find()

update_status()

PredictionRepository

save()

find()

AuditRepository

append()

find()

Repositories never contain business rules.

---

# Service Contracts

StorageService

upload()

download()

delete()

exists()

AnalyzerService

analyze()

JobService

create()

queue()

cancel()

complete()

PredictionService

aggregate()

validate()

persist()

ExportService

csv()

json()

---

# State Machines

## AudioAsset

Uploaded

↓

Validated

↓

Queued

↓

Processing

↓

Processed

↓

Completed

or

↓

Failed

---

## Job

Pending

↓

Queued

↓

Running

↓

Completed

↓

Failed

↓

Cancelled

Retry

↓

Running

---

# Domain Events

BatchUploaded

AudioValidated

AudioQueued

AudioProcessingStarted

PredictionCompleted

PredictionFailed

JobCompleted

JobFailed

ExportGenerated

---

# Business Rules

Rule 1

Prediction cannot exist without AudioAsset.

Rule 2

AudioAsset belongs to exactly one Batch.

Rule 3

One AudioAsset produces exactly one Prediction.

Rule 4

Prediction is immutable.

Rule 5

Job completion percentage

=

Completed Assets

/

Total Assets

Rule 6

Failed files never stop batch processing.

Rule 7

Unsupported audio formats are skipped with error reporting.

Rule 8

Storage keys are immutable after upload.

---

# Invariants

A Prediction always belongs to an AudioAsset.

An AudioAsset always belongs to one Batch.

A Batch always owns one Job.

Job progress is always between 0 and 100.

Confidence is always between 0.0 and 1.0.

Emotion intensity cannot exist without emotion.

Noise severity must be "none" when no noise exists.

Noise type must be empty when no noise exists.

---

# Future Extension Points

Speaker Diarization

Keyword Detection

Summarization

Compliance

Fraud Detection

Sales Coaching

Topic Classification

Sentiment Timeline

Conversation Quality

All future capabilities should extend existing analyzers instead of modifying existing entities.

---

# Architecture Rule

Business rules belong only inside the Domain Layer.

Infrastructure must never implement business decisions.

The domain must remain independent from frameworks.