"""Tests that reclaimrx reuses the shared tenant contextvar.

P1 Item 4 of the emergency wiring pass. reclaimrx previously defined its
own ``_current_tenant`` ContextVar disconnected from
``shared.db.tenant_context.current_tenant_id``. Under the core-platform
middleware (which sets the shared contextvar), reclaimrx code saw ``None``
and fell back to manual WHERE clauses that could easily be forgotten.
"""

from __future__ import annotations

import uuid

from shared.db.tenant_context import current_tenant_id as shared_ctx
from shared.db.tenant_context import set_tenant_context, clear_tenant_context

from src._shim import db as reclaimrx_db


def test_reclaimrx_reads_shared_contextvar() -> None:
    tid = uuid.uuid4()
    token = set_tenant_context(tid)
    try:
        # reclaimrx_db.current_tenant_id must return the same UUID that the
        # shared tenant context is holding.
        assert reclaimrx_db.current_tenant_id() == tid
    finally:
        clear_tenant_context(token)


def test_reclaimrx_context_manager_sets_shared_contextvar() -> None:
    tid = uuid.uuid4()
    # Use reclaimrx's own context manager — the shared contextvar must see it.
    with reclaimrx_db.tenant_context(tid):
        assert shared_ctx.get() == tid
    # After exit, shared context must also be cleared.
    assert shared_ctx.get() is None


def test_reclaimrx_and_shared_agree_on_none_default() -> None:
    # No tenant set anywhere.
    assert reclaimrx_db.current_tenant_id() is None
    assert shared_ctx.get() is None
