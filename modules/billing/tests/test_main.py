"""Smoke tests for billing module main.py application factory.

Verifies create_app() mounts all expected routers so integration tests
through create_app() catch regressions (LESSON-006).
"""

from __future__ import annotations


def _route_paths(app) -> set[str]:
    return {r.path for r in app.routes}


def test_create_app_mounts_uploads_router():
    from src.main import create_app
    app = create_app()
    paths = _route_paths(app)
    assert any("/uploads" in p for p in paths), f"uploads router not mounted: {paths}"


def test_create_app_mounts_inbox_router():
    from src.main import create_app
    app = create_app()
    paths = _route_paths(app)
    assert any("/inbox" in p for p in paths), f"inbox router not mounted: {paths}"


def test_create_app_mounts_cycles_router():
    from src.main import create_app
    app = create_app()
    paths = _route_paths(app)
    assert any("/cycles" in p for p in paths), f"cycles router not mounted: {paths}"


def test_create_app_mounts_carryovers_router():
    from src.main import create_app
    app = create_app()
    paths = _route_paths(app)
    assert any("/carryovers" in p for p in paths), f"carryovers router not mounted: {paths}"


def test_create_app_mounts_payment_runs_router():
    from src.main import create_app
    app = create_app()
    paths = _route_paths(app)
    assert any("/payment-runs" in p for p in paths), f"payment-runs router not mounted: {paths}"


def test_create_app_mounts_bank_settlements_router():
    from src.main import create_app
    app = create_app()
    paths = _route_paths(app)
    assert any("/bank-settlements" in p for p in paths), f"bank-settlements router not mounted: {paths}"


def test_create_app_mounts_reconciliations_router():
    from src.main import create_app
    app = create_app()
    paths = _route_paths(app)
    assert any("/reconciliations" in p for p in paths), f"reconciliations router not mounted: {paths}"
