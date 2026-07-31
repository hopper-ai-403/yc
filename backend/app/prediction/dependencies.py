"""Prediction feature FastAPI dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import PredictionSettings, Settings, get_settings
from app.dependencies import get_db_session, get_storage
from app.prediction.factory import (
    build_prediction_export_service,
    build_prediction_service,
)
from app.prediction.export import PredictionExportService
from app.prediction.service import PredictionService
from app.shared.storage.provider import StorageProvider


def get_prediction_settings(settings: Settings = Depends(get_settings)) -> PredictionSettings:
    return settings.prediction


def get_prediction_service(
    session: AsyncSession = Depends(get_db_session),
    storage: StorageProvider = Depends(get_storage),
    settings: PredictionSettings = Depends(get_prediction_settings),
) -> PredictionService:
    return build_prediction_service(session, storage=storage, settings=settings)


def get_prediction_export_service(
    session: AsyncSession = Depends(get_db_session),
) -> PredictionExportService:
    return build_prediction_export_service(session)
