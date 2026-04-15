"""State prescribing authority rules service.

Pre-loaded rules for represented states. Anything **not** explicitly modeled
falls back to a SAFE default (restricted authority + manual review) per Wave
3C / DEA compliance. The previous implementation defaulted to *full* authority
which silently authorized controlled-substance prescribing in ~40 unmodeled
states — a patient-safety and DEA compliance risk flagged in the audit (CR-09
adjacent).

Convention for ``schedule_restrictions``:
    * ``None`` — no restrictions; provider may prescribe any schedule the
      ``controlled_substance_authority`` field permits.
    * ``list[str]`` — the set of schedules the provider IS allowed to
      prescribe in this state. (i.e. allow-list, not deny-list.)
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
    requires_manual_review: bool = False


# Representative state prescribing rules.
# Coverage targets the 10+ most populous states for MD / NP / PA at minimum,
# plus dental/optometry/podiatry exemplars. Rules are current as of 2026.
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
    ("MI", "MD", True, False, "full", None, None),
    ("NY", "MD", True, False, "full", None, None),
    ("NC", "MD", True, False, "full", None, None),
    ("OH", "MD", True, False, "full", None, None),
    ("PA", "MD", True, False, "full", None, None),
    ("TX", "MD", True, False, "full", None, None),
    ("WA", "MD", True, False, "full", None, None),
    # --- DOs mirror MDs in all states ---
    ("CA", "DO", True, False, "full", None, None),
    ("FL", "DO", True, False, "full", None, None),
    ("MI", "DO", True, False, "full", None, "MI has the largest DO population in the country"),
    ("NY", "DO", True, False, "full", None, None),
    ("PA", "DO", True, False, "full", None, None),
    ("TX", "DO", True, False, "full", None, None),
    # --- Nurse Practitioners (NP) ---
    # Full practice authority states (independent, full CS)
    ("AK", "NP", True, False, "full", None, "Full practice authority"),
    ("AZ", "NP", True, False, "full", None, "Full practice authority"),
    ("CO", "NP", True, False, "full", None, "Full practice authority"),
    ("IL", "NP", True, False, "full", None, "Full practice authority — 2023"),
    ("NY", "NP", True, False, "full", None, "Full practice authority — 2023"),
    ("WA", "NP", True, False, "full", None, "Full practice authority"),
    # Reduced practice states (require collaborative agreement)
    ("AL", "NP", False, True, "limited", ["3", "3N", "4", "5"], "Collaborative agreement required; no Schedule 2"),
    ("CA", "NP", False, True, "full", None, "Collaborative practice agreement; AB 890 transition"),
    ("FL", "NP", False, True, "full", None, "Collaborative agreement required for prescribing"),
    ("GA", "NP", False, True, "limited", ["4", "5"], "Supervision required; limited schedule authority"),
    ("MI", "NP", False, True, "limited", ["3", "3N", "4", "5"], "Supervision required; no Schedule 2"),
    ("NC", "NP", False, True, "limited", ["3", "3N", "4", "5"], "Joint supervision required; no Schedule 2"),
    ("OH", "NP", False, True, "full", None, "Standard care arrangement required"),
    ("PA", "NP", False, True, "full", None, "Collaborative agreement required (4140 hours)"),
    ("TX", "NP", False, True, "limited", ["3", "3N", "4", "5"], "Supervision required; no Sch 2 independently"),
    # --- Physician Assistants (PA) ---
    ("AK", "PA", False, True, "full", None, "Collaborative agreement with supervising physician"),
    ("AZ", "PA", False, True, "full", None, "Supervising physician required"),
    ("CA", "PA", False, True, "full", None, "Practice agreement under SB 697"),
    ("CO", "PA", False, True, "full", None, "Supervision required"),
    ("FL", "PA", False, True, "full", None, "Supervision required"),
    ("GA", "PA", False, True, "full", None, "Supervision required; protocol required"),
    ("IL", "PA", False, True, "full", None, "Supervision required"),
    ("MI", "PA", False, True, "full", None, "Practice agreement required"),
    ("NC", "PA", False, True, "full", None, "Supervision required (formerly required practice agreement)"),
    ("NY", "PA", False, True, "full", None, "Supervision required"),
    ("OH", "PA", False, True, "full", None, "Supervision agreement required"),
    ("PA", "PA", False, True, "full", None, "Written agreement with supervising physician"),
    ("TX", "PA", False, True, "limited", ["3", "3N", "4", "5"], "Supervision required; Schedule 2 restricted"),
    ("WA", "PA", False, True, "full", None, "Supervision required"),
    # --- Dentists (DDS) ---
    ("CA", "DDS", True, False, "limited", ["2", "2N", "3", "3N", "4", "5"], "Limited to dental procedures"),
    ("FL", "DDS", True, False, "limited", ["2", "2N", "3", "3N", "4", "5"], "Limited to dental procedures"),
    ("IL", "DDS", True, False, "limited", ["2", "2N", "3", "3N", "4", "5"], "Limited to dental procedures"),
    ("NY", "DDS", True, False, "limited", ["2", "2N", "3", "3N", "4", "5"], "Limited to dental procedures"),
    ("TX", "DDS", True, False, "limited", ["2", "2N", "3", "3N", "4", "5"], "Limited to dental procedures"),
    # --- Optometrists (OD) ---
    ("CA", "OD", True, False, "limited", ["3", "3N", "4", "5"], "Limited therapeutic authority"),
    ("FL", "OD", True, False, "limited", ["3", "3N", "4", "5"], "Limited therapeutic authority"),
    ("IL", "OD", True, False, "limited", ["3", "3N", "4", "5"], "Limited therapeutic authority"),
    ("NY", "OD", True, False, "limited", ["3", "3N", "4", "5"], "Limited therapeutic authority"),
    ("TX", "OD", True, False, "limited", ["3", "3N", "4", "5"], "Limited therapeutic authority"),
    # --- Podiatrists ---
    ("IL", "DPM", True, False, "limited", ["2", "2N", "3", "3N", "4", "5"], "Limited to podiatric scope"),
    ("NY", "DPM", True, False, "limited", ["2", "2N", "3", "3N", "4", "5"], "Limited to podiatric scope"),
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

# SAFE default rule when no specific state/provider rule is found.
# Wave 3C: the previous default granted full authority, which silently
# authorized controlled-substance prescribing for the ~40 unmodeled states.
# The new default forces a manual review and grants no controlled-substance
# authority — adjudication callers can choose to escalate or deny based on
# the ``requires_manual_review`` flag.
_DEFAULT_RULE = StateRule(
    state_code="DEFAULT",
    provider_type="DEFAULT",
    can_prescribe_independently=False,
    requires_collaborative_agreement=True,
    controlled_substance_authority="none",
    schedule_restrictions=[],
    notes=(
        "State rules not yet modeled — default to restricted per DEA "
        "compliance. Manual review required before authorizing controlled "
        "substances. Add a row to _STATE_RULES with the verified state/"
        "provider rule to lift this restriction."
    ),
    requires_manual_review=True,
)


class StatePrescribingRuleService:
    """Look up state-specific prescribing authority rules.

    Used by adjudication to verify controlled substance authority
    considering the prescriber's state and provider type.
    """

    def get_rule(self, state_code: str, provider_type: str) -> StateRule:
        """Return the rule for a specific state + provider type.

        Falls back to a SAFE default (manual review required, no controlled-
        substance authority) when the (state, provider) pair is not modeled.
        """
        return _RULE_MAP.get(
            (state_code.upper(), provider_type.upper()),
            _DEFAULT_RULE,
        )

    def can_prescribe_controlled(
        self, state_code: str, provider_type: str, schedule: str
    ) -> bool:
        """Check if a provider type can prescribe a controlled substance.

        Returns False for any (state, provider) where no rule is modeled —
        callers must route to manual review via ``requires_manual_review``.
        """
        rule = self.get_rule(state_code, provider_type)
        if rule.controlled_substance_authority == "none":
            return False
        if rule.schedule_restrictions is not None:
            return schedule in rule.schedule_restrictions
        return True

    def requires_supervision(self, state_code: str, provider_type: str) -> bool:
        rule = self.get_rule(state_code, provider_type)
        return not rule.can_prescribe_independently or rule.requires_collaborative_agreement

    def requires_manual_review(self, state_code: str, provider_type: str) -> bool:
        """True when the (state, provider) combination is not modeled.

        Adjudication should hold any controlled-substance claim from these
        prescribers for human review until a verified rule row is added.
        """
        return self.get_rule(state_code, provider_type).requires_manual_review

    def list_rules_for_state(self, state_code: str) -> list[StateRule]:
        return [rule for (sc, _), rule in _RULE_MAP.items() if sc == state_code.upper()]

    def all_rules(self) -> list[StateRule]:
        return list(_RULE_MAP.values())
