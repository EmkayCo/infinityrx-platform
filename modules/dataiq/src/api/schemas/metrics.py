"""Pydantic schemas for DataIQ metrics API."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MetricDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    metric_key: str
    name: str
    description: str | None
    category: str
    calculation_type: str
    spc_enabled: bool
    spc_window_days: int
    spc_sigma_threshold: Decimal
    created_at: datetime


class MetricSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    metric_key: str
    snapshot_date: date
    snapshot_hour: int | None
    value: Decimal
    moving_average: Decimal | None
    upper_control_limit: Decimal | None
    lower_control_limit: Decimal | None
    is_anomalous: bool


class MetricHistoryResponse(BaseModel):
    metric_key: str
    snapshots: list[MetricSnapshotResponse]
    mean: Decimal | None
    ucl: Decimal | None
    lcl: Decimal | None


class AnomalyResponse(BaseModel):
    metric_key: str
    snapshot_date: date
    value: Decimal
    ucl: Decimal
    lcl: Decimal
    rule_violations: list[str] = Field(default_factory=list)


class DecompositionRequest(BaseModel):
    start_period: date
    end_period: date
    drug_class: str | None = None


class DecompositionResponse(BaseModel):
    period_pair: str
    drug_class: str
    utilization_effect: Decimal
    price_effect: Decimal
    mix_effect: Decimal
    total_delta: Decimal
    old_spend: Decimal
    new_spend: Decimal


class TopDrugsRequest(BaseModel):
    start_date: date
    end_date: date
    limit: int = Field(default=10, ge=1, le=100)
    sort_by: str = "spend"


class TopDrugResponse(BaseModel):
    ndc: str
    drug_name: str
    total_spend: Decimal
    claim_count: int
    avg_cost_per_claim: Decimal
    rank: int


class DataQualityScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score_date: date
    overall_score: Decimal
    volume_score: Decimal | None
    completeness_score: Decimal | None
    format_score: Decimal | None
    timeliness_score: Decimal | None
    consistency_score: Decimal | None
    referential_score: Decimal | None
    issues: list[dict[str, Any]] | None


class InsightAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    insight_type: str
    severity: str
    title: str
    description: str
    metric_key: str | None
    metric_value: Decimal | None
    threshold_value: Decimal | None
    affected_entity_type: str | None
    affected_entity_name: str | None
    recommended_action: str | None
    acknowledged_at: datetime | None
    created_at: datetime


class InsightSummaryResponse(BaseModel):
    total_unacknowledged: int
    critical_count: int
    warning_count: int
    info_count: int


class BenchmarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    metric_key: str
    benchmark_type: str
    target_value: Decimal | None
    warning_threshold: Decimal | None
    critical_threshold: Decimal | None
    is_active: bool


class BenchmarkCreateRequest(BaseModel):
    name: str
    metric_key: str
    benchmark_type: str
    target_value: Decimal | None = None
    warning_threshold: Decimal | None = None
    critical_threshold: Decimal | None = None
    comparison_operator: str = "gte"


class NetworkAdequacyResponse(BaseModel):
    total_members: int
    covered_members: int
    pct_members_covered: Decimal
    radius_miles: Decimal
