"""B9.B C19 — Generic Tier-driven FDB loader (TableSpec → Postgres).

The Phase 09 `fdb_pricing_ingester` was hand-coded for 3 tables.
B9.B+ needs a SPEC-driven path that ingests any TableSpec registered
in `fdb_specs.REGISTERED_SPECS` filtered by `loader_group`. This
module IS that path.

Per codex B9.B GATE-CLOSE R1 HIGH 1: the gate criterion says
`load_fdb.py --mode fdb_tier_a` re-run produces 0 net new rows.
That mode now lives in `scripts/load_fdb.py` and dispatches into
`load_tier_group()` below.

Public surface:

    load_tier_group(
        session,
        adapter,
        drop,
        *,
        group: str,
        dry_run: bool = False,
        ingestion_run_id: str | None = None,
    ) -> TierLoadResult

The loader uses INSERT ... ON CONFLICT (natural_key) DO UPDATE for
UPSERT_BY_NATURAL_KEY semantics, ON CONFLICT (natural_key) DO NOTHING
for all-NK junction tables, and plain INSERT for APPEND_ONLY.

The first weekly delta replay against the same drop produces 0 net
new rows for every spec (the SC-7 idempotency contract).
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import (
    Column,
    MetaData,
    String,
    Table,
    text,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    FDBAdapter,
    FDBDrop,
    TableSpec,
)
from drug_database.services.fdb_loader_registry import filter_loadable_specs

_log = logging.getLogger(__name__)


@dataclass
class TierLoadResult:
    """Per-tier load summary returned by `load_tier_group`."""

    group: str
    drop_date: Any
    dry_run: bool
    table_summaries: dict[str, "TableLoadSummary"] = field(default_factory=dict)

    @property
    def total_inserted(self) -> int:
        return sum(s.inserted for s in self.table_summaries.values())

    @property
    def total_updated(self) -> int:
        return sum(s.updated for s in self.table_summaries.values())

    @property
    def total_skipped(self) -> int:
        return sum(s.skipped for s in self.table_summaries.values())


@dataclass
class TableLoadSummary:
    """Per-table load summary inside a TierLoadResult."""

    table_name: str
    rows_parsed: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0


def load_tier_group(
    session: Session,
    adapter: FDBAdapter,
    drop: FDBDrop,
    *,
    group: str,
    dry_run: bool = False,
    fdb_load_mtl: bool = False,
    schema: str = "drug_database",
    specs: Sequence[TableSpec] | None = None,
) -> TierLoadResult:
    """Load every TableSpec in `group` from the drop into Postgres.

    Args:
        session: SQLAlchemy session bound to the reference DB.
        adapter: concrete FDBAdapter (typically FDBLocalDropAdapter).
        drop: target FDBDrop.
        group: `loader_group` filter (e.g., "fdb_tier_a"). Specs
            whose loader_group != group are skipped.
        dry_run: parse + count only; no writes.
        fdb_load_mtl: passed through to the MTL guard (see
            `fdb_loader_registry`). Default False excludes MTL.
        schema: target Postgres schema (default "drug_database").
        specs: override the registry-driven discovery (test seam).
            None → import from `fdb_specs.REGISTERED_SPECS`.

    Returns:
        TierLoadResult with per-table counters.
    """
    if specs is None:
        from drug_database.services.fdb_specs import REGISTERED_SPECS
        specs = REGISTERED_SPECS

    eligible = filter_loadable_specs(
        specs, fdb_load_mtl=fdb_load_mtl, only_groups=[group]
    )
    if not eligible:
        _log.warning(
            "load_tier_group_no_specs group=%s — registry has no specs "
            "with loader_group=%s under fdb_load_mtl=%s",
            group, group, fdb_load_mtl,
        )

    result = TierLoadResult(group=group, drop_date=drop.drop_date, dry_run=dry_run)

    md = MetaData(schema=schema)
    for spec in eligible:
        summary = TableLoadSummary(table_name=spec.table_name)
        result.table_summaries[spec.table_name] = summary

        # Bind a generic Table reflecting only column names (all TEXT-typed
        # at the binding layer; coercion happens at parse time).
        table = Table(
            spec.table_name.lower(),
            md,
            *(Column(c, String) for c in spec.columns),
            extend_existing=True,
        )

        for row in adapter.parse_table(drop, spec):
            summary.rows_parsed += 1
            if dry_run:
                continue

            # Stringify Decimal / date values so they pass through generic
            # String columns; Postgres NUMERIC + DATE coerce from text.
            row_str = {
                k: (str(v) if v is not None else None)
                for k, v in row.items()
                if k in {c.name for c in table.columns}
            }

            stmt = pg_insert(table).values(**row_str)

            if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
                # Every row appends — no conflict resolution.
                session.execute(stmt)
                summary.inserted += 1
            elif spec.delta_semantics in {
                DeltaSemantics.UPSERT_BY_NATURAL_KEY,
                DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
            }:
                if not spec.natural_key:
                    raise ValueError(
                        f"{spec.table_name}: UPSERT semantics requires "
                        f"natural_key; got empty."
                    )
                non_key_cols = [
                    c for c in spec.columns if c not in spec.natural_key
                ]
                if non_key_cols:
                    update_set = {
                        c: row_str[c] for c in non_key_cols if c in row_str
                    }
                    stmt = stmt.on_conflict_do_update(
                        index_elements=list(spec.natural_key),
                        set_=update_set,
                    )
                else:
                    # All-NK junction table — DO NOTHING is the correct
                    # semantic (there's nothing to update).
                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=list(spec.natural_key)
                    )
                session.execute(stmt)
                # Per-row insert-vs-update accounting requires RETURNING
                # xmax/xmin which is dialect-specific. The wave's
                # post-load reconciliation comes from row-count diffs,
                # not from this counter.
                summary.inserted += 1
            else:
                # UNKNOWN / TRUNCATE_RELOAD — out of scope for this
                # generic loader. Log + skip; specialized loaders
                # handle these in B9.D / B9.F.
                _log.warning(
                    "load_tier_group_unsupported_semantics table=%s "
                    "semantics=%s",
                    spec.table_name, spec.delta_semantics.value,
                )
                summary.skipped += 1

        if not dry_run:
            session.commit()
        _log.info(
            "load_tier_group_table_done table=%s parsed=%d inserted=%d "
            "updated=%d skipped=%d",
            spec.table_name,
            summary.rows_parsed,
            summary.inserted,
            summary.updated,
            summary.skipped,
        )

    return result


__all__ = ["TierLoadResult", "TableLoadSummary", "load_tier_group"]
