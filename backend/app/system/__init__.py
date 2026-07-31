"""System operations module.

Purpose: Operational readiness (health aggregation, worker registry) and
    batch benchmarking.
Responsibilities: /system/metrics, /system/workers, /system/benchmark.
Dependencies: HealthService collaborators, JobProgressCache, BenchmarkRunner.
Extension points: Prometheus export, additional benchmark dimensions.
"""

from app.system.service import SystemService

__all__ = ["SystemService"]
