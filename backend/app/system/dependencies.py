"""System feature FastAPI dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_storage
from app.shared.storage.provider import StorageProvider
from app.system.factory import build_system_service
from app.system.service import SystemService


def get_system_service(
    session: AsyncSession = Depends(get_db_session),
    storage: StorageProvider = Depends(get_storage),
) -> SystemService:
    return build_system_service(session, storage=storage)
