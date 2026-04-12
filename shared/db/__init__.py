"""Async database layer: engine, session, tenant-scoped session, ORM base."""

from shared.db.base import Base, metadata
from shared.db.engine import dispose_engine, get_engine
from shared.db.session import get_session, get_sessionmaker, transaction
from shared.db.tenant_context import (
    TENANT_EXEMPT_ATTR,
    MissingTenantContextError,
    clear_tenant_context,
    current_tenant_id,
    set_tenant_context,
    tenant_exempt,
)

__all__ = [
    "Base",
    "metadata",
    "get_engine",
    "dispose_engine",
    "get_session",
    "get_sessionmaker",
    "transaction",
    "current_tenant_id",
    "set_tenant_context",
    "clear_tenant_context",
    "tenant_exempt",
    "TENANT_EXEMPT_ATTR",
    "MissingTenantContextError",
]
