"""Speech / silence segmentation derived from VAD timestamps."""

from __future__ import annotations

from app.audio.analysis.schemas import TimeSegment, VADResult


def build_vad_result(
    speech_segments: list[TimeSegment],
    *,
    total_duration: float,
) -> VADResult:
    """Compute silence segments and aggregate VAD statistics."""
    duration = max(0.0, total_duration)
    cleaned = _merge_segments(
        [
            TimeSegment(start=max(0.0, s.start), end=min(duration, s.end))
            for s in speech_segments
            if s.end > s.start
        ]
    )

    silence = _silence_from_speech(cleaned, duration)
    speech_duration = float(sum(seg.duration for seg in cleaned))
    speech_ratio = (speech_duration / duration) if duration > 0 else 0.0
    largest_silence = float(max((seg.duration for seg in silence), default=0.0))
    speech_start = cleaned[0].start if cleaned else None
    speech_end = cleaned[-1].end if cleaned else None

    return VADResult(
        speech_segments=cleaned,
        silence_segments=silence,
        speech_duration=round(speech_duration, 6),
        speech_ratio=round(min(1.0, max(0.0, speech_ratio)), 6),
        largest_silence=round(largest_silence, 6),
        speech_start=speech_start,
        speech_end=speech_end,
    )


def _merge_segments(segments: list[TimeSegment]) -> list[TimeSegment]:
    if not segments:
        return []
    ordered = sorted(segments, key=lambda s: s.start)
    merged: list[TimeSegment] = [ordered[0]]
    for segment in ordered[1:]:
        last = merged[-1]
        if segment.start <= last.end:
            merged[-1] = TimeSegment(start=last.start, end=max(last.end, segment.end))
        else:
            merged.append(segment)
    return merged


def _silence_from_speech(
    speech: list[TimeSegment],
    duration: float,
) -> list[TimeSegment]:
    if duration <= 0:
        return []
    if not speech:
        return [TimeSegment(start=0.0, end=duration)]

    silence: list[TimeSegment] = []
    cursor = 0.0
    for segment in speech:
        if segment.start > cursor:
            silence.append(TimeSegment(start=cursor, end=segment.start))
        cursor = max(cursor, segment.end)
    if cursor < duration:
        silence.append(TimeSegment(start=cursor, end=duration))
    return silence
