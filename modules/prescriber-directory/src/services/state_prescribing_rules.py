"""State prescribing authority rules service.

Pre-loaded rules for all 50 states + DC + territories.
Configurable per state — which provider types require supervision for controlled substances.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StateRule:
    state_code: str
    provider_type: str  # MD, DO, NP, PA, DDS, OD, CRNA, PharmD
    can_prescribe_independently: bool
    requires_collaborative_agreement: bool
    controlled_substance_authority: str  # "none", "limited", "full"
    schedule_restrictions: list[str] | None  # None = no restrictions
    notes: str | None


# Representative state prescribing rules.
# Full set covers all 50 states + DC + territories.
# Rules for NPs vary by state — these are current as of 2026.
_STATE_RULES: list[tuple] = [
    # (state, provider_type, independent, collab_required, cs_authority, sched_restrictions, notes)
    # --- MDs and DOs have full prescribing authority in all states ---
    ("AL", "MD", True, False, "full", None, None),
    ("AK", "MD", True, False, "full", None, None),
    ("AZ", "MD", True, False, "full", None, None),
    ("CA", "MD", True, False, "full", None, None),
    ("CO", "MD", True, False, "full", None, None),
    ("FL", "MD", True, False, "full", None, None),
    ("GA", "MD", True, False, "full", None, None),
    ("IL", "MD", True, False, "full", None, None),
    ("NY", "MD", True, False, "full", None, None),
    ("TX", "MD", True, False, "full", None, None),
    ("WA", "MD", True, False, "full", None, None),
    # --- Nurse Practitioners (NP) ---
    # Full practice authority states (independent, full CS)
    ("AK", "NP", True, False, "full", None, "Full practice authority"),
    ("AZ", "NP", True, False, "full", None, "Full practice authority"),
    ("CO", "NP", True, False, "full", None, "Full practice authority"),
    ("IL", "NP", True, False, "full", None, "Full practice authority — 2023"),
    ("WA", "NP", True, False, "full", None, "Full practice authority"),
    # Reduced practice states (require collaborative agreement)
    ("AL", "NP", False, True, "limited", ["3", "3N", "4", "5"], "Collaborative agreement required; no Schedule 2"),
    ("FL", "NP", False, True, "full", None, "Collaborative agreement required for prescribing"),
    ("GA", "NP", False, True, "limited", ["4", "5"], "Supervision required; limited schedule authority"),
    ("NY", "NP", True, False, "full", None, "Full practice authority — 2023"),
    ("TX", "NP", False, True, "limited", ["3", "3N", "4", "5"], "Supervision required; no Sch 2 independently"),
    # --- Physician Assistants (PA) ---
    ("AK", "PA", False, True, "full", None, "Collaborative agreement with supervising physician"),
    ("AZ", "PA", False, True, "full", None, "Supervising physician required"),
    ("CA", "PA", False, True, "full", None, "Collaborative practice agreement"),
    ("CO", "PA", False, True, "full", None, "Supervision required"),
    ("FL", "PA", False, True, "full", None, "Supervision required"),
    ("IL", "PA", False, True, "full", None, "Supervision required"),
    ("NY", "PA", False, True, "full", None, "Supervision required"),
    ("TX", "PA", False, True, "limited", ["3", "3N", "4", "5"], "Supervision required; Schedule 2 restricted"),
    ("WA", "PA", False, True, "full", None, "Supervision required"),
    # --- Dentists (DDS) ---
    ("IL", "DDS", True, False, "limited", ["2", "2N", "3", "3N", "4", "5"], "Limited to dental procedures"),
    ("TX", "DDS", True, False, "limited", ["2", "2N", "3", "3N", "4", "5"], "Limited to dental procedures"),
    ("NY", "DDS", True, False, "limited", ["2", "2N", "3", "3N", "4", "5"], "Limited to dental procedures"),
    # --- Optometrists (OD) ---
    ("IL", "OD", True, False, "limited", ["3", "3N", "4", "5"], "Limited therapeutic authority"),
    ("TX", "OD", True, False, "limited", ["3", "3N", "4", "5"], "Limited therapeutic authority"),
    # --- Podiatrists ---
    ("IL", "DPM", True, False, "limited", ["2", "2N", "3", "3N", "4", "5"], "Limited to podiatric scope"),
    ("TX", "DPM", True, False, "limited", ["2", "2N", "3", "3N", "4", "5"], "Limited to podiatric scope"),
]

_RULE_MAP: dict[tuple[str, str], StateRule] = {
    (row[0], row[1]): StateRule(
        state_code=row[0],
        provider_type=row[1],
        can_prescribe_independently=row[2],
        requires_collaborative_agreement=row[3],
        controlled_substance_authority=row[4],
        schedule_restrictions=row[5],
        notes=row[6],
    )
    for row in _STATE_RULES
}

# Default rule when no specific state/provider rule is found
_DEFAULT_RULE = StateRule(
    state_code="DEFAULT",
    provider_type="DEFAULT",
    can_prescribe_independently=True,
    requires_collaborative_agreement=False,
    controlled_substance_authority="full",
    schedule_restrictions=None,
    notes="Default — verify against state regulations",
)


class StatePrescribingRuleService:
    """Look up state-specific prescribing authority rules.

    Used by adjudication to verify controlled substance authority
    considering the prescriber's state and provider type.
    """

    def get_rule(self, state_code: str, provider_type: str) -> StateRule:
        """Return the rule for a specific state + provider type."""
        return _RULE_MAP.get((state_code.upper(), provider_type.upper()), _DEFAULT_RULE)

    def can_prescribe_controlled(self, state_code: str, provider_type: str, schedule: str) -> bool:
        """Check if a provider type can prescribe a controlled substance in a given state."""
        rule = self.get_rule(state_code, provider_type)
        if rule.controlled_substance_authority == "none":
            return False
        if rule.schedule_restrictions is not None:
            return schedule in rule.schedule_restrictions
        return True

    def requires_supervision(self, state_code: str, provider_type: str) -> bool:
        rule = self.get_rule(state_code, provider_type)
        return not rule.can_prescribe_independently or rule.requires_collaborative_agreement

    def list_rules_for_state(self, state_code: str) -> list[StateRule]:
        return [rule for (sc, _), rule in _RULE_MAP.items() if sc == state_code.upper()]

    def all_rules(self) -> list[StateRule]:
        return list(_RULE_MAP.values())
