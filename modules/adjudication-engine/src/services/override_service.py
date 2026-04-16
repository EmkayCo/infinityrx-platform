"""Claim-level rule override service.

Manages member-level overrides that skip specific rules during
adjudication. Includes safety guardrails that prevent overriding
DUR critical hard stops and government exclusion rules.

Override workflow:
1. create_override() creates a pending override
2. Approval config determines if supervisor approval is needed
3. approve_override() activates the override
4. check_overrides() returns active overrides during adjudication
5. Adjudication pipeline skips overridden rules with trace notation
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from shared.utils.money import ZERO

logger = logging.getLogger("adjudication_engine.override_service")

# ---------------------------------------------------------------------------
# Safety guardrails — rule types that CANNOT be overridden
# ---------------------------------------------------------------------------

# DUR critical hard stops — patient safety, never overridable
NON_OVERRIDABLE_DUR_TYPES = frozenset({
    "dur_critical_drug_drug",
    "dur_critical_allergy",
    "dur_critical_contraindication",
    "dur_critical_pregnancy",
    "dur_critical_pediatric",
    "dur_critical_geriatric",
})

# Government exclusion rules — regulatory compliance, never overridable
NON_OVERRIDABLE_GOVT_TYPES = frozenset({
    "govt_excluded_drug",
    "govt_opa_exclusion",
    "govt_controlled_substance_limit",
    "govt_cms_excluded",
    "govt_state_exclusion",
})

ALL_NON_OVERRIDABLE = NON_OVERRIDABLE_DUR_TYPES | NON_OVERRIDABLE_GOVT_TYPES

# Valid scope values
VALID_SCOPES = frozenset({
    "member_rule_drug",
    "member_rule_any",
    "member_rule_pharmacy",
})

# Valid duration types
VALID_DURATION_TYPES = frozenset({
    "one_time",
    "fixed_period",
    "benefit_year",
    "permanent",
})

# Valid status values
VALID_STATUSES = frozenset({
    "pending_approval",
    "active",
    "expired",
    "revoked",
})

# Rule types that auto-approve (low risk)
AUTO_APPROVE_RULE_TYPES = frozenset({
    "quantity_limit_rule",
    "refill_rule",
    "age_rule",
    "days_supply_rule",
})

# Rule types requiring supervisor approval (financial impact)
SUPERVISOR_REQUIRED_RULE_TYPES = frozenset({
    "copay_rule",
    "bill_cost_calculator",
    "dispense_fee_rule",
    "step_therapy_rule",
    "pa_required_rule",
})

# Default override durations
DEFAULT_DURATIONS = {
    "one_time": timedelta(hours=24),
    "fixed_period": timedelta(days=90),
    "benefit_year": timedelta(days=365),
}


# ---------------------------------------------------------------------------
# Override data structure (in-process, for pipeline integration)
# ---------------------------------------------------------------------------


class OverrideError(Exception):
    """Raised when an override operation violates safety guardrails."""


def create_override(
    tenant_id: uuid.UUID,
    member_id: uuid.UUID,
    rule_id: uuid.UUID,
    rule_type: str,
    scope: str,
    reason_code: str,
    reason_text: str,
    duration_type: str,
    created_by: str,
    ndc: str | None = None,
    expires_at: datetime | None = None,
    original_claim_id: uuid.UUID | None = None,
    approval_config_lookup: Any | None = None,
) -> dict[str, Any]:
    """Create a new claim override.

    Safety guardrails:
    - Cannot override DUR critical hard stops
    - Cannot override government exclusion rules

    Auto-approval for low-risk rule types.
    Supervisor approval required for financial impact rules.

    Args:
        tenant_id: Tenant UUID.
        member_id: Member UUID.
        rule_id: Rule instance ID being overridden.
        rule_type: Rule type code (e.g. 'copay_rule', 'quantity_limit_rule').
        scope: Override scope (member_rule_drug/member_rule_any/member_rule_pharmacy).
        reason_code: Standardized reason code.
        reason_text: Human-readable justification.
        duration_type: one_time/fixed_period/benefit_year/permanent.
        created_by: User ID of the creator.
        ndc: Optional NDC for drug-scoped overrides.
        expires_at: Optional explicit expiration.
        original_claim_id: Optional original claim that triggered the override.
        approval_config_lookup: Optional callable for tenant approval config.

    Returns:
        Dict representing the created override.

    Raises:
        OverrideError: If the rule type is non-overridable or parameters are invalid.
    """
    # Safety guardrail: non-overridable rule types
    if rule_type in ALL_NON_OVERRIDABLE:
        raise OverrideError(
            f"Cannot override rule type '{rule_type}': "
            f"{'DUR critical hard stop' if rule_type in NON_OVERRIDABLE_DUR_TYPES else 'government exclusion rule'} "
            f"— patient safety and regulatory compliance rules are never overridable"
        )

    # Validate scope
    if scope not in VALID_SCOPES:
        raise OverrideError(
            f"Invalid scope '{scope}': must be one of {sorted(VALID_SCOPES)}"
        )

    # Validate duration
    if duration_type not in VALID_DURATION_TYPES:
        raise OverrideError(
            f"Invalid duration_type '{duration_type}': must be one of {sorted(VALID_DURATION_TYPES)}"
        )

    # Validate scope/ndc consistency
    if scope == "member_rule_drug" and not ndc:
        raise OverrideError(
            "member_rule_drug scope requires an NDC"
        )

    # Calculate expiration
    if expires_at is None and duration_type != "permanent":
        default_duration = DEFAULT_DURATIONS.get(duration_type)
        if default_duration:
            expires_at = datetime.now(UTC) + default_duration

    # Determine approval status
    requires_approval = _check_requires_approval(
        rule_type, tenant_id, approval_config_lookup
    )
    status = "pending_approval" if requires_approval else "active"

    override_id = uuid.uuid4()

    override = {
        "id": str(override_id),
        "tenant_id": str(tenant_id),
        "member_id": str(member_id),
        "rule_id": str(rule_id),
        "rule_type": rule_type,
        "ndc": ndc,
        "scope": scope,
        "reason_code": reason_code,
        "reason_text": reason_text,
        "duration_type": duration_type,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "status": status,
        "created_by": created_by,
        "approved_by": created_by if not requires_approval else None,
        "original_claim_id": str(original_claim_id) if original_claim_id else None,
        "created_at": datetime.now(UTC).isoformat(),
    }

    logger.info(
        "override.created",
        extra={
            "svc_override_id": str(override_id),
            "svc_member_id": str(member_id),
            "svc_rule_type": rule_type,
            "svc_scope": scope,
            "svc_status": status,
            "svc_tenant_id": str(tenant_id),
        },
    )

    return override


def _check_requires_approval(
    rule_type: str,
    tenant_id: uuid.UUID,
    approval_config_lookup: Any | None = None,
) -> bool:
    """Determine if an override requires supervisor approval.

    Checks tenant-specific approval config first, then falls back to
    default rules based on rule type.
    """
    if approval_config_lookup is not None:
        config = approval_config_lookup(rule_type, tenant_id)
        if config is not None:
            return config.get("requires_approval", True)

    # Default: auto-approve low-risk, require approval for financial
    if rule_type in AUTO_APPROVE_RULE_TYPES:
        return False
    if rule_type in SUPERVISOR_REQUIRED_RULE_TYPES:
        return True

    # Unknown rule types default to requiring approval
    return True


def approve_override(
    override: dict[str, Any],
    approved_by: str,
) -> dict[str, Any]:
    """Approve a pending override, activating it.

    Args:
        override: The override dict to approve.
        approved_by: User ID of the approver.

    Returns:
        Updated override dict with active status.

    Raises:
        OverrideError: If the override is not in pending_approval status.
    """
    if override.get("status") != "pending_approval":
        raise OverrideError(
            f"Cannot approve override in status '{override.get('status')}': "
            f"only 'pending_approval' overrides can be approved"
        )

    override["status"] = "active"
    override["approved_by"] = approved_by

    logger.info(
        "override.approved",
        extra={
            "svc_override_id": override.get("id", ""),
            "svc_approved_by": approved_by,
            "svc_tenant_id": override.get("tenant_id", ""),
        },
    )

    return override


def revoke_override(
    override: dict[str, Any],
    revoked_by: str,
) -> dict[str, Any]:
    """Revoke an active override.

    Args:
        override: The override dict to revoke.
        revoked_by: User ID of the revoker.

    Returns:
        Updated override dict with revoked status.

    Raises:
        OverrideError: If the override is not in active or pending_approval status.
    """
    if override.get("status") not in ("active", "pending_approval"):
        raise OverrideError(
            f"Cannot revoke override in status '{override.get('status')}'"
        )

    override["status"] = "revoked"

    logger.info(
        "override.revoked",
        extra={
            "svc_override_id": override.get("id", ""),
            "svc_revoked_by": revoked_by,
            "svc_tenant_id": override.get("tenant_id", ""),
        },
    )

    return override


def check_overrides(
    member_id: uuid.UUID,
    rule_id: uuid.UUID | None,
    drug_ndc: str | None,
    tenant_id: uuid.UUID,
    overrides_store: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Check for active overrides applicable to a member/rule/drug combination.

    Filters by:
    1. Tenant match
    2. Member match
    3. Status == 'active'
    4. Not expired
    5. Scope/NDC matching

    Args:
        member_id: Member UUID.
        rule_id: Optional rule ID to check against.
        drug_ndc: Optional NDC for drug-scoped override matching.
        tenant_id: Tenant UUID.
        overrides_store: Optional list of overrides (for testing/in-memory).

    Returns:
        List of active, non-expired overrides matching the criteria.
    """
    if overrides_store is None:
        return []

    now = datetime.now(UTC)
    active_overrides: list[dict[str, Any]] = []

    for override in overrides_store:
        # Tenant match
        if override.get("tenant_id") != str(tenant_id):
            continue

        # Member match
        if override.get("member_id") != str(member_id):
            continue

        # Status must be active
        if override.get("status") != "active":
            continue

        # Check expiration
        expires_at_str = override.get("expires_at")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at < now:
                    continue
            except (ValueError, TypeError):
                continue

        # Rule match (if specified)
        if rule_id is not None and override.get("rule_id") != str(rule_id):
            continue

        # Scope/NDC matching
        scope = override.get("scope", "")
        if scope == "member_rule_drug":
            # Must match NDC
            if drug_ndc and override.get("ndc") != drug_ndc:
                continue
        elif scope == "member_rule_any":
            # Matches any drug for this rule
            pass
        elif scope == "member_rule_pharmacy":
            # Pharmacy scoping handled at a higher level
            pass

        active_overrides.append(override)

    return active_overrides


def is_overridable(rule_type: str) -> bool:
    """Check if a rule type can be overridden.

    Returns False for DUR critical hard stops and government exclusion rules.
    """
    return rule_type not in ALL_NON_OVERRIDABLE
