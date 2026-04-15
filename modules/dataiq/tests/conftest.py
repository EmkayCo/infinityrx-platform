"""Shared test fixtures for DataIQ module tests."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Ensure the module src is importable as `src.*`
_src_path = str(Path(__file__).parent.parent / "src")
if _src_path not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))


def make_mock_db_session() -> AsyncMock:
    """Return a mock async DB session that returns empty result sets.

    This allows router tests to run without a live database connection.
    The mock is configured to return objects that satisfy SQLAlchemy's
    AsyncResult protocol used in `await session.execute(...)`.
    """
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    mock_result.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    return mock_session


async def _mock_get_session(mock_session: AsyncMock):
    """Async generator that yields the mock session (matches get_session signature)."""
    yield mock_session
