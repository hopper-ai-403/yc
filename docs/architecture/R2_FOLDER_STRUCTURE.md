# R2 Folder Structure

Bucket: configured via `R2_BUCKET_NAME` (example: `ycaudiointelligence`)

```text
{bucket}/
  uploads/
    {batch_id}/
      original/
        call-001.wav
        call-002.mp3
        call-003.ogg
```

## Key format

```text
uploads/{batch_id}/original/{filename}
```

## Rules

- Only original uploaded media is stored in Sprint 2
- Filenames are basename-sanitized (no directories)
- Object metadata includes `checksum_sha256` and `batch_id`
- Future sprints may add:

```text
uploads/{batch_id}/
  original/
  processed/
  derivatives/
```

without changing the original key layout.
