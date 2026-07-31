# Audio Analysis Foundation

Purpose: Produce reusable VAD + signal feature artifacts consumed by future AI engines.

Responsibilities: Voice activity detection, speech/silence segmentation, signal features, persistence.

Dependencies: Normalized audio from preprocessing, Silero VAD (`torch`), `librosa`, R2, `AudioRepository`.

Extension points: Technical / Acoustic / Speech Intelligence engines read `AnalysisArtifact` without re-running VAD.

---

## Pipeline

```mermaid
sequenceDiagram
    participant Worker as process_audio
    participant Pre as preprocess_audio
    participant Ana as analyze_audio
    participant VAD as Silero VAD
    participant Feat as FeatureExtractor
    participant R2 as Cloudflare R2
    participant DB as Postgres

    Worker->>Pre: preprocess (normalized WAV)
    Pre-->>Worker: ok
    Worker->>Ana: analyze_audio(audio_id)
    Ana->>R2: download normalized WAV
    Ana->>VAD: detect speech
    Ana->>Feat: extract features
    Ana->>R2: uploads/{batch}/analysis/{audio}.json
    Ana->>DB: analysis_completed + markers
    Worker->>Worker: mark COMPLETED
```

---

## Job orchestration

```text
process_batch
  └─ process_audio
       ├─ preprocess_audio
       ├─ analyze_audio
       └─ complete
```

No emotion / noise / prediction / confidence in this sprint.

---

## R2 layout

```text
uploads/{batch_id}/analysis/{audio_id}.json
```

---

## Database

| Column | Meaning |
|--------|---------|
| `analysis_completed` | Idempotency flag |
| `analysis_storage_key` | R2 JSON key |
| `analysis_version` | Artifact schema version (`1.0.0`) |
| `analysis_completed_at` | Timestamp |
| `analysis_json` | Cached artifact for API reads |

---

## HTTP API

- `GET /api/v1/audio/{id}/analysis`
- `GET /api/v1/audio/{id}/segments`
