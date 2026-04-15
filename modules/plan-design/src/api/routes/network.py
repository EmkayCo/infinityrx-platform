"""Network API routes — pharmacies, adequacy, AWP applications."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from shared.auth.dependencies import get_current_user

from src.api.dependencies import DBSession, TenantId
from src.api.schemas.network import (
    AWPApplicationCreate,
    AWPApplicationResponse,
    AWPApplicationUpdate,
    NetworkAdequacyResponse,
    NetworkCreate,
    NetworkPharmacyCreate,
    NetworkPharmacyResponse,
    NetworkResponse,
    NetworkUpdate,
)
from src.services.network import NetworkService

router = APIRouter(
    prefix="/networks",
    tags=["networks"],
    dependencies=[Depends(get_current_user)],
)

# ---------------------------------------------------------------------------
# Network CRUD
# ---------------------------------------------------------------------------


@router.post("", response_model=NetworkResponse, status_code=status.HTTP_201_CREATED)
async def create_network(
    body: NetworkCreate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = NetworkService(db, tenant_id)
    network = svc.create_network(body.model_dump())
    db.commit()
    return network


@router.get("", response_model=list[NetworkResponse])
async def list_networks(
    status_filter: str | None = None,
    db: DBSession = Depends(),
    tenant_id: TenantId = Depends(),
) -> Any:
    svc = NetworkService(db, tenant_id)
    return svc.list_networks(status=status_filter)


@router.get("/{network_id}", response_model=NetworkResponse)
async def get_network(
    network_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = NetworkService(db, tenant_id)
    network = svc.get_network(network_id)
    if network is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Network not found")
    return network


@router.patch("/{network_id}", response_model=NetworkResponse)
async def update_network(
    network_id: uuid.UUID,
    body: NetworkUpdate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = NetworkService(db, tenant_id)
    network = svc.update_network(network_id, body.model_dump(exclude_none=True))
    if network is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Network not found")
    db.commit()
    return network


# ---------------------------------------------------------------------------
# Network Pharmacies
# ---------------------------------------------------------------------------


@router.post("/{network_id}/pharmacies", response_model=NetworkPharmacyResponse, status_code=status.HTTP_201_CREATED)
async def add_pharmacy(
    network_id: uuid.UUID,
    body: NetworkPharmacyCreate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = NetworkService(db, tenant_id)
    pharmacy = svc.add_pharmacy(network_id, body.model_dump())
    db.commit()
    return pharmacy


@router.get("/{network_id}/pharmacies", response_model=list[NetworkPharmacyResponse])
async def list_pharmacies(
    network_id: uuid.UUID,
    pharmacy_type: str | None = None,
    db: DBSession = Depends(),
    tenant_id: TenantId = Depends(),
) -> Any:
    svc = NetworkService(db, tenant_id)
    return svc.list_pharmacies(network_id, pharmacy_type=pharmacy_type)


@router.delete("/{network_id}/pharmacies/{pharmacy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_pharmacy(
    network_id: uuid.UUID,
    pharmacy_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
) -> None:
    svc = NetworkService(db, tenant_id)
    removed = svc.remove_pharmacy(pharmacy_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pharmacy not found")
    db.commit()


# ---------------------------------------------------------------------------
# Network Adequacy
# ---------------------------------------------------------------------------


@router.get("/{network_id}/adequacy", response_model=NetworkAdequacyResponse)
async def get_network_adequacy(
    network_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = NetworkService(db, tenant_id)
    return svc.calculate_adequacy(network_id)


# ---------------------------------------------------------------------------
# AWP Applications
# ---------------------------------------------------------------------------


@router.post("/{network_id}/awp-applications", response_model=AWPApplicationResponse, status_code=status.HTTP_201_CREATED)
async def submit_awp_application(
    network_id: uuid.UUID,
    body: AWPApplicationCreate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = NetworkService(db, tenant_id)
    app = svc.submit_awp_application(network_id, body.model_dump())
    db.commit()
    return app


@router.get("/{network_id}/awp-applications", response_model=list[AWPApplicationResponse])
async def list_awp_applications(
    network_id: uuid.UUID,
    status_filter: str | None = None,
    db: DBSession = Depends(),
    tenant_id: TenantId = Depends(),
) -> Any:
    svc = NetworkService(db, tenant_id)
    return svc.list_awp_applications(network_id, status=status_filter)


@router.patch("/{network_id}/awp-applications/{app_id}", response_model=AWPApplicationResponse)
async def update_awp_application(
    network_id: uuid.UUID,
    app_id: uuid.UUID,
    body: AWPApplicationUpdate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = NetworkService(db, tenant_id)
    app = svc.update_awp_application(app_id, body.model_dump(exclude_none=True))
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AWP application not found")
    db.commit()
    return app
