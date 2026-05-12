"""B9.A C10 — FDW name-collision preflight.

Generates the expected B9 table names (217 tables across Tiers A/B/C/D
plus RNDC14 + pricing) and scans every schema in `infinityrx_reference`
for any pre-existing table with the same name. Any collision aborts
B9.B before a single migration runs.

Why this exists: B9.B-G land alembic migrations into the
`drug_database` schema. If any other schema (`reference`, `shared`,
`public`, or a leftover dev schema) already contains a table whose
name matches a B9 table, the migration succeeds but the FDW exposure
silently picks the wrong one — operator sees stale data and never
gets a hard error.

The collision check is namespace-aware:
  * Collision = (any_schema, name in B9-expected-list)
  * Same-schema-different-name: ignored.
  * Different-name-but-similar: ignored.
  * `drug_database.<b9_name>`: NOT a collision IF the table was
    created by a prior B9.B-G migration (alembic_version proves it).
    Conservative path: any pre-existing table in `drug_database`
    matching a B9 name is reported, operator confirms it is owned
    by B9 before continuing.

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python infrastructure/scripts/preflight_b9_name_collision.py
    python infrastructure/scripts/preflight_b9_name_collision.py \\
        --record-counts data/reference/fdb/TEL251759D/Current/RECORD_COUNTS.TXT \\
        --evidence-out waves/B9/preflight_collision_evidence.md

Exit codes:
    0  no collisions
    1  config error (missing env var, RECORD_COUNTS missing, etc.)
    2  collisions found — operator MUST resolve before B9.B

Test seam: `scan_for_collisions` takes a `table_lister` callable so
unit tests can inject a fake (set of (schema, name) tuples) without
needing Postgres. The default reads
`information_schema.tables WHERE table_type='BASE TABLE'`.
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

logger = logging.getLogger("preflight_b9")


# ---------------------------------------------------------------------------
# Name generation
# ---------------------------------------------------------------------------


def fdb_name_to_table_name(fdb_table_name: str) -> str:
    """Convert a RECORD_COUNTS.TXT key to the DB table name.

    Convention used by `gen_fdb_tier_migration.py` (B9.A C2):
      RFOO_BAR_BAZ  →  rfoo_bar_baz
      RNP3_NDC_PRICE → rnp3_ndc_price

    The transformation is lower-case only — underscores are preserved
    byte-for-byte. No other normalization. Matches the
    `spec.table_name.lower()` call in `_create_table_block`.
    """
    return fdb_table_name.strip().lower()


def load_expected_names(record_counts_path: Path) -> list[str]:
    """Read RECORD_COUNTS.TXT and return the full list of expected DB table names.

    Real-file format observed at `data/reference/fdb/TEL251759D/Current/`:
      <KEY>|<count>
    one entry per CRLF line; blanks and `#` comments tolerated.

    The loader accepts BOTH `|` (production format) and `=` (legacy
    synthetic test fixtures). Matches `_fdb_contract._parse_record_counts`.

    Returns DB-shaped names (lower-cased). Order preserved from the
    file for reproducibility.
    """
    text = record_counts_path.read_text(encoding="latin-1")
    out: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            key, _, _val = line.partition("|")
        elif "=" in line:
            key, _, _val = line.partition("=")
        else:
            continue
        db_name = fdb_name_to_table_name(key)
        if db_name in seen:
            continue
        seen.add(db_name)
        out.append(db_name)
    return out


# ---------------------------------------------------------------------------
# Collision scan
# ---------------------------------------------------------------------------


# Schemas that are EXPECTED to contain B9-named tables after the
# migration runs. Pre-existing tables here are reported but operator
# may sign them off if they came from a prior B9 partial run.
_OWNED_SCHEMAS = frozenset({"drug_database"})

# Schemas that should NEVER contain B9-named tables. Any pre-existing
# match here is an immediate hard collision.
_HARD_COLLISION_SCHEMAS = frozenset({
    "reference",  # FDW-fronted; conflicts produce silent wrong-data
    "shared",
    "public",
    "drug_db",   # legacy schema name still present per Phase 11A
    "pharmacy_dir",
    "prescriber_dir",
    "core",
})


def scan_for_collisions(
    expected_names: Iterable[str],
    *,
    table_lister: Callable[[], set[tuple[str, str]]],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (hard_collisions, soft_collisions) lists of (schema, name) tuples.

    A hard collision aborts; a soft collision is reported and
    requires explicit operator sign-off before continuing.
    """
    existing = table_lister()
    expected_set = set(expected_names)

    hard: list[tuple[str, str]] = []
    soft: list[tuple[str, str]] = []

    for schema, name in existing:
        if name not in expected_set:
            continue
        if schema in _HARD_COLLISION_SCHEMAS:
            hard.append((schema, name))
        elif schema in _OWNED_SCHEMAS:
            soft.append((schema, name))
        else:
            # Unknown schema — treat as hard. Better a false alarm than
            # a silent collision in a schema we forgot to classify.
            hard.append((schema, name))

    # Stable ordering for evidence reproducibility
    return sorted(hard), sorted(soft)


# ---------------------------------------------------------------------------
# Postgres lister (default — replaced in tests)
# ---------------------------------------------------------------------------


def _postgres_table_lister(connection_string: str) -> set[tuple[str, str]]:
    """Read base tables from information_schema across all non-system schemas."""
    from sqlalchemy import create_engine, text
    engine = create_engine(connection_string)
    out: set[tuple[str, str]] = set()
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT table_schema, table_name "
                "FROM information_schema.tables "
                "WHERE table_type = 'BASE TABLE' "
                "AND table_schema NOT IN "
                "  ('pg_catalog', 'information_schema', 'pg_toast')"
            ))
            for schema, name in result.fetchall():
                out.add((schema, name))
    finally:
        engine.dispose()
    return out


# ---------------------------------------------------------------------------
# Evidence formatter
# ---------------------------------------------------------------------------


def format_evidence(
    expected_names: list[str],
    hard: list[tuple[str, str]],
    soft: list[tuple[str, str]],
) -> str:
    """Build the markdown evidence body operator commits under waves/B9/."""
    lines: list[str] = [
        "# B9.A C10 — FDW Name-Collision Preflight Evidence",
        "",
        f"Expected B9 table names: **{len(expected_names)}**",
        f"Hard collisions:         **{len(hard)}**",
        f"Soft collisions (owned-schema match): **{len(soft)}**",
        "",
    ]
    if hard:
        lines.append("## Hard collisions — MUST resolve before B9.B")
        lines.append("")
        lines.append("| Schema | Table |")
        lines.append("|---|---|")
        for schema, name in hard:
            lines.append(f"| `{schema}` | `{name}` |")
        lines.append("")
    if soft:
        lines.append("## Soft collisions — drug_database tables matching B9 names")
        lines.append("")
        lines.append(
            "These may be leftovers from a prior partial B9 run. "
            "Operator confirms via alembic_version + manual schema "
            "review before continuing."
        )
        lines.append("")
        lines.append("| Schema | Table |")
        lines.append("|---|---|")
        for schema, name in soft:
            lines.append(f"| `{schema}` | `{name}` |")
        lines.append("")
    if not hard and not soft:
        lines.append("**No collisions found.** B9.B clear to proceed.")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--record-counts",
        type=Path,
        default=None,
        help="Path to FDB RECORD_COUNTS.TXT (defaults to data/reference/fdb/TEL251759D/Current/).",
    )
    parser.add_argument(
        "--evidence-out",
        type=Path,
        default=None,
        help="Optional markdown output path (defaults to stdout-only).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
    )

    # --record-counts default
    if args.record_counts is None:
        repo_root = Path(__file__).resolve().parents[2]
        args.record_counts = (
            repo_root / "data" / "reference" / "fdb" / "TEL251759D"
            / "Current" / "RECORD_COUNTS.TXT"
        )
    if not args.record_counts.exists():
        logger.error(
            "RECORD_COUNTS.TXT not found at %s — pass --record-counts or "
            "verify the FDB drop is on disk.",
            args.record_counts,
        )
        return 1

    expected = load_expected_names(args.record_counts)
    logger.info("preflight_b9_expected_names count=%d", len(expected))

    # Resolve reference-DB URL via shared guard (strict — no fallback).
    try:
        # Avoid hard dependency in unit tests; import only at run time.
        from shared.db.write_path_guard import resolve_reference_db_url
        db_url = resolve_reference_db_url()
    except RuntimeError as e:
        logger.error("%s", e)
        return 1

    def _lister() -> set[tuple[str, str]]:
        return _postgres_table_lister(db_url)

    hard, soft = scan_for_collisions(expected, table_lister=_lister)
    evidence = format_evidence(expected, hard, soft)
    print(evidence)
    if args.evidence_out:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(evidence, encoding="utf-8")
        logger.info("preflight_b9_evidence_written path=%s", args.evidence_out)

    if hard:
        logger.error(
            "preflight_b9_hard_collisions count=%d — refusing to proceed",
            len(hard),
        )
        return 2
    if soft:
        logger.warning(
            "preflight_b9_soft_collisions count=%d — operator sign-off required",
            len(soft),
        )
    logger.info("preflight_b9_clear")
    return 0


if __name__ == "__main__":
    sys.exit(main())
