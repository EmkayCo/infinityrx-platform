"""Integration test: PostgresIdempotencyStore is wired through create_app().

R1 BLOCK 6 fix: prove the in-memory store is gone and the durable store
is used by every consumer registered via wire_consumers().

R9 BLOCK-27 fix: do NOT import src.main or src.events at module scope --
that would freeze a reference to get_async_engine_for_idempotency inside
src.events BEFORE pytest runs the test (and therefore before
monkeypatch.setattr could replace it). All imports happen inside the
test body, AFTER the patch is in place.
"""
from __future__ import annotations

import pytest


def test_idempotency_store_is_postgres_not_in_memory(monkeypatch):
    """get_idempotency_store() returns PostgresIdempotencyStore, not InMemoryIdempotencyStore.

    R8 BLOCK-27 / R9 BLOCK-27 fix: stub get_async_engine_for_idempotency BEFORE any
    production module imports it. CI does not have a live Postgres at module load time.
    """
    from unittest.mock import MagicMock  # noqa: PLC0415

    # Stub the async engine factory FIRST, in the canonical location.
    # The accessor in src.events imports it on every call to get_idempotency_store()
    # (R9 BLOCK-27 follow-up in events/__init__.py), so the patch takes effect even
    # though src.events may already be imported by other tests in the same session.
    fake_engine = MagicMock(name="FakeAsyncEngine")
    monkeypatch.setattr(
        "src._shim.db.get_async_engine_for_idempotency",
        lambda: fake_engine,
    )

    # Reset the module-level singleton so a prior test cannot mask the patched factory.
    import src.events as _events_module  # noqa: PLC0415
    monkeypatch.setattr(_events_module, "_idempotency_store", None)

    # Imports happen AFTER the patch + singleton reset.
    from shared.events.idempotency import (  # noqa: PLC0415
        PostgresIdempotencyStore,
        InMemoryIdempotencyStore,
    )
    from src.events import get_idempotency_store  # noqa: PLC0415
    from src.main import create_app  # noqa: PLC0415

    # R10 NIT-7 fix: build the app + drive lifespan startup so the lifespan-registered
    # wire_consumers() actually runs. TestClient as context manager triggers startup.
    from fastapi.testclient import TestClient  # noqa: PLC0415
    with TestClient(create_app()) as _client:
        _client.get("/health")

    store = get_idempotency_store()
    assert isinstance(store, PostgresIdempotencyStore), (
        f"expected PostgresIdempotencyStore, got {type(store).__name__}"
    )
    assert not isinstance(store, InMemoryIdempotencyStore)


def test_module_does_not_import_inmemory_store():
    """events/__init__.py must not IMPORT InMemoryIdempotencyStore at module load.

    R7 BLOCK-24 fix: AST parse ONLY the import nodes so explanatory comments
    that mention the class name are ignored.
    """
    import ast
    import src.events as events_module

    tree = ast.parse(open(events_module.__file__).read())
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.add(alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.name.rsplit(".", 1)[-1])

    assert "InMemoryIdempotencyStore" not in imported_names, (
        "events/__init__.py still IMPORTS InMemoryIdempotencyStore -- "
        "replace with PostgresIdempotencyStore per A2 BLOCK 6. "
        f"(Imported names: {sorted(imported_names)})"
    )
