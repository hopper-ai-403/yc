"""Signal feature extraction for shared analysis artifacts."""

from __future__ import annotations

import numpy as np

from app.audio.analysis.exceptions import FeatureExtractionException
from app.audio.analysis.schemas import SignalFeatures, TimeSegment, VADResult
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class FeatureExtractor:
    """Extract spectral / temporal features from a mono waveform."""

    def extract(
        self,
        waveform: np.ndarray,
        sample_rate: int,
        *,
        vad: VADResult | None = None,
    ) -> SignalFeatures:
        try:
            import librosa
        except ImportError as exc:  # pragma: no cover
            raise FeatureExtractionException(
                "librosa is required for feature extraction",
                details={"error": str(exc)},
            ) from exc

        if waveform.ndim != 1 or waveform.size == 0:
            raise FeatureExtractionException(
                "Feature extraction requires a non-empty mono waveform",
                details={"shape": list(np.shape(waveform))},
            )
        if sample_rate <= 0:
            raise FeatureExtractionException(
                "Invalid sample rate",
                details={"sample_rate": sample_rate},
            )

        try:
            duration = float(len(waveform) / sample_rate)
            rms_energy = float(np.sqrt(np.mean(np.square(waveform))))
            peak_amplitude = float(np.max(np.abs(waveform)))
            zcr = float(np.mean(librosa.feature.zero_crossing_rate(y=waveform)))
            centroid = float(
                np.mean(librosa.feature.spectral_centroid(y=waveform, sr=sample_rate))
            )
            bandwidth = float(
                np.mean(librosa.feature.spectral_bandwidth(y=waveform, sr=sample_rate))
            )
            rolloff = float(
                np.mean(librosa.feature.spectral_rolloff(y=waveform, sr=sample_rate))
            )
            mfcc = librosa.feature.mfcc(y=waveform, sr=sample_rate, n_mfcc=13)
            mfcc_means = [float(x) for x in np.mean(mfcc, axis=1)]

            pitch_f0 = self._estimate_pitch(waveform, sample_rate)
            tempo_estimate = self._estimate_tempo(waveform, sample_rate)

            peak_db = 20.0 * np.log10(max(peak_amplitude, 1e-12))
            rms_db = 20.0 * np.log10(max(rms_energy, 1e-12))
            dynamic_range = float(peak_db - rms_db)
            snr_estimate = self._estimate_snr(waveform, sample_rate, vad)

            features = SignalFeatures(
                duration=round(duration, 6),
                rms_energy=float(rms_energy),
                peak_amplitude=float(peak_amplitude),
                zero_crossing_rate=float(zcr),
                spectral_centroid=float(centroid),
                spectral_bandwidth=float(bandwidth),
                spectral_rolloff=float(rolloff),
                mfcc=mfcc_means,
                pitch_f0=pitch_f0,
                tempo_estimate=tempo_estimate,
                dynamic_range=float(dynamic_range),
                snr_estimate=snr_estimate,
                sample_rate=sample_rate,
            )
        except FeatureExtractionException:
            raise
        except Exception as exc:
            raise FeatureExtractionException(
                "Feature extraction failed",
                details={"error": str(exc)},
            ) from exc

        logger.info(
            "features_extracted",
            duration=features.duration,
            rms_energy=features.rms_energy,
            pitch_f0=features.pitch_f0,
            status="ok",
        )
        return features

    @staticmethod
    def _estimate_pitch(waveform: np.ndarray, sample_rate: int) -> float | None:
        try:
            import librosa

            f0 = librosa.yin(
                waveform,
                fmin=50,
                fmax=min(500, sample_rate // 2 - 1),
                sr=sample_rate,
            )
            finite = f0[np.isfinite(f0)]
            if finite.size == 0:
                return None
            return float(np.median(finite))
        except Exception:
            return None

    @staticmethod
    def _estimate_tempo(waveform: np.ndarray, sample_rate: int) -> float | None:
        try:
            import librosa

            tempo, _ = librosa.beat.beat_track(y=waveform, sr=sample_rate)
            if isinstance(tempo, np.ndarray):
                tempo_value = float(tempo[0]) if tempo.size else None
            else:
                tempo_value = float(tempo)
            return tempo_value
        except Exception:
            return None

    @staticmethod
    def _estimate_snr(
        waveform: np.ndarray,
        sample_rate: int,
        vad: VADResult | None,
    ) -> float | None:
        if vad is None or not vad.speech_segments:
            return None

        def _slice_energy(segments: list[TimeSegment]) -> float:
            energies: list[float] = []
            for segment in segments:
                start = int(segment.start * sample_rate)
                end = int(segment.end * sample_rate)
                chunk = waveform[start:end]
                if chunk.size:
                    energies.append(float(np.mean(np.square(chunk))))
            if not energies:
                return 0.0
            return float(np.mean(energies))

        speech_power = _slice_energy(list(vad.speech_segments))
        silence_power = _slice_energy(list(vad.silence_segments))
        if speech_power <= 0:
            return None
        noise = max(silence_power, 1e-12)
        return float(10.0 * np.log10(speech_power / noise))
