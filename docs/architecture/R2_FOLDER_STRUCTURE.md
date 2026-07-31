# R2 Folder Structure

Bucket: configured via `R2_BUCKET_NAME` (example: `ycaudiointelligence`)

```text
{bucket}/
  uploads/
    {batch_id}/
      original/
        call-001.wav
      normalized/
        {audio_id}.wav
      metadata/
        {audio_id}.json
      analysis/
        {audio_id}.json
      technical/
        {audio_id}.json
      acoustic/
        {audio_id}.json
      speech/
        {audio_id}.json
      predictions/
        {audio_id}.json
```

## Key formats

```text
uploads/{batch_id}/original/{filename}
uploads/{batch_id}/normalized/{audio_id}.wav
uploads/{batch_id}/metadata/{audio_id}.json
uploads/{batch_id}/analysis/{audio_id}.json
uploads/{batch_id}/technical/{audio_id}.json
uploads/{batch_id}/acoustic/{audio_id}.json
uploads/{batch_id}/speech/{audio_id}.json
uploads/{batch_id}/predictions/{audio_id}.json
```

## Rules

- Original keys are immutable after upload
- Normalized audio is always PCM WAV 16 kHz mono 16-bit
- Metadata JSON mirrors `AudioTechnicalMetadata`
- Object metadata includes `audio_id`, `batch_id`, and `stage`
