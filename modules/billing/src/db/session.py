"""SQLAlchemy session factory for billing module.

Tenant isolation: this factory installs the shared tenant loader on the
sync ``Session`` class so that any model inheriting
:class:`TenantScopedMixin` is auto-filtered by the active tenant
contextvar. Billing's own models do not yet inherit the mixin — tracked
as a follow-up task — but wiring the loader here means the billing module
participates in platform-wide isolation the moment those models are
migrated.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from shared.db.tenant_context import install_tenant_loader

_DATABASE_URL = os.environ.get(
    "BILLING_DATABASE_URL",
    "postgresql+psycopg2://billing:billing@localhost:5432/infinityrx_billing",
)

_engine = create_engine(_DATABASE_URL, pool_pre_ping=True)
_SessionFactory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

# Wire the platform-wide tenant loader to the sync Session class. Safe
# to call every import — the loader de-dupes via a class attribute flag.
install_tenant_loader(_SessionFactory)


@contextmanager
def get_db_session() -> Generator[Session]:
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
