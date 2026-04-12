"""Registers the `exclusion_refresh` job handler.

Runs OIG + SAM ingestion then re-screens active entities via a
provider protocol. Other modules will implement the provider to
surface pharmacies / prescribers / members.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Iterable, Protocol

import httpx

from .._shim.config import settings
from .._shim.db import get_sessionmaker
from ..jobs.registry import default_registry
from .ingestion import OIGIngestionClient, SAMIngestionClient
from .matching import MatchCandidate
from .screening_service import ExclusionScreeningService


class ActiveEntityProvider(Protocol):
    def list_active(self, tenant_id: str | None) -> Iterable[MatchCandidate]: ...


class _NoopEntityProvider:
    def list_active(self, tenant_id: str | None) -> Iterable[MatchCandidate]:
        return []


_provider: ActiveEntityProvider = _NoopEntityProvider()


def set_entity_provider(provider: ActiveEntityProvider) -> None:
    global _provider
    _provider = provider


def get_entity_provider() -> ActiveEntityProvider:
    return _provider


HttpClientFactory = Callable[[], httpx.AsyncClient]


def _default_client_factory() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=60.0)


async def run_exclusion_refresh(
    payload: Dict[str, Any],
    *,
    http_client_factory: HttpClientFactory = _default_client_factory,
) -> Dict[str, Any]:
    SessionLocal = get_sessionmaker()
    total_inserted = 0
    total_updated = 0
    total_skipped = 0
    async with http_client_factory() as client:
        session = SessionLocal()
        try:
            oig = OIGIngestionClient(client, url=settings.OIG_EXCLUSION_URL)
            oig_report = await oig.ingest(session)
            sam = SAMIngestionClient(client, api_key=settings.SAM_API_KEY)
            sam_report = await sam.ingest(session)
            total_inserted = oig_report.inserted + sam_report.inserted
            total_updated = oig_report.updated + sam_report.updated
            total_skipped = oig_report.skipped_malformed + sam_report.skipped_malformed
            tenant_id = payload.get("tenant_id")
            svc = ExclusionScreeningService(session)
            rescreened = 0
            for candidate in _provider.list_active(tenant_id):
                svc.screen_entity(tenant_id=tenant_id or "", entity=candidate)
                rescreened += 1
        finally:
            session.close()
    return {
        "items_processed": total_inserted + total_updated,
        "items_failed": total_skipped,
        "inserted": total_inserted,
        "updated": total_updated,
        "skipped": total_skipped,
        "rescreened": rescreened,
    }


default_registry.register("exclusion_refresh", run_exclusion_refresh)
