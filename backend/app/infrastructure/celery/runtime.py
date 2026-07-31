"""Celery async runtime helpers for worker tasks."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable, Coroutine
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.database.session import async_session_factory

T = TypeVar("T")


def run_async(coro: Coroutine[object, object, T]) -> T:
    """Run an async coroutine from a sync Celery task."""
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(coro)


async def with_session(handler: Callable[[AsyncSession], Awaitable[T]]) -> T:
    """Open a short-lived DB session, commit on success, rollback on error."""
    factory = async_session_factory()
    async with factory() as session:
        try:
            result = await handler(session)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise
