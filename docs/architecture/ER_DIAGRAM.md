# Entity Relationship Diagram

```mermaid
erDiagram
    USER ||--o{ AUDIO_BATCH : uploads
    USER ||--o{ AUDIT_LOG : acts
    AUDIO_BATCH ||--|{ AUDIO_ASSET : contains
    AUDIO_BATCH ||--|| JOB : owns
    AUDIO_ASSET ||--o| PREDICTION : yields

    USER {
        uuid id PK
        string email UK
        string password_hash
        enum role
        bool is_active
        timestamptz created_at
        timestamptz updated_at
    }

    AUDIO_BATCH {
        uuid id PK
        string original_filename
        int total_files
        uuid uploaded_by FK
        enum status
        timestamptz created_at
        timestamptz updated_at
    }

    AUDIO_ASSET {
        uuid id PK
        uuid batch_id FK
        string filename
        string format
        float duration
        int sample_rate
        int channels
        string storage_key UK
        enum processing_status
        timestamptz created_at
        timestamptz updated_at
    }

    JOB {
        uuid id PK
        uuid batch_id FK_UK
        enum status
        int progress
        int retry_count
        timestamptz started_at
        timestamptz completed_at
        timestamptz created_at
        timestamptz updated_at
    }

    PREDICTION {
        uuid id PK
        uuid audio_asset_id FK_UK
        enum emotional_tone
        enum emotional_intensity
        bool background_noise_present
        string background_noise_type
        enum background_noise_severity
        enum audio_quality
        bool speaker_overlap
        bool long_silence
        float confidence
        bool is_persisted
        timestamptz created_at
        timestamptz updated_at
    }

    AUDIT_LOG {
        uuid id PK
        uuid actor_id FK
        string action
        string resource_type
        uuid resource_id
        jsonb details
        timestamptz created_at
        timestamptz updated_at
    }
```
