"""Unit tests for router.py — verifies router mounts and basic import health."""
from __future__ import annotations

import pytest
from fastapi import FastAPI

from src.api.router import router


def test_router_has_prefix() -> None:
    assert router.prefix == "/api/v1/reclaimrx"


def test_router_mounts_on_app() -> None:
    app = FastAPI()
    app.include_router(router)
    routes = {r.path for r in app.routes}
    assert "/api/v1/reclaimrx/flags" in routes
    assert "/api/v1/reclaimrx/investigations" in routes
    assert "/api/v1/reclaimrx/graph-runs/trigger" in routes


def test_router_has_ml_scores_route() -> None:
    app = FastAPI()
    app.include_router(router)
    routes = {r.path for r in app.routes}
    assert "/api/v1/reclaimrx/ml-scores" in routes


def test_router_has_graph_runs_route() -> None:
    app = FastAPI()
    app.include_router(router)
    routes = {r.path for r in app.routes}
    assert "/api/v1/reclaimrx/graph-runs" in routes


def test_router_has_fraud_rings_route() -> None:
    app = FastAPI()
    app.include_router(router)
    routes = {r.path for r in app.routes}
    assert "/api/v1/reclaimrx/fraud-rings" in routes


def test_router_has_thresholds_route() -> None:
    app = FastAPI()
    app.include_router(router)
    routes = {r.path for r in app.routes}
    assert "/api/v1/reclaimrx/thresholds" in routes


def test_router_has_rule_firings_route() -> None:
    app = FastAPI()
    app.include_router(router)
    routes = {r.path for r in app.routes}
    assert "/api/v1/reclaimrx/rule-firings" in routes


def test_router_has_notes_route() -> None:
    app = FastAPI()
    app.include_router(router)
    routes = {r.path for r in app.routes}
    assert "/api/v1/reclaimrx/investigations/{investigation_id}/notes" in routes
