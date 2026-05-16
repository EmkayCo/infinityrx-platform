"""Registers the `exclusion_refresh` job handler.

Runs OIG + SAM ingestion then re-screens active entities via a
provider protocol. Other modules will implement the provider to
surface pharmacies / prescribers / members.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Protocol

import httpx

from .._shim.config import settings
from .._shim.db import get_sessionmaker
from ..jobs.registry import default_registry
from .ingestion import OIGIngestionClient, SAMIngestionClient
from .matching import MatchCandidate
from .screening_service import ExclusionScreeningService

import logging as _logging

_job_logger = _logging.getLogger("core.exclusions.job_handler")


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
    _excl_table: str = "core.exclusion_list",
    _oig_table: str = "shared.oig_leie_exclusions",
    _sam_table: str = "shared.sam_exclusions",
) -> Dict[str, Any]:
    from scripts.aggregate_exclusion_list import run_aggregation  # noqa: PLC0415

    SessionLocal = get_sessionmaker()
    total_inserted = 0
    total_updated = 0
    total_skipped = 0
    rescreened = 0
    async with http_client_factory() as client:
        session = SessionLocal()
        try:
            # Stage 1 — OIG ingestion → source shim
            oig = OIGIngestionClient(client, url=settings.OIG_EXCLUSION_URL)
            oig_report = await oig.ingest(session)
            _job_logger.info(
                "excl_stage_oig_done",
                extra={
                    "excl_inserted": oig_report.inserted,
                    "excl_updated": oig_report.updated,
                    "excl_skipped": oig_report.skipped_malformed,
                },
            )

            # Stage 2 — SAM ingestion → source shim
            sam = SAMIngestionClient(client, api_key=settings.SAM_API_KEY)
            sam_report = await sam.ingest(session)
            _job_logger.info(
                "excl_stage_sam_done",
                extra={
                    "excl_inserted": sam_report.inserted,
                    "excl_updated": sam_report.updated,
                    "excl_skipped": sam_report.skipped_malformed,
                },
            )

            total_inserted = oig_report.inserted + sam_report.inserted
            total_updated = oig_report.updated + sam_report.updated
            total_skipped = oig_report.skipped_malformed + sam_report.skipped_malformed

            # Stage 3 — aggregate source shims → production core.exclusion_list
            agg_result = run_aggregation(
                session,
                oig_table=_oig_table,
                sam_table=_sam_table,
                excl_table=_excl_table,
                oig_min_rows=0,
                sam_min_rows=0,
            )
            session.commit()
            _job_logger.info(
                "excl_stage_aggregate_done",
                extra={
                    "excl_agg_inserted": agg_result.total_inserted,
                    "excl_agg_updated": agg_result.total_updated,
                    "excl_agg_delisted": agg_result.delisted,
                    "excl_agg_errors": agg_result.total_errors,
                },
            )

            # Stage 4 — re-screen active entities
            tenant_id = payload.get("tenant_id")
            svc = ExclusionScreeningService(session)
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
        "aggregated_inserted": agg_result.total_inserted,
        "aggregated_updated": agg_result.total_updated,
    }


default_registry.register("exclusion_refresh", run_exclusion_refresh)
