"""FastAPI router for the reporting module.

All endpoints are tenant-scoped. PHI access is logged.
Mutating endpoints are audit-logged.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import (
    get_current_tenant_id,
    get_current_user_id,
    get_db,
    get_user_permissions,
    get_user_role,
)
from src.api.schemas.dashboards import (
    DashboardCreate,
    DashboardRead,
    DashboardUpdate,
    FilterPresetCreate,
    FilterPresetRead,
    UserDashboardUpdate,
)
from src.api.schemas.regulatory import (
    ActuarialModelRead,
    RegulatoryStatusUpdate,
    RegulatorySubmissionCreate,
    RegulatorySubmissionRead,
)
from src.api.schemas.reports import (
    ReportDefinitionCreate,
    ReportDefinitionRead,
    ReportRunRead,
    ReportRunRequest,
)
from src.services.dashboard_service import DashboardService
from src.services.report_service import ReportService

router = APIRouter(prefix="/api/v1/reporting", tags=["reporting"])

TenantId = Annotated[str, Depends(get_current_tenant_id)]
UserId = Annotated[str, Depends(get_current_user_id)]
UserRole = Annotated[str, Depends(get_user_role)]
Permissions = Annotated[list[str], Depends(get_user_permissions)]
DB = Annotated[AsyncSession, Depends(get_db)]


# ─── Reports ───────────────────────────────────────────────────────────────────


@router.get("/reports", response_model=list[ReportDefinitionRead])
async def list_reports(
    tenant_id: TenantId,
    db: DB,
    category: str | None = None,
) -> list[ReportDefinitionRead]:
    svc = ReportService(db)
    defns = await svc.list_definitions(tenant_id=tenant_id, category=category)
    return [ReportDefinitionRead.model_validate(d) for d in defns]


@router.get("/reports/{report_id}", response_model=ReportDefinitionRead)
async def get_report(
    report_id: str,
    tenant_id: TenantId,
    db: DB,
) -> ReportDefinitionRead:
    svc = ReportService(db)
    defn = await svc.get_definition(report_id, tenant_id)
    if defn is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND"}})
    return ReportDefinitionRead.model_validate(defn)


@router.post("/reports", response_model=ReportDefinitionRead, status_code=201)
async def create_report(
    body: ReportDefinitionCreate,
    tenant_id: TenantId,
    user_id: UserId,
    db: DB,
) -> ReportDefinitionRead:
    svc = ReportService(db)
    defn = await svc.create_definition(tenant_id=tenant_id, data=body.model_dump())
    return ReportDefinitionRead.model_validate(defn)


@router.post("/reports/{report_id}/run", response_model=ReportRunRead, status_code=202)
async def run_report(
    report_id: str,
    body: ReportRunRequest,
    tenant_id: TenantId,
    user_id: UserId,
    db: DB,
) -> ReportRunRead:
    svc = ReportService(db)
    run = await svc.execute_report(
        report_id=report_id,
        tenant_id=tenant_id,
        filters=body.filters,
        requested_by=user_id,
        output_format=body.output_format,
    )
    return ReportRunRead.model_validate(run)


@router.get("/reports/{report_id}/runs", response_model=list[ReportRunRead])
async def list_report_runs(
    report_id: str,
    tenant_id: TenantId,
    db: DB,
) -> list[ReportRunRead]:
    svc = ReportService(db)
    runs = await svc.list_runs(tenant_id=tenant_id, report_id=report_id)
    return [ReportRunRead.model_validate(r) for r in runs]


@router.get("/reports/runs/{run_id}", response_model=ReportRunRead)
async def get_run(
    run_id: str,
    tenant_id: TenantId,
    db: DB,
) -> ReportRunRead:
    svc = ReportService(db)
    run = await svc.get_run(run_id, tenant_id)
    if run is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND"}})
    return ReportRunRead.model_validate(run)


# ─── Dashboards ────────────────────────────────────────────────────────────────


@router.get("/dashboards", response_model=list[DashboardRead])
async def list_dashboards(
    tenant_id: TenantId,
    db: DB,
    role_target: str | None = None,
) -> list[DashboardRead]:
    svc = DashboardService(db)
    dashboards = await svc.list_dashboards(tenant_id=tenant_id, role_target=role_target)
    return [DashboardRead.model_validate(d) for d in dashboards]


@router.get("/dashboards/{dashboard_id}", response_model=DashboardRead)
async def get_dashboard(
    dashboard_id: str,
    tenant_id: TenantId,
    db: DB,
) -> DashboardRead:
    svc = DashboardService(db)
    dashboard = await svc.get_dashboard(dashboard_id, tenant_id)
    if dashboard is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND"}})
    return DashboardRead.model_validate(dashboard)


@router.post("/dashboards", response_model=DashboardRead, status_code=201)
async def create_dashboard(
    body: DashboardCreate,
    tenant_id: TenantId,
    user_id: UserId,
    db: DB,
) -> DashboardRead:
    svc = DashboardService(db)
    dashboard = await svc.create_dashboard(tenant_id=tenant_id, data=body.model_dump())
    return DashboardRead.model_validate(dashboard)


@router.put("/dashboards/{dashboard_id}", response_model=DashboardRead)
async def update_dashboard(
    dashboard_id: str,
    body: DashboardUpdate,
    tenant_id: TenantId,
    user_id: UserId,
    db: DB,
) -> DashboardRead:
    svc = DashboardService(db)
    dashboard = await svc.update_dashboard(
        dashboard_id, tenant_id, body.model_dump(exclude_none=True)
    )
    if dashboard is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND"}})
    return DashboardRead.model_validate(dashboard)


# ─── User customization ────────────────────────────────────────────────────────


@router.put("/my/dashboard")
async def save_my_dashboard(
    body: UserDashboardUpdate,
    tenant_id: TenantId,
    user_id: UserId,
    db: DB,
    dashboard_id: str = "",
) -> dict[str, str]:
    svc = DashboardService(db)
    await svc.save_user_dashboard(
        user_id=user_id,
        tenant_id=tenant_id,
        dashboard_id=dashboard_id,
        custom_layout=body.custom_layout,
        pinned_filters=body.pinned_filters,
    )
    return {"status": "saved"}


@router.get("/my/filter-presets", response_model=list[FilterPresetRead])
async def list_filter_presets(
    tenant_id: TenantId,
    user_id: UserId,
    db: DB,
) -> list[FilterPresetRead]:
    svc = DashboardService(db)
    presets = await svc.list_filter_presets(tenant_id=tenant_id, user_id=user_id)
    return [FilterPresetRead.model_validate(p) for p in presets]


@router.post("/my/filter-presets", response_model=FilterPresetRead, status_code=201)
async def save_filter_preset(
    body: FilterPresetCreate,
    tenant_id: TenantId,
    user_id: UserId,
    db: DB,
) -> FilterPresetRead:
    svc = DashboardService(db)
    preset = await svc.save_filter_preset(
        tenant_id=tenant_id,
        user_id=user_id if not body.shared else None,
        name=body.name,
        filters=body.filters,
        applies_to=body.applies_to,
    )
    return FilterPresetRead.model_validate(preset)


@router.delete("/my/filter-presets/{preset_id}", status_code=204)
async def delete_filter_preset(
    preset_id: str,
    tenant_id: TenantId,
    user_id: UserId,
    db: DB,
) -> Response:
    svc = DashboardService(db)
    deleted = await svc.delete_filter_preset(preset_id, tenant_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND"}})
    return Response(status_code=204)


# ─── Report Builder ────────────────────────────────────────────────────────────


@router.get("/builder/data-sources")
async def list_data_sources(tenant_id: TenantId) -> dict[str, list[str]]:
    return {
        "data_sources": [
            "claims",
            "billing_ap",
            "billing_ar",
            "journal",
            "fwa",
            "members",
            "pharmacies",
            "prescribers",
            "programs",
        ]
    }


@router.get("/builder/fields/{source}")
async def get_data_source_fields(source: str, tenant_id: TenantId) -> dict[str, Any]:
    from src.services.report_builder import get_available_fields

    fields = get_available_fields(source)
    return {"source": source, "fields": fields}


@router.post("/builder/preview")
async def preview_report(
    body: dict[str, Any],
    tenant_id: TenantId,
    user_id: UserId,
    db: DB,
) -> dict[str, Any]:
    return {"rows": [], "total_count": 0, "preview_limit": 100}


# ─── Client API ────────────────────────────────────────────────────────────────


@router.get("/client-api/claims")
async def client_claims(
    tenant_id: TenantId,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    return {"data": [], "page": page, "page_size": page_size, "total": 0}


@router.get("/client-api/billing")
async def client_billing(tenant_id: TenantId) -> dict[str, Any]:
    return {"data": {}, "tenant_id": tenant_id}


@router.get("/client-api/program-performance")
async def client_program_performance(tenant_id: TenantId) -> dict[str, Any]:
    return {"data": {}, "tenant_id": tenant_id}


@router.get("/client-api/fwa-summary")
async def client_fwa_summary(tenant_id: TenantId) -> dict[str, Any]:
    return {"data": {}, "tenant_id": tenant_id}


# ─── Regulatory ────────────────────────────────────────────────────────────────


@router.get("/regulatory", response_model=list[RegulatorySubmissionRead])
async def list_regulatory(tenant_id: TenantId, db: DB) -> list[RegulatorySubmissionRead]:
    from src.services.regulatory_service import RegulatoryService

    svc = RegulatoryService(db)
    subs = await svc.list_submissions(tenant_id)
    return [RegulatorySubmissionRead.model_validate(s) for s in subs]


@router.post("/regulatory", response_model=RegulatorySubmissionRead, status_code=201)
async def create_regulatory(
    body: RegulatorySubmissionCreate,
    tenant_id: TenantId,
    user_id: UserId,
    db: DB,
) -> RegulatorySubmissionRead:
    from src.services.regulatory_service import RegulatoryService

    svc = RegulatoryService(db)
    sub = await svc.create_submission(tenant_id=tenant_id, data=body.model_dump())
    return RegulatorySubmissionRead.model_validate(sub)


@router.put("/regulatory/{submission_id}", response_model=RegulatorySubmissionRead)
async def update_regulatory(
    submission_id: str,
    body: RegulatoryStatusUpdate,
    tenant_id: TenantId,
    user_id: UserId,
    db: DB,
) -> RegulatorySubmissionRead:
    from src.services.regulatory_service import RegulatoryService

    svc = RegulatoryService(db)
    sub = await svc.update_status(submission_id, tenant_id, body.status)
    if sub is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND"}})
    return RegulatorySubmissionRead.model_validate(sub)


@router.get("/regulatory/deadlines")
async def regulatory_deadlines(tenant_id: TenantId, db: DB) -> dict[str, Any]:
    from src.services.regulatory_service import RegulatoryService

    svc = RegulatoryService(db)
    deadlines = await svc.get_upcoming_deadlines(tenant_id)
    return {"deadlines": deadlines}


# ─── Actuarial ─────────────────────────────────────────────────────────────────


@router.get("/actuarial/models", response_model=list[ActuarialModelRead])
async def list_actuarial_models(tenant_id: TenantId, db: DB) -> list[ActuarialModelRead]:
    from src.services.actuarial_service import ActuarialService

    svc = ActuarialService(db)
    models = await svc.list_models(tenant_id)
    return [ActuarialModelRead.model_validate(m) for m in models]


@router.post("/actuarial/reprice")
async def actuarial_reprice(
    body: dict[str, Any],
    tenant_id: TenantId,
    user_id: UserId,
    db: DB,
) -> dict[str, Any]:
    from src.services.actuarial_service import ActuarialService

    svc = ActuarialService(db)
    result = await svc.reprice_claims(tenant_id, body)
    return result


# ─── Quality / Star Ratings ────────────────────────────────────────────────────


@router.get("/quality/star-ratings")
async def get_star_ratings(tenant_id: TenantId, db: DB) -> dict[str, Any]:
    from src.services.quality_service import QualityService

    svc = QualityService(db)
    return await svc.get_star_ratings_dashboard(tenant_id)


@router.get("/quality/adherence/{measure}")
async def get_adherence(measure: str, tenant_id: TenantId, db: DB) -> dict[str, Any]:
    from src.services.quality_service import QualityService

    svc = QualityService(db)
    return await svc.get_adherence_detail(tenant_id, measure)


@router.get("/quality/gaps")
async def get_adherence_gaps(tenant_id: TenantId, db: DB) -> dict[str, Any]:
    from src.services.quality_service import QualityService

    svc = QualityService(db)
    return await svc.get_gap_members(tenant_id)


@router.get("/quality/projections")
async def get_star_projections(tenant_id: TenantId, db: DB) -> dict[str, Any]:
    from src.services.quality_service import QualityService

    svc = QualityService(db)
    return await svc.get_year_end_projections(tenant_id)
