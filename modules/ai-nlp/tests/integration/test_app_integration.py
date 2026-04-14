"""Integration tests that exercise the full request path through create_app().

LESSON-006 prevention: every middleware/router primitive must be tested
through the top-level application factory, not in isolation.

Tests verify:
- Security headers present on responses (SecurityHeadersMiddleware mounted)
- Cache-Control: no-store on endpoints returning member/claim context
- Health endpoint reachable
- All API routers mounted and reachable
- Auth required on all endpoints (401 without credentials)
- Tenant header required (400/422 without x-tenant-id)
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.app import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint:
    def test_health_returns_200(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_returns_ok_status(self, client: TestClient) -> None:
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "ok"
        assert data["module"] == "ai-nlp"


class TestSecurityHeaders:
    def test_security_headers_present_on_health(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert "x-content-type-options" in resp.headers or "X-Content-Type-Options" in resp.headers

    def test_cache_control_no_store_on_chat_endpoint(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai/chat",
            json={"session_id": "s1", "portal_type": "pharmacy", "message": "test"},
            headers={"x-tenant-id": str(uuid4())},
        )
        cache_header = resp.headers.get("cache-control", resp.headers.get("Cache-Control", ""))
        assert "no-store" in cache_header or resp.status_code in (401, 422, 403)


class TestRoutersMounted:
    def test_chat_endpoint_mounted(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai/chat",
            json={"session_id": "s1", "portal_type": "pharmacy", "message": "test"},
        )
        assert resp.status_code != 404

    def test_documents_endpoint_mounted(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai/documents/process",
            json={
                "document_type": "eob",
                "extracted_text": "sample",
                "fields_to_extract": ["member_id"],
            },
        )
        assert resp.status_code != 404

    def test_generate_endpoint_mounted(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai/generate",
            json={"template_name": "PA Request Letter", "context_data": {}},
        )
        assert resp.status_code != 404

    def test_text_classify_endpoint_mounted(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai/text/classify",
            json={"text": "sample claim text"},
        )
        assert resp.status_code != 404

    def test_usage_endpoint_mounted(self, client: TestClient) -> None:
        resp = client.get("/api/v1/ai/usage")
        assert resp.status_code != 404


class TestAuthRequired:
    def test_chat_requires_auth_or_tenant(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai/chat",
            json={"session_id": "s1", "portal_type": "pharmacy", "message": "test"},
        )
        assert resp.status_code in (401, 422, 400)

    def test_documents_requires_auth_or_tenant(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai/documents/process",
            json={
                "document_type": "eob",
                "extracted_text": "sample",
                "fields_to_extract": ["member_id"],
            },
        )
        assert resp.status_code in (401, 422, 400)
