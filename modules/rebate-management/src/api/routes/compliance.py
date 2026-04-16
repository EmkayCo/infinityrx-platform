"""Compliance, transparency, and fiduciary dashboard API routes."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.dependencies import get_db, get_tenant_id
from src.services.transparency import TransparencyReportService
from src.services.compliance_dashboard import ComplianceDashboardService
from src.services.bfsf import BFSFService
from src.services.audit_export import AuditExportService
from src.services.benchmarks import BenchmarkService

router = APIRouter(prefix="/compliance", tags=["compliance"])


# --- Transparency Reports ---


class TransparencyReportRequest(BaseModel):
    sponsor_id: uuid.UUID
    report_type: str = "semiannual"
    period_start: date
    period_end: date


@router.post("/transparency-reports", status_code=201)
async def generate_transparency_report(
    body: TransparencyReportRequest,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict[str, Any]:
    svc = TransparencyReportService(db)
    report = svc.generate_report(
        tenant_id=tenant_id,
        sponsor_id=body.sponsor_id,
        report_type=body.report_type,
        period_start=body.period_start,
        period_end=body.period_end,
    )
    db.commit()
    return {"id": str(report.id), "status": report.status}


# --- Fiduciary Dashboard ---


@router.get("/fiduciary-dashboard/{sponsor_id}")
async def get_fiduciary_dashboard(
    sponsor_id: uuid.UUID,
    as_of: date | None = None,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict[str, Any]:
    svc = ComplianceDashboardService(db)
    return svc.get_dashboard(tenant_id, sponsor_id, as_of)


# --- BFSF ---


class BFSFCreateRequest(BaseModel):
    sponsor_id: uuid.UUID
    assessment_year: int
    contract_id: uuid.UUID | None = None
    services_detail: list[dict[str, Any]]


@router.post("/bfsf-documents", status_code=201)
async def create_bfsf_document(
    body: BFSFCreateRequest,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict[str, Any]:
    svc = BFSFService(db)
    doc = svc.create_document(
        tenant_id=tenant_id,
        sponsor_id=body.sponsor_id,
        assessment_year=body.assessment_year,
        contract_id=body.contract_id,
        services_detail=body.services_detail,
    )
    db.commit()
    return {"id": str(doc.id), "total_fee": str(doc.total_fee), "status": doc.status}


# --- Audit Export ---


class AuditExportRequest(BaseModel):
    sponsor_id: uuid.UUID | None = None
    date_from: date
    date_to: date
    export_type: str = "full"
    requested_by: uuid.UUID


@router.post("/audit-export", status_code=201)
async def request_audit_export(
    body: AuditExportRequest,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict[str, Any]:
    svc = AuditExportService(db)
    export = svc.request_export(
        tenant_id=tenant_id,
        sponsor_id=body.sponsor_id,
        date_from=body.date_from,
        date_to=body.date_to,
        export_type=body.export_type,
        requested_by=body.requested_by,
    )
    db.commit()
    return {"id": str(export.id), "status": export.status}


# --- Benchmarks ---


@router.get("/benchmarks/{program_id}")
async def get_program_benchmarks(
    program_id: uuid.UUID,
    period_start: date | None = None,
    period_end: date | None = None,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict[str, Any]:
    svc = BenchmarkService(db)
    return svc.get_benchmarks(tenant_id, program_id, period_start, period_end)
