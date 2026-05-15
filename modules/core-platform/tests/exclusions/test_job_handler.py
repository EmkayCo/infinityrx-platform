from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import respx

from src.exclusions import job_handler as jh
from src.exclusions.matching import MatchCandidate
from src.jobs.registry import default_registry


def test_exclusion_refresh_registered():
    assert "exclusion_refresh" in default_registry.known_types()


@respx.mock
async def test_run_exclusion_refresh_pipeline(db_session, monkeypatch):
    # Mock both HTTP endpoints via the URLs the clients use
    from src._shim import config as cfg

    monkeypatch.setattr(cfg.settings, "OIG_EXCLUSION_URL", "https://example.test/oig.csv")
    respx.get("https://example.test/oig.csv").mock(
        return_value=httpx.Response(
            200,
            text="LASTNAME,FIRSTNAME,NPI,STATE\nSMITH,JOHN,1234567890,NY\n",
        )
    )
    respx.get("https://api.sam.gov/entity-information/v4/exclusions").mock(
        return_value=httpx.Response(200, json={"exclusionDetails": []})
    )

    # Provide a fake entity provider with one hit
    class FakeProvider:
        def list_active(self, tenant_id):  # noqa: ARG002
            return [
                MatchCandidate(
                    entity_type="prescriber", entity_id="p1", npi="1234567890"
                )
            ]

    jh.set_entity_provider(FakeProvider())
    try:
        result = await jh.run_exclusion_refresh({"tenant_id": "t1"})
    finally:
        jh.set_entity_provider(jh._NoopEntityProvider())

    assert result["inserted"] >= 1
    assert result["rescreened"] == 1


async def test_run_exclusion_refresh_default_noop_provider(db_session, monkeypatch):
    from src._shim import config as cfg

    monkeypatch.setattr(cfg.settings, "OIG_EXCLUSION_URL", "https://example.test/oig.csv")

    @asynccontextmanager
    async def fake_client_factory():
        class FakeHttp:
            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, *a):
                return None

            async def get(self_inner, url, params=None):  # noqa: ARG002
                if "oig" in url:
                    return httpx.Response(200, text="LASTNAME\nA\n", request=httpx.Request("GET", url))
                return httpx.Response(200, json={"exclusionDetails": []}, request=httpx.Request("GET", url))

        return FakeHttp()

    # Build a factory matching HttpClientFactory signature
    def factory():
        client = httpx.AsyncClient(transport=httpx.MockTransport(_mock))
        return client

    def _mock(request: httpx.Request) -> httpx.Response:
        if "oig" in str(request.url):
            return httpx.Response(200, text="LASTNAME\nA\n")
        return httpx.Response(200, json={"exclusionDetails": []})

    result = await jh.run_exclusion_refresh({}, http_client_factory=factory)
    assert result["rescreened"] == 0


def test_get_entity_provider_returns_default():
    jh.set_entity_provider(jh._NoopEntityProvider())
    assert jh.get_entity_provider() is not None
    assert list(jh.get_entity_provider().list_active(None)) == []


async def test_default_client_factory_returns_client():
    c = jh._default_client_factory()
    assert isinstance(c, httpx.AsyncClient)
    await c.aclose()
