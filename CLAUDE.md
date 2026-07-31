# CLAUDE.md

# Audio Intelligence Platform

This file defines the engineering constitution for the project.

Every implementation must follow this document.

Do NOT redesign the architecture.

Do NOT simplify the architecture.

Do NOT introduce new frameworks unless explicitly requested.

Always preserve modularity.

---

# Project Overview

This project is a production-grade Audio Intelligence Platform.

The goal is NOT simply to classify emotions.

The goal is to build a scalable SaaS platform capable of processing batches of customer call recordings and producing structured predictions.

Current prediction schema:

- emotional_tone
- emotional_intensity
- background_noise_present
- background_noise_type
- background_noise_severity
- audio_quality
- speaker_overlap
- long_silence
- confidence

The architecture must remain extensible for future features like:

- Call Summarization
- Compliance Detection
- Sales Coaching
- Fraud Detection
- QA Analytics

Never hardcode logic that prevents future expansion.

---

# Engineering Principles

Always follow:

- SOLID
- Clean Code
- Separation of Concerns
- Dependency Injection
- Repository Pattern
- Service Layer
- Modular Monolith
- Domain Driven Feature Modules

Never place business logic inside API routes.

Never access SQLAlchemy directly from API routes.

Never access Cloudflare R2 directly from API routes.

Never access Redis directly from API routes.

---

# Feature Module Structure

Every business capability owns its own files.

Example:

jobs/

api.py

service.py

repository.py

schemas.py

models.py

exceptions.py

dependencies.py

Tests belong beside the feature or inside tests/.

Never create huge utility files.

Never create misc.py.

---

# Shared Module

Only common code belongs here.

Examples:

shared/database

shared/storage

shared/security

shared/logging

shared/exceptions

shared/response

shared/types

Do not place business logic inside shared.

---

# Infrastructure Layer

All external services belong here.

Examples:

Cloudflare R2

Redis

Celery

PostgreSQL

FFmpeg

Future external APIs

Application code should communicate only through interfaces.

---

# Storage

Storage provider:

Cloudflare R2

Never use local storage except temporary processing.

Always use the StorageProvider abstraction.

Never import boto3 directly outside infrastructure.

---

# Database

Use:

SQLAlchemy 2.x

Alembic

UUID primary keys

Every table must contain:

id

created_at

updated_at

Repositories perform all database access.

Services never execute raw SQL.

---

# Dependency Injection

Always use FastAPI Depends.

Never instantiate repositories or services inside routes.

Inject:

Repositories

Storage

Settings

Logger

Services

AI Engines

---

# AI Architecture

Separate AI into modules.

emotion/

acoustic/

technical/

aggregation/

confidence/

Do not mix responsibilities.

Emotion module should never classify noise.

Noise module should never compute confidence.

Aggregation combines predictions.

---

# API Standards

Every endpoint returns:

{
  "success": true,
  "message": "",
  "data": {}
}

Errors:

{
  "success": false,
  "error": {
      "code":"",
      "message":"",
      "details":{}
  }
}

Never invent different response formats.

---

# Logging

Use structured logging.

Every log should contain whenever applicable:

request_id

job_id

audio_id

user_id

service

latency

status

No print statements.

---

# Exceptions

Create specific exceptions.

ValidationException

StorageException

AuthenticationException

InferenceException

QueueException

Never raise generic Exception unless absolutely necessary.

---

# Type Hints

Everything must be typed.

No Any unless unavoidable.

Functions must have return types.

---

# Configuration

All configuration comes from Settings.

Never call os.getenv() inside business logic.

---

# Testing

Every feature should eventually have:

Unit tests

Integration tests

API tests

Workers should be independently testable.

---

# Docker

Separate containers:

backend

worker

frontend

postgres

redis

flower

Never assume localhost.

Everything communicates through Docker networks.

---

# Security

Passwords:

Argon2

JWT:

Access + Refresh

Validate uploads.

Validate MIME types.

Never trust user input.

---

# Code Quality

Follow:

Black

Ruff

Pyright

Pytest

No commented-out code.

No TODOs in production code.

No dead code.

---

# Documentation

Every major module should include:

Purpose

Responsibilities

Dependencies

Extension points

---

# If Unsure

Never invent architecture.

Instead:

Follow the existing architecture.

Preserve modularity.

Keep components loosely coupled.

Favor extensibility over shortcuts.

Assume this project will be maintained by multiple senior engineers.