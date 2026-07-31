"""Database connectivity helpers for health checks."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def check_database_connection(engine: AsyncEngine) -> bool:
    """Return True if the database accepts a simple SELECT 1."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
