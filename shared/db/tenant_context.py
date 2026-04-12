"""Tenant isolation at the ORM session layer.

The platform stores dozens of tenants' PHI in a single database. A single
missed ``WHERE tenant_id = :tid`` on any query could cross-contaminate
tenants — a HIPAA breach. We refuse to trust developers to remember the
filter on every query. Instead we install a SQLAlchemy ``with_loader_criteria``
at session-factory creation time that pins every SELECT/UPDATE/DELETE to the
current tenant context, transparently.

Mechanism
---------
1. A :class:`contextvars.ContextVar` holds the active tenant UUID for the
   current request / task. Middleware sets it from the JWT before the route
   runs and clears it after (even on exceptions).
2. :func:`install_tenant_loader` registers a ``do_orm_execute`` event on the
   session that calls :func:`sqlalchemy.orm.with_loader_criteria` with a
   lambda that compares ``Model.tenant_id`` to the contextvar's value.
3. Any ORM model inheriting from :class:`TenantScopedMixin` is filtered.
   Models without ``tenant_id`` (e.g. ``core.permissions``) are untouched.
4. A query may opt out by setting ``execution_options(tenant_exempt=True)``,
   but only if the request has been explicitly marked exempt AND the caller
   holds the ``platform_admin`` role. The middleware enforces the role check;
   the session-layer enforces that ``tenant_exempt`` may not be used when no
   tenant context is set *unless* the exempt flag was explicitly granted.
5. If tenant_scoped query runs with no tenant context set AND no exempt
   flag, we raise :class:`MissingTenantContextError` — fail loud, never silent.

This module is a security boundary: 100% test coverage is mandatory.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any
from uuid import UUID

from sqlalchemy import UUID as SA_UUID
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Mapped, declarative_mixin, mapped_column, with_loader_criteria

# ---------------------------------------------------------------------------
# Context variable
# ---------------------------------------------------------------------------

current_tenant_id: ContextVar[UUID | None] = ContextVar(
    "infinityrx_current_tenant_id", default=None
)

#: execution_options key set on a statement (or session) to bypass scoping.
TENANT_EXEMPT_ATTR = "tenant_exempt"


class MissingTenantContextError(RuntimeError):
    """Raised when a tenant-scoped query runs with no tenant context."""


def set_tenant_context(tenant_id: UUID) -> object:
    """Set the active tenant id; return the token used to reset it."""
    return current_tenant_id.set(tenant_id)


def clear_tenant_context(token: object | None = None) -> None:
    """Clear the tenant context. If *token* is given, resets precisely."""
    if token is None:
        current_tenant_id.set(None)
    else:
        current_tenant_id.reset(token)  # type: ignore[arg-type]


def tenant_exempt(statement):  # type: ignore[no-untyped-def]
    """Attach the exempt flag to a SQLAlchemy statement.

    Usage::

        stmt = tenant_exempt(select(Tenant))
        result = await session.execute(stmt)

    The middleware must have authorised the caller as ``platform_admin``
    before any code path builds an exempt statement.
    """
    return statement.execution_options(**{TENANT_EXEMPT_ATTR: True})


# ---------------------------------------------------------------------------
# Mixin applied to tenant-scoped ORM models
# ---------------------------------------------------------------------------


@declarative_mixin
class TenantScopedMixin:
    """Mixin that marks a model as tenant-scoped and declares ``tenant_id``."""

    tenant_id: Mapped[UUID] = mapped_column(SA_UUID(as_uuid=True), nullable=False, index=True)


def _is_tenant_scoped(entity_cls: type) -> bool:
    return isinstance(entity_cls, type) and issubclass(entity_cls, TenantScopedMixin)


# ---------------------------------------------------------------------------
# Session event installer
# ---------------------------------------------------------------------------


def install_tenant_loader(
    sessionmaker: async_sessionmaker,  # type: ignore[type-arg]
) -> None:
    """Install the ``do_orm_execute`` handler on a session factory.

    Safe to call multiple times; each call wires a handler to any sessions
    produced by *sessionmaker*. In practice this is called once from
    :func:`shared.db.session.get_sessionmaker`.
    """
    from sqlalchemy import event
    from sqlalchemy.orm import Session

    sync_session_cls = sessionmaker.kw.get("sync_session_class", Session)
    if getattr(sync_session_cls, "_infinityrx_tenant_loader_installed", False):
        return
    event.listen(sync_session_cls, "do_orm_execute", _apply_tenant_filter)
    sync_session_cls._infinityrx_tenant_loader_installed = True  # type: ignore[attr-defined]


def _apply_tenant_filter(state: Any) -> None:
    """Attach a loader criteria to every tenant-scoped entity in *state*.

    Called from the ``do_orm_execute`` hook. Raises
    :class:`MissingTenantContextError` if the query touches a tenant-scoped
    model without an active tenant context and without the exempt flag.
    """
    if not getattr(state, "is_select", False) and not (
        getattr(state, "is_update", False) or getattr(state, "is_delete", False)
    ):
        return

    exempt = bool(state.execution_options.get(TENANT_EXEMPT_ATTR, False))
    tid = current_tenant_id.get()

    # Walk all mapped entities the statement touches.
    scoped_entities: list[type] = []
    for desc in state.all_mappers:
        cls = desc.class_
        if _is_tenant_scoped(cls):
            scoped_entities.append(cls)

    if not scoped_entities:
        return  # Query touches only non-tenant-scoped models — safe.

    if exempt:
        return  # Explicitly authorised cross-tenant query.

    if tid is None:
        raise MissingTenantContextError(
            "Tenant-scoped query executed with no active tenant context. "
            "Ensure the tenant isolation middleware ran for this request, "
            "or use `tenant_exempt()` with platform_admin authorisation."
        )

    # Build the loader criteria using a bindparam that is re-resolved on
    # every execution — this defeats SQLAlchemy's per-lambda statement
    # cache. A simple lambda that closes over the tid would be cached
    # against its first-seen value and then reused across requests,
    # causing a cross-tenant leak.
    from sqlalchemy import bindparam

    for cls in scoped_entities:
        tid_bind = bindparam(
            f"infinityrx_tid_{cls.__name__}", value=tid, literal_execute=True
        )
        state.statement = state.statement.options(
            with_loader_criteria(
                cls,
                cls.tenant_id == tid_bind,
                include_aliases=True,
            )
        )
