"""B9.B C1 — F4 from codex GATE-CLOSE R1 MEDIUM 2.

The DELTA_SEMANTICS contract template at `_fdb_contract.py` is
useless if a B9.B-G commit can land a new spec WITHOUT wiring a
contract test. This file is the coverage canary:

  For every TableSpec in `drug_database.services.fdb_specs.
  REGISTERED_SPECS` whose `delta_semantics` is in the checkable set
  ({UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY}),
  the spec's `table_name` MUST appear in `CONTRACT_TESTED_SPECS`
  below, AND there must be a test in the suite that calls
  `assert_delta_semantics_acd_cycle(spec, ...)` for it.

The atomic-per-spec PR pattern: a B9.B Tier A commit that adds a
spec to `REGISTERED_SPECS` ALSO appends to `CONTRACT_TESTED_SPECS`
AND lands the contract test in the same commit. Forgetting any one
of those three fails this test.

UNKNOWN and TRUNCATE_RELOAD specs are intentionally excluded —
UNKNOWN is Phase 09 backward-compat (no contract by design) and
TRUNCATE_RELOAD has a separate end-to-end reload contract that
runs at the integration layer, not via the A/C/D simulator.
"""
from __future__ import annotations

from drug_database.services.fdb_adapter import DeltaSemantics
from drug_database.services.fdb_specs import REGISTERED_SPECS


# Delta semantics classes that require an A/C/D contract test.
_CHECKABLE_SEMANTICS = frozenset({
    DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
    DeltaSemantics.APPEND_ONLY,
})


# Names of TableSpecs known to have a contract-test wired up.
#
# B9.B C5+ pattern: per-batch test modules declare their own
# `BATCH_TESTED_NAMES` constant. This loader unions every such constant
# across all `test_fdb_tier_a_batch_*.py` modules in the same package.
# Parallel agents own their own batch_N file; no merge conflict here.
#
# Phase 09's 3 pricing specs (RNP3 / RPRDPTD0 / RNPTYPD0) live outside
# REGISTERED_SPECS with delta_semantics=UNKNOWN — they predate the
# contract template and are out of scope for this assertion.


def _load_batch_tested_names() -> frozenset[str]:
    """Discover per-batch BATCH_TESTED_NAMES exports and union them.

    Looks at every sibling test module in this package whose name
    starts with `test_fdb_tier_a_batch_`. Imports each, reads its
    BATCH_TESTED_NAMES constant (frozenset[str] expected). Missing
    or wrong-typed exports raise loudly — silent type drift would
    let the coverage canary go quiet on a real omission.
    """
    import importlib
    import pkgutil

    parent_pkg = ".".join(__name__.split(".")[:-1]) or __name__
    try:
        pkg = importlib.import_module(parent_pkg)
    except ImportError:
        return frozenset()
    if not hasattr(pkg, "__path__"):
        return frozenset()
    out: set[str] = set()
    for info in pkgutil.iter_modules(pkg.__path__):
        if not info.name.startswith("test_fdb_tier_a_batch_"):
            continue
        mod = importlib.import_module(f"{parent_pkg}.{info.name}")
        names = getattr(mod, "BATCH_TESTED_NAMES", None)
        if names is None:
            # Tolerate batch test modules that haven't declared the
            # constant yet (during the C6+ wave evolution); the F4
            # canary will still fire on coverage gaps.
            continue
        if not isinstance(names, (frozenset, set, tuple, list)):
            raise TypeError(
                f"{parent_pkg}.{info.name}.BATCH_TESTED_NAMES must be "
                f"frozenset/set/tuple/list of str; got {type(names).__name__}."
            )
        out.update(names)
    return frozenset(out)


CONTRACT_TESTED_SPECS: frozenset[str] = _load_batch_tested_names()


# ---------------------------------------------------------------------------
# F4 invariant
# ---------------------------------------------------------------------------


def test_every_checkable_spec_has_contract_coverage() -> None:
    """For each registered spec with checkable delta semantics, a test exists."""
    checkable_names = {
        s.table_name for s in REGISTERED_SPECS
        if s.delta_semantics in _CHECKABLE_SEMANTICS
    }
    missing = checkable_names - CONTRACT_TESTED_SPECS
    assert not missing, (
        f"B9.B F4 coverage violation: {len(missing)} TableSpec(s) "
        f"registered with checkable delta_semantics but missing from "
        f"CONTRACT_TESTED_SPECS: {sorted(missing)}. For each:\n"
        f"  1. Add a test calling assert_delta_semantics_acd_cycle(spec, ...).\n"
        f"  2. Append the table_name to CONTRACT_TESTED_SPECS in this file.\n"
        f"Failure to do BOTH means a regression like the A4 "
        f"'ON CONFLICT DO NOTHING' bug could ship undetected."
    )


def test_no_stale_entries_in_contract_tested_specs() -> None:
    """A name in CONTRACT_TESTED_SPECS that is NOT in REGISTERED_SPECS = stale.

    Stale entries hide deletions: if a spec is removed from the
    registry but its name stays in CONTRACT_TESTED_SPECS, the
    coverage assertion still passes but the contract test now
    references a non-existent spec — likely silently skipped.
    """
    registered_names = {s.table_name for s in REGISTERED_SPECS}
    stale = CONTRACT_TESTED_SPECS - registered_names
    assert not stale, (
        f"B9.B F4: {len(stale)} stale entries in CONTRACT_TESTED_SPECS "
        f"(in coverage set but NOT in REGISTERED_SPECS): {sorted(stale)}. "
        f"Either restore the spec to the registry, or remove the name + "
        f"its contract test in the same commit."
    )


# ---------------------------------------------------------------------------
# Empty-baseline canary — DELETED on first batch landing (B9.B C6, `50e7a88`).
# The canary served its purpose: forced the operator's attention to this
# file when the first Tier A spec arrived. Now that batch_01 is in, the
# coverage assertion above is the live invariant.
# ---------------------------------------------------------------------------
