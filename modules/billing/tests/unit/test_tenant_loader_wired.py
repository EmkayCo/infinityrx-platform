"""Verifies billing's session factory wires the shared tenant loader.

P1 Item 4 of the emergency wiring pass. Billing previously had its own
sync sessionmaker with no call to ``install_tenant_loader``. Any future
billing model that inherits ``TenantScopedMixin`` would silently fall
through without the loader being attached.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.db.session import set_engine, _get_session_factory


def _make_test_engine():
    """Create a minimal in-memory SQLite engine for session-factory tests."""
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_tenant_loader_installed_on_session_class() -> None:
    # Wire a test engine so _get_session_factory() can construct the sessionmaker.
    set_engine(_make_test_engine())
    _get_session_factory()  # triggers install_tenant_loader()

    # Once installed, the session class carries the de-dupe flag.
    assert getattr(
        Session, "_infinityrx_tenant_loader_installed", False
    ), "billing session factory did not install the shared tenant loader"


def test_install_is_idempotent() -> None:
    from shared.db.tenant_context import install_tenant_loader

    # Ensure factory is initialised (may already be from prior test).
    set_engine(_make_test_engine())
    factory = _get_session_factory()

    # Calling again must not raise and must not double-attach.
    install_tenant_loader(factory)
    install_tenant_loader(factory)
    assert getattr(Session, "_infinityrx_tenant_loader_installed", False) is True
