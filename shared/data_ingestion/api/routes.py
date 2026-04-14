"""FastAPI router for the data-ingestion meta-API.

Mount this router in each module's ``create_app()`` factory::

    from shared.data_ingestion.api.routes import router as ingestion_router
    app.include_router(ingestion_router, prefix="/api/v1/data-ingestion")

Do NOT mount it here — this module ships the router only.

All handlers are ``async def`` per architecture rules. Structured error
responses follow the platform envelope:
    ``{"error": {"code": "...", "message": "...", "correlation_id": "..."}}``
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.data_ingestion.api.schemas import (
    CancelResponse,
    CancelRunRequest,
    FieldCatalogEntry,
    FieldCatalogResponse,
    RunDetail,
    RunSummary,
    SourceStatus,
    TriggerResponse,
    TriggerRunRequest,
)
from shared.data_ingestion.field_registry import registry as field_registry
from shared.data_ingestion.models import IngestionRun, IngestionSchedule

logger = logging.getLogger(__name__)

router = APIRouter(tags=["data-ingestion"])


# ---------------------------------------------------------------------------
# Dependency injection helpers
# ---------------------------------------------------------------------------


def _get_db(request: Request) -> Session:
    """Retrieve the DB session attached to the request state by the module app."""
    db: Session | None = getattr(request.state, "db", None)
    if db is None:
        raise HTTPException(status_code=500, detail="DB session not configured")
    return db


def _correlation_id(request: Request) -> str:
    """Return the correlation id from request state or generate a new one."""
    return str(getattr(request.state, "correlation_id", uuid.uuid4()))


def _error(code: str, message: str, correlation_id: str, status: int = 400) -> HTTPException:
    """Build a structured HTTPException with the platform error envelope."""
    detail: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "correlation_id": correlation_id,
        }
    }
    return HTTPException(status_code=status, detail=detail)


# ---------------------------------------------------------------------------
# Helper: build RunSummary from IngestionRun ORM row
# ---------------------------------------------------------------------------


def _run_summary(run: IngestionRun) -> RunSummary:
    duration = None
    if run.completed_at and run.started_at:
        duration = int((run.completed_at - run.started_at).total_seconds())
    return RunSummary(
        id=run.id,
        source=run.source,
        run_type=run.run_type,
        status=run.status,
        records_processed=run.records_processed,
        records_inserted=run.records_inserted,
        records_updated=run.records_updated,
        records_skipped=run.records_skipped,
        records_errored=run.records_errored,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=duration,
        error_message=run.error_message,
    )


def _run_detail(run: IngestionRun) -> RunDetail:
    summary = _run_summary(run)
    samples = None
    if run.error_samples and isinstance(run.error_samples, dict):
        samples = run.error_samples.get("samples")
    return RunDetail(
        **summary.model_dump(),
        source_url=run.source_url,
        source_file_name=run.source_file_name,
        source_file_size_bytes=run.source_file_size_bytes,
        source_file_checksum=run.source_file_checksum,
        records_in_source=run.records_in_source,
        download_seconds=run.download_seconds,
        parse_seconds=run.parse_seconds,
        load_seconds=run.load_seconds,
        error_samples=samples,
        triggered_by=run.triggered_by,
        created_at=run.created_at,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/{source}/trigger",
    response_model=TriggerResponse,
    summary="Trigger a manual ingestion run",
)
async def trigger_run(
    source: str,
    body: TriggerRunRequest,
    request: Request,
    db: Session = Depends(_get_db),
) -> TriggerResponse:
    """Start a manual ingestion run for *source*.

    Returns the new ``run_id`` immediately. The run executes asynchronously.
    Poll ``GET /runs/{run_id}`` for status.
    """
    cid = _correlation_id(request)

    # Verify source exists in the schedule table
    schedule = db.execute(
        select(IngestionSchedule).where(IngestionSchedule.source == source)
    ).scalar_one_or_none()
    if schedule is None:
        raise _error(
            "SOURCE_NOT_FOUND",
            f"No schedule registered for source '{source}'",
            cid,
            status=404,
        )

    # Prevent duplicate in-flight runs
    in_flight = db.execute(
        select(IngestionRun).where(
            IngestionRun.source == source,
            IngestionRun.status == "running",
        )
    ).scalar_one_or_none()
    if in_flight is not None:
        raise _error(
            "RUN_ALREADY_IN_FLIGHT",
            f"Source '{source}' already has a running job (run_id={in_flight.id})",
            cid,
            status=409,
        )

    run = IngestionRun(
        source=source,
        run_type=body.run_type,
        status="running",
        started_at=datetime.now(UTC),
        triggered_by=body.triggered_by,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    run_id = run.id

    logger.info(
        "Manual ingestion run triggered via API",
        extra={
            "ingest_source": source,
            "ingest_run_id": str(run_id),
            "ingest_correlation_id": cid,
        },
    )

    return TriggerResponse(
        run_id=run_id,
        source=source,
        status="running",
        message=f"Ingestion run started for source '{source}'",
    )


@router.post(
    "/upload/{source}",
    response_model=TriggerResponse,
    summary="Upload a file and trigger ingestion",
)
async def upload_and_ingest(
    source: str,
    file: UploadFile,
    request: Request,
    db: Session = Depends(_get_db),
) -> TriggerResponse:
    """Accept a file upload as an alternative to scheduled download.

    The run row is created immediately; callers poll ``GET /runs/{run_id}``
    for completion. The uploaded file is stored to a temporary path and
    processed by the source's ingester.
    """
    cid = _correlation_id(request)

    schedule = db.execute(
        select(IngestionSchedule).where(IngestionSchedule.source == source)
    ).scalar_one_or_none()
    if schedule is None:
        raise _error(
            "SOURCE_NOT_FOUND",
            f"No schedule registered for source '{source}'",
            cid,
            status=404,
        )

    run = IngestionRun(
        source=source,
        run_type="file_upload",
        status="running",
        started_at=datetime.now(UTC),
        source_file_name=file.filename,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    logger.info(
        "File upload ingestion triggered",
        extra={
            "ingest_source": source,
            "ingest_run_id": str(run.id),
            "ingest_filename": file.filename,
        },
    )

    return TriggerResponse(
        run_id=run.id,
        source=source,
        status="running",
        message=f"File upload ingestion started for source '{source}'",
    )


@router.get(
    "/status",
    response_model=list[SourceStatus],
    summary="Current state of all sources",
)
async def get_all_status(
    request: Request,
    db: Session = Depends(_get_db),
) -> list[SourceStatus]:
    """Return the current state of every registered ingestion source."""
    schedules = db.execute(select(IngestionSchedule)).scalars().all()

    result: list[SourceStatus] = []
    for schedule in schedules:
        last_run = None
        if schedule.last_run_id is not None:
            run_row = db.execute(
                select(IngestionRun).where(IngestionRun.id == schedule.last_run_id)
            ).scalar_one_or_none()
            if run_row is not None:
                last_run = _run_summary(run_row)

        result.append(
            SourceStatus(
                source=schedule.source,
                cron_expression=schedule.cron_expression,
                enabled=schedule.enabled,
                last_run=last_run,
                last_success_at=schedule.last_success_at,
                next_run_at=schedule.next_run_at,
            )
        )
    return result


@router.get(
    "/{source}/history",
    response_model=list[RunSummary],
    summary="Run history for a source",
)
async def get_source_history(
    source: str,
    limit: int = 50,
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(_get_db),
) -> list[RunSummary]:
    """Return the most recent *limit* runs for *source*."""
    cid = _correlation_id(request) if request else str(uuid.uuid4())

    schedule = db.execute(
        select(IngestionSchedule).where(IngestionSchedule.source == source)
    ).scalar_one_or_none()
    if schedule is None:
        raise _error(
            "SOURCE_NOT_FOUND",
            f"No schedule registered for source '{source}'",
            cid,
            status=404,
        )

    runs = (
        db.execute(
            select(IngestionRun)
            .where(IngestionRun.source == source)
            .order_by(IngestionRun.started_at.desc())
            .limit(max(1, min(limit, 500)))
        )
        .scalars()
        .all()
    )
    return [_run_summary(r) for r in runs]


@router.get(
    "/runs/{run_id}",
    response_model=RunDetail,
    summary="Get a single run by ID",
)
async def get_run_detail(
    run_id: uuid.UUID,
    request: Request,
    db: Session = Depends(_get_db),
) -> RunDetail:
    """Return full detail for a single ingestion run."""
    cid = _correlation_id(request)

    run = db.execute(
        select(IngestionRun).where(IngestionRun.id == run_id)
    ).scalar_one_or_none()
    if run is None:
        raise _error("RUN_NOT_FOUND", f"Run {run_id} not found", cid, status=404)

    return _run_detail(run)


@router.post(
    "/{source}/cancel",
    response_model=CancelResponse,
    summary="Cancel a running ingestion job",
)
async def cancel_run(
    source: str,
    body: CancelRunRequest,
    request: Request,
    db: Session = Depends(_get_db),
) -> CancelResponse:
    """Cancel the in-flight run for *source*, if any."""
    cid = _correlation_id(request)

    run = db.execute(
        select(IngestionRun).where(
            IngestionRun.source == source,
            IngestionRun.status == "running",
        )
    ).scalar_one_or_none()

    if run is None:
        raise _error(
            "NO_RUNNING_JOB",
            f"No running job found for source '{source}'",
            cid,
            status=404,
        )

    run.status = "cancelled"
    run.error_message = body.reason or "Cancelled via API"
    run.completed_at = datetime.now(UTC)
    db.commit()

    logger.info(
        "Ingestion run cancelled",
        extra={
            "ingest_source": source,
            "ingest_run_id": str(run.id),
            "ingest_correlation_id": cid,
        },
    )

    return CancelResponse(
        run_id=run.id,
        source=source,
        status="cancelled",
        message=f"Run for source '{source}' has been cancelled",
    )


@router.get(
    "/field-catalog",
    response_model=FieldCatalogResponse,
    summary="Dump the field registry",
)
async def get_field_catalog() -> FieldCatalogResponse:
    """Return all field mappings registered by source ingesters."""
    all_fields = field_registry.as_dict_list()
    return FieldCatalogResponse(
        total=len(all_fields),
        fields=[FieldCatalogEntry(**f) for f in all_fields],
    )


__all__ = ["router"]
