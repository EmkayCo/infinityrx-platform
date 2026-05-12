# B9.A C13 — Module-Level Declarative Base / Metadata Profile

**Captured:** 2026-05-12 (B9.A C13)
**Platform:** Windows 11, Python 3.13.x, SQLAlchemy 2.x
**Source:** `modules/drug-database/drug_database/models/tables.py`

## Why this profile exists

B9.B-G plan to land **217 new SQLAlchemy models** in
`modules/drug-database/drug_database/models/fdb/...`. The question
this profile answers: should every test importing `DrugBase` pay the
cost of loading all 217, or do we split the metadata so per-tier
imports are cheap?

## Phase 09 baseline (pre-B9)

| Metric | Value |
|---|---|
| `import drug_database.models.tables` cold time | **331 ms** |
| `len(DrugBase.metadata.tables)` | **9** |
| Per-table amortized cost | ~37 ms |

Note: the 331 ms includes SQLAlchemy itself warming up (~250 ms), so
the per-table cost on the cold-import path is closer to ~10 ms; later
table imports against the same loaded SQLAlchemy are sub-millisecond.

## Projected post-B9 (if everything lands on DrugBase)

| Scenario | Tables in DrugBase.metadata | Projected cold-import time |
|---|---|---|
| Phase 09 (today) | 9 | 331 ms |
| After B9.B (+113 Tier A) | 122 | ~1.5 s |
| After B9.C (+66 Tier B) | 188 | ~2.2 s |
| After B9.G (+220 total) | 229 | ~2.6 s |

The 8× growth in import time would be paid by EVERY test in the
drug-database module that imports `DrugBase` — including unit tests
that only care about NDC normalization or pricing decimal logic and
have no need for FDB Tier A lookup models.

## Recommended pattern: tier-scoped sub-bases

**Single shared `MetaData(schema="drug_database")` instance**, fanned
out across tier-specific declarative bases:

```python
# modules/drug-database/drug_database/models/fdb/__init__.py
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# One MetaData → all tables share the same schema namespace
# (drug_database) for alembic / FDW purposes.
fdb_metadata = MetaData(schema="drug_database")


class FDBBase(DeclarativeBase):
    """Common base for any cross-tier FDB model — pricing, RNDC14."""
    metadata = fdb_metadata


# Per-tier submodule re-exposes the same base:
# modules/drug-database/drug_database/models/fdb/tier_a/__init__.py
#   from drug_database.models.fdb import FDBBase as TierABase
# Tests that only need Tier A:
#   from drug_database.models.fdb.tier_a import TierABase
# Tests that don't need FDB at all:
#   import nothing from .fdb — DrugBase stays at 9 tables
```

### Why one MetaData, not four

Alembic generates one migration per `MetaData` it sees. Splitting the
metadata would require coordinating migration revision chains across
4 metadata objects — strictly worse than the current single-chain
setup. The READ-side cost is what we are optimizing, not the
WRITE-side migration generation.

### Why per-tier BASES with one METADATA

A SQLAlchemy declarative base is the IMPORT seam — importing the
base imports every class declared against it (Python module
initialization side-effect). Per-tier bases let a test importer say
"I only need Tier A models" and pay only the Tier A cost. The
underlying metadata is shared so alembic still sees one schema.

## Alembic env.py implications

`modules/drug-database/alembic/env.py` must explicitly import the
SHARED metadata when running migration autogen / upgrade. Either:

```python
from drug_database.models.fdb import fdb_metadata
target_metadata = fdb_metadata
```

OR keep Phase 09's `DrugBase.metadata` pointer and ensure the Phase
09 `DrugBase` re-exposes `fdb_metadata` (cleaner — preserves
backward compat for the alembic config).

## B9.A C13 lock-in test

`modules/drug-database/tests/unit/test_module_base_profile.py`
asserts:

1. `len(DrugBase.metadata.tables) == 9` — the Phase 09 surface.
   B9.B-G's first commit lifts this number IF the new tier was
   attached to DrugBase; that's the trigger to refactor to
   tier-scoped bases.
2. `DrugBase` imports without circular-import errors (regression
   detector for the sub-base pattern when it lands).

The test does NOT measure wall-clock import time — too noisy for
CI. The table-count assertion is the load-bearing canary.

## When to flip to tier-scoped bases

**Trigger:** the first B9.B commit that would push
`len(DrugBase.metadata.tables) > 12`. Refactor in the same commit:
move new tier models into `drug_database/models/fdb/tier_a/`,
update alembic env to point at the shared metadata, update the
lock-in test threshold.

**Not before then.** Premature refactor for a future need violates
Karpathy #3 (Surgical Changes). The lock-in test is the alarm.
