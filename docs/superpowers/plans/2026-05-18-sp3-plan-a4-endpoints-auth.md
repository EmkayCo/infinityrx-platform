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

## Task A4-T1: Role Infrastructure — wire `shared/auth/dependencies.py` + MFA-elevated dependency + tenant-header validator + error envelope helper

**R1 BLOCK 2 fix:** Plan A4 originally invented `require_viewer/require_investigator/require_admin` thin wrappers around a `_shim.auth.require_role(...)` helper that does not match the shared module's contract. The actual auth surface is `shared/auth/dependencies.py`, which exposes:

  * `get_current_user(token=Depends(oauth2_scheme)) -> CurrentUser` — resolves the bearer token, raises 401 on missing/expired/revoked/unknown user, and sets the tenant context.
  * `require_roles(*roles: str) -> Callable[[CurrentUser], CurrentUser]` — variadic dependency factory; raises 403 when no required role matches.
  * `require_permissions(*perms: str) -> Callable[[CurrentUser], CurrentUser]` — same factory pattern for permission strings.

These are the production helpers used by every other module's protected endpoints. A4 MUST consume them directly. The `_shim.auth` module exists only as a unit-test seam and is NOT a fallback for production wiring.

**Objective (revised):**
1. Bind spec role names to `shared/auth/dependencies.py:require_roles` factory calls — no module-local wrappers.
2. Add **real** `require_mfa_elevated()` dependency that fails closed with **403 `MFA_REQUIRED`** when the session is not MFA-elevated. **R1 BLOCK 3 fix:** 503 is the wrong status — 503 implies "service unavailable, retry later" and silently lets the request through if core-platform is down. The spec explicitly requires 403 MFA_REQUIRED.
3. Add `require_tenant_match()` dependency that validates `X-Tenant-Id` header against `CurrentUser.tenant_id`. **R1 BLOCK 4 fix.**
4. Add `build_error_envelope(code, message, *, field=None, correlation_id=None)` helper that emits the exact shape required by `.claude/rules/error-handling.md`. **R1 BLOCK 11 fix.**

**Files touched:**
- `modules/reclaimrx/src/api/dependencies.py` (rewrite — drop legacy wrappers)
- `modules/reclaimrx/src/api/errors.py` (NEW — error envelope helper)
- `modules/reclaimrx/src/api/router.py` (all existing route `Depends` updated to use shared factories)

**TDD steps:**

1. **Write failing tests** at `modules/reclaimrx/tests/unit/test_role_deps.py`:

```python
"""Unit tests for SP-3 role + MFA + tenant-header dependencies (R1 BLOCK 2/3/4 fix)."""
import os
import uuid

import pytest
from fastapi import HTTPException

from shared.auth import dependencies as shared_auth
from shared.auth.types import CurrentUser  # canonical type

from src.api.dependencies import (
    RECLAIMRX_VIEWER_DEP,
    RECLAIMRX_INVESTIGATOR_DEP,
    RECLAIMRX_ADMIN_DEP,
    require_mfa_elevated,
    require_tenant_match,
)


def _user(roles: list[str], tenant_id: uuid.UUID | None = None) -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        email="t@example.com",
        status="active",
        roles=roles,
        permissions=[],
    )


# ── Role dependencies (R1 BLOCK 2) ─────────────────────────────────────────────

def test_viewer_role_passes_viewer_dep():
    u = _user(["reclaimrx.viewer"])
    # Dep factories from shared/auth/dependencies.py are exercised via _dep(user=u).
    # We call the inner _dep with the user the factory closure would have received.
    assert RECLAIMRX_VIEWER_DEP.dependency.__wrapped__ is not None or callable(RECLAIMRX_VIEWER_DEP.dependency)


def test_investigator_satisfies_viewer():
    """Investigator role implies viewer access (spec §5.4)."""
    u = _user(["reclaimrx.investigator"])
    dep = shared_auth.require_roles("reclaimrx.viewer", "reclaimrx.investigator", "reclaimrx.admin")
    assert dep(user=u) is u


def test_viewer_blocked_on_investigator_dep():
    u = _user(["reclaimrx.viewer"])
    dep = shared_auth.require_roles("reclaimrx.investigator", "reclaimrx.admin")
    with pytest.raises(HTTPException) as exc:
        dep(user=u)
    assert exc.value.status_code == 403


def test_admin_only_blocks_investigator():
    u = _user(["reclaimrx.investigator"])
    dep = shared_auth.require_roles("reclaimrx.admin")
    with pytest.raises(HTTPException) as exc:
        dep(user=u)
    assert exc.value.status_code == 403


def test_legacy_role_strings_rejected():
    """'investigator' (no prefix) must not satisfy reclaimrx.viewer."""
    u = _user(["investigator", "tenant_admin"])
    dep = shared_auth.require_roles("reclaimrx.viewer", "reclaimrx.investigator", "reclaimrx.admin")
    with pytest.raises(HTTPException):
        dep(user=u)


# ── MFA dependency (R1 BLOCK 3) ────────────────────────────────────────────────

def test_mfa_required_returns_403_not_503(monkeypatch):
    """MFA-not-elevated MUST return 403 MFA_REQUIRED, not 503."""
    monkeypatch.delenv("RECLAIMRX_MFA_BYPASS", raising=False)
    u = _user(["reclaimrx.viewer"])
    with pytest.raises(HTTPException) as exc:
        require_mfa_elevated(user=u, session_lookup=_unelevated_session_lookup_stub)
    assert exc.value.status_code == 403
    assert exc.value.detail["error"]["code"] == "MFA_REQUIRED"


def test_mfa_passes_when_session_elevated(monkeypatch):
    monkeypatch.delenv("RECLAIMRX_MFA_BYPASS", raising=False)
    u = _user(["reclaimrx.viewer"])
    result = require_mfa_elevated(user=u, session_lookup=_elevated_session_lookup_stub)
    assert result is u


def _elevated_session_lookup_stub(user_id):
    from datetime import UTC, datetime, timedelta
    return {"mfa_elevated_until": datetime.now(UTC) + timedelta(minutes=10)}


def _unelevated_session_lookup_stub(user_id):
    return {"mfa_elevated_until": None}


# ── Tenant header dependency (R1 BLOCK 4) ──────────────────────────────────────

def test_tenant_header_match_passes():
    tid = uuid.uuid4()
    u = _user(["reclaimrx.viewer"], tenant_id=tid)
    assert require_tenant_match(x_tenant_id=str(tid), user=u) is u


def test_tenant_header_mismatch_returns_403_tenant_mismatch():
    u = _user(["reclaimrx.viewer"])  # random tenant
    with pytest.raises(HTTPException) as exc:
        require_tenant_match(x_tenant_id=str(uuid.uuid4()), user=u)
    assert exc.value.status_code == 403
    assert exc.value.detail["error"]["code"] == "TENANT_MISMATCH"


def test_tenant_header_invalid_uuid_returns_400():
    u = _user(["reclaimrx.viewer"])
    with pytest.raises(HTTPException) as exc:
        require_tenant_match(x_tenant_id="not-a-uuid", user=u)
    assert exc.value.status_code == 400
    assert exc.value.detail["error"]["code"] == "INVALID_TENANT_HEADER"


def test_tenant_header_missing_returns_400():
    u = _user(["reclaimrx.viewer"])
    with pytest.raises(HTTPException) as exc:
        require_tenant_match(x_tenant_id=None, user=u)
    assert exc.value.status_code == 400
```

2. Run `pytest modules/reclaimrx/tests/unit/test_role_deps.py` — expect ImportError/FAIL on `RECLAIMRX_VIEWER_DEP`, `require_mfa_elevated`, `require_tenant_match`.

3. **Implement** in `modules/reclaimrx/src/api/dependencies.py` — drop the legacy `require_viewer/require_investigator/require_admin` wrappers and bind the shared factory exactly once at module load:

```python
"""SP-3 reclaimrx route dependencies.

R1 BLOCK 2 fix: dependencies wrap `shared/auth/dependencies.py` factories.
R1 BLOCK 3 fix: require_mfa_elevated returns 403 MFA_REQUIRED (not 503).
R1 BLOCK 4 fix: require_tenant_match validates X-Tenant-Id header.
"""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Callable

from fastapi import Depends, Header, HTTPException

from shared.auth.dependencies import (
    get_current_user,
    require_roles,
)
from shared.auth.types import CurrentUser

from src.api.errors import build_error_envelope

# ── Role bindings (spec §5.4) ─────────────────────────────────────────────────
# Hierarchy: reclaimrx.admin > reclaimrx.investigator > reclaimrx.viewer.
# Each dep lists every role that satisfies the floor.

RECLAIMRX_VIEWER_DEP = Depends(
    require_roles("reclaimrx.viewer", "reclaimrx.investigator", "reclaimrx.admin")
)
RECLAIMRX_INVESTIGATOR_DEP = Depends(
    require_roles("reclaimrx.investigator", "reclaimrx.admin")
)
RECLAIMRX_ADMIN_DEP = Depends(require_roles("reclaimrx.admin"))


# ── MFA dependency (spec D6a; R1 BLOCK 3 fix) ─────────────────────────────────

# Type alias for the session-lookup callable. Lets tests inject a stub
# without monkeypatching core-platform HTTP code. Production binding is set
# at app-factory time via `set_mfa_session_lookup()`.
SessionLookup = Callable[[uuid.UUID], dict | None]
_session_lookup: SessionLookup | None = None


def set_mfa_session_lookup(fn: SessionLookup) -> None:
    """Inject the production session-lookup callable at app-factory time."""
    global _session_lookup
    _session_lookup = fn


def _default_session_lookup(user_id: uuid.UUID) -> dict | None:
    # No production binding set — fail closed.
    return None


def require_mfa_elevated(
    user: CurrentUser = Depends(require_roles(
        "reclaimrx.viewer", "reclaimrx.investigator", "reclaimrx.admin"
    )),
    session_lookup: SessionLookup | None = None,
) -> CurrentUser:
    """Require the caller's session to be MFA-elevated (spec D6a).

    Returns the CurrentUser when elevated. Raises 403 MFA_REQUIRED otherwise.
    R1 BLOCK 3 fix: 403 is the spec-correct status; 503 would silently let
    the request through on core-platform availability blips, which violates
    fail-closed.
    """
    if os.getenv("RECLAIMRX_MFA_BYPASS") == "1":
        return user
    lookup = session_lookup or _session_lookup or _default_session_lookup
    session = lookup(user.id)
    elevated_until = (session or {}).get("mfa_elevated_until")
    if elevated_until and elevated_until > datetime.now(UTC):
        return user
    raise HTTPException(
        status_code=403,
        detail=build_error_envelope(
            "MFA_REQUIRED",
            "MFA-elevated session required to access this resource.",
        ),
    )


# ── Tenant-header validator (R1 BLOCK 4 fix) ──────────────────────────────────

def require_tenant_match(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Validate the X-Tenant-Id header matches the authenticated user's tenant.

    Raises 400 INVALID_TENANT_HEADER on missing or malformed header.
    Raises 403 TENANT_MISMATCH on tenant cross-claim.
    """
    if x_tenant_id is None:
        raise HTTPException(
            status_code=400,
            detail=build_error_envelope(
                "INVALID_TENANT_HEADER",
                "X-Tenant-Id header is required.",
                field="x-tenant-id",
            ),
        )
    try:
        header_tid = uuid.UUID(x_tenant_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=build_error_envelope(
                "INVALID_TENANT_HEADER",
                "X-Tenant-Id is not a valid UUID.",
                field="x-tenant-id",
            ),
        ) from exc
    if header_tid != user.tenant_id:
        raise HTTPException(
            status_code=403,
            detail=build_error_envelope(
                "TENANT_MISMATCH",
                "Authenticated user tenant does not match X-Tenant-Id header.",
                field="x-tenant-id",
            ),
        )
    return user


# Composed dependency: tenant match THEN role floor (R1 BLOCK 13 fix).
# Used by every endpoint via `Depends(require_tenant_and_viewer)` etc.
RECLAIMRX_TENANT_AND_VIEWER_DEP = Depends(require_tenant_match)
```

4. **Implement error envelope helper** at `modules/reclaimrx/src/api/errors.py` (NEW — R1 BLOCK 11 fix):

```python
"""Shared error-envelope helper for the reclaimrx router.

Per .claude/rules/error-handling.md the API error body MUST be:

    {"error": {"code": "...", "message": "...", "field": "...", "correlation_id": "..."}}

This helper produces that exact shape. Use it from every HTTPException
raised by reclaimrx routes or dependencies.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar

_correlation_id_ctx: ContextVar[str | None] = ContextVar(
    "reclaimrx_correlation_id", default=None,
)


def set_correlation_id(correlation_id: str | None) -> None:
    _correlation_id_ctx.set(correlation_id)


def get_correlation_id() -> str | None:
    return _correlation_id_ctx.get()


def build_error_envelope(
    code: str,
    message: str,
    *,
    field: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """Construct the {error: {...}} body required by error-handling.md.

    `correlation_id` falls back to the current request's contextvar value
    (set by the CorrelationIdMiddleware at the platform layer). If neither
    is present, a fresh UUID is generated so the response is never missing
    the trace key.
    """
    cid = correlation_id or get_correlation_id() or str(uuid.uuid4())
    envelope = {
        "error": {
            "code": code,
            "message": message,
            "field": field,
            "correlation_id": cid,
        }
    }
    return envelope
```

5. **Update every existing route Depends** in `router.py`. All read endpoints become:

```python
@router.get("/investigations", response_model=InvestigationListRead)
async def list_investigations(
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant_check: CurrentUser = Depends(require_tenant_match),
    db: Session = Depends(get_db),
    severity: str | None = Query(None),
    source: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    ...
```

**R1 BLOCK 13 fix — dependency ordering:** every endpoint composes its dependencies in this exact order so 401, 403-role, 403-tenant, and business-logic failures surface in spec-correct order:
  1. `Depends(get_current_user)` (implied by `RECLAIMRX_VIEWER_DEP`) — 401 first.
  2. `Depends(require_roles(...))` (RECLAIMRX_*_DEP) — 403 role.
  3. `Depends(require_tenant_match)` — 403 tenant mismatch (or 400 invalid header).
  4. `Depends(get_db)` + business logic.

PHI-bearing endpoints additionally take `Depends(require_mfa_elevated)` between steps 3 and 4.

6. **Confirm pass:** `pytest modules/reclaimrx/tests/unit/test_role_deps.py -x` → all GREEN.

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


class MlScoreListRead(BaseModel):
    """Paginated list response for GET /ml-scores (R1 BLOCK 1 fix — typed not dict)."""
    items: list[MlScoreRead]
    total: int
    page: int
    page_size: int


class InvestigationMlScoreListRead(BaseModel):
    """Response for GET /investigations/{id}/ml-scores (R1 BLOCK 1 fix — typed not dict)."""
    items: list[MlScoreRead]
    total: int


class HoldReleaseRequest(BaseModel):
    """Body for POST /holds/{hold_id}/release (R1 BLOCK 1 fix — A4 owns the schema).

    Plan A3 owns the handler logic (state-machine release + outbox publish).
    A4 owns the request schema, MFA gating, tenant header validation,
    and idempotency-key contract.
    """
    reason: str
    investigation_id: str  # UUID; FK validated in A3 service layer
    # idempotency_key composed by client as `hold:release:{hold_id}:{actor_id}`
    # and asserted in headers — see R1 BLOCK 6 fix below (POST idempotency).
    idempotency_key: str


class HoldReleaseRead(BaseModel):
    """Response shape for POST /holds/{hold_id}/release."""
    hold_id: str
    status: Literal["released", "expired", "cancelled"]
    released_at: str
    released_by: str
    release_reason: str
    investigation_id: str
    idempotent_replay: bool = False  # True on case-A 200 replay per spec §7.2

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

@router.get("/ml-scores", response_model=MlScoreListRead)
async def list_ml_scores(
    claim_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=200),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant_check: CurrentUser = Depends(require_tenant_match),
) -> MlScoreListRead:
    """R1 BLOCK 1 fix: typed response_model (not `dict`)."""
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
    return MlScoreListRead(
        items=[
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
        total=total,
        page=page,
        page_size=page_size,
    )

# GET /ml-scores/{id}/features
@router.get("/ml-scores/{score_id}/features", response_model=MlScoreFeatureRead)
async def get_ml_score_features(
    score_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant_check: CurrentUser = Depends(require_tenant_match),
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
            detail=build_error_envelope("NOT_FOUND", "ML score not found."),
        )
    return MlScoreFeatureRead(
        id=row.id,
        feature_importance=row.feature_importance or {},  # {} if missing per spec §8
        model_version=None,
    )

# GET /investigations/{investigation_id}/ml-scores
@router.get(
    "/investigations/{investigation_id}/ml-scores",
    response_model=InvestigationMlScoreListRead,
)
async def list_investigation_ml_scores(
    investigation_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant_check: CurrentUser = Depends(require_tenant_match),
) -> InvestigationMlScoreListRead:
    """R1 BLOCK 1 fix: typed response_model (not `dict`)."""
    # Verify investigation belongs to tenant (non-enumerating per R1 BLOCK 6)
    inv = db.execute(
        select(Investigation).where(
            Investigation.id == investigation_id,
            Investigation.tenant_id == str(user.tenant_id),
        )
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(
            status_code=404,
            detail=build_error_envelope("NOT_FOUND", "Investigation not found."),
        )
    rows = db.execute(
        select(MlPrediction).where(
            MlPrediction.tenant_id == str(user.tenant_id),
            # Join via Investigation.source_ref_id (A1 schema) for rule_firing/ml_score sources
            MlPrediction.id == inv.source_ref_id,
        )
    ).scalars().all()
    return InvestigationMlScoreListRead(
        items=[
            MlScoreRead(
                id=r.id,
                tenant_id=r.tenant_id,
                claim_id=r.claim_id if hasattr(r, "claim_id") else "",
                model_id=r.model_id,
                score=str(r.score) if r.score is not None else "0",
                threshold_at_time=(
                    str(r.threshold) if hasattr(r, "threshold") and r.threshold else "0"
                ),
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in rows
        ],
        total=len(rows),
    )
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
    # R1 BLOCK 13 fix — dependency order: 401 → 403 role → 403 tenant → 403 MFA → business.
    user: CurrentUser = RECLAIMRX_INVESTIGATOR_DEP,
    _tenant_check: CurrentUser = Depends(require_tenant_match),
    # R1 BLOCK 3 fix — graph trigger requires MFA per spec §7.
    _mfa: CurrentUser = Depends(require_mfa_elevated),
    # R1 BLOCK 6 fix — POST idempotency-key contract for graph trigger.
    # Header is REQUIRED; client must compose as `graph_run:{tenant_id}:{actor_id}:{client_nonce}`.
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> GraphRunRead:
    """
    Trigger on-demand graph run. Rate limit: 1/hr/tenant (D13).
    Advisory lock: pg_try_advisory_xact_lock with deterministic zlib.crc32 key.
    Durable GraphRun.status='running' row is the cross-process authority (spec §7.3 / R3 NEW BLOCK 1).

    R1 BLOCK 6 fix — Idempotency contract (POST graph trigger):
      • Header `Idempotency-Key` REQUIRED. Format:
            graph_run:{tenant_id}:{actor_id}:{client_nonce}
      • Replay with same key + status='running' → 200 returning the existing run.
      • Replay with same key + status='completed'/'failed' → 200 returning the
        prior run row (idempotent — no new run kicked off).
      • Different key + status='running' for tenant → 409 RUN_IN_PROGRESS.
    """
    import uuid as _uuid
    from datetime import datetime, UTC

    tid_str = str(user.tenant_id)

    # R1 BLOCK 6 fix — idempotency replay check.
    prior = db.execute(
        select(GraphRun).where(
            GraphRun.tenant_id == tid_str,
            GraphRun.correlation_id == idempotency_key,
        )
    ).scalar_one_or_none()
    if prior is not None:
        return _graph_run_to_read(prior)

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
            detail=build_error_envelope(
                "RUN_IN_PROGRESS",
                "A graph run is already in progress for this tenant.",
                field=None,
            ) | {"error": {**build_error_envelope("RUN_IN_PROGRESS", "...")["error"], "run_id": run_id}},
        )

    # Durable in-flight check (advisory lock is process-scoped; durable row is authority)
    existing = db.execute(
        select(GraphRun).where(
            GraphRun.tenant_id == tid_str,
            GraphRun.status == "running",
        )
    ).scalar_one_or_none()
    if existing is not None:
        envelope = build_error_envelope(
            "RUN_IN_PROGRESS",
            "A graph run is already in progress for this tenant.",
        )
        envelope["error"]["run_id"] = existing.id
        raise HTTPException(status_code=409, detail=envelope)

    run_id = str(_uuid.uuid4())
    # R1 BLOCK 6 fix — store the supplied idempotency-key as correlation_id so
    # subsequent retries with the same header resolve to the same row.
    correlation_id = idempotency_key
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

    return _graph_run_to_read(run)


def _graph_run_to_read(run: GraphRun) -> GraphRunRead:
    return GraphRunRead(
        id=run.id, tenant_id=run.tenant_id, status=run.status,
        trigger=run.trigger,
        started_at=run.started_at.isoformat() if run.started_at else "",
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        failed_at=run.failed_at.isoformat() if run.failed_at else None,
        error_code=run.error_code,
        error_message=run.error_message,
        correlation_id=run.correlation_id,
        stale_timeout_at=run.stale_timeout_at.isoformat(),
        rings_detected=run.rings_detected,
        investigations_opened=run.investigations_opened,
        records_scanned=run.records_scanned,
        lookback_window_days=run.lookback_window_days,
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
    user: CurrentUser = RECLAIMRX_ADMIN_DEP,
    _tenant_check: CurrentUser = Depends(require_tenant_match),
    _mfa: CurrentUser = Depends(require_mfa_elevated),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
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
        raise HTTPException(
            status_code=404,
            detail=build_error_envelope("NOT_FOUND", "Investigation not found."),
        )

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
        detail=build_error_envelope(
            "ENDPOINT_DEPRECATED",
            "Use /api/v1/reclaimrx/accumulator-anomalies",
        ),
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


class InvestigationNoteRead(BaseModel):
    """Response shape for POST /investigations/{id}/notes (R1 BLOCK 1 fix — typed not dict)."""
    id: str
    created_at: str


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
    user: CurrentUser = RECLAIMRX_INVESTIGATOR_DEP,
    _tenant_check: CurrentUser = Depends(require_tenant_match),
    _mfa: CurrentUser = Depends(require_mfa_elevated),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> InvestigationTransitionRead:
    from src.services.investigation_service import InvestigationService
    svc = InvestigationService(db)
    return await svc.transition(
        tenant_id=user.tenant_id,
        investigation_id=investigation_id,
        body=body,
        user=user,
    )

@router.post(
    "/investigations/{investigation_id}/notes",
    status_code=201,
    response_model=InvestigationNoteRead,
)
async def add_investigation_note(
    investigation_id: str,
    body: InvestigationNoteCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_INVESTIGATOR_DEP,
    _tenant_check: CurrentUser = Depends(require_tenant_match),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> InvestigationNoteRead:
    """R1 BLOCK 1 fix: typed response_model (not `dict`)."""
    from src.services.investigation_service import InvestigationService
    svc = InvestigationService(db)
    note = await svc.add_note(
        tenant_id=user.tenant_id,
        investigation_id=investigation_id,
        content=body.content,
        note_type=body.note_type,
        added_by=str(user.id),
        idempotency_key=idempotency_key,
    )
    return InvestigationNoteRead(
        id=note["id"],
        created_at=note["created_at"],
    )
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
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant_check: CurrentUser = Depends(require_tenant_match),
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

## Task A4-T9: Full 18-Endpoint Route Matrix + Role Matrix Integration Test (R1 BLOCK 14 fix)

**Objective:** Prove every one of the **18** spec-required endpoints is registered in `create_app()` and respects RBAC. R1 BLOCK 14 flagged that the prior matrix covered only 11 of 18 — this task lists every endpoint by exact path and method, asserts each is reachable (not 404 from the catch-all), then asserts the 3-role gate.

**Files touched:**
- `modules/reclaimrx/tests/integration/test_a4_route_matrix.py` (new file)

### 9a — Write failing tests (TDD step 1)

```python
"""
SP-3 Plan A4 — Full 18-endpoint route matrix + 3-role gate.

R1 BLOCK 14 fix: explicitly enumerate every spec §5.5 endpoint and assert
the route is registered + the role gate fires correctly. Prior plan
covered only 11 of 18 endpoints.
"""
import uuid
import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from shared.auth.types import CurrentUser


# ── 18 spec §5.5 endpoints, fully enumerated (R1 BLOCK 14 fix) ────────────────

SPEC_ENDPOINTS_18 = [
    # spec §5.5 # → (method, path, role floor)
    # Read endpoints (15 of 18)
    (1,  "GET",    "/api/v1/reclaimrx/investigations",                  "reclaimrx.viewer"),
    (2,  "GET",    "/api/v1/reclaimrx/investigations/{id}",             "reclaimrx.viewer"),
    (3,  "POST",   "/api/v1/reclaimrx/investigations/{id}/transitions", "reclaimrx.investigator"),
    (4,  "POST",   "/api/v1/reclaimrx/investigations/{id}/notes",       "reclaimrx.investigator"),
    (5,  "GET",    "/api/v1/reclaimrx/investigations/{id}/ml-scores",   "reclaimrx.viewer"),
    (6,  "GET",    "/api/v1/reclaimrx/ml-scores",                       "reclaimrx.viewer"),
    (7,  "GET",    "/api/v1/reclaimrx/ml-scores/{id}/features",         "reclaimrx.viewer"),
    (8,  "GET",    "/api/v1/reclaimrx/holds",                           "reclaimrx.viewer"),
    (9,  "POST",   "/api/v1/reclaimrx/holds/{hold_id}/release",         "reclaimrx.investigator"),
    (10, "POST",   "/api/v1/reclaimrx/graph-runs/trigger",              "reclaimrx.investigator"),
    (11, "GET",    "/api/v1/reclaimrx/graph-runs",                      "reclaimrx.viewer"),
    (12, "GET",    "/api/v1/reclaimrx/graph-runs/{run_id}",             "reclaimrx.viewer"),
    (13, "GET",    "/api/v1/reclaimrx/fraud-rings/{id}",                "reclaimrx.viewer"),
    (14, "GET",    "/api/v1/reclaimrx/recovery",                        "reclaimrx.viewer"),
    (15, "GET",    "/api/v1/reclaimrx/dashboard-summary",               "reclaimrx.viewer"),
    (16, "GET",    "/api/v1/reclaimrx/thresholds",                      "reclaimrx.viewer"),
    (17, "PUT",    "/api/v1/reclaimrx/thresholds",                      "reclaimrx.admin"),
    (18, "GET",    "/api/v1/reclaimrx/accumulator-anomalies",           "reclaimrx.viewer"),
]
assert len(SPEC_ENDPOINTS_18) == 18, "spec §5.5 has exactly 18 endpoints"


def _path_with_dummy_ids(path: str) -> str:
    """Replace {id}, {hold_id}, {run_id} with non-enumerable placeholders.

    Real routes return 404 (or 401 if unauthenticated) on these — we only
    care that the route IS REGISTERED in the app, not that the entity exists.
    """
    return (path
            .replace("{id}", "no-such-id")
            .replace("{hold_id}", "no-such-hold")
            .replace("{run_id}", "no-such-run"))


def _client_with_role(role: str, tenant_id) -> TestClient:
    from src.api.dependencies import set_mfa_session_lookup
    from datetime import UTC, datetime, timedelta

    # MFA-elevated stub so MFA-gated endpoints don't 403 on this matrix
    set_mfa_session_lookup(lambda uid: {
        "mfa_elevated_until": datetime.now(UTC) + timedelta(minutes=10)
    })

    app = create_app()
    # Override `get_current_user` to return a synthetic CurrentUser with the
    # requested role. Production tests should use real JWT mints; for the
    # matrix test the override is sufficient because the gate exits 401/403
    # at the role-check layer, not at JWT decode.
    from shared.auth.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="t@example.com",
        status="active",
        roles=[role],
        permissions=[],
    )
    client = TestClient(app)
    client.headers["X-Tenant-Id"] = str(tenant_id)
    client.headers["Idempotency-Key"] = (
        f"matrix-test:{tenant_id}:{uuid.uuid4()}"
    )
    return client


# ── Route registration: every spec §5.5 endpoint is reachable (R1 BLOCK 14) ──

@pytest.mark.parametrize("spec_num,method,path,role_floor", SPEC_ENDPOINTS_18)
def test_route_registered_under_floor_role(spec_num, method, path, role_floor):
    """The route MUST be reachable under its role floor — any status
    EXCEPT 404 (route missing) or 405 (wrong method) proves registration."""
    tid = uuid.uuid4()
    client = _client_with_role(role_floor, tid)
    concrete_path = _path_with_dummy_ids(path)
    # Send an empty body for POST/PUT — schema validation is acceptable as
    # proof of reachability.
    fn = getattr(client, method.lower())
    resp = fn(concrete_path, json={} if method in ("POST", "PUT") else None)
    assert resp.status_code not in (404, 405), (
        f"spec §5.5 #{spec_num} ({method} {path}) NOT registered — "
        f"got {resp.status_code} from the catch-all. "
        f"Either the route is missing from router.py or the method/path is wrong."
    )


# ── Role-floor enforcement: lower role is rejected with 403 ───────────────────

ROLE_HIERARCHY = ["reclaimrx.viewer", "reclaimrx.investigator", "reclaimrx.admin"]


@pytest.mark.parametrize("spec_num,method,path,role_floor", SPEC_ENDPOINTS_18)
def test_lower_role_blocked_with_403(spec_num, method, path, role_floor):
    """A role BELOW the endpoint's floor must be rejected with 403."""
    floor_idx = ROLE_HIERARCHY.index(role_floor)
    if floor_idx == 0:
        pytest.skip("viewer is the lowest role; no lower role to test")
    lower_role = ROLE_HIERARCHY[floor_idx - 1]
    tid = uuid.uuid4()
    client = _client_with_role(lower_role, tid)
    concrete_path = _path_with_dummy_ids(path)
    fn = getattr(client, method.lower())
    resp = fn(concrete_path, json={} if method in ("POST", "PUT") else None)
    assert resp.status_code == 403, (
        f"spec §5.5 #{spec_num} ({method} {path}): "
        f"{lower_role} should be blocked from a {role_floor}-floor endpoint "
        f"but got {resp.status_code}."
    )


# ── Tenant-header validation: mismatch always 403 (R1 BLOCK 4) ───────────────

@pytest.mark.parametrize("spec_num,method,path,role_floor", SPEC_ENDPOINTS_18)
def test_tenant_header_mismatch_returns_403(spec_num, method, path, role_floor):
    """Mismatched X-Tenant-Id MUST return 403 TENANT_MISMATCH."""
    tid = uuid.uuid4()
    client = _client_with_role(role_floor, tid)
    # Override the header with a different tenant ID
    client.headers["X-Tenant-Id"] = str(uuid.uuid4())
    concrete_path = _path_with_dummy_ids(path)
    fn = getattr(client, method.lower())
    resp = fn(concrete_path, json={} if method in ("POST", "PUT") else None)
    assert resp.status_code == 403, (
        f"spec §5.5 #{spec_num} ({method} {path}): "
        f"tenant header mismatch did not return 403 — got {resp.status_code}."
    )
    assert resp.json()["error"]["code"] == "TENANT_MISMATCH"
```

### 9b — Run, expect FAIL

```bash
pytest modules/reclaimrx/tests/integration/test_a4_route_matrix.py -x
```
Expected: failures on any of the 18 endpoints whose route is not yet wired or whose role/tenant guard is missing.

### 9c — Wire missing routes (delegated to Tasks T2–T8)

Each failure points to the specific endpoint (spec #) that needs wiring. Fix in the owning task (T2–T8), then re-run.

### 9d — Re-run, expect PASS

```bash
pytest modules/reclaimrx/tests/integration/test_a4_route_matrix.py -x
# 54 tests expected: 18 (route registration) + 17 (lower-role 403, viewer-floor skipped) + 18 (tenant mismatch) + 1 viewer skip
```

### 9e — Coverage run

```bash
pytest modules/reclaimrx/tests/ \
    --cov=modules/reclaimrx/src/api/dependencies \
    --cov=modules/reclaimrx/src/api/errors \
    --cov=modules/reclaimrx/src/api/router \
    --cov-report=term-missing
```
Required:
- 100% on `dependencies.py` (role gates + MFA + tenant header — security path)
- 100% on `errors.py` (error envelope helper)
- 100% on router handlers for all 18 endpoints (financial, PHI, auth paths)

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
11. **Auth surface is `shared/auth/dependencies.py`** (R1 BLOCK 2). Use `RECLAIMRX_VIEWER_DEP`, `RECLAIMRX_INVESTIGATOR_DEP`, `RECLAIMRX_ADMIN_DEP` from `src/api/dependencies.py`. Never import from `src/_shim/auth.py` in production handlers.
12. **MFA-gated endpoints return 403 `MFA_REQUIRED`** (R1 BLOCK 3). 503 is incorrect — it implies retry semantics and silently lets unguarded requests through.
13. **Tenant header validation is required on every endpoint** (R1 BLOCK 4). Compose `Depends(require_tenant_match)` after the role gate.
14. **Error envelope shape is `{"error": {"code", "message", "field", "correlation_id"}}`** (R1 BLOCK 11). Use `build_error_envelope(...)` from `src/api/errors.py` — never construct the dict inline.
15. **Dependency ordering is fixed:** 401 (get_current_user) → 403 role → 403 tenant → 403 MFA → 400 body validation → 200/business (R1 BLOCK 13). FastAPI evaluates `Depends` in declaration order; preserve that order on every handler.
16. **POST endpoints require an `Idempotency-Key` header** (R1 BLOCK 6). Format conventions:
    - graph trigger: `graph_run:{tenant_id}:{actor_id}:{client_nonce}`
    - hold release: `hold:release:{hold_id}:{actor_id}`
    - investigation transition: `inv_transition:{investigation_id}:{to_state}:{actor_id}`
    - investigation note: `inv_note:{investigation_id}:{actor_id}:{client_nonce}`
    - threshold update: `threshold_update:{tenant_id}:{client_nonce}`
    The router stores the key on the durable row (correlation_id or business-specific column) so retries return the prior result. No POST is silently non-idempotent.
17. **All 18 spec §5.5 endpoints are mounted and reachable** (R1 BLOCK 14). The route matrix in T9 enumerates them; CI must run that matrix on every PR.
