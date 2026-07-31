"""Evaluation feature module.

Purpose: End-to-end batch execution workflow (run → monitor → export → metrics).
Responsibilities: Batch run orchestration, status, metrics persistence,
    export artifact management.
Dependencies: jobs (orchestration), prediction (exports), audio repositories,
    StorageProvider.
Extension points: Additional export formats and metric dimensions.
"""

from app.evaluation.service import EvaluationService

__all__ = ["EvaluationService"]
