"""Evaluation feature FastAPI dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_storage
from app.evaluation.factory import build_evaluation_service
from app.evaluation.service import EvaluationService
from app.shared.storage.provider import StorageProvider


def get_evaluation_service(
    session: AsyncSession = Depends(get_db_session),
    storage: StorageProvider = Depends(get_storage),
) -> EvaluationService:
    return build_evaluation_service(session, storage=storage)
