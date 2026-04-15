"""CR-06: verify notifications, bank_holidays, and audit routers are mounted
on the core-platform create_app() aggregator. Without this, each of the three
routers existed but responded 404 because they were never included.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def app():
    from src.main import create_app

    return create_app()


def test_audit_router_mounted(app) -> None:
    paths = {route.path for route in app.routes}
    assert "/api/v1/audit" in paths, f"audit list endpoint missing. sample: {sorted(paths)[:10]}"
    assert "/api/v1/audit/{entry_id}" in paths or any(p.startswith("/api/v1/audit/") for p in paths)


def test_bank_holidays_router_mounted(app) -> None:
    paths = {route.path for route in app.routes}
    assert any(p.startswith("/bank-holidays") for p in paths), "bank-holidays endpoints missing"


def test_notifications_router_mounted(app) -> None:
    paths = {route.path for route in app.routes}
    assert any(p.startswith("/api/v1/notifications") for p in paths), "notifications endpoints missing"
