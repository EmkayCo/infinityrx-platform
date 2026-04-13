#!/usr/bin/env python3
"""Verify a pg_dump backup by restoring it and comparing row counts.

Used by CI and by oncall to validate that backups are actually
restorable (a HIPAA contingency-plan requirement — a backup you've
never restored is not a backup you can rely on).

Algorithm:
    1. Enumerate source DB: list (schema, table, row_count) for every
       user table (excludes pg_catalog / information_schema).
    2. Run restore.sh against a throwaway target DB.
    3. Enumerate target DB: same (schema, table, row_count) list.
    4. Compare. Fail if any table is missing or row counts differ.

Usage:
    ./verify_backup.py <backup_file.sql.gz>

Environment (mirrors backup.sh / restore.sh):
    PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE

Exit codes:
    0  row counts match exactly
    1  discrepancy detected
    2  bad arguments
    3  restore failed
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

import psycopg2

ROW_COUNT_SQL = """
SELECT schemaname, relname, n_live_tup
FROM pg_stat_user_tables
ORDER BY schemaname, relname
"""


def _connect(dbname: str):
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        user=os.getenv("PGUSER", "infinityrx"),
        password=os.getenv("PGPASSWORD", ""),
        dbname=dbname,
    )


def _analyze(dbname: str) -> None:
    """Force pg_stat_user_tables to refresh by running ANALYZE."""
    conn = _connect(dbname)
    try:
        conn.autocommit = True  # ANALYZE cannot run inside a transaction block
        with conn.cursor() as cur:
            cur.execute("ANALYZE")
    finally:
        conn.close()


def _row_counts(dbname: str) -> dict[tuple[str, str], int]:
    conn = _connect(dbname)
    try:
        with conn.cursor() as cur:
            cur.execute(ROW_COUNT_SQL)
            return {(row[0], row[1]): int(row[2]) for row in cur.fetchall()}
    finally:
        conn.close()


def _exact_row_counts(dbname: str, tables: Iterable[tuple[str, str]]) -> dict[tuple[str, str], int]:
    """Issue COUNT(*) per table for an exact check — pg_stat is approximate."""
    out: dict[tuple[str, str], int] = {}
    conn = _connect(dbname)
    try:
        with conn.cursor() as cur:
            for schema, table in tables:
                # Identifiers must be quoted to survive special characters.
                cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
                row = cur.fetchone()
                out[(schema, table)] = int(row[0]) if row else 0
    finally:
        conn.close()
    return out


def verify(backup_file: str) -> int:
    source_db = os.getenv("PGDATABASE", "infinityrx")
    target_db = f"infinityrx_verify_{int(time.time())}"

    if not Path(backup_file).is_file():
        print(f"FATAL: backup file not found: {backup_file}", file=sys.stderr)
        return 2

    print(f"[verify] source={source_db} target={target_db}")

    # Snapshot source row counts BEFORE restoring (target restore won't
    # touch the source, but we want a stable baseline).
    _analyze(source_db)
    source_tables = list(_row_counts(source_db).keys())
    source_counts = _exact_row_counts(source_db, source_tables)
    print(f"[verify] source tables={len(source_counts)} total_rows={sum(source_counts.values())}")

    # Run restore.sh
    script = Path(__file__).parent / "restore.sh"
    proc = subprocess.run(
        ["bash", str(script), backup_file, target_db],
        env=os.environ.copy(),
        check=False,
    )
    if proc.returncode != 0:
        print("[verify] restore.sh failed", file=sys.stderr)
        return 3

    # Count in the restored DB
    _analyze(target_db)
    target_counts = _exact_row_counts(target_db, source_tables)
    print(f"[verify] target tables={len(target_counts)} total_rows={sum(target_counts.values())}")

    # Compare
    mismatches: list[str] = []
    for key, expected in source_counts.items():
        actual = target_counts.get(key)
        if actual is None:
            mismatches.append(f"missing table {key[0]}.{key[1]}")
        elif actual != expected:
            mismatches.append(
                f"row count mismatch {key[0]}.{key[1]}: source={expected} target={actual}"
            )

    # Also flag tables present in target but not source (unexpected residue).
    for key in target_counts.keys() - source_counts.keys():
        mismatches.append(f"unexpected table in target: {key[0]}.{key[1]}")

    # Cleanup: drop the throwaway DB (best effort).
    try:
        admin_conn = _connect("postgres")
        admin_conn.autocommit = True
        try:
            with admin_conn.cursor() as cur:
                cur.execute(f'DROP DATABASE IF EXISTS "{target_db}"')
        finally:
            admin_conn.close()
    except Exception as exc:  # pragma: no cover
        print(f"[verify] WARN: could not drop {target_db}: {exc}", file=sys.stderr)

    if mismatches:
        print("[verify] FAILED", file=sys.stderr)
        for m in mismatches:
            print(f"  - {m}", file=sys.stderr)
        return 1

    print("[verify] OK — all row counts match")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: verify_backup.py <backup_file.sql.gz>", file=sys.stderr)
        return 2
    return verify(argv[1])


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv))
