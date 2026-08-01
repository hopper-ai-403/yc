#!/usr/bin/env python3
"""Inference calibration runner (mappings + thresholds only).

Runs each engine independently, saves stage intermediates, proposes generic
threshold/mapping updates from observed score distributions, and writes
calibration_report.json.

Does NOT modify model weights, APIs, DB, Celery, frontend, or pipelines.
Does NOT special-case filenames or invent ground truth.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


AUDIO_EXTENSIONS = {".wav", ".flac", ".ogg", ".mp3", ".m4a"}


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    arr = np.asarray(sorted(values), dtype=np.float64)
    return float(np.quantile(arr, p))


def _entropy(probs: list[float]) -> float:
    total = sum(max(0.0, p) for p in probs)
    if total <= 0 or len(probs) <= 1:
        return 0.0
    norm = [max(0.0, p) / total for p in probs]
    return float(-sum(p * math.log(p + 1e-12) for p in norm) / math.log(len(norm)))


def _margin(probs: list[float]) -> float:
    ordered = sorted((max(0.0, p) for p in probs), reverse=True)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    return max(0.0, ordered[0] - ordered[1])


def _iter_audio(audio_dir: Path) -> list[Path]:
    return sorted(
        p for p in audio_dir.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    )


def _load_optional_ground_truth(path: Path | None) -> dict[str, dict[str, Any]]:
    """Load optional GT keyed by stem. Never invents labels."""
    if path is None or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "items" in payload:
        items = payload["items"]
    elif isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = [{"audio_id": k, **v} for k, v in payload.items() if isinstance(v, dict)]
    else:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("audio_id") or item.get("filename") or item.get("id") or "")
        key = Path(key).stem
        if key:
            out[key] = item
    return out


def _compare_fields(
    predicted: dict[str, Any], truth: dict[str, Any]
) -> dict[str, Any]:
    fields = [
        "emotional_tone",
        "emotional_intensity",
        "background_noise_present",
        "background_noise_type",
        "background_noise_severity",
        "audio_quality",
        "speaker_overlap_present",
        "long_silence_present",
    ]
    comparisons: dict[str, Any] = {}
    matches = 0
    compared = 0
    for field in fields:
        if field not in truth:
            continue
        compared += 1
        pred = predicted.get(field)
        exp = truth.get(field)
        ok = pred == exp
        if ok:
            matches += 1
        comparisons[field] = {"predicted": pred, "expected": exp, "match": ok}
    return {
        "fields": comparisons,
        "matched": matches,
        "compared": compared,
        "accuracy": (matches / compared) if compared else None,
    }


def _load_and_resample(path: Path, target_sr: int = 16_000) -> tuple[np.ndarray, int]:
    """Load arbitrary audio and resample to the platform analysis rate.

    Calibration operates on raw eval files that may not be preprocessed.
    Production pipelines still require normalized 16 kHz WAV.
    """
    from app.audio.analysis.signal import load_waveform

    waveform, sample_rate = load_waveform(path.read_bytes(), expected_sample_rate=None)
    if int(sample_rate) == target_sr:
        return waveform, target_sr
    import librosa

    resampled = librosa.resample(
        waveform.astype(np.float32, copy=False),
        orig_sr=sample_rate,
        target_sr=target_sr,
    ).astype(np.float32, copy=False)
    return resampled, target_sr


def run_calibration(
    *,
    audio_dir: Path,
    output_dir: Path,
    ground_truth_path: Path | None,
    apply: bool,
) -> dict[str, Any]:
    from app.ai.acoustic.classifier import HeuristicNoiseClassifier
    from app.ai.acoustic.detector import SignalBasedNoiseDetector
    from app.ai.acoustic.event_classifier import (
        HuggingFaceAudioEventClassifier,
        _get_or_load_event_pipeline,
        reset_event_model_registry,
    )
    from app.ai.acoustic.severity import DeterministicSeverityEstimator
    from app.ai.speech.inference import (
        _prediction_certainty,
        get_or_load_model,
        map_intensity,
        reset_model_registry,
        select_tone,
    )
    from app.ai.speech.mapping import load_label_mapping
    from app.ai.technical.overlap import SignalBasedOverlapDetector
    from app.ai.technical.quality import AudioQualityAnalyzer
    from app.ai.technical.silence import LongSilenceDetector
    from app.audio.analysis.factory import build_vad
    from app.audio.analysis.features import FeatureExtractor
    from app.config.settings import get_settings
    from app.prediction.builder import PredictionBuilder
    from app.prediction.confidence import WeightedConfidenceEstimator
    from app.prediction.schemas import AnalysisResult
    from app.prediction.validator import PredictionValidator
    from app.ai.acoustic.schemas import AcousticResult
    from app.ai.speech.schemas import SpeechResult
    from app.ai.technical.schemas import TechnicalResult
    from app.shared.domain.enums import NoiseSeverity, NoiseType

    settings = get_settings()
    reset_model_registry()
    reset_event_model_registry()

    intermediates_dir = output_dir / "intermediates"
    intermediates_dir.mkdir(parents=True, exist_ok=True)

    vad = build_vad(settings.analysis)
    features_extractor = FeatureExtractor()
    speech_model = get_or_load_model(settings.speech)
    speech_model.load()
    noise_detector = SignalBasedNoiseDetector(settings.acoustic)
    noise_fallback = HeuristicNoiseClassifier(settings.acoustic)
    noise_classifier = HuggingFaceAudioEventClassifier(
        settings.acoustic, fallback=noise_fallback
    )
    severity = DeterministicSeverityEstimator(settings.acoustic)
    silence = LongSilenceDetector(settings.technical)
    quality = AudioQualityAnalyzer(settings.technical)
    overlap = SignalBasedOverlapDetector(settings.technical)
    confidence = WeightedConfidenceEstimator(settings.prediction)
    builder = PredictionBuilder()
    validator = PredictionValidator(
        confidence_rounding=settings.prediction.confidence_rounding
    )

    ground_truth = _load_optional_ground_truth(ground_truth_path)
    audio_files = _iter_audio(audio_dir)
    if not audio_files:
        raise SystemExit(f"No audio files under {audio_dir}")

    # Force event pipeline load once (logs model readiness).
    try:
        _get_or_load_event_pipeline(
            settings.acoustic.event_model_name, settings.acoustic.event_device
        )
    except Exception as exc:
        print(f"WARN: AST model load failed, heuristic fallback only: {exc}")

    records: list[dict[str, Any]] = []
    certainty_scores: list[float] = []
    noise_scores: list[float] = []
    overlap_scores: list[float] = []
    quality_scores: list[float] = []
    snr_values: list[float] = []
    speech_ratios: list[float] = []
    observed_ser_labels: dict[str, int] = {}
    observed_ast_labels: dict[str, int] = {}
    speech_confidences: list[float] = []
    technical_confidences: list[float] = []
    acoustic_confidences: list[float] = []

    mapping = load_label_mapping(settings.speech.label_mapping_path)

    for path in audio_files:
        audio_id = path.stem
        print(f"\n=== Calibrating {path.name} ===")
        waveform, sample_rate = _load_and_resample(
            path, settings.speech.expected_sample_rate
        )

        # --- Analysis features / VAD ---
        vad_result = vad.detect(waveform, sample_rate)
        features = features_extractor.extract(waveform, sample_rate, vad=vad_result)
        analysis_stage = {
            "sample_rate": sample_rate,
            "duration": features.duration,
            "snr_estimate": features.snr_estimate,
            "dynamic_range": features.dynamic_range,
            "peak_amplitude": features.peak_amplitude,
            "zero_crossing_rate": features.zero_crossing_rate,
            "spectral_centroid": features.spectral_centroid,
            "spectral_bandwidth": features.spectral_bandwidth,
            "speech_ratio": vad_result.speech_ratio,
            "largest_silence": vad_result.largest_silence,
            "speech_segments": len(vad_result.speech_segments),
        }
        if features.snr_estimate is not None:
            snr_values.append(float(features.snr_estimate))
        speech_ratios.append(float(vad_result.speech_ratio))

        # --- Speech ---
        prediction = speech_model.predict(waveform, sample_rate)
        scores = [
            {"label": s.label, "probability": round(float(s.probability), 6)}
            for s in sorted(prediction.scores, key=lambda x: -x.probability)
        ]
        top5 = scores[:5]
        probs = [float(s.probability) for s in prediction.scores]
        ent = _entropy(probs)
        mar = _margin(probs)
        certainty = _prediction_certainty(prediction, settings.speech)
        tone, tone_probs = select_tone(prediction, settings.speech)
        intensity = map_intensity(prediction, settings.speech)
        for s in prediction.scores:
            observed_ser_labels[s.label.lower()] = (
                observed_ser_labels.get(s.label.lower(), 0) + 1
            )
        certainty_scores.append(certainty)
        speech_stage = {
            "model": settings.speech.model_name,
            "top5": top5,
            "entropy": round(ent, 6),
            "margin": round(mar, 6),
            "certainty": round(certainty, 6),
            "mapped_tone": tone.value,
            "mapped_intensity": intensity.value,
            "tone_probabilities": tone_probs,
            "raw_top_label": prediction.top.label,
            "raw_top_probability": round(float(prediction.top.probability), 6),
            "unmapped_labels": [
                s.label
                for s in prediction.scores
                if s.label.strip().lower() not in mapping
            ],
        }
        print(
            f"  speech: {tone.value}/{intensity.value} "
            f"top={prediction.top.label}@{prediction.top.probability:.3f} "
            f"margin={mar:.3f} entropy={ent:.3f}"
        )

        # --- Noise detection ---
        present, noise_score, noise_details = noise_detector.detect(features, vad_result)
        noise_scores.append(float(noise_score))
        noise_detection_stage = {
            "present": present,
            "score": noise_score,
            "threshold": settings.acoustic.noise_presence_score_threshold,
            "details": noise_details,
            "decision": "NOISE" if present else "CLEAR",
        }

        # --- Noise classification (AST top-10 always logged) ---
        ast_top10: list[dict[str, Any]] = []
        try:
            pipe = _get_or_load_event_pipeline(
                settings.acoustic.event_model_name, settings.acoustic.event_device
            )
            outputs = pipe(
                {"raw": waveform, "sampling_rate": sample_rate},
                top_k=10,
            )
            for item in outputs or []:
                label = str(item["label"])
                score = float(item["score"])
                ast_top10.append({"label": label, "probability": round(score, 6)})
                observed_ast_labels[label] = observed_ast_labels.get(label, 0) + 1
        except Exception as exc:
            ast_top10 = [{"error": str(exc)}]

        if present:
            noise_classifier.bind_waveform(waveform, sample_rate)
            noise_type, classification_details = noise_classifier.classify(
                features, vad_result
            )
            sev, severity_details = severity.estimate(features, vad_result, noise_score)
        else:
            noise_type = NoiseType.NONE
            classification_details = {}
            sev = NoiseSeverity.NONE
            severity_details = {}

        noise_classification_stage = {
            "ast_top10": ast_top10,
            "mapped_type": noise_type.value,
            "mapped_severity": sev.value,
            "classification_details": classification_details,
            "severity_details": severity_details,
        }
        print(
            f"  noise: present={present} score={noise_score:.3f} "
            f"type={noise_type.value}/{sev.value}"
        )

        # --- Overlap ---
        overlap_present, overlap_score, overlap_details = overlap.detect(
            features, vad_result
        )
        overlap_scores.append(float(overlap_score))
        overlap_stage = {
            "present": overlap_present,
            "score": overlap_score,
            "threshold": settings.technical.overlap_threshold,
            "speech_density": overlap_details.get("speech_density"),
            "bandwidth_score": overlap_details.get("bandwidth_score"),
            "centroid_spread_score": overlap_details.get("centroid_spread_score"),
            "zcr_score": overlap_details.get("zcr_score"),
            "details": overlap_details,
        }
        print(f"  overlap: present={overlap_present} score={overlap_score:.3f}")

        # --- Quality ---
        long_silence_present, silence_details = silence.detect(vad_result)
        audio_quality, breakdown, quality_score = quality.score(features, vad_result)
        quality_scores.append(float(quality_score))
        silence_ratio = 1.0 - float(vad_result.speech_ratio)
        quality_stage = {
            "audio_quality": audio_quality.value,
            "quality_score": quality_score,
            "snr": features.snr_estimate,
            "dynamic_range": features.dynamic_range,
            "speech_ratio": vad_result.speech_ratio,
            "silence_ratio": silence_ratio,
            "peak_amplitude": features.peak_amplitude,
            "clipping_likely": bool(features.peak_amplitude >= 0.99),
            "penalties": breakdown.model_dump(),
            "long_silence_present": long_silence_present,
            "silence_details": silence_details,
            "thresholds": {
                "clear": settings.technical.clear_threshold,
                "slightly_impaired": settings.technical.slightly_impaired_threshold,
                "snr_good_db": settings.technical.snr_good_db,
                "snr_ok_db": settings.technical.snr_ok_db,
            },
        }
        print(f"  quality: {audio_quality.value} score={quality_score:.2f}")

        # --- Assemble prediction + confidence ---
        speech_result = SpeechResult(
            audio_id=audio_id,
            batch_id="calibration",
            emotional_tone=tone,
            emotional_intensity=intensity,
            top_probability=round(float(prediction.top.probability), 6),
            tone_probabilities=tone_probs,
            model_name=settings.speech.model_name,
            raw_label=prediction.top.label,
        )
        technical_result = TechnicalResult(
            audio_id=audio_id,
            batch_id="calibration",
            audio_quality=audio_quality,
            speaker_overlap_present=overlap_present,
            long_silence_present=long_silence_present,
            quality_score=quality_score,
            quality_breakdown=breakdown,
            overlap_score=overlap_score,
            overlap_details=overlap_details,
            silence_details=silence_details,
        )
        acoustic_result = AcousticResult(
            audio_id=audio_id,
            batch_id="calibration",
            background_noise_present=present,
            background_noise_type=noise_type,
            background_noise_severity=sev,
            noise_score=noise_score,
            noise_details=noise_details,
            classification_details=classification_details,
            severity_details=severity_details,
        )
        analysis = AnalysisResult(
            technical=technical_result,
            acoustic=acoustic_result,
            speech=speech_result,
        )
        conf = confidence.estimate(analysis)
        speech_confidences.append(conf.speech)
        technical_confidences.append(conf.technical)
        acoustic_confidences.append(conf.acoustic)
        assessment = validator.validate(builder.build(analysis, conf))
        prediction_stage = assessment.to_public_dict()
        confidence_stage = conf.to_dict()
        print(f"  confidence: overall={conf.overall} speech={conf.speech}")

        mapped = {
            "emotional_tone": prediction_stage["emotional_tone"],
            "emotional_intensity": prediction_stage["emotional_intensity"],
            "background_noise_present": prediction_stage["background_noise_present"],
            "background_noise_type": prediction_stage["background_noise_type"],
            "background_noise_severity": prediction_stage["background_noise_severity"],
            "audio_quality": prediction_stage["audio_quality"],
            "speaker_overlap_present": prediction_stage["speaker_overlap_present"],
            "long_silence_present": prediction_stage["long_silence_present"],
            "confidence": prediction_stage["confidence"],
        }
        comparison = None
        if audio_id in ground_truth:
            comparison = _compare_fields(mapped, ground_truth[audio_id])

        record = {
            "audio_id": audio_id,
            "path": str(path),
            "analysis": analysis_stage,
            "speech": speech_stage,
            "noise_detection": noise_detection_stage,
            "noise_classification": noise_classification_stage,
            "overlap": overlap_stage,
            "quality": quality_stage,
            "confidence": confidence_stage,
            "prediction": prediction_stage,
            "per_field_comparison": comparison,
        }
        records.append(record)
        (intermediates_dir / f"{audio_id}.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )

    # ---------- Calibration proposals (generic, distribution-based) ----------
    proposals: dict[str, Any] = {"speech": {}, "noise": {}, "quality": {}, "overlap": {}, "confidence": {}}

    # Speech intensity thresholds from certainty distribution.
    if certainty_scores:
        p40 = _percentile(certainty_scores, 0.40) or 0.45
        p75 = _percentile(certainty_scores, 0.75) or 0.70
        # Keep ordering and sane bounds.
        med = max(0.35, min(0.55, round(p40, 2)))
        high = max(med + 0.1, min(0.85, round(p75, 2)))
        proposals["speech"]["intensity_medium_probability"] = med
        proposals["speech"]["intensity_high_probability"] = high
        proposals["speech"]["observed_certainty"] = {
            "min": round(min(certainty_scores), 4),
            "p40": round(p40, 4),
            "p75": round(p75, 4),
            "max": round(max(certainty_scores), 4),
        }
        unmapped = sorted(
            {
                label
                for rec in records
                for label in rec["speech"]["unmapped_labels"]
            }
        )
        proposals["speech"]["unmapped_labels_observed"] = unmapped
        # Suggest identity-safe SUPERB aliases already covered; only note gaps.
        proposals["speech"]["mapping_action"] = (
            "extend speech_label_mapping.json for unmapped labels"
            if unmapped
            else "mapping covers all observed labels"
        )

    # Noise detection threshold: place between clear/noisy score clusters when possible.
    if noise_scores:
        p30 = _percentile(noise_scores, 0.30) or 0.35
        p60 = _percentile(noise_scores, 0.60) or 0.5
        # Slightly above lower cluster center to avoid false positives on clean speech.
        tuned = round(max(0.30, min(0.55, (p30 + p60) / 2)), 2)
        proposals["noise"]["noise_presence_score_threshold"] = tuned
        proposals["noise"]["observed_noise_scores"] = {
            "min": round(min(noise_scores), 4),
            "p30": round(p30, 4),
            "p60": round(p60, 4),
            "max": round(max(noise_scores), 4),
        }
        # Recommend mapping additions for frequent AST labels not in mapping file.
        from app.ai.acoustic.mapping import load_noise_label_mapping

        existing = load_noise_label_mapping(settings.acoustic.event_label_mapping_path)
        missing_ast = sorted(
            label
            for label, count in observed_ast_labels.items()
            if label.lower() not in existing and count >= 1
        )
        proposals["noise"]["ast_labels_missing_from_mapping"] = missing_ast[:40]
        proposals["noise"]["ast_label_frequency"] = dict(
            sorted(observed_ast_labels.items(), key=lambda kv: -kv[1])[:30]
        )

    # Quality thresholds from observed SNR / quality score distribution.
    if snr_values and quality_scores:
        snr_p50 = _percentile(snr_values, 0.50) or 20.0
        snr_p25 = _percentile(snr_values, 0.25) or 12.0
        q_p25 = _percentile(quality_scores, 0.25) or 65.0
        q_p60 = _percentile(quality_scores, 0.60) or 85.0
        proposals["quality"]["snr_good_db"] = round(max(18.0, min(30.0, snr_p50 + 2)), 1)
        proposals["quality"]["snr_ok_db"] = round(max(8.0, min(18.0, snr_p25)), 1)
        proposals["quality"]["clear_threshold"] = round(max(75.0, min(92.0, q_p60)), 1)
        proposals["quality"]["slightly_impaired_threshold"] = round(
            max(50.0, min(80.0, q_p25)), 1
        )
        proposals["quality"]["observed"] = {
            "snr_min": round(min(snr_values), 3),
            "snr_p50": round(snr_p50, 3),
            "quality_min": round(min(quality_scores), 3),
            "quality_p60": round(q_p60, 3),
        }

    # Overlap threshold: above typical mono-speaker density scores.
    if overlap_scores:
        p70 = _percentile(overlap_scores, 0.70) or 0.55
        tuned_overlap = round(max(0.45, min(0.75, p70 + 0.05)), 2)
        proposals["overlap"]["overlap_threshold"] = tuned_overlap
        proposals["overlap"]["observed_overlap_scores"] = {
            "min": round(min(overlap_scores), 4),
            "p50": round(_percentile(overlap_scores, 0.50) or 0.0, 4),
            "p70": round(p70, 4),
            "max": round(max(overlap_scores), 4),
        }

    # Confidence weights: emphasize the more discriminative component.
    if speech_confidences and technical_confidences and acoustic_confidences:
        speech_var = float(np.var(speech_confidences))
        tech_var = float(np.var(technical_confidences))
        ac_var = float(np.var(acoustic_confidences))
        total_var = speech_var + tech_var + ac_var
        if total_var > 1e-9:
            # Blend variance-proportional weights with speech-dominant prior.
            raw = {
                "speech": 0.45 + 0.35 * (speech_var / total_var),
                "technical": 0.15 + 0.25 * (tech_var / total_var),
                "acoustic": 0.15 + 0.25 * (ac_var / total_var),
            }
        else:
            raw = {"speech": 0.6, "technical": 0.2, "acoustic": 0.2}
        s = sum(raw.values())
        weights = {k: round(v / s, 3) for k, v in raw.items()}
        # Clamp speech dominance without exceeding 1.0 total.
        if weights["speech"] < 0.5:
            weights = {"speech": 0.55, "technical": 0.25, "acoustic": 0.20}
        # Renormalize
        s2 = sum(weights.values())
        weights = {k: round(v / s2, 3) for k, v in weights.items()}
        # Fix float drift
        drift = round(1.0 - sum(weights.values()), 3)
        weights["speech"] = round(weights["speech"] + drift, 3)
        proposals["confidence"]["confidence_weights"] = weights
        proposals["confidence"]["component_variance"] = {
            "speech": round(speech_var, 6),
            "technical": round(tech_var, 6),
            "acoustic": round(ac_var, 6),
        }

    applied: dict[str, Any] = {}
    if apply:
        applied = _apply_proposals(proposals, settings, REPO_ROOT)

    field_accuracies: dict[str, Any] = {}
    compared_records = [r for r in records if r.get("per_field_comparison")]
    if compared_records:
        field_hits: dict[str, list[bool]] = {}
        for rec in compared_records:
            for field, detail in rec["per_field_comparison"]["fields"].items():
                field_hits.setdefault(field, []).append(bool(detail["match"]))
        field_accuracies = {
            field: round(sum(vals) / len(vals), 4) for field, vals in field_hits.items()
        }
        overall_acc = round(
            sum(r["per_field_comparison"]["matched"] for r in compared_records)
            / max(1, sum(r["per_field_comparison"]["compared"] for r in compared_records)),
            4,
        )
    else:
        overall_acc = None

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audio_dir": str(audio_dir),
        "file_count": len(records),
        "models": {
            "speech": settings.speech.model_name,
            "noise_event": settings.acoustic.event_model_name,
            "noise_detector": "SignalBasedNoiseDetector",
            "overlap": "SignalBasedOverlapDetector",
            "quality": "AudioQualityAnalyzer",
        },
        "thresholds_before": {
            "speech_intensity_medium": settings.speech.intensity_medium_probability,
            "speech_intensity_high": settings.speech.intensity_high_probability,
            "noise_presence": settings.acoustic.noise_presence_score_threshold,
            "overlap": settings.technical.overlap_threshold,
            "quality_clear": settings.technical.clear_threshold,
            "quality_slightly_impaired": settings.technical.slightly_impaired_threshold,
            "snr_good_db": settings.technical.snr_good_db,
            "snr_ok_db": settings.technical.snr_ok_db,
            "confidence_weights": settings.prediction.confidence_weights,
        },
        "calibration_proposals": proposals,
        "applied": applied,
        "observed_ser_labels": observed_ser_labels,
        "evaluation_accuracy": {
            "overall": overall_acc,
            "per_field": field_accuracies,
            "ground_truth_provided": bool(ground_truth),
            "files_with_ground_truth": len(compared_records),
        },
        "files": records,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "calibration_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    # Also mirror to repo root for convenience.
    (REPO_ROOT / "calibration_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(f"\nWrote {report_path}")
    print(f"Wrote {REPO_ROOT / 'calibration_report.json'}")
    return report


def _apply_proposals(
    proposals: dict[str, Any], settings: Any, repo_root: Path
) -> dict[str, Any]:
    """Persist mapping/threshold calibrations into config files and .env."""
    applied: dict[str, Any] = {}

    # --- Speech mapping: add missing SUPERB-style aliases if observed unmapped ---
    speech_path = repo_root / "config" / "speech_label_mapping.json"
    speech_map = json.loads(speech_path.read_text(encoding="utf-8"))
    # Generic safe aliases commonly emitted by HF SER checkpoints.
    generic_aliases = {
        "label_0": {"emotion": "NEUTRAL", "weight": 0.5},
        "other": {"emotion": "NEUTRAL", "weight": 0.4},
        "unknown": {"emotion": "NEUTRAL", "weight": 0.4},
    }
    unmapped = proposals.get("speech", {}).get("unmapped_labels_observed", [])
    for label in unmapped:
        key = label.strip().lower()
        if key in speech_map:
            continue
        if key in generic_aliases:
            speech_map[key] = generic_aliases[key]
        # Do not invent emotion for unknown domain labels.
    speech_path.write_text(json.dumps(speech_map, indent=2) + "\n", encoding="utf-8")
    applied["speech_label_mapping"] = str(speech_path)

    # --- Noise mapping: add high-frequency AST speech-adjacent / mechanical labels ---
    noise_path = repo_root / "config" / "noise_label_mapping.json"
    noise_map = json.loads(noise_path.read_text(encoding="utf-8"))
    # Generic AudioSet → platform mappings for common call-center events.
    generic_noise = {
        "Speech": {"type": "OFFICE_CHATTER", "weight": 0.35},
        "Male speech, man speaking": {"type": "OFFICE_CHATTER", "weight": 0.45},
        "Female speech, woman speaking": {"type": "OFFICE_CHATTER", "weight": 0.45},
        "Child speech, kid speaking": {"type": "OFFICE_CHATTER", "weight": 0.45},
        "Conversation": {"type": "OFFICE_CHATTER", "weight": 1.0},
        "Narration, monologue": {"type": "OFFICE_CHATTER", "weight": 0.7},
        "Babbling": {"type": "OFFICE_CHATTER", "weight": 0.8},
        "Whispering": {"type": "OFFICE_CHATTER", "weight": 0.6},
        "Laughter": {"type": "OTHER", "weight": 0.5},
        "Crying, sobbing": {"type": "OTHER", "weight": 0.5},
        "Applause": {"type": "OTHER", "weight": 0.4},
        "Clapping": {"type": "OTHER", "weight": 0.4},
        "Silence": {"type": "NONE", "weight": 1.0},
        "Inside, small room": {"type": "OTHER", "weight": 0.3},
        "Inside, large room or hall": {"type": "OTHER", "weight": 0.3},
        "Outside, urban or manmade": {"type": "TRAFFIC", "weight": 0.45},
        "Railway": {"type": "TRAFFIC", "weight": 0.8},
        "Subway, metro, underground": {"type": "TRAFFIC", "weight": 0.85},
        "Aircraft": {"type": "TRAFFIC", "weight": 0.7},
        "Helicopter": {"type": "TRAFFIC", "weight": 0.7},
        "Emergency vehicle": {"type": "TRAFFIC", "weight": 0.75},
        "Siren": {"type": "TRAFFIC", "weight": 0.7},
        "Alarm": {"type": "MECHANICAL", "weight": 0.55},
        "Telephone": {"type": "MECHANICAL", "weight": 0.6},
        "Telephone bell ringing": {"type": "MECHANICAL", "weight": 0.7},
        "Dial tone": {"type": "STATIC", "weight": 0.8},
        "Busy signal": {"type": "STATIC", "weight": 0.8},
        "White noise": {"type": "STATIC", "weight": 1.0},
        "Noise": {"type": "STATIC", "weight": 0.7},
        "Environmental noise": {"type": "OTHER", "weight": 0.55},
        "Background noise": {"type": "OTHER", "weight": 0.55},
        "Rustling leaves": {"type": "WIND", "weight": 0.5},
        "Rain": {"type": "WIND", "weight": 0.55},
        "Thunder": {"type": "WIND", "weight": 0.5},
        "Television": {"type": "TV", "weight": 1.0},
        "Radio": {"type": "TV", "weight": 0.8},
    }
    missing = proposals.get("noise", {}).get("ast_labels_missing_from_mapping", [])
    for label in missing:
        if label in noise_map:
            continue
        if label in generic_noise:
            noise_map[label] = generic_noise[label]
    # Always ensure dial-tone / telephone aliases exist for call recordings.
    for label, entry in generic_noise.items():
        noise_map.setdefault(label, entry)
    noise_path.write_text(json.dumps(noise_map, indent=2) + "\n", encoding="utf-8")
    applied["noise_label_mapping"] = str(noise_path)

    # --- Thresholds into .env ---
    env_path = repo_root / ".env"
    env_text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""

    def upsert(text: str, key: str, value: str) -> str:
        lines = text.splitlines()
        out: list[str] = []
        found = False
        for line in lines:
            if line.startswith(f"{key}="):
                out.append(f"{key}={value}")
                found = True
            else:
                out.append(line)
        if not found:
            out.append(f"{key}={value}")
        return "\n".join(out) + "\n"

    updates: dict[str, str] = {}
    sp = proposals.get("speech", {})
    if "intensity_medium_probability" in sp:
        updates["SPEECH_INTENSITY_MEDIUM_PROBABILITY"] = str(
            sp["intensity_medium_probability"]
        )
    if "intensity_high_probability" in sp:
        updates["SPEECH_INTENSITY_HIGH_PROBABILITY"] = str(
            sp["intensity_high_probability"]
        )
    nz = proposals.get("noise", {})
    if "noise_presence_score_threshold" in nz:
        updates["ACOUSTIC_NOISE_PRESENCE_SCORE_THRESHOLD"] = str(
            nz["noise_presence_score_threshold"]
        )
    ql = proposals.get("quality", {})
    for key, env_key in [
        ("snr_good_db", "TECHNICAL_SNR_GOOD_DB"),
        ("snr_ok_db", "TECHNICAL_SNR_OK_DB"),
        ("clear_threshold", "TECHNICAL_CLEAR_THRESHOLD"),
        ("slightly_impaired_threshold", "TECHNICAL_SLIGHTLY_IMPAIRED_THRESHOLD"),
    ]:
        if key in ql:
            updates[env_key] = str(ql[key])
    ov = proposals.get("overlap", {})
    if "overlap_threshold" in ov:
        updates["TECHNICAL_OVERLAP_THRESHOLD"] = str(ov["overlap_threshold"])
    cf = proposals.get("confidence", {})
    if "confidence_weights" in cf:
        updates["PREDICTION_CONFIDENCE_WEIGHTS"] = json.dumps(
            cf["confidence_weights"], separators=(",", ":")
        )

    for key, value in updates.items():
        env_text = upsert(env_text, key, value)
    env_path.write_text(env_text, encoding="utf-8")
    applied["env_updates"] = updates

    # Mirror critical defaults in settings.py source defaults via .env only
    # (architecture freeze — settings code defaults already sensible).
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate inference mappings/thresholds")
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "calibration",
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=None,
        help="Optional JSON ground truth (never invented)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write calibrated mappings/thresholds into config/.env",
    )
    args = parser.parse_args()
    run_calibration(
        audio_dir=args.audio_dir,
        output_dir=args.output_dir,
        ground_truth_path=args.ground_truth,
        apply=args.apply,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
