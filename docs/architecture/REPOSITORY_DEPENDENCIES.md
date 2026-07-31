# Repository Dependency Diagram

```mermaid
flowchart TB
    subgraph Domain["Shared Domain"]
        Enums[enums]
        VOs[value_objects]
        DomEx[domain exceptions]
    end

    subgraph Features["Feature Modules"]
        AuthModel[auth.models.User]
        AudioModel[audio.models.AudioBatch / AudioAsset]
        JobModel[jobs.models.Job]
        PredModel[prediction.models.Prediction]
        AuditModel[audit.models.AuditLog]

        UserRepo[UserRepository]
        BatchRepo[AudioBatchRepository]
        AudioRepo[AudioRepository]
        JobRepo[JobRepository]
        PredRepo[PredictionRepository]
        AuditRepo[AuditRepository]
    end

    subgraph Persistence["SQLAlchemy Implementations"]
        SAUser[SqlAlchemyUserRepository]
        SABatch[SqlAlchemyAudioBatchRepository]
        SAAudio[SqlAlchemyAudioRepository]
        SAJob[SqlAlchemyJobRepository]
        SAPred[SqlAlchemyPredictionRepository]
        SAAudit[SqlAlchemyAuditRepository]
        Session[AsyncSession / Neon]
    end

    Enums --> AuthModel
    Enums --> AudioModel
    Enums --> JobModel
    Enums --> PredModel
    VOs --> PredModel
    DomEx --> PredRepo
    DomEx --> JobRepo

    AuthModel --> UserRepo
    AudioModel --> BatchRepo
    AudioModel --> AudioRepo
    JobModel --> JobRepo
    PredModel --> PredRepo
    AuditModel --> AuditRepo

    UserRepo --> SAUser
    BatchRepo --> SABatch
    AudioRepo --> SAAudio
    JobRepo --> SAJob
    PredRepo --> SAPred
    AuditRepo --> SAAudit

    SAUser --> Session
    SABatch --> Session
    SAAudio --> Session
    SAJob --> Session
    SAPred --> Session
    SAAudit --> Session
```

## Ownership rules

| Aggregate / Entity | Repository | Notes |
| --- | --- | --- |
| User | `UserRepository` | create, find_by_id, find_by_email, update |
| AudioBatch | `AudioBatchRepository` | create, find_by_id, update_status, list_by_uploader |
| AudioAsset | `AudioRepository` | create, find, update_status, find_by_batch |
| Job | `JobRepository` | create, find, find_active, update_status |
| Prediction | `PredictionRepository` | save (immutable after), find |
| AuditLog | `AuditRepository` | append, find |

Repositories contain persistence only. Domain invariants live in value objects, entity methods, and repository guards (prediction immutability).
