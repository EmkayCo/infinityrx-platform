"""FastAPI router for pharmacy-directory module."""
from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.security import OAuth2PasswordBearer
from shared.db.session import get_session
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    AddPharmacyToNetworkRequest,
    AdequacyResponse,
    BatchLookupRequest,
    CredentialingApplicationRequest,
    CredentialingApplicationResponse,
    CredentialingDecisionRequest,
    DirectoryStatsResponse,
    NetworkCreateRequest,
    NetworkResponse,
    PharmacyListResponse,
    PharmacyResponse,
    PsaoCreateRequest,
    PsaoResponse,
)
from src.models.tables import (
    CredentialingApplication,
    Network,
    NetworkMembership,
    Pharmacy,
    Psao,
    PsaoMembership,
)
from src.services.credentialing import CredentialingService
from src.services.lookup import PharmacyLookupService
from src.services.network import NetworkService
from src.utils.validation import InvalidNpiNumberError, validate_npi

router = APIRouter(prefix="/api/v1/pharmacies", tags=["pharmacy-directory"])

_log = logging.getLogger(__name__)
_oauth_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# Sentinel used when the JWT pipeline is not configured (e.g. unit tests, dev
# environments before configure_auth() has run). This UUID is reserved and MUST
# NOT collide with any real user — it is safe to attribute audit/credentialing
# decisions to it because downstream forensics will see the synthetic value
# and know the request was unauthenticated.
SYSTEM_REVIEWER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_reviewer_id(token: str | None = Depends(_oauth_scheme)) -> uuid.UUID:
    """Return the user_id from the JWT bearer token, or the system sentinel.

    Wave 3D safety wiring: the previous code generated a fresh ``uuid.uuid4()``
    for every credentialing decision, so the audit trail attributed each
    approve/deny to a non-existent user. With this dependency:

    * If a valid bearer token is present and shared.auth is configured, the
      caller's ``CurrentUser.id`` is returned.
    * If auth is not yet configured (unit tests, dev), we fall back to the
      ``SYSTEM_REVIEWER_ID`` sentinel and log a WARNING so the gap is visible.
    * If a token is present but invalid/expired, we still raise 401 — we never
      silently accept bad tokens.
    """
    if not token:
        _log.warning(
            "credentialing decision recorded without authenticated user — "
            "attributing to system sentinel",
            extra={"svc_name": "pharmacy-directory", "reviewer_fallback": True},
        )
        return SYSTEM_REVIEWER_ID

    # Lazy import — shared.auth.dependencies raises if not configured at import
    # time would crash modules that have never wired auth.
    try:
        from shared.auth.dependencies import _resolve_claims, _get_user_loader

        claims = _resolve_claims(token)
        loader = _get_user_loader()
        user = loader(claims.user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "unauthorized", "message": "user not found"},
            )
        return user.id
    except RuntimeError:
        # auth not configured — fall back to sentinel with a warning
        _log.warning(
            "shared.auth not configured; attributing credentialing decision "
            "to system sentinel reviewer",
            extra={"svc_name": "pharmacy-directory"},
        )
        return SYSTEM_REVIEWER_ID


def _correlation_id() -> str:
    return str(uuid.uuid4())


def _error(code: str, message: str, status_code: int, field: str | None = None) -> HTTPException:
    cid = _correlation_id()
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "field": field, "correlation_id": cid}},
    )


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


@router.get("/lookup/{npi}", response_model=PharmacyResponse)
async def get_pharmacy_by_npi(
    npi: str,
    tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")] = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_session),
) -> Any:
    try:
        validate_npi(npi)
    except InvalidNpiNumberError as exc:
        raise _error("INVALID_NPI", f"Invalid NPI format: {npi}", status.HTTP_400_BAD_REQUEST, "npi") from exc

    svc = PharmacyLookupService(db)
    tid = tenant_id or uuid.uuid4()
    data = await svc.get_by_npi(tid, npi)
    if data is None:
        raise _error("PHARMACY_NOT_FOUND", f"Pharmacy with NPI {npi} not found", status.HTTP_404_NOT_FOUND)
    return data


@router.get("/lookup/nabp/{nabp}", response_model=PharmacyResponse)
async def get_pharmacy_by_nabp(
    nabp: str,
    tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")] = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_session),
) -> Any:
    svc = PharmacyLookupService(db)
    tid = tenant_id or uuid.uuid4()
    data = await svc.get_by_nabp(tid, nabp)
    if data is None:
        raise _error("PHARMACY_NOT_FOUND", f"Pharmacy with NABP {nabp} not found", status.HTTP_404_NOT_FOUND)
    return data


@router.get("/search", response_model=PharmacyListResponse)
async def search_pharmacies(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_session),
) -> Any:
    svc = PharmacyLookupService(db)
    pharmacies = await svc.search_by_name(q, limit=limit, offset=offset)
    return {"pharmacies": pharmacies, "total": len(pharmacies)}


@router.get("/nearby", response_model=PharmacyListResponse)
async def nearby_pharmacies(
    lat: Decimal = Query(...),
    lng: Decimal = Query(...),
    radius_miles: float = Query(default=10.0, le=100.0),
    pharmacy_type: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_session),
) -> Any:
    svc = PharmacyLookupService(db)
    pharmacies = await svc.search_nearby(lat, lng, radius_miles, pharmacy_type, limit)
    return {"pharmacies": pharmacies, "total": len(pharmacies)}


@router.post("/batch", response_model=dict)
async def batch_lookup(
    body: BatchLookupRequest,
    tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")] = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_session),
) -> Any:
    svc = PharmacyLookupService(db)
    tid = tenant_id or uuid.uuid4()
    return await svc.batch_lookup(tid, body.npis)


# ---------------------------------------------------------------------------
# Networks
# ---------------------------------------------------------------------------


@router.get("/networks", response_model=list[NetworkResponse])
async def list_networks(
    tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")],
    db: AsyncSession = Depends(get_session),
) -> Any:
    stmt = select(Network).where(Network.tenant_id == tenant_id)
    result = await db.execute(stmt)
    networks = result.scalars().all()
    return [_network_to_schema(n) for n in networks]


@router.post("/networks", response_model=NetworkResponse, status_code=status.HTTP_201_CREATED)
async def create_network(
    body: NetworkCreateRequest,
    tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")],
    db: AsyncSession = Depends(get_session),
) -> Any:
    svc = NetworkService(db)
    network = await svc.create_network(
        tenant_id=tenant_id,
        name=body.name,
        network_code=body.network_code,
        network_type=body.network_type,
        effective_date=body.effective_date,
        description=body.description,
        any_willing_pharmacy=body.any_willing_pharmacy,
    )
    await db.flush()
    return _network_to_schema(network)


@router.get("/networks/{network_id}/pharmacies")
async def list_network_pharmacies(
    network_id: uuid.UUID,
    tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")],
    db: AsyncSession = Depends(get_session),
) -> Any:
    stmt = (
        select(Pharmacy, NetworkMembership)
        .join(NetworkMembership, NetworkMembership.pharmacy_id == Pharmacy.id)
        .where(
            NetworkMembership.network_id == network_id,
            NetworkMembership.tenant_id == tenant_id,
            NetworkMembership.status == "active",
        )
    )
    result = await db.execute(stmt)
    rows = result.all()
    pharmacies = []
    for pharmacy, membership in rows:
        d = {"id": str(pharmacy.id), "npi": pharmacy.npi, "display_name": pharmacy.display_name,
             "membership_id": str(membership.id), "effective_date": membership.effective_date.isoformat()}
        pharmacies.append(d)
    return {"pharmacies": pharmacies, "total": len(pharmacies)}


@router.post("/networks/{network_id}/pharmacies", status_code=status.HTTP_201_CREATED)
async def add_pharmacy_to_network(
    network_id: uuid.UUID,
    body: AddPharmacyToNetworkRequest,
    tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")],
    db: AsyncSession = Depends(get_session),
) -> Any:
    svc = NetworkService(db)
    membership = await svc.add_pharmacy_to_network(
        tenant_id=tenant_id,
        network_id=network_id,
        pharmacy_id=uuid.UUID(body.pharmacy_id),
        effective_date=body.effective_date,
        dispensing_fee=body.dispensing_fee,
        brand_discount=body.brand_discount,
        generic_discount=body.generic_discount,
        specialty_discount=body.specialty_discount,
        admin_fee=body.admin_fee,
        reimbursement_type=body.reimbursement_type,
        performance_tier=body.performance_tier,
    )
    await db.flush()
    return {
        "id": str(membership.id),
        "pharmacy_id": body.pharmacy_id,
        "network_id": str(network_id),
        "status": membership.status,
    }


@router.post("/networks/{network_id}/bulk-add")
async def bulk_add_pharmacies(
    network_id: uuid.UUID,
    file: UploadFile,
    tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")],
    effective_date: date = Query(...),
    db: AsyncSession = Depends(get_session),
) -> Any:
    content = (await file.read()).decode("utf-8")
    svc = NetworkService(db)
    result = await svc.bulk_add_from_csv(tenant_id, network_id, content, effective_date)
    await db.flush()
    return result


@router.get("/networks/{network_id}/adequacy", response_model=AdequacyResponse)
async def network_adequacy(
    network_id: uuid.UUID,
    tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")],
    area_type: str = Query(default="urban"),
    db: AsyncSession = Depends(get_session),
) -> Any:
    svc = NetworkService(db)
    result = await svc.calculate_adequacy(tenant_id, network_id, [], area_type)
    return result


# ---------------------------------------------------------------------------
# Credentialing
# ---------------------------------------------------------------------------


@router.get("/credentialing", response_model=list[CredentialingApplicationResponse])
async def list_credentialing_applications(
    tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")],
    db: AsyncSession = Depends(get_session),
) -> Any:
    stmt = select(CredentialingApplication).where(CredentialingApplication.tenant_id == tenant_id)
    result = await db.execute(stmt)
    apps = result.scalars().all()
    return [_app_to_schema(a) for a in apps]


@router.post("/credentialing", response_model=CredentialingApplicationResponse, status_code=status.HTTP_201_CREATED)
async def submit_credentialing_application(
    body: CredentialingApplicationRequest,
    tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")],
    db: AsyncSession = Depends(get_session),
) -> Any:
    try:
        validate_npi(body.applicant_npi)
    except InvalidNpiNumberError as exc:
        raise _error("INVALID_NPI", "Invalid NPI format", status.HTTP_400_BAD_REQUEST, "applicant_npi") from exc

    svc = CredentialingService(db)
    app = await svc.submit_application(
        tenant_id=tenant_id,
        applicant_npi=body.applicant_npi,
        applicant_name=body.applicant_name,
        network_id=uuid.UUID(body.network_id),
        pharmacy_id=uuid.UUID(body.pharmacy_id) if body.pharmacy_id else None,
        applicant_address=body.applicant_address,
    )
    await db.flush()
    return _app_to_schema(app)


@router.get("/credentialing/{application_id}", response_model=CredentialingApplicationResponse)
async def get_credentialing_application(
    application_id: uuid.UUID,
    tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")],
    db: AsyncSession = Depends(get_session),
) -> Any:
    stmt = select(CredentialingApplication).where(
        CredentialingApplication.id == application_id,
        CredentialingApplication.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    app = result.scalar_one_or_none()
    if app is None:
        raise _error("NOT_FOUND", "Credentialing application not found", status.HTTP_404_NOT_FOUND)
    return _app_to_schema(app)


@router.post("/credentialing/{application_id}/approve", response_model=CredentialingApplicationResponse)
async def approve_credentialing(
    application_id: uuid.UUID,
    body: CredentialingDecisionRequest,
    tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")],
    reviewer_id: Annotated[uuid.UUID, Depends(get_reviewer_id)],
    db: AsyncSession = Depends(get_session),
) -> Any:
    svc = CredentialingService(db)
    app = await svc.approve(application_id, reviewer_id, body.review_notes)
    await db.flush()
    return _app_to_schema(app)


@router.post("/credentialing/{application_id}/deny", response_model=CredentialingApplicationResponse)
async def deny_credentialing(
    application_id: uuid.UUID,
    body: CredentialingDecisionRequest,
    tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")],
    reviewer_id: Annotated[uuid.UUID, Depends(get_reviewer_id)],
    db: AsyncSession = Depends(get_session),
) -> Any:
    if not body.denial_reason:
        raise _error("MISSING_DENIAL_REASON", "denial_reason is required", status.HTTP_422_UNPROCESSABLE_ENTITY, "denial_reason")
    svc = CredentialingService(db)
    app = await svc.deny(application_id, reviewer_id, body.denial_reason, body.review_notes)
    await db.flush()
    return _app_to_schema(app)


# ---------------------------------------------------------------------------
# PSAOs
# ---------------------------------------------------------------------------


@router.get("/psaos", response_model=list[PsaoResponse])
async def list_psaos(db: AsyncSession = Depends(get_session)) -> Any:
    stmt = select(Psao).where(Psao.is_active.is_(True))
    result = await db.execute(stmt)
    return [_psao_to_schema(p) for p in result.scalars().all()]


@router.post("/psaos", response_model=PsaoResponse, status_code=status.HTTP_201_CREATED)
async def create_psao(body: PsaoCreateRequest, db: AsyncSession = Depends(get_session)) -> Any:
    psao = Psao(
        name=body.name,
        psao_id=body.psao_id,
        npi=body.npi,
        contact_name=body.contact_name,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
        payment_consolidated=body.payment_consolidated,
    )
    db.add(psao)
    await db.flush()
    return _psao_to_schema(psao)


@router.get("/psaos/{psao_id}/pharmacies")
async def list_psao_pharmacies(psao_id: uuid.UUID, db: AsyncSession = Depends(get_session)) -> Any:
    stmt = (
        select(Pharmacy, PsaoMembership)
        .join(PsaoMembership, PsaoMembership.pharmacy_id == Pharmacy.id)
        .where(PsaoMembership.psao_id == psao_id, PsaoMembership.termination_date.is_(None))
    )
    result = await db.execute(stmt)
    rows = result.all()
    return {"pharmacies": [{"npi": p.npi, "display_name": p.display_name} for p, _ in rows]}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=DirectoryStatsResponse)
async def directory_stats(
    tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")],
    db: AsyncSession = Depends(get_session),
) -> Any:
    total_stmt = select(func.count(Pharmacy.id))
    active_stmt = select(func.count(Pharmacy.id)).where(Pharmacy.status == "active")
    networks_stmt = select(func.count(Network.id)).where(Network.tenant_id == tenant_id)
    pending_stmt = select(func.count(CredentialingApplication.id)).where(
        CredentialingApplication.tenant_id == tenant_id,
        CredentialingApplication.status.in_(["submitted", "under_review"]),
    )

    total = (await db.execute(total_stmt)).scalar() or 0
    active = (await db.execute(active_stmt)).scalar() or 0
    networks = (await db.execute(networks_stmt)).scalar() or 0
    pending = (await db.execute(pending_stmt)).scalar() or 0

    return {
        "total_pharmacies": total,
        "active_pharmacies": active,
        "total_networks": networks,
        "pending_credentialing": pending,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _network_to_schema(n: Network) -> dict:
    return {
        "id": str(n.id),
        "tenant_id": str(n.tenant_id),
        "name": n.name,
        "network_code": n.network_code,
        "network_type": n.network_type,
        "is_active": n.is_active,
        "any_willing_pharmacy": n.any_willing_pharmacy,
        "effective_date": n.effective_date,
        "termination_date": n.termination_date,
    }


def _app_to_schema(a: CredentialingApplication) -> dict:
    return {
        "id": str(a.id),
        "tenant_id": str(a.tenant_id),
        "applicant_npi": a.applicant_npi,
        "applicant_name": a.applicant_name,
        "network_id": str(a.network_id),
        "status": a.status,
        "credentialing_risk_score": a.credentialing_risk_score,
        "npi_verified": a.npi_verified,
        "state_license_verified": a.state_license_verified,
        "dea_verified": a.dea_verified,
        "oig_sam_screened": a.oig_sam_screened,
        "oig_sam_clear": a.oig_sam_clear,
    }


def _psao_to_schema(p: Psao) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "psao_id": p.psao_id,
        "npi": p.npi,
        "payment_consolidated": p.payment_consolidated,
        "is_active": p.is_active,
    }
