# Feature Schema

Purpose: Define the shared signal feature payload inside analysis JSON.

---

## Artifact envelope

```json
{
  "audio_id": "...",
  "batch_id": "...",
  "version": "1.0.0",
  "sample_rate": 16000,
  "vad": { "...": "..." },
  "features": {
    "duration": 12.5,
    "rms_energy": 0.05,
    "peak_amplitude": 0.9,
    "zero_crossing_rate": 0.08,
    "spectral_centroid": 1800.0,
    "spectral_bandwidth": 2200.0,
    "spectral_rolloff": 4500.0,
    "mfcc": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3],
    "pitch_f0": 160.0,
    "tempo_estimate": 120.0,
    "dynamic_range": 18.0,
    "snr_estimate": 12.5,
    "sample_rate": 16000
  }
}
```

Pydantic models: `AnalysisArtifact`, `SignalFeatures`, `VADResult` in `app.audio.analysis.schemas`.

---

## Notes

- MFCC is exactly 13 coefficients (mean over time)
- `snr_estimate` uses VAD speech vs silence energy ratio (dB)
- Features are **not** emotion/noise labels — downstream engines interpret them
