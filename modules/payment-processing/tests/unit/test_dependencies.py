"""Unit tests for FastAPI dependency functions."""
from __future__ import annotations

from src.api.dependencies import get_current_user, get_db


class TestGetDb:
    def test_get_db_yields_session(self):
        gen = get_db()
        session = next(gen)
        assert session is not None
        try:
            next(gen)
        except StopIteration:
            pass


class TestGetCurrentUser:
    def test_get_current_user_returns_user(self):
        user = get_current_user()
        assert user is not None
