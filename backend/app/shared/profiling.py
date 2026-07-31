"""Pipeline stage profiling middleware.

Every pipeline stage records start_time, end_time, duration_ms, and status.
The profile is stored in per-audio timing metadata and in the internal
prediction metadata.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class PipelineProfiler:
    """Collect per-stage timing for one audio processing run."""

    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled
        self._stages: list[dict[str, Any]] = []
        self._started = time.perf_counter()

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        """Record one stage execution."""
        if not self._enabled:
            yield
            return

        start_time = datetime.now(timezone.utc)
        started = time.perf_counter()
        status = "ok"
        try:
            yield
        except Exception:
            status = "failed"
            raise
        finally:
            end_time = datetime.now(timezone.utc)
            duration_ms = (time.perf_counter() - started) * 1000.0
            self._stages.append(
                {
                    "stage": name,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "duration_ms": round(duration_ms, 2),
                    "status": status,
                }
            )
            logger.info(
                "pipeline_stage_profiled",
                stage=name,
                duration_ms=round(duration_ms, 2),
                status=status,
            )

    @property
    def stages(self) -> list[dict[str, Any]]:
        return list(self._stages)

    def total_duration_ms(self) -> float:
        return round((time.perf_counter() - self._started) * 1000.0, 2)

    def durations_ms(self) -> dict[str, float]:
        """Map of stage name → duration for persisted timing metadata."""
        return {
            f"{stage['stage']}_duration_ms": float(stage["duration_ms"])
            for stage in self._stages
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "stages": self.stages,
            "total_pipeline_duration_ms": self.total_duration_ms(),
        }


NULL_PROFILER = PipelineProfiler(enabled=False)
