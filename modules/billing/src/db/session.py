"""SQLAlchemy session factory for billing module.

Tenant isolation: this factory installs the shared tenant loader on the
sync ``Session`` class so that any model inheriting
:class:`TenantScopedMixin` is auto-filtered by the active tenant
contextvar. Billing's own models do not yet inherit the mixin — tracked
as a follow-up task — but wiring the loader here means the billing module
participates in platform-wide isolation the moment those models are
migrated.

M-16: No hardcoded DB URL fallback. BILLING_DATABASE_URL must be set
in the environment. A clear RuntimeError is raised at first use if absent.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from shared.db.tenant_context import install_tenant_loader

_engine = None
_SessionFactory = None


def _get_engine():
    global _engine
    if _engine is None:
        db_url = os.environ.get("BILLING_DATABASE_URL")
        if not db_url:
            raise RuntimeError(
                "BILLING_DATABASE_URL environment variable is required but not set. "
                "Set it to a valid PostgreSQL connection string."
            )
        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def _get_session_factory() -> sessionmaker:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False)
        # Wire the platform-wide tenant loader to the sync Session class. Safe
        # to call every factory rebuild — the loader de-dupes via a class attribute flag.
        install_tenant_loader(_SessionFactory)
    return _SessionFactory


def set_engine(engine) -> None:
    """Override engine — used by tests. Resets factory so tenant loader is applied."""
    global _engine, _SessionFactory
    _engine = engine
    _SessionFactory = None  # force rebuild via _get_session_factory() on next call


@contextmanager
def get_db_session() -> Generator[Session]:
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
