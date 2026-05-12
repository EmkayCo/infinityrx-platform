"""B9.B — Registry of FDB TableSpec instances by tier.

This module is the SINGLE SOURCE OF TRUTH for which FDB tables the
platform knows about. B9.B-G populates it tier by tier:

  B9.B → 113 Tier A specs
  B9.C → 66 Tier B specs
  B9.D → 16 Tier C non-RNDC14
  B9.E → 1 RNDC14
  B9.F → 2 pricing big (RNP2 + RPRDPP0)
  B9.G → 19 Tier D / MTL specs

Phase 09's 3 pricing specs (RNP3, RPRDPTD0, RNPTYPD0) live inside
`fdb_pricing_ingester.py` for historical reasons — they predate the
unified registry. The B9 F4 coverage assertion does NOT scan them
because their `delta_semantics` is UNKNOWN (backward-compat default).
They will migrate into this registry in a future cleanup wave.

The F4 contract (codex GATE-CLOSE R1 MEDIUM 2):
  For every spec in REGISTERED_SPECS whose delta_semantics is in
  {UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY},
  there MUST be a contract-test wired up — see
  `tests/unit/test_fdb_contract_coverage.py`.
"""
from __future__ import annotations

from drug_database.services.fdb_adapter import TableSpec


# B9.B starts empty. Each B9.B Tier A commit appends to this list AND
# updates the CONTRACT_TESTED_SPECS frozenset in
# `tests/unit/test_fdb_contract_coverage.py` — atomic per-spec PRs.
REGISTERED_SPECS: list[TableSpec] = []


__all__ = ["REGISTERED_SPECS"]
