#!/usr/bin/env python3
"""Offline model evaluation utility (does not affect production code paths).

Usage (from repo root, with backend venv active):

  python scripts/evaluate_models.py --audio-dir ./samples --output evaluation.csv

  python scripts/evaluate_models.py --audio-dir ./samples --ser-benchmark \\
      --ser-models superb/hubert-large-superb-er,superb/wav2vec2-base-superb-er
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

# Allow running from repo root without installing the package.
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _load_local_waveform(path: Path, sample_rate: int = 16_000) -> tuple[np.ndarray, int]:
    from app.audio.analysis.signal import load_waveform

    return load_waveform(path.read_bytes(), expected_sample_rate=sample_rate)


def _iter_audio_files(audio_dir: Path) -> list[Path]:
    extensions = {".wav", ".flac", ".ogg", ".mp3", ".m4a"}
    return sorted(
        p for p in audio_dir.rglob("*") if p.is_file() and p.suffix.lower() in extensions
    )


def _run_full_evaluation(audio_files: list[Path], output: Path) -> None:
    from app.ai.acoustic.analyzer import AcousticAnalyzer
    from app.ai.acoustic.detector import SignalBasedNoiseDetector
    from app.ai.acoustic.event_classifier import HuggingFaceAudioEventClassifier
    from app.ai.acoustic.classifier import HeuristicNoiseClassifier
    from app.ai.acoustic.severity import DeterministicSeverityEstimator
    from app.ai.speech.analyzer import SpeechAnalyzer
    from app.ai.speech.inference import get_or_load_model, reset_model_registry
    from app.ai.technical.analyzer import TechnicalAnalyzer
    from app.ai.technical.overlap import SignalBasedOverlapDetector
    from app.ai.technical.quality import AudioQualityAnalyzer
    from app.ai.technical.silence import LongSilenceDetector
    from app.audio.analysis.factory import build_vad
    from app.audio.analysis.features import FeatureExtractor
    from app.audio.analysis.schemas import AnalysisArtifact
    from app.config.settings import get_settings
    from app.prediction.confidence import WeightedConfidenceEstimator
    from app.prediction.schemas import AnalysisResult

    settings = get_settings()
    reset_model_registry()

    vad = build_vad(settings.analysis)
    feature_extractor = FeatureExtractor()
    speech_model = get_or_load_model(settings.speech)
    speech_analyzer = SpeechAnalyzer(model=speech_model, settings=settings.speech)
    technical_analyzer = TechnicalAnalyzer(
        silence=LongSilenceDetector(settings.technical),
        quality=AudioQualityAnalyzer(settings.technical),
        overlap=SignalBasedOverlapDetector(settings.technical),
    )
    acoustic_analyzer = AcousticAnalyzer(
        detector=SignalBasedNoiseDetector(settings.acoustic),
        classifier=HuggingFaceAudioEventClassifier(
            settings.acoustic,
            fallback=HeuristicNoiseClassifier(settings.acoustic),
        ),
        severity=DeterministicSeverityEstimator(settings.acoustic),
    )
    confidence = WeightedConfidenceEstimator(settings.prediction)

    rows: list[dict[str, object]] = []
    for path in audio_files:
        waveform, sample_rate = _load_local_waveform(path)
        audio_id = path.stem
        vad_result = vad.detect(waveform, sample_rate)
        features = feature_extractor.extract(waveform, sample_rate, vad=vad_result)
        artifact = AnalysisArtifact(
            audio_id=audio_id,
            batch_id="eval",
            sample_rate=sample_rate,
            vad=vad_result,
            features=features,
        )
        technical = technical_analyzer.analyze(artifact)
        acoustic = acoustic_analyzer.analyze(
            artifact, waveform=waveform, sample_rate=sample_rate
        )
        speech = speech_analyzer.analyze(
            audio_id=audio_id,
            batch_id="eval",
            waveform=waveform,
            sample_rate=sample_rate,
        )
        breakdown = confidence.estimate(
            AnalysisResult(technical=technical, acoustic=acoustic, speech=speech)
        )
        rows.append(
            {
                "audio": str(path),
                "emotion": speech.emotional_tone.value,
                "intensity": speech.emotional_intensity.value,
                "raw_label": speech.raw_label,
                "noise_present": acoustic.background_noise_present,
                "noise": acoustic.background_noise_type.value,
                "noise_severity": acoustic.background_noise_severity.value,
                "quality": technical.audio_quality.value,
                "overlap": technical.speaker_overlap_present,
                "confidence": breakdown.overall,
                "speech_confidence": breakdown.speech,
                "technical_confidence": breakdown.technical,
                "acoustic_confidence": breakdown.acoustic,
                "ser_model": speech.model_name,
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    print(f"Wrote {len(rows)} rows → {output}")


def _run_ser_benchmark(
    audio_files: list[Path],
    model_names: list[str],
    output: Path,
) -> None:
    from app.ai.speech.benchmark import evaluate_ser_models
    from app.config.settings import SpeechSettings

    waveforms: dict[str, tuple[np.ndarray, int]] = {}
    for path in audio_files:
        waveforms[path.stem] = _load_local_waveform(path)

    rows = evaluate_ser_models(
        waveforms=waveforms,
        model_names=model_names,
        base_settings=SpeechSettings(),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = [row.to_dict() for row in rows]
    if output.suffix.lower() == ".json":
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        flat_rows = []
        for row in payload:
            flat = {**row, "scores": json.dumps(row["scores"])}
            flat_rows.append(flat)
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=list(flat_rows[0].keys()) if flat_rows else []
            )
            if flat_rows:
                writer.writeheader()
                writer.writerows(flat_rows)
    print(f"Wrote SER benchmark ({len(rows)} rows) → {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Audio Intelligence models offline")
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("evaluation.csv"))
    parser.add_argument(
        "--ser-benchmark",
        action="store_true",
        help="Compare multiple SER models instead of full pipeline evaluation",
    )
    parser.add_argument(
        "--ser-models",
        type=str,
        default="superb/hubert-large-superb-er,superb/wav2vec2-base-superb-er",
        help="Comma-separated Hugging Face SER model IDs",
    )
    args = parser.parse_args()

    if not args.audio_dir.is_dir():
        print(f"Audio directory not found: {args.audio_dir}", file=sys.stderr)
        return 1

    audio_files = _iter_audio_files(args.audio_dir)
    if not audio_files:
        print(f"No audio files found under {args.audio_dir}", file=sys.stderr)
        return 1

    if args.ser_benchmark:
        models = [m.strip() for m in args.ser_models.split(",") if m.strip()]
        _run_ser_benchmark(audio_files, models, args.output)
    else:
        _run_full_evaluation(audio_files, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
