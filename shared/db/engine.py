"""Async SQLAlchemy engine factory with production-grade pool settings.

Pool sizing rationale: at 100M claims/year we need head-room without
exhausting Postgres connections. pool_size=20 per process + max_overflow=10
gives 30 peak per worker; pool_pre_ping eliminates stale-connection errors
after idle cycles; pool_recycle=1800 (30 min) avoids Postgres's idle-kill
policies and NAT timeouts common in AKS clusters.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from shared.config import get_settings

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Return a process-wide singleton AsyncEngine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=1800,
            future=True,
        )
    return _engine


async def dispose_engine() -> None:
    """Dispose the engine (closes all pooled connections). Call on shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
