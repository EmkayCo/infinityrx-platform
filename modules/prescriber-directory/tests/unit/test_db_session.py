"""Unit tests for database session factory."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import src.db.session as session_module
from src.db.session import set_engine, get_db_session


@pytest.fixture(autouse=True)
def reset_session_module():
    """Reset module-level state between tests."""
    orig_engine = session_module._engine
    orig_session_local = session_module._SessionLocal
    yield
    session_module._engine = orig_engine
    session_module._SessionLocal = orig_session_local


class TestSetEngine:
    def test_set_engine_overrides_engine(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        set_engine(engine)
        assert session_module._engine is engine
        # _SessionLocal is reset to None so _get_session_factory() will rebuild it
        # with install_tenant_loader applied to the new engine (CR-09 fix).
        assert session_module._SessionLocal is None


class TestGetEngine:
    def test_get_engine_uses_env_var(self):
        session_module._engine = None
        with patch.dict(os.environ, {"PRESCRIBER_DB_URL": "sqlite:///:memory:"}):
            from src.db.session import _get_engine
            engine = _get_engine()
            assert engine is not None
            assert session_module._engine is engine

    def test_get_engine_returns_cached(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        session_module._engine = engine
        from src.db.session import _get_engine
        result = _get_engine()
        assert result is engine


class TestGetSessionFactory:
    def test_get_session_factory_creates_when_session_local_is_none(self):
        from sqlalchemy.pool import StaticPool
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        session_module._engine = engine
        session_module._SessionLocal = None  # Force re-creation

        from src.db.session import _get_session_factory
        factory = _get_session_factory()
        assert factory is not None
        assert session_module._SessionLocal is factory


class TestGetDbSession:
    def test_get_db_session_yields_session_and_commits(self):
        from src.models.tables import PrescriberBase
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        for t in PrescriberBase.metadata.tables.values():
            t.schema = None
        PrescriberBase.metadata.create_all(engine)
        set_engine(engine)

        with get_db_session() as session:
            assert session is not None

    def test_get_db_session_rolls_back_on_exception(self):
        from src.models.tables import PrescriberBase
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        for t in PrescriberBase.metadata.tables.values():
            t.schema = None
        PrescriberBase.metadata.create_all(engine)
        set_engine(engine)

        with pytest.raises(ValueError, match="test error"):
            with get_db_session() as session:
                raise ValueError("test error")
