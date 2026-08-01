"""Celery async runtime helpers for worker tasks."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable, Coroutine
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.database.session import async_session_factory

T = TypeVar("T")

_worker_loop: asyncio.AbstractEventLoop | None = None


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    """Reuse one event loop for the worker process.

    Celery solo/prefork tasks must not call ``asyncio.run()`` per task on
    Windows — that closes the loop and breaks cached Redis/SQLAlchemy clients.
    """
    global _worker_loop
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    return _worker_loop


def run_async(coro: Coroutine[object, object, T]) -> T:
    """Run an async coroutine from a sync Celery task."""
    loop = _get_worker_loop()
    return loop.run_until_complete(coro)


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
