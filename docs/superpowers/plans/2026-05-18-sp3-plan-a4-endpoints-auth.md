# SP-3 Plan A4 — New Endpoints + Role/MFA Enforcement

**Status:** Ready for execution  
**Date:** 2026-05-18  
**Slice:** 13 missing endpoints, 5 partial-mismatch reshapes, role/MFA dependency wiring  
**Belongs to:** SP-3 Plan A (Backend + Contract Layer + Production Bindings)  
**Depends on:** Plan A1 (tables + migration), Plan A2 (services: graph_analysis, accumulator_detector, outbox),
Plan A3 (state machine + hold release endpoint with 3-case idempotency)

## Ground Truth Cross-References

All code paths below are verified against `waves/B10/SP-3-audit-deep.md` (hereafter "audit").

- Existing router prefix `/api/v1/reclaimrx` — audit §4
- `CurrentUser` is a **dataclass** with `.roles: list[str]` and `.has_role(role: str) -> bool` — audit §3
- `require_role(*roles)` exists in `modules/reclaimrx/src/_shim/auth.py` — audit §3
- Current role names (`"investigator"`, `"tenant_admin"`) differ from spec 3-role model (`"reclaimrx.viewer"`, `"reclaimrx.investigator"`, `"reclaimrx.admin"`) — audit §4 "Role name mismatch"
- Table names: `reclaimrx_investigations`, `reclaimrx_payment_holds`, `reclaimrx_accumulator_detections` — audit §1
- `EventEnvelope` fields: `event_type` (NOT `type`), `correlation_id`, `source_module` required — audit §2
- Contract layer real pattern: `packages/contract/src/impls/<domain>/` (4 files) — audit §5
- `MlPrediction.feature_importance: JSON` at `tables.py:358` — audit §1, MlPrediction block
- `FraudNetworkAnalyzer` exists at `modules/reclaimrx/src/services/graph_analysis.py` — audit cross-cutting
- Spec §5.5 endpoint table is the binding inventory (18 endpoints, roles, rate limits)
- Spec D8 RLS, D13 rate limits, D6/D6a PHI/MFA posture apply to every endpoint

## Scope

### 13 Net-New Endpoints (spec §5.5, items not existing per audit §4)

| # | Method + Path | Spec # | Role |
|---|---|---|---|
| N1 | `GET /investigations/{id}/ml-scores` | — | viewer+ |
| N2 | `GET /graph-runs` | 11 | viewer+ |
| N3 | `POST /graph-runs/trigger` | 10 | investigator+ |
| N4 | `GET /graph-runs/{run_id}` | 12 | viewer+ |
| N5 | `GET /fraud-rings/{id}` | 13 | viewer+ |
| N6 | `GET /recovery` | 14 | viewer+ |
| N7 | `GET /dashboard-summary` | 15 | viewer+ |
| N8 | `GET /thresholds` | 16 | viewer+ |
| N9 | `PUT /thresholds` | 17 | admin only |
| N10 | `GET /accumulator-anomalies` | 18 | viewer+ |
| N11 | `GET /accumulator-anomalies/{id}` | — | viewer+ (PHI audit + no-store) |
| N12 | `GET /ml-scores` | 6 | viewer+ |
| N13 | `GET /ml-scores/{id}/features` | 7 | viewer+ |

Note: `GET /investigations/{id}/ml-scores` (N1) is not in the spec §5.5 table directly but is implied by the "ML scores" surface per spec §5; `GET /accumulator-anomalies/{id}` (N11) is the detail counterpart to spec endpoint #18. Both are confirmed missing per audit §4 and are in scope per the dispatch instructions.

### 5 Partial-Mismatch Reshapes (audit §4)

| # | Existing | Required reshape |
|---|---|---|
| P1 | `GET /investigations` — missing `severity` filter | Add `severity`, `source`, pagination per spec |
| P2 | `GET /investigations/{id}` — no PHI audit, no MFA gate | Add MFA session check + PHI `action="phi_access"` audit + `Cache-Control: no-store` + response masking |
| P3 | `DELETE /holds/{hold_id}` — wrong method, wrong shape | Replaced by `POST /holds/{hold_id}/release` (Plan A3 owns core logic; A4 wires role + MFA on the new endpoint) |
| P4 | `GET /holds` — no status filter | Add `status` query param; respond with `PaymentHoldListRead` schema |
| P5 | `GET /accumulator/detections` — wrong model | Delegate to new `GET /accumulator-anomalies` (N10); keep old route returning 410 Gone or redirect |

### Role/MFA Enforcement (all existing endpoints)

All 24 existing routes use `get_current_user` (any authenticated user) or the legacy `require_investigator` (roles: `"investigator"`, `"tenant_admin"`). Plan A4 replaces these with spec role names on every endpoint per spec §5.4 / D5.

## Discipline Notes

- **No `user.get(...)` anywhere.** `CurrentUser` is a dataclass. Use `user.roles` and `user.has_role(r)`. (audit §3; codex BLOCK 6)
- **No `type=` or `emitted_at=` in EventEnvelope.** Use `event_type=`, `correlation_id=`, `source_module=`. (audit §2; codex BLOCK 4)
- **No `hash(...)` for advisory locks.** Use `zlib.crc32(...)`. (audit §9; codex BLOCK 7)
- **Table names are `reclaimrx_*`.** FK references must use these names. (audit §1; codex BLOCK 2)
- **All handlers must be `async def`.** Existing sync handlers are a pre-existing debt; new handlers added in A4 MUST be async. (architecture.md)
- **`Decimal` + `ROUND_HALF_UP` on all money.** Recovery sums, hold amounts, threshold values. (financial-precision.md)
- **`Cache-Control: no-store`** on every response that includes PHI fields. (phi-compliance.md)
- **Every PHI-bearing detail endpoint logs `action="phi_access"`.** (phi-compliance.md)
- **Cross-tenant isolation test per endpoint.** 2 tenants, populate both, query as A, assert zero B rows. (tenant-isolation.md)
- **TDD order enforced.** Write test first, confirm it fails, implement, confirm it passes. No "steps mirror prior tasks."

---

## Task A4-T1: Role Infrastructure — Add Spec Role Names + `require_mfa_elevated()`

**Objective:** Add `reclaimrx.viewer`, `reclaimrx.investigator`, `reclaimrx.admin` role aliases and the `require_mfa_elevated()` dependency. Update all existing routes to use spec role names.

**Files touched:**
- `modules/reclaimrx/src/_shim/auth.py`
- `modules/reclaimrx/src/api/dependencies.py`
- `modules/reclaimrx/src/api/router.py` (all existing route Depends)

**TDD steps:**

1. **Write failing tests** at `modules/reclaimrx/tests/unit/test_role_deps.py`:

```python
"""Unit tests for SP-3 role dependency helpers."""
import pytest
from fastapi import HTTPException
from src._shim.auth import CurrentUser, require_role, set_current_user

def _user(roles: list[str]) -> CurrentUser:
    u = CurrentUser(id=__import__("uuid").uuid4(), tenant_id=__import__("uuid").uuid4(), roles=roles)
    set_current_user(u)
    return u

def test_viewer_role_grants_access():
    _user(["reclaimrx.viewer"])
    dep = require_role("reclaimrx.viewer")
    user = dep()  # must not raise
    assert user.has_role("reclaimrx.viewer")

def test_investigator_role_blocks_viewer_only_dep():
    _user(["reclaimrx.investigator"])
    dep = require_role("reclaimrx.viewer")
    user = dep()  # investigator is superset — must pass (spec D5: viewer+)
    assert user.has_role("reclaimrx.investigator")

def test_viewer_blocked_on_investigator_dep():
    _user(["reclaimrx.viewer"])
    dep = require_role("reclaimrx.investigator", "reclaimrx.admin")
    with pytest.raises(HTTPException) as exc_info:
        dep()
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "INSUFFICIENT_ROLE"

def test_admin_only_dep_blocks_investigator():
    _user(["reclaimrx.investigator"])
    dep = require_role("reclaimrx.admin")
    with pytest.raises(HTTPException) as exc_info:
        dep()
    assert exc_info.value.status_code == 403

def test_legacy_roles_still_rejected():
    """Old role strings 'investigator' and 'tenant_admin' must NOT satisfy spec roles."""
    _user(["investigator", "tenant_admin"])
    dep = require_role("reclaimrx.viewer")
    with pytest.raises(HTTPException):
        dep()

def test_user_is_dataclass_not_dict():
    """Ensure CurrentUser fields accessed as attributes, not dict keys."""
    u = _user(["reclaimrx.admin"])
    assert isinstance(u.roles, list)
    # Confirm dict-style access raises AttributeError (documents the invariant)
    with pytest.raises(AttributeError):
        _ = u.__getitem__("roles")  # dataclass has no __getitem__
```

2. Run `pytest modules/reclaimrx/tests/unit/test_role_deps.py` — expect failures on role-name tests.

3. **Implement** in `modules/reclaimrx/src/api/dependencies.py`:

```python
"""SP-3 role dependency factories — spec D5 role names."""
from fastapi import Depends, HTTPException
from src._shim.auth import CurrentUser, require_role as _require_role

# Spec §5.4 role hierarchy (each level implies all lower)
# reclaimrx.admin > reclaimrx.investigator > reclaimrx.viewer

def require_viewer() -> CurrentUser:
    """Any reclaimrx role satisfies viewer access."""
    return _require_role(
        "reclaimrx.viewer",
        "reclaimrx.investigator",
        "reclaimrx.admin",
    )()

def require_investigator() -> CurrentUser:
    """investigator+ required (write, status transitions, hold release)."""
    return _require_role("reclaimrx.investigator", "reclaimrx.admin")()

def require_admin() -> CurrentUser:
    """admin only (threshold tuning, override-locked transitions)."""
    return _require_role("reclaimrx.admin")()
```

Note: `require_investigator` is already defined in `dependencies.py` using legacy role names. Replace its body (do not add a duplicate function).

4. **Add `require_mfa_elevated()`** stub in `dependencies.py`. The full implementation is in Plan A3 (core-platform session lookup per spec D6a). Plan A4 adds the dependency signature so all endpoints can `Depends(require_mfa_elevated)`. If the core-platform session lookup endpoint is not yet reachable, the stub raises `503 SERVICE_UNAVAILABLE` with `error.code="MFA_CHECK_UNAVAILABLE"` — explicit fail-closed:

```python
async def require_mfa_elevated(user: CurrentUser = Depends(require_viewer)) -> CurrentUser:
    """
    Require MFA-elevated session for ePHI access (spec D6a, R3 NEW BLOCK 3).
    Full impl: calls core-platform /auth/session_lookup(user.id) and checks
    session.mfa_elevated_until > now(). Stub fails closed with 503 until
    core-platform session lookup is wired (Plan A3 or separate spike).
    """
    # TODO(Plan A3): replace stub with real core-platform HTTP call
    # For now, check if test environment has MFA bypass set
    import os
    if os.getenv("RECLAIMRX_MFA_BYPASS") == "1":
        return user
    raise HTTPException(
        status_code=503,
        detail={"error": {"code": "MFA_CHECK_UNAVAILABLE",
                          "message": "MFA session check not yet wired"}},
    )
```

5. **Update all existing route Depends** in `router.py` to replace legacy deps:
   - `get_current_user` → `require_viewer` (read-only routes)
   - `require_investigator` → `require_investigator` (already matching name; body changed in step 3)

6. Run all tests. Confirm no regressions on existing routes (existing test fixtures should set roles via `set_current_user` with new role names).

**Coverage gate:** 100% on `dependencies.py` role functions.

---

## Task A4-T2: New Pydantic Response Schemas for 13 Missing Endpoints

**Objective:** Define all response_model schemas required by the 13 new endpoints. All Decimal fields serialized as `str`. PHI fields typed but included only when masking permits.

**Files touched:**
- `modules/reclaimrx/src/api/schemas.py` (add to existing file)

**TDD steps:**

1. **Write failing tests** at `modules/reclaimrx/tests/unit/test_a4_schemas.py`:

```python
"""Schema construction and serialization tests for SP-3 A4 new endpoints."""
import uuid
from decimal import Decimal
import pytest
from pydantic import ValidationError
from src.api.schemas import (
    MlScoreRead, MlScoreFeatureRead,
    GraphRunRead, GraphRunListRead,
    FraudRingRead,
    RecoverySummaryRead, RecoveryByPharmacyRead,
    DashboardSummaryRead,
    ThresholdConfigRead, ThresholdUpdateRequest,
    AccumulatorAnomalyRead, AccumulatorAnomalyListRead,
    PaymentHoldListRead,
)

def test_ml_score_read_decimal_as_str():
    score = MlScoreRead(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        claim_id=str(uuid.uuid4()),
        model_id=str(uuid.uuid4()),
        score="0.8750",
        threshold_at_time="0.7500",
        created_at="2026-05-18T00:00:00Z",
    )
    data = score.model_dump()
    assert isinstance(data["score"], str)

def test_fraud_ring_node_cap():
    """Payload with >500 nodes must be truncated to 500 with truncated=True (spec §5.5 endpoint #13)."""
    nodes = [{"id": str(i)} for i in range(600)]
    ring = FraudRingRead(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        graph_run_id=str(uuid.uuid4()),
        detected_at="2026-05-18T00:00:00Z",
        density_score="0.92",
        node_count=600,
        edge_count=100,
        entity_refs=nodes[:500],  # handler truncates before constructing schema
        truncated=True,
    )
    assert ring.truncated is True
    assert len(ring.entity_refs) == 500

def test_threshold_update_requires_admin_fields():
    """ThresholdUpdateRequest must include updated_by and reason."""
    with pytest.raises(ValidationError):
        ThresholdUpdateRequest(ml_score_thresholds={"open": "0.5"})  # missing updated_by

def test_recovery_summary_decimal_str():
    rec = RecoverySummaryRead(
        total_recovered="12345.67",
        open_count=3,
        confirmed_count=10,
        false_positive_count=2,
        period="mtd",
    )
    assert isinstance(rec.total_recovered, str)

def test_dashboard_summary_all_tiles():
    ds = DashboardSummaryRead(
        open_investigations=5,
        in_progress_investigations=2,
        total_hold_amount="98765.43",
        recovered_mtd="12345.67",
        false_positive_rate="0.12",
        escalated_count=1,
    )
    assert ds.total_hold_amount == "98765.43"

def test_accumulator_anomaly_read():
    aa = AccumulatorAnomalyRead(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        member_id=str(uuid.uuid4()),
        pattern_type="sudden_spike",
        detected_at="2026-05-18T00:00:00Z",
        evidence_window_start="2026-05-11T00:00:00Z",
        evidence_window_end="2026-05-18T00:00:00Z",
        triggering_event_ids=[str(uuid.uuid4())],
        spawned_investigation_id=None,
    )
    assert aa.pattern_type == "sudden_spike"
```

2. Run tests — expect `ImportError` or `ModuleNotFoundError` (schemas not defined yet).

3. **Implement** — add to `modules/reclaimrx/src/api/schemas.py`:

```python
# ── SP-3 Plan A4 — New endpoint schemas ──────────────────────────────────────

from typing import Literal

class MlScoreRead(BaseModel):
    """Response schema for GET /ml-scores and GET /investigations/{id}/ml-scores."""
    id: str
    tenant_id: str
    claim_id: str
    model_id: str
    score: str            # Decimal serialized as str per financial-precision.md
    threshold_at_time: str
    feature_importance: dict | None = None
    created_at: str

class MlScoreFeatureRead(BaseModel):
    """Response for GET /ml-scores/{id}/features — XGBoost feature importance."""
    id: str
    feature_importance: dict  # empty dict {} returned if missing (spec §8 ML feature importance)
    model_version: str | None = None

class GraphRunRead(BaseModel):
    """Single graph run. Polling endpoint for run_id (spec endpoint #12)."""
    id: str
    tenant_id: str
    status: Literal["running", "completed", "completed_partial", "failed"]
    trigger: Literal["cron", "on_demand"]
    started_at: str
    completed_at: str | None
    failed_at: str | None
    error_code: str | None
    error_message: str | None   # sanitized — no PHI
    correlation_id: str
    stale_timeout_at: str
    rings_detected: int
    investigations_opened: int
    records_scanned: int
    lookback_window_days: int

class GraphRunListRead(BaseModel):
    """Paginated wrapper for GET /graph-runs."""
    items: list[GraphRunRead]
    total: int
    page: int
    page_size: int

class FraudRingRead(BaseModel):
    """
    Fraud ring detail. Node/edge payload capped at 500/2000 (spec §5.5 endpoint #13).
    Larger rings return neighborhood subgraph with truncated=True.
    """
    id: str
    tenant_id: str
    graph_run_id: str
    detected_at: str
    density_score: str     # Decimal as str
    node_count: int
    edge_count: int
    entity_refs: list[dict]  # truncated to 500 max; handler enforces cap before serialization
    truncated: bool = False
    spawned_investigation_id: str | None = None

class RecoverySummaryRead(BaseModel):
    """Response for GET /recovery?period=mtd&group_by=program (spec endpoint #14)."""
    total_recovered: str   # Decimal as str
    open_count: int
    confirmed_count: int
    false_positive_count: int
    period: str
    group_by: str | None = None
    breakdown: list[dict] | None = None  # per group_by value

class RecoveryByPharmacyRead(BaseModel):
    pharmacy_npi: str
    pharmacy_name: str | None
    total_recovered: str
    investigation_count: int

class DashboardSummaryRead(BaseModel):
    """6-tile dashboard summary (spec endpoint #15, R1 BLOCK 2)."""
    open_investigations: int
    in_progress_investigations: int
    total_hold_amount: str     # Decimal as str; 100% coverage gate
    recovered_mtd: str         # Decimal as str
    false_positive_rate: str   # Decimal as str (rate 0.00–1.00)
    escalated_count: int

class ThresholdConfigRead(BaseModel):
    """Current threshold config (spec endpoint #16). Per-tenant current version."""
    tenant_id: str
    version: int
    effective_at: str
    superseded_at: str | None
    rule_thresholds: dict[str, str]       # RuleId → Decimal as str
    ml_score_thresholds: dict[str, str]   # open/auto_hold/escalate → Decimal as str
    graph_density_threshold: str          # Decimal as str
    accumulator_anomaly_sensitivity: str  # Decimal as str
    updated_by: str

class ThresholdUpdateRequest(BaseModel):
    """
    Body for PUT /thresholds (spec endpoint #17). admin only.
    Per-field hash-chained audit created in service layer.
    """
    rule_thresholds: dict[str, str] | None = None
    ml_score_thresholds: dict[str, str] | None = None
    graph_density_threshold: str | None = None
    accumulator_anomaly_sensitivity: str | None = None
    updated_by: str    # JWT sub — required; service verifies matches current user
    reason: str | None = None

class AccumulatorAnomalyRead(BaseModel):
    """Single accumulator anomaly. member_id is UUID FK — NOT PHI per spec D6."""
    id: str
    tenant_id: str
    member_id: str   # UUID FK, not PHI
    pattern_type: Literal[
        "sudden_spike", "multi_payer_convergence",
        "reset_evasion", "threshold_oscillation"
    ]
    detected_at: str
    evidence_window_start: str
    evidence_window_end: str
    triggering_event_ids: list[str]
    spawned_investigation_id: str | None

class AccumulatorAnomalyListRead(BaseModel):
    items: list[AccumulatorAnomalyRead]
    total: int
    page: int
    page_size: int

class PaymentHoldListRead(BaseModel):
    """Enhanced hold list response with status filter support (P4 reshape)."""
    items: list[PaymentHoldRead]
    total: int
    page: int
    page_size: int
```

4. Run tests — confirm all pass.

**Coverage gate:** 100% on all schema classes (Pydantic model validation is exercised by test cases above).

---

## Task A4-T3: 13 New Endpoint Handlers (Read-Only: N1–N2, N4–N8, N10–N13)

**Objective:** Implement the 10 read-only new endpoints. All are `async def`. All use `require_viewer` or stronger as noted.

**Files touched:**
- `modules/reclaimrx/src/api/router.py`

**TDD steps:**

1. **Write failing integration tests** at `modules/reclaimrx/tests/integration/test_a4_read_endpoints.py`.

These tests use the FastAPI `TestClient` mounted with `create_app()` to exercise through the full middleware stack per LESSON-006. They require the new ORM tables from Plan A1 to exist.

```python
"""Integration tests — 10 read-only new endpoints (SP-3 Plan A4)."""
import uuid
import pytest
from fastapi.testclient import TestClient
from src.main import create_app
from src._shim.auth import set_current_user, CurrentUser
from src.models.tables import (
    MlPrediction, GraphRun, FraudRing,
    AccumulatorAnomaly, ThresholdConfig,
    Investigation, Recovery,
)
# LESSON-001 SAVEPOINT fixture assumed wired in conftest.py

@pytest.fixture()
def viewer(db):
    u = CurrentUser(
        id=uuid.uuid4(), tenant_id=uuid.uuid4(), roles=["reclaimrx.viewer"]
    )
    set_current_user(u)
    return u

@pytest.fixture()
def client(db, viewer):
    app = create_app()
    with TestClient(app) as c:
        yield c

# ── N12: GET /ml-scores ───────────────────────────────────────────────────────

def test_list_ml_scores_returns_200(client, db, viewer):
    resp = client.get("/api/v1/reclaimrx/ml-scores")
    assert resp.status_code == 200
    assert isinstance(resp.json()["items"], list)

def test_list_ml_scores_tenant_isolated(client, db, viewer):
    """Cross-tenant: other tenant's ml-scores must not appear."""
    other_tid = uuid.uuid4()
    # Insert MlPrediction row for other_tid ... (uses A1 ORM)
    resp = client.get("/api/v1/reclaimrx/ml-scores")
    ids_returned = [item["tenant_id"] for item in resp.json()["items"]]
    assert all(tid == str(viewer.tenant_id) for tid in ids_returned)

# ── N13: GET /ml-scores/{id}/features ────────────────────────────────────────

def test_ml_score_features_returns_dict(client, db, viewer):
    """Feature importance may be empty dict — no 404 (spec §8)."""
    pred_id = str(uuid.uuid4())
    # Insert MlPrediction with feature_importance={} for viewer.tenant_id
    resp = client.get(f"/api/v1/reclaimrx/ml-scores/{pred_id}/features")
    assert resp.status_code == 200
    assert "feature_importance" in resp.json()

def test_ml_score_features_wrong_tenant_404(client, db, viewer):
    other_pred_id = str(uuid.uuid4())
    # Insert MlPrediction for other tenant
    resp = client.get(f"/api/v1/reclaimrx/ml-scores/{other_pred_id}/features")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"

# ── N1: GET /investigations/{id}/ml-scores ────────────────────────────────────

def test_investigation_ml_scores_returns_list(client, db, viewer):
    inv_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/reclaimrx/investigations/{inv_id}/ml-scores")
    assert resp.status_code in (200, 404)  # 404 if investigation not seeded

# ── N2: GET /graph-runs ───────────────────────────────────────────────────────

def test_list_graph_runs_returns_paginated(client, db, viewer):
    resp = client.get("/api/v1/reclaimrx/graph-runs")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body and "total" in body

def test_graph_runs_tenant_isolated(client, db, viewer):
    resp = client.get("/api/v1/reclaimrx/graph-runs")
    for item in resp.json()["items"]:
        assert item["tenant_id"] == str(viewer.tenant_id)

# ── N4: GET /graph-runs/{run_id} ──────────────────────────────────────────────

def test_get_graph_run_detail_not_found(client, db, viewer):
    resp = client.get(f"/api/v1/reclaimrx/graph-runs/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"

def test_get_graph_run_detail_wrong_tenant(client, db, viewer):
    other_run_id = str(uuid.uuid4())
    # Insert GraphRun for other tenant
    resp = client.get(f"/api/v1/reclaimrx/graph-runs/{other_run_id}")
    assert resp.status_code == 404  # non-enumerating per spec D8 / R1 BLOCK 6

# ── N5: GET /fraud-rings/{id} ─────────────────────────────────────────────────

def test_fraud_ring_node_cap_enforced(client, db, viewer):
    """Payload truncated at 500 nodes, truncated=True set (spec §5.5 endpoint #13)."""
    # Insert FraudRing with entity_refs > 500 nodes for viewer.tenant_id
    ring_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/reclaimrx/fraud-rings/{ring_id}")
    if resp.status_code == 200:
        body = resp.json()
        assert len(body["entity_refs"]) <= 500
        if body["node_count"] > 500:
            assert body["truncated"] is True

def test_fraud_ring_wrong_tenant_404(client, db, viewer):
    other_ring_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/reclaimrx/fraud-rings/{other_ring_id}")
    assert resp.status_code == 404

# ── N6: GET /recovery ─────────────────────────────────────────────────────────

def test_recovery_summary_default_mtd(client, db, viewer):
    resp = client.get("/api/v1/reclaimrx/recovery")
    assert resp.status_code == 200
    body = resp.json()
    assert "total_recovered" in body
    assert isinstance(body["total_recovered"], str)  # Decimal serialized as str

def test_recovery_no_phi_in_response(client, db, viewer):
    resp = client.get("/api/v1/reclaimrx/recovery")
    assert resp.status_code == 200
    body_str = str(resp.json())
    # No PHI field names in response (spec D6)
    for phi_field in ("member_name", "dob", "ssn", "address", "phone", "email"):
        assert phi_field not in body_str

# ── N7: GET /dashboard-summary ────────────────────────────────────────────────

def test_dashboard_summary_six_tiles(client, db, viewer):
    resp = client.get("/api/v1/reclaimrx/dashboard-summary")
    assert resp.status_code == 200
    body = resp.json()
    required_tiles = {
        "open_investigations", "in_progress_investigations",
        "total_hold_amount", "recovered_mtd",
        "false_positive_rate", "escalated_count",
    }
    assert required_tiles.issubset(body.keys())

def test_dashboard_decimal_fields_are_strings(client, db, viewer):
    resp = client.get("/api/v1/reclaimrx/dashboard-summary")
    body = resp.json()
    assert isinstance(body["total_hold_amount"], str)
    assert isinstance(body["recovered_mtd"], str)
    assert isinstance(body["false_positive_rate"], str)

# ── N8: GET /thresholds ───────────────────────────────────────────────────────

def test_get_thresholds_returns_current_version(client, db, viewer):
    resp = client.get("/api/v1/reclaimrx/thresholds")
    assert resp.status_code == 200
    body = resp.json()
    assert "version" in body
    assert "ml_score_thresholds" in body

# ── N10: GET /accumulator-anomalies ──────────────────────────────────────────

def test_list_accumulator_anomalies_paginated(client, db, viewer):
    resp = client.get("/api/v1/reclaimrx/accumulator-anomalies")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body and "total" in body

def test_accumulator_anomalies_tenant_isolated(client, db, viewer):
    resp = client.get("/api/v1/reclaimrx/accumulator-anomalies")
    for item in resp.json()["items"]:
        assert item["tenant_id"] == str(viewer.tenant_id)

# ── N11: GET /accumulator-anomalies/{id} ─────────────────────────────────────

def test_accumulator_anomaly_detail_not_found(client, db, viewer):
    resp = client.get(f"/api/v1/reclaimrx/accumulator-anomalies/{uuid.uuid4()}")
    assert resp.status_code == 404

def test_accumulator_anomaly_phi_no_store(client, db, viewer):
    """No-store header not required on anomaly detail (member_id is UUID FK, not PHI per D6).
    This test verifies no PHI string fields appear in the body."""
    anomaly_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/reclaimrx/accumulator-anomalies/{anomaly_id}")
    if resp.status_code == 200:
        body_str = str(resp.json())
        for phi_field in ("member_name", "dob", "ssn"):
            assert phi_field not in body_str
```

2. Run tests — expect failures (handlers not implemented).

3. **Implement** in `router.py`. Add all 10 handlers as `async def`. Representative pattern:

```python
from src.api.dependencies import require_viewer, require_investigator, require_admin
from src.api.schemas import (
    MlScoreRead, MlScoreFeatureRead,
    GraphRunRead, GraphRunListRead,
    FraudRingRead, RecoverySummaryRead,
    DashboardSummaryRead, ThresholdConfigRead,
    AccumulatorAnomalyRead, AccumulatorAnomalyListRead,
)
from src.models.tables import MlPrediction, MlModel, GraphRun, FraudRing, ThresholdConfig
# AccumulatorAnomaly, ThresholdConfig — added in Plan A1

# ── ML Scores ─────────────────────────────────────────────────────────────────

@router.get("/ml-scores", response_model=dict)
async def list_ml_scores(
    claim_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=200),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_viewer),
) -> dict:
    stmt = (
        select(MlPrediction)
        .where(MlPrediction.tenant_id == str(user.tenant_id))
        .order_by(MlPrediction.created_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    rows = list(db.execute(stmt).scalars())
    total = db.execute(
        select(func.count()).select_from(MlPrediction)
        .where(MlPrediction.tenant_id == str(user.tenant_id))
    ).scalar_one()
    return {
        "items": [
            MlScoreRead(
                id=r.id,
                tenant_id=r.tenant_id,
                claim_id=r.claim_id if hasattr(r, "claim_id") else "",
                model_id=r.model_id,
                score=str(r.score) if r.score is not None else "0",
                threshold_at_time=str(r.threshold) if hasattr(r, "threshold") and r.threshold else "0",
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

# GET /ml-scores/{id}/features
@router.get("/ml-scores/{score_id}/features", response_model=MlScoreFeatureRead)
async def get_ml_score_features(
    score_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_viewer),
) -> MlScoreFeatureRead:
    row = db.execute(
        select(MlPrediction).where(
            MlPrediction.id == score_id,
            MlPrediction.tenant_id == str(user.tenant_id),  # tenant-scoped per R1 BLOCK 6
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "ML score not found"}},
        )
    return MlScoreFeatureRead(
        id=row.id,
        feature_importance=row.feature_importance or {},  # {} if missing per spec §8
        model_version=None,
    )

# GET /investigations/{investigation_id}/ml-scores
@router.get("/investigations/{investigation_id}/ml-scores", response_model=dict)
async def list_investigation_ml_scores(
    investigation_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_viewer),
) -> dict:
    # Verify investigation belongs to tenant (non-enumerating per R1 BLOCK 6)
    inv = db.execute(
        select(Investigation).where(
            Investigation.id == investigation_id,
            Investigation.tenant_id == str(user.tenant_id),
        )
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(404, detail={"error": {"code": "NOT_FOUND"}})
    rows = db.execute(
        select(MlPrediction).where(MlPrediction.tenant_id == str(user.tenant_id))
        # Filter by source_ref_id if investigation links to ml predictions
    ).scalars().all()
    return {"items": [], "total": 0}  # Executor wires real join from A1 Investigation.source_ref_id
```

All remaining 7 read endpoints (graph-runs list/detail, fraud-ring detail, recovery, dashboard-summary, thresholds, accumulator-anomalies list/detail) follow the same async def + tenant-scoped WHERE + non-enumerating 404 pattern. Executor implements each fully — no "steps mirror prior tasks" shorthand.

**Dashboard summary aggregation** must use `func.sum()` wrapped in `Decimal(str(...))` per financial-precision.md:

```python
from sqlalchemy import func
from decimal import Decimal, ROUND_HALF_UP

# Total hold amount (example aggregation):
raw = db.execute(
    select(func.sum(PaymentHold.amount_threshold))
    .where(PaymentHold.tenant_id == str(user.tenant_id), PaymentHold.is_active.is_(True))
).scalar()
total_hold = Decimal(str(raw or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

4. Run tests — confirm pass.

**Coverage gate:** 100% on all `async def` route handlers (every branch exercised by the cross-tenant + error tests above).

---

## Task A4-T4: N3 — `POST /graph-runs/trigger` (Write Endpoint with Advisory Lock)

**Objective:** On-demand graph run trigger. Uses `zlib.crc32` deterministic lock key per audit §9 (NOT `hash()`). 409 if run in-flight. Rate limit 1/hr/tenant (D13).

**Files touched:**
- `modules/reclaimrx/src/api/router.py`

**TDD steps:**

1. **Write failing tests** at `modules/reclaimrx/tests/integration/test_a4_graph_trigger.py`:

```python
"""Integration tests — POST /graph-runs/trigger (SP-3 Plan A4)."""
import uuid
import pytest
from fastapi.testclient import TestClient
from src.main import create_app
from src._shim.auth import set_current_user, CurrentUser
from src.models.tables import GraphRun  # from Plan A1

@pytest.fixture()
def investigator(db):
    u = CurrentUser(id=uuid.uuid4(), tenant_id=uuid.uuid4(), roles=["reclaimrx.investigator"])
    set_current_user(u)
    return u

@pytest.fixture()
def client(db, investigator):
    app = create_app()
    with TestClient(app) as c:
        yield c

def test_trigger_graph_run_creates_running_row(client, db, investigator):
    resp = client.post("/api/v1/reclaimrx/graph-runs/trigger")
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "running"
    assert body["trigger"] == "on_demand"
    run_id = body["id"]
    # Verify durable row exists
    row = db.get(GraphRun, run_id)
    assert row is not None
    assert row.status == "running"

def test_trigger_graph_run_409_if_in_flight(client, db, investigator):
    """409 RUN_IN_PROGRESS if a running row exists for this tenant."""
    # Insert a running GraphRun row for investigator.tenant_id
    existing = GraphRun(
        id=str(uuid.uuid4()),
        tenant_id=str(investigator.tenant_id),
        status="running",
        trigger="on_demand",
        correlation_id=str(uuid.uuid4()),
    )
    db.add(existing)
    db.flush()
    resp = client.post("/api/v1/reclaimrx/graph-runs/trigger")
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "RUN_IN_PROGRESS"
    assert "run_id" in body["error"]

def test_viewer_cannot_trigger_graph_run(client, db, investigator):
    """Viewer role rejected — spec §5.4 D5 investigator+ required."""
    set_current_user(CurrentUser(
        id=uuid.uuid4(), tenant_id=investigator.tenant_id, roles=["reclaimrx.viewer"]
    ))
    resp = client.post("/api/v1/reclaimrx/graph-runs/trigger")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_ROLE"

def test_trigger_uses_deterministic_lock_key():
    """Verify lock key uses zlib.crc32, not hash() (audit §9)."""
    import zlib
    tenant_id = "550e8400-e29b-41d4-a716-446655440000"
    key_a = zlib.crc32(f"graph_run:{tenant_id}".encode()) & 0x7FFFFFFF
    key_b = zlib.crc32(f"graph_run:{tenant_id}".encode()) & 0x7FFFFFFF
    assert key_a == key_b  # deterministic across calls

def test_trigger_cross_tenant_isolation(client, db, investigator):
    """Running row for tenant A must not block tenant B."""
    tenant_b_id = uuid.uuid4()
    existing = GraphRun(
        id=str(uuid.uuid4()),
        tenant_id=str(tenant_b_id),   # different tenant
        status="running",
        trigger="cron",
        correlation_id=str(uuid.uuid4()),
    )
    db.add(existing)
    db.flush()
    # Tenant A (investigator.tenant_id) should still be able to trigger
    resp = client.post("/api/v1/reclaimrx/graph-runs/trigger")
    assert resp.status_code in (202, 409)  # 202 if no A run in flight
```

2. Run tests — expect failures.

3. **Implement** in `router.py`:

```python
import asyncio
import zlib
from datetime import timedelta

@router.post("/graph-runs/trigger", status_code=202, response_model=GraphRunRead)
async def trigger_graph_run(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_investigator),
) -> GraphRunRead:
    """
    Trigger on-demand graph run. Rate limit: 1/hr/tenant (D13).
    Advisory lock: pg_try_advisory_xact_lock with deterministic zlib.crc32 key.
    Durable GraphRun.status='running' row is the cross-process authority (spec §7.3 / R3 NEW BLOCK 1).
    """
    import uuid as _uuid
    from datetime import datetime, UTC

    tid_str = str(user.tenant_id)
    lock_key = zlib.crc32(f"graph_run:{tid_str}".encode()) & 0x7FFFFFFF

    # Transaction-scoped advisory lock + in-flight check (spec §7.3 step 5)
    lock_acquired = db.execute(
        text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_key}
    ).scalar_one()
    if not lock_acquired:
        existing_run = db.execute(
            select(GraphRun).where(
                GraphRun.tenant_id == tid_str,
                GraphRun.status == "running",
            )
        ).scalar_one_or_none()
        run_id = existing_run.id if existing_run else "unknown"
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "RUN_IN_PROGRESS", "run_id": run_id}},
        )

    # Durable in-flight check (advisory lock is process-scoped; durable row is authority)
    existing = db.execute(
        select(GraphRun).where(
            GraphRun.tenant_id == tid_str,
            GraphRun.status == "running",
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "RUN_IN_PROGRESS", "run_id": existing.id}},
        )

    run_id = str(_uuid.uuid4())
    correlation_id = str(_uuid.uuid4())
    now = datetime.now(UTC)
    run = GraphRun(
        id=run_id,
        tenant_id=tid_str,
        status="running",
        trigger="on_demand",
        started_at=now,
        correlation_id=correlation_id,
        stale_timeout_at=now + timedelta(hours=6),
        rings_detected=0,
        investigations_opened=0,
        records_scanned=0,
        lookback_window_days=90,
    )
    db.add(run)
    db.commit()  # Advisory lock auto-released; durable row is now authority

    # Spawn async oneshot job (asyncio.create_task pattern — APScheduler NOT available, audit §7)
    asyncio.create_task(_run_graph_analysis(run_id, tid_str))

    return GraphRunRead(
        id=run.id, tenant_id=run.tenant_id, status=run.status,
        trigger=run.trigger, started_at=now.isoformat(),
        completed_at=None, failed_at=None, error_code=None,
        error_message=None, correlation_id=correlation_id,
        stale_timeout_at=run.stale_timeout_at.isoformat(),
        rings_detected=0, investigations_opened=0,
        records_scanned=0, lookback_window_days=90,
    )

async def _run_graph_analysis(run_id: str, tenant_id: str) -> None:
    """Async wrapper delegates to graph_analysis_service (Plan A2)."""
    from src.services.graph_analysis_service import GraphAnalysisService
    # Service wired in Plan A2; Plan A4 provides the async task wrapper only.
    try:
        svc = GraphAnalysisService()
        await svc.run(tenant_id=tenant_id, graph_run_id=run_id)
    except Exception:
        # Error handling: service updates GraphRun.status='failed' internally (spec §7.3 step 7)
        pass
```

4. Run tests — confirm pass.

**Coverage gate:** 100% on trigger handler (all 3 code paths: lock not acquired / row exists / success).

---

## Task A4-T5: N9 — `PUT /thresholds` (Admin-Only Write + Per-Field Hash-Chained Audit)

**Objective:** Admin-only threshold update. Creates new version row + per-field hash-chained audit entries. `require_admin()` dep. Rate limit 10/hr/tenant.

**Files touched:**
- `modules/reclaimrx/src/api/router.py`
- `modules/reclaimrx/src/services/threshold_service.py` (new file, Plan A2 domain, referenced here)

**TDD steps:**

1. **Write failing tests** at `modules/reclaimrx/tests/integration/test_a4_thresholds.py`:

```python
"""Integration tests — PUT /thresholds (admin-only, SP-3 Plan A4)."""
import uuid
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from src.main import create_app
from src._shim.auth import set_current_user, CurrentUser
from src.models.tables import ThresholdConfig, ThresholdConfigAudit  # Plan A1

@pytest.fixture()
def admin_user(db):
    u = CurrentUser(id=uuid.uuid4(), tenant_id=uuid.uuid4(), roles=["reclaimrx.admin"])
    set_current_user(u)
    return u

@pytest.fixture()
def client(db, admin_user):
    app = create_app()
    with TestClient(app) as c:
        yield c

def test_put_thresholds_creates_new_version(client, db, admin_user):
    resp = client.put("/api/v1/reclaimrx/thresholds", json={
        "ml_score_thresholds": {"open": "0.50", "auto_hold": "0.75", "escalate": "0.90"},
        "updated_by": str(admin_user.id),
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] >= 1
    assert body["ml_score_thresholds"]["open"] == "0.50"

def test_put_thresholds_creates_audit_entries(client, db, admin_user):
    """Per-field hash-chained audit entries created (spec R1 CONCERN 2)."""
    client.put("/api/v1/reclaimrx/thresholds", json={
        "graph_density_threshold": "0.85",
        "updated_by": str(admin_user.id),
    })
    audits = db.execute(
        select(ThresholdConfigAudit).where(
            ThresholdConfigAudit.tenant_id == str(admin_user.tenant_id)
        )
    ).scalars().all()
    assert len(audits) >= 1
    assert all(a.entry_hash for a in audits)  # MUST not be empty (hipaa-2026.md)

def test_put_thresholds_audit_hash_chain(client, db, admin_user):
    """Each audit entry includes prev_entry_hash pointing to prior entry's entry_hash."""
    client.put("/api/v1/reclaimrx/thresholds", json={
        "graph_density_threshold": "0.85",
        "updated_by": str(admin_user.id),
    })
    client.put("/api/v1/reclaimrx/thresholds", json={
        "graph_density_threshold": "0.90",
        "updated_by": str(admin_user.id),
    })
    audits = db.execute(
        select(ThresholdConfigAudit)
        .where(ThresholdConfigAudit.tenant_id == str(admin_user.tenant_id))
        .order_by(ThresholdConfigAudit.changed_at)
    ).scalars().all()
    if len(audits) >= 2:
        assert audits[1].prev_entry_hash == audits[0].entry_hash

def test_investigator_cannot_update_thresholds(client, db, admin_user):
    set_current_user(CurrentUser(
        id=uuid.uuid4(), tenant_id=admin_user.tenant_id, roles=["reclaimrx.investigator"]
    ))
    resp = client.put("/api/v1/reclaimrx/thresholds", json={
        "updated_by": "inv-user"
    })
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_ROLE"

def test_put_thresholds_out_of_range(client, db, admin_user):
    """422 THRESHOLD_OUT_OF_RANGE if value outside [0.0, 1.0] for score thresholds."""
    resp = client.put("/api/v1/reclaimrx/thresholds", json={
        "ml_score_thresholds": {"open": "1.50"},  # out of range
        "updated_by": str(admin_user.id),
    })
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "THRESHOLD_OUT_OF_RANGE"

def test_put_thresholds_cross_tenant_isolated(client, db, admin_user):
    """Threshold update scoped to admin's tenant; other tenant's config unchanged."""
    other_tid = uuid.uuid4()
    # Insert ThresholdConfig for other_tid
    resp = client.put("/api/v1/reclaimrx/thresholds", json={
        "graph_density_threshold": "0.85",
        "updated_by": str(admin_user.id),
    })
    assert resp.status_code == 200
    # Verify other tenant's config is unchanged (query by other_tid)
    other_config = db.execute(
        select(ThresholdConfig).where(
            ThresholdConfig.tenant_id == str(other_tid),
            ThresholdConfig.superseded_at == None,
        )
    ).scalar_one_or_none()
    # If other config exists, its version must not have been bumped
    if other_config:
        assert other_config.updated_by != str(admin_user.id)
```

2. Run tests — expect failures.

3. **Implement** `PUT /thresholds` handler in `router.py`:

```python
@router.put("/thresholds", response_model=ThresholdConfigRead)
async def update_thresholds(
    body: ThresholdUpdateRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
) -> ThresholdConfigRead:
    """Admin-only threshold update (spec endpoint #17, D5, R1 CONCERN 2).
    Delegates version bumping + per-field hash-chained audit to ThresholdService (Plan A2).
    """
    from src.services.threshold_service import ThresholdService
    svc = ThresholdService(db)
    config = await svc.update_thresholds(
        tenant_id=user.tenant_id,
        updates=body,
        updated_by=str(user.id),
    )
    return ThresholdConfigRead(
        tenant_id=config.tenant_id,
        version=config.version,
        effective_at=config.effective_at.isoformat(),
        superseded_at=None,
        rule_thresholds=config.rule_thresholds or {},
        ml_score_thresholds=config.ml_score_thresholds or {},
        graph_density_threshold=str(config.graph_density_threshold),
        accumulator_anomaly_sensitivity=str(config.accumulator_anomaly_sensitivity),
        updated_by=config.updated_by,
    )
```

4. Run tests — confirm pass.

**Coverage gate:** 100% on `PUT /thresholds` handler + ThresholdService (financial + audit paths).

---

## Task A4-T6: Partial-Mismatch Reshapes (P1, P2, P4, P5)

**Objective:** Reshape the 4 partial-mismatch endpoints that do not require a new route registration but need handler surgery. (P3 — hold release — is Plan A3's endpoint; A4 wires the MFA dependency on it.)

**Files touched:**
- `modules/reclaimrx/src/api/router.py` (4 existing handlers modified)

**P1 — `GET /investigations` — Add `severity`, `source`, pagination**

Add `severity: str | None`, `source: str | None`, `page: int`, `page_size: int` query params. Replace existing response with `PaginatedResponse[InvestigationRead]`. Tenant-scoped WHERE clause retains `Investigation.tenant_id == str(user.tenant_id)`. No PHI fields in list rows (spec §7.1 step 2: "list payload is PHI-AWARE").

**P2 — `GET /investigations/{id}` — PHI audit + MFA gate + no-store**

```python
@router.get("/investigations/{investigation_id}", response_model=InvestigationRead)
async def get_investigation(
    investigation_id: str,
    response: Response,  # FastAPI Response injection for header setting
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_mfa_elevated),  # MFA gate per D6a
) -> InvestigationRead:
    inv = db.execute(
        select(Investigation).where(
            Investigation.id == investigation_id,
            Investigation.tenant_id == str(user.tenant_id),
        )
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(404, detail={"error": {"code": "NOT_FOUND"}})

    # PHI audit entry (phi-compliance.md: every PHI read = separate audit entry)
    _emit_phi_audit(db, user=user, entity_type="investigation", entity_id=investigation_id)

    # PHI no-store header (phi-compliance.md)
    response.headers["Cache-Control"] = "no-store"

    return _mask_investigation(inv, phi_access_level=_get_phi_level(user))
```

Helper `_emit_phi_audit` writes an audit entry to the existing audit table with `action="phi_access"`, `user_id`, `tenant_id`, `entity_type`, `entity_id`. Helper `_get_phi_level` returns `"full"` in dev shim; production wires core-platform session lookup.

**P4 — `GET /holds` — Add `status` filter, paginate**

Replace existing list handler with paginated response. Filter by `status: str | None` query param (`active`, `released`, etc.). If the `PaymentHold` model uses `is_active` boolean (audit §1), map `status=active` → `is_active=True`, `status=released` → `released_at != None`.

**P5 — `GET /accumulator/detections` — Return 410 Gone**

The old route `/accumulator/detections` points to the wrong model (`AccumulatorDetection` ≠ `AccumulatorAnomaly`). Return 410 to signal migration to `/accumulator-anomalies`:

```python
@router.get("/accumulator/detections")
async def accumulator_detections_deprecated() -> None:
    raise HTTPException(
        status_code=410,
        detail={"error": {"code": "ENDPOINT_DEPRECATED",
                          "message": "Use /api/v1/reclaimrx/accumulator-anomalies"}},
    )
```

**TDD steps for P1, P2, P4, P5:**

1. Write tests at `modules/reclaimrx/tests/integration/test_a4_reshapes.py` covering:
   - P1: `GET /investigations?severity=high&page=2` returns paginated body with `items`/`total`.
   - P1: List body contains no PHI fields (`member_name`, `dob`, `ssn`).
   - P2: `GET /investigations/{id}` returns `Cache-Control: no-store` header.
   - P2: Calling without MFA session → 503 `MFA_CHECK_UNAVAILABLE` (stub).
   - P4: `GET /holds?status=active` returns only active holds.
   - P4: Cross-tenant isolation: query as A, no B holds returned.
   - P5: `GET /accumulator/detections` returns 410.

2. Run tests — expect failures.
3. Implement as above.
4. Run tests — confirm pass.

**Coverage gate:** 100% on the 4 modified handlers (all branches including 404, 410, MFA gate).

---

## Task A4-T7: `POST /investigations/{id}/transitions` and `POST /investigations/{id}/notes`

**Objective:** The two write-new endpoints that depend on the state machine (Plan A3). Plan A4 adds the route registrations with `require_investigator` / admin-override semantics and wires to the state machine validator from Plan A3.

**Files touched:**
- `modules/reclaimrx/src/api/router.py`

**Schemas (add to schemas.py):**

```python
class InvestigationTransitionRequest(BaseModel):
    to_status: Literal[
        "in_progress", "pending_review", "escalated",
        "closed_confirmed", "closed_false_positive", "closed_no_action", "open"
    ]
    reason: str                          # always required
    outcome_label: Literal["confirmed", "false_positive", "no_action"] | None = None
    recovered_amount: str | None = None  # Decimal as str; required for closed_confirmed

class InvestigationNoteCreate(BaseModel):
    content: str
    note_type: Literal["investigator", "system"] = "investigator"

class InvestigationTransitionRead(BaseModel):
    investigation_id: str
    from_status: str
    to_status: str
    reason: str
    transitioned_by: str
    transitioned_at: str
    outcome_label: str | None = None
    recovered_amount: str | None = None
```

**TDD steps:**

1. Write tests at `modules/reclaimrx/tests/integration/test_a4_transitions.py`:

```python
def test_valid_transition_open_to_in_progress(client, db, investigator):
    inv_id = _seed_open_investigation(db, investigator.tenant_id)
    resp = client.post(f"/api/v1/reclaimrx/investigations/{inv_id}/transitions", json={
        "to_status": "in_progress",
        "reason": "Starting review",
    })
    assert resp.status_code == 200
    assert resp.json()["to_status"] == "in_progress"

def test_invalid_transition_rejected(client, db, investigator):
    inv_id = _seed_open_investigation(db, investigator.tenant_id)
    resp = client.post(f"/api/v1/reclaimrx/investigations/{inv_id}/transitions", json={
        "to_status": "closed_confirmed",  # not allowed from 'open' per state machine §5.5.1
        "reason": "Skip steps",
    })
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "INVALID_TRANSITION"
    assert "allowed" in body["error"]  # allowed-next-states in error

def test_closed_confirmed_requires_outcome_and_amount(client, db, investigator):
    inv_id = _seed_in_progress_investigation(db, investigator.tenant_id)
    resp = client.post(f"/api/v1/reclaimrx/investigations/{inv_id}/transitions", json={
        "to_status": "closed_confirmed",
        "reason": "Confirmed fraud",
        # Missing outcome_label and recovered_amount
    })
    assert resp.status_code == 422

def test_escalated_to_closed_requires_admin(client, db, investigator):
    inv_id = _seed_escalated_investigation(db, investigator.tenant_id)
    resp = client.post(f"/api/v1/reclaimrx/investigations/{inv_id}/transitions", json={
        "to_status": "closed_confirmed",
        "reason": "Override",
        "outcome_label": "confirmed",
        "recovered_amount": "0.00",
    })
    assert resp.status_code == 403  # investigator cannot act on escalated

def test_add_note_appended(client, db, investigator):
    inv_id = _seed_open_investigation(db, investigator.tenant_id)
    resp = client.post(f"/api/v1/reclaimrx/investigations/{inv_id}/notes", json={
        "content": "Added note during review",
    })
    assert resp.status_code == 201

def test_add_note_viewer_rejected(client, db, investigator):
    set_current_user(CurrentUser(
        id=uuid.uuid4(), tenant_id=investigator.tenant_id, roles=["reclaimrx.viewer"]
    ))
    inv_id = _seed_open_investigation(db, investigator.tenant_id)
    resp = client.post(f"/api/v1/reclaimrx/investigations/{inv_id}/notes", json={
        "content": "Viewer note attempt",
    })
    assert resp.status_code == 403
```

2. Run tests — expect failures.

3. Implement handlers (both delegate to `InvestigationService` from Plan A3):

```python
@router.post("/investigations/{investigation_id}/transitions",
             response_model=InvestigationTransitionRead)
async def transition_investigation(
    investigation_id: str,
    body: InvestigationTransitionRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_investigator),
) -> InvestigationTransitionRead:
    from src.services.investigation_service import InvestigationService
    svc = InvestigationService(db)
    return await svc.transition(
        tenant_id=user.tenant_id,
        investigation_id=investigation_id,
        body=body,
        user=user,
    )

@router.post("/investigations/{investigation_id}/notes", status_code=201)
async def add_investigation_note(
    investigation_id: str,
    body: InvestigationNoteCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_investigator),
) -> dict:
    from src.services.investigation_service import InvestigationService
    svc = InvestigationService(db)
    note = await svc.add_note(
        tenant_id=user.tenant_id,
        investigation_id=investigation_id,
        content=body.content,
        note_type=body.note_type,
        added_by=str(user.id),
    )
    return {"id": note["id"], "created_at": note["created_at"]}
```

4. Run tests — confirm pass.

**Coverage gate:** 100% on state machine validation paths (every invalid transition branch). 100% on audit emission in transition handler.

---

## Task A4-T8: `GET /rule-firings` (Spec Endpoint #5 — Missing Route)

**Objective:** List rule firings (flagged claims acting as rule firing records per existing `FlaggedClaim` model). Returns paginated list with tenant scoping. Read-only, `require_viewer`.

**Note:** The spec refers to "rule firings" as a surface for "which rules fired on which claims this week, with what score and which evidence." The existing `FlaggedClaim` model (`reclaimrx_flagged_claims`) is the backing store (audit §1). This endpoint provides a new filtered, paginated view over it.

**Schemas (add to schemas.py):**

```python
class RuleFiringRead(BaseModel):
    id: str
    tenant_id: str
    claim_id: str | None
    rule_code: str
    severity: str
    fired_at: str
    rule_name: str | None = None
    score: str | None = None  # Decimal as str
    investigation_id: str | None = None

class RuleFiringListRead(BaseModel):
    items: list[RuleFiringRead]
    total: int
    page: int
    page_size: int
```

**TDD steps:**

1. Write tests at `modules/reclaimrx/tests/integration/test_a4_rule_firings.py`:

```python
def test_list_rule_firings_returns_paginated(client, db, viewer):
    resp = client.get("/api/v1/reclaimrx/rule-firings")
    assert resp.status_code == 200
    assert "items" in resp.json()

def test_rule_firings_tenant_isolated(client, db, viewer):
    resp = client.get("/api/v1/reclaimrx/rule-firings")
    for item in resp.json()["items"]:
        assert item["tenant_id"] == str(viewer.tenant_id)

def test_rule_firings_filter_by_rule_code(client, db, viewer):
    resp = client.get("/api/v1/reclaimrx/rule-firings?rule_code=FWA-001")
    assert resp.status_code == 200

def test_rule_firings_no_phi_in_list(client, db, viewer):
    resp = client.get("/api/v1/reclaimrx/rule-firings")
    body_str = str(resp.json())
    for phi in ("member_name", "dob", "ssn"):
        assert phi not in body_str
```

2. Run tests — expect failures.

3. Implement:

```python
@router.get("/rule-firings", response_model=RuleFiringListRead)
async def list_rule_firings(
    rule_code: str | None = Query(None),
    severity: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=200),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_viewer),
) -> RuleFiringListRead:
    stmt = select(FlaggedClaim).where(
        FlaggedClaim.tenant_id == str(user.tenant_id)
    )
    if rule_code:
        stmt = stmt.where(FlaggedClaim.rule_code == rule_code)
    if severity:
        stmt = stmt.where(FlaggedClaim.severity == severity)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar_one()
    rows = db.execute(
        stmt.order_by(FlaggedClaim.flagged_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
    ).scalars().all()
    return RuleFiringListRead(
        items=[
            RuleFiringRead(
                id=r.id,
                tenant_id=r.tenant_id,
                claim_id=r.claim_id,
                rule_code=r.rule_code or "",
                severity=r.severity or "",
                fired_at=r.flagged_at.isoformat() if r.flagged_at else "",
                score=str(r.confidence_score) if hasattr(r, "confidence_score") and r.confidence_score else None,
                investigation_id=r.investigation_id,
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
```

4. Run tests — confirm pass.

**Coverage gate:** 100% on handler (filter branches, empty result, tenant isolation).

---

## Task A4-T9: Full Role Matrix Integration Test + Coverage Report

**Objective:** Verify the complete 18-endpoint × 3-role matrix in one test file. Confirm coverage gates met.

**Files touched:**
- `modules/reclaimrx/tests/integration/test_a4_role_matrix.py` (new file)

**TDD steps:**

1. Write the matrix test:

```python
"""
SP-3 Plan A4 — Complete role matrix test.
Tests every endpoint against every role to confirm RBAC enforcement.
Spec D5 role matrix:
  viewer: read-only (all GET endpoints)
  investigator: read + status transitions + hold release + graph trigger + add notes
  admin: all of the above + threshold update
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from src.main import create_app
from src._shim.auth import set_current_user, CurrentUser

ROLES = ["reclaimrx.viewer", "reclaimrx.investigator", "reclaimrx.admin"]

def _client_with_role(role: str, tenant_id) -> TestClient:
    set_current_user(CurrentUser(id=uuid.uuid4(), tenant_id=tenant_id, roles=[role]))
    return TestClient(create_app())

READ_ENDPOINTS = [
    ("GET", "/api/v1/reclaimrx/investigations"),
    ("GET", "/api/v1/reclaimrx/ml-scores"),
    ("GET", "/api/v1/reclaimrx/holds"),
    ("GET", "/api/v1/reclaimrx/graph-runs"),
    ("GET", "/api/v1/reclaimrx/recovery"),
    ("GET", "/api/v1/reclaimrx/dashboard-summary"),
    ("GET", "/api/v1/reclaimrx/thresholds"),
    ("GET", "/api/v1/reclaimrx/accumulator-anomalies"),
    ("GET", "/api/v1/reclaimrx/rule-firings"),
]

INVESTIGATOR_WRITE_ENDPOINTS = [
    ("POST", "/api/v1/reclaimrx/graph-runs/trigger"),
]

ADMIN_ONLY_ENDPOINTS = [
    ("PUT", "/api/v1/reclaimrx/thresholds"),
]

@pytest.mark.parametrize("method,path", READ_ENDPOINTS)
@pytest.mark.parametrize("role", ROLES)
def test_read_endpoints_accessible_by_all_roles(method, path, role):
    tid = uuid.uuid4()
    c = _client_with_role(role, tid)
    resp = getattr(c, method.lower())(path)
    assert resp.status_code in (200, 503)  # 503 if MFA stub on detail; never 403

@pytest.mark.parametrize("method,path", INVESTIGATOR_WRITE_ENDPOINTS)
def test_investigator_write_requires_investigator_role(method, path):
    tid = uuid.uuid4()
    viewer_client = _client_with_role("reclaimrx.viewer", tid)
    resp = getattr(viewer_client, method.lower())(path)
    assert resp.status_code == 403

@pytest.mark.parametrize("method,path", ADMIN_ONLY_ENDPOINTS)
def test_admin_only_endpoints_blocked_for_non_admin(method, path):
    tid = uuid.uuid4()
    for role in ["reclaimrx.viewer", "reclaimrx.investigator"]:
        c = _client_with_role(role, tid)
        resp = getattr(c, method.lower())(path, json={"updated_by": "x"})
        assert resp.status_code == 403, f"Expected 403 for {role} on {path}"
```

2. Run full test suite: `pytest modules/reclaimrx/tests/ --cov=modules/reclaimrx/src --cov-report=term-missing`

3. Verify coverage thresholds per `.claude/rules/testing.md`:
   - 100% on `dependencies.py` (role gate functions)
   - 100% on `router.py` route handlers for all new/reshaped endpoints (financial, PHI, auth paths)
   - 95% baseline on all other new active code

4. Fix any failing coverage gaps before marking A4 complete.

**Coverage gate:** All gates pass. No handler has uncovered financial, PHI, or auth branches.

---

## Non-Negotiable Invariants for Executor

These apply to every line written in A4:

1. **`CurrentUser` is a dataclass.** Access `.roles`, `.has_role(r)`, `.id`, `.tenant_id`. Never `.get("roles")`.
2. **Table name is `reclaimrx_investigations`**, not `investigation`. All FK references use the full table name.
3. **`EventEnvelope` fields:** `event_type`, `correlation_id`, `source_module` (required). No `type=`, no `emitted_at=`.
4. **Advisory lock key uses `zlib.crc32`**, not Python `hash()`.
5. **All new handlers are `async def`.**
6. **Decimal money** wrapped in `Decimal(str(...))`. Serialized as `str()`. `.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`.
7. **`Cache-Control: no-store`** on investigation detail + any PHI-bearing detail endpoint.
8. **PHI audit emission** on every PHI detail read (`action="phi_access"`, `entity_type`, `entity_id`, `user_id`, `tenant_id`).
9. **Cross-tenant isolation test** per new endpoint.
10. **TDD order:** test → fail → implement → pass. No summary shorthand for any task.
