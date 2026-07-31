# Metadata Schema

Purpose: Define the JSON metadata produced by preprocessing and stored in R2 + `metadata_json`.

---

## R2 object

Key: `uploads/{batch_id}/metadata/{audio_id}.json`

Content-Type: `application/json`

---

## Schema

```json
{
  "duration": 12.45,
  "sample_rate": 44100,
  "channels": 2,
  "bitrate": 128000,
  "codec": "mp3",
  "container": "mp3",
  "file_size": 204800,
  "peak_db": -1.2,
  "rms_db": -18.5,
  "normalized_sample_rate": 16000,
  "normalized_channels": 1,
  "normalized_codec": "pcm_s16le",
  "normalized_file_size": 396800,
  "normalized_duration": 12.40,
  "metadata_storage_key": "uploads/{batch_id}/metadata/{audio_id}.json"
}
```

| Field | Source |
|-------|--------|
| `duration`, `sample_rate`, `channels`, `bitrate`, `codec`, `container`, `file_size` | Original (ffprobe + file size) |
| `peak_db`, `rms_db` | `volumedetect` on original |
| `normalized_*` | Target format / post-normalize probe |

Pydantic model: `AudioTechnicalMetadata` in `app.audio.preprocessing.metadata`.

---

## DB denormalization

Also copied to columns: `duration`, `sample_rate`, `channels` for query convenience.
