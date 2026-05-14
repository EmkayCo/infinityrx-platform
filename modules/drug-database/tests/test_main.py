"""B11 w1 — drug-database root /health endpoint regression test.

Closes B11 F-002: pre-fix the /health route lived under the
/api/v1/drugs prefix and returned 404 at root, breaking the
.qa_start_backend.py smoke probe and any other module that uses
root /health as the liveness contract.
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_root_health_endpoint_returns_200() -> None:
    """Root /health must return 200 with at minimum a {'status': 'ok'} body
    so smoke probes and load balancers can detect liveness without auth."""
    from src.main import create_app  # noqa: PLC0415

    app = create_app()
    client = TestClient(app)
    resp = client.get("/health")

    assert resp.status_code == 200, (
        f"/health returned {resp.status_code}; expected 200. "
        f"Body: {resp.text[:300]}"
    )
    payload = resp.json()
    assert isinstance(payload, dict)
    # Allow either flat or nested status — both conventions exist across modules
    has_status = (
        payload.get("status") == "ok"
        or payload.get("status") == "healthy"
        or any(v == "ok" for v in payload.values())
    )
    assert has_status, f"Expected an 'ok'/'healthy' status field in {payload}"
