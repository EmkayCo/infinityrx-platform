"""Manufacturer self-service program builder routes.

Endpoints:
  POST/GET  /manufacturer-configs
  GET/PATCH  /manufacturer-configs/{id}
  POST  /manufacturer-configs/{id}/submit-for-review
  POST  /manufacturer-configs/{id}/recommend-copay
  POST  /manufacturer-configs/{id}/promote
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from shared.auth.dependencies import CurrentUser, get_current_user

from src.api.schemas.programs import (
    CopayRecommendRequest,
    CopayRecommendResponse,
    ManufacturerConfigCreateRequest,
    ManufacturerConfigResponse,
    ManufacturerConfigUpdateRequest,
)
from src.models.tables import ManufacturerProgramConfig, ProgramActivityLog
from src.services.copay_recommender import (
    CopayRecommender,
    CopayRecommenderInput,
)

router = APIRouter(prefix="/manufacturer-configs", tags=["manufacturer"])


def _get_db():  # pragma: no cover
    from shared.db.session import get_db
    yield from get_db()


def _not_found(config_id: uuid.UUID, corr: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "CONFIG_NOT_FOUND", "message": f"Manufacturer config {config_id} not found", "correlation_id": corr}},
    )


@router.post("", response_model=ManufacturerConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_manufacturer_config(
    body: ManufacturerConfigCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())
    config = ManufacturerProgramConfig(
        tenant_id=current_user.tenant_id,
        manufacturer_id=body.manufacturer_id,
        wizard_data=body.wizard_data,
    )
    db.add(config)

    log_entry = ProgramActivityLog(
        tenant_id=current_user.tenant_id,
        program_id=None,
        entity_type="manufacturer_config",
        entity_id=config.id,
        action="created",
        performed_by=current_user.id,
        before_state=None,
        after_state={"review_status": "draft"},
        correlation_id=uuid.UUID(correlation_id),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(config)
    return config


@router.get("", response_model=list[ManufacturerConfigResponse])
async def list_manufacturer_configs(
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    return (
        db.query(ManufacturerProgramConfig)
        .filter_by(tenant_id=current_user.tenant_id)
        .order_by(ManufacturerProgramConfig.created_at.desc())
        .all()
    )


@router.get("/{config_id}", response_model=ManufacturerConfigResponse)
async def get_manufacturer_config(
    config_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())
    config = db.query(ManufacturerProgramConfig).filter_by(
        id=config_id, tenant_id=current_user.tenant_id
    ).first()
    if not config:
        raise _not_found(config_id, correlation_id)
    return config


@router.patch("/{config_id}", response_model=ManufacturerConfigResponse)
async def update_manufacturer_config(
    config_id: uuid.UUID,
    body: ManufacturerConfigUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())
    config = db.query(ManufacturerProgramConfig).filter_by(
        id=config_id, tenant_id=current_user.tenant_id
    ).first()
    if not config:
        raise _not_found(config_id, correlation_id)

    if config.review_status not in ("draft",):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "NOT_EDITABLE", "message": "Config can only be edited in draft status", "correlation_id": correlation_id}},
        )

    update_data = body.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(config, key, value)

    db.commit()
    db.refresh(config)
    return config


@router.post("/{config_id}/recommend-copay", response_model=CopayRecommendResponse)
async def recommend_copay(
    config_id: uuid.UUID,
    body: CopayRecommendRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    """AI (deterministic rule-based) copay recommendation."""
    correlation_id = str(uuid.uuid4())
    config = db.query(ManufacturerProgramConfig).filter_by(
        id=config_id, tenant_id=current_user.tenant_id
    ).first()
    if not config:
        raise _not_found(config_id, correlation_id)

    recommender = CopayRecommender()
    inputs = CopayRecommenderInput(
        drug_wac_per_30_day=body.drug_wac_per_30_day,
        commercial_payer_mix_fraction=body.commercial_payer_mix_fraction,
        competitive_benchmark_copay=body.competitive_benchmark_copay,
        gtn_budget_per_patient=body.gtn_budget_per_patient,
        avg_fills_per_year=body.avg_fills_per_year,
    )
    recommendation = recommender.recommend(inputs)

    # Persist recommendations on the config for audit trail
    config.ai_recommendations = {
        "recommended_copay": recommendation.recommended_copay,
        "recommended_per_fill_cap": recommendation.recommended_per_fill_cap,
        "recommended_annual_max": recommendation.recommended_annual_max,
        "accumulator_strategy": recommendation.accumulator_strategy,
        "rationale": recommendation.rationale,
        "scores": recommendation.scores,
        "input": {
            "drug_wac_per_30_day": body.drug_wac_per_30_day,
            "commercial_payer_mix_fraction": body.commercial_payer_mix_fraction,
            "competitive_benchmark_copay": body.competitive_benchmark_copay,
            "gtn_budget_per_patient": body.gtn_budget_per_patient,
            "avg_fills_per_year": body.avg_fills_per_year,
        },
    }
    config.recommended_copay_amount = Decimal(recommendation.recommended_copay).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    config.recommended_per_fill_cap = Decimal(recommendation.recommended_per_fill_cap).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    config.recommended_annual_max = Decimal(recommendation.recommended_annual_max).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    config.accumulator_strategy = recommendation.accumulator_strategy

    db.commit()

    return CopayRecommendResponse(
        recommended_copay=recommendation.recommended_copay,
        recommended_per_fill_cap=recommendation.recommended_per_fill_cap,
        recommended_annual_max=recommendation.recommended_annual_max,
        accumulator_strategy=recommendation.accumulator_strategy,
        rationale=recommendation.rationale,
        scores=recommendation.scores,
    )


@router.post("/{config_id}/submit-for-review", response_model=ManufacturerConfigResponse)
async def submit_for_review(
    config_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    correlation_id = str(uuid.uuid4())
    config = db.query(ManufacturerProgramConfig).filter_by(
        id=config_id, tenant_id=current_user.tenant_id
    ).first()
    if not config:
        raise _not_found(config_id, correlation_id)

    if config.review_status != "draft":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "NOT_DRAFT", "message": "Only draft configs can be submitted for review", "correlation_id": correlation_id}},
        )

    config.review_status = "submitted"
    config.submitted_at = datetime.now(UTC)

    log_entry = ProgramActivityLog(
        tenant_id=current_user.tenant_id,
        program_id=config.program_id,
        entity_type="manufacturer_config",
        entity_id=config.id,
        action="submitted_for_review",
        performed_by=current_user.id,
        before_state={"review_status": "draft"},
        after_state={"review_status": "submitted"},
        correlation_id=uuid.UUID(correlation_id),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(config)
    return config


@router.post("/{config_id}/promote", response_model=ManufacturerConfigResponse)
async def promote_config(
    config_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db=Depends(_get_db),
) -> Any:
    """IFX operator promotes a reviewed+approved manufacturer config to production."""
    correlation_id = str(uuid.uuid4())
    config = db.query(ManufacturerProgramConfig).filter_by(
        id=config_id, tenant_id=current_user.tenant_id
    ).first()
    if not config:
        raise _not_found(config_id, correlation_id)

    if config.review_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "NOT_APPROVED", "message": "Config must be approved before promoting to live", "correlation_id": correlation_id}},
        )

    config.review_status = "live"
    config.reviewed_by = current_user.id

    log_entry = ProgramActivityLog(
        tenant_id=current_user.tenant_id,
        program_id=config.program_id,
        entity_type="manufacturer_config",
        entity_id=config.id,
        action="promoted_to_live",
        performed_by=current_user.id,
        before_state={"review_status": "approved"},
        after_state={"review_status": "live"},
        correlation_id=uuid.UUID(correlation_id),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(config)
    return config
