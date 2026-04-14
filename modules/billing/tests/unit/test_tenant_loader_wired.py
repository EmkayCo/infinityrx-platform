"""Verifies billing's session factory wires the shared tenant loader.

P1 Item 4 of the emergency wiring pass. Billing previously had its own
sync sessionmaker with no call to ``install_tenant_loader``. Any future
billing model that inherits ``TenantScopedMixin`` would silently fall
through without the loader being attached.
"""

from __future__ import annotations

from sqlalchemy.orm import Session


def test_tenant_loader_installed_on_session_class() -> None:
    # Import triggers the install_tenant_loader() call at module load time.
    from src.db import session as billing_session  # noqa: F401

    # Once installed, the session class carries the de-dupe flag.
    assert getattr(
        Session, "_infinityrx_tenant_loader_installed", False
    ), "billing session factory did not install the shared tenant loader"


def test_install_is_idempotent() -> None:
    from shared.db.tenant_context import install_tenant_loader
    from src.db.session import _SessionFactory

    # Calling it again must not raise and must not double-attach.
    install_tenant_loader(_SessionFactory)
    install_tenant_loader(_SessionFactory)
    assert getattr(Session, "_infinityrx_tenant_loader_installed", False) is True
