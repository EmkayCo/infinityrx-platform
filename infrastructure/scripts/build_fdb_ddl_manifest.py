"""B9.B C4 — Extract per-table DDL into a structured manifest.

Reads the 6 ANSI SQL files inside `NDDF Plus DDL.zip` and produces a
JSON manifest (`infrastructure/scripts/lib/fdb_table_ddl_manifest.json`)
that B9.B-G builder agents consume to author per-table TableSpec +
SQLAlchemy models + contract tests without re-parsing the zip.

Manifest schema:

    {
      "<TABLE_NAME>": {
        "dataset": "NDDF BASICS 3.0" | "NDDF ETC 1.0" | ...,
        "columns": [
          {"name": "...", "sql_type": "VARCHAR(40)" | "NUMBER(10)" | ...,
           "nullable": true|false},
          ...
        ]
      },
      ...
    }

Run:
    python infrastructure/scripts/build_fdb_ddl_manifest.py
        [--ddl-zip <path>] [--out <path>]

Default ddl-zip:
    data/reference/fdb/TEL251759D/Current/NDDF Plus DDL/NDDF PLUS DDL.zip
Default out:
    infrastructure/scripts/lib/fdb_table_ddl_manifest.json

Idempotent — re-running produces the same JSON byte-for-byte.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(\w+)\s*\((.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)

# Match a column line:  <name>  <type>(<args>)  [NULL|NOT NULL]  [...]
_COLUMN_RE = re.compile(
    r"""
    ^\s*
    (?P<name>\w+)\s+
    (?P<type>
        \w+
        (?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?
    )
    (?P<rest>.*?)\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _dataset_from_path(zip_member: str) -> str:
    """Extract the dataset directory name (e.g. 'NDDF BASICS 3.0')."""
    parts = zip_member.split("/")
    # Zip layout: NDDF Plus DDL/<descriptive>/<dataset>/<file>.SQL
    if len(parts) >= 3:
        return parts[-2]
    return "UNKNOWN"


def _parse_columns(body: str) -> list[dict[str, Any]]:
    """Split CREATE TABLE body on commas, parse each column line."""
    cols: list[dict[str, Any]] = []
    # Strip leading/trailing whitespace and comments
    body = re.sub(r"--[^\n]*", "", body)
    # Split on top-level commas (no nested parens to worry about for
    # ANSI SQL column types — the only parens are in (n) or (n,m))
    depth = 0
    buf = ""
    fragments: list[str] = []
    for ch in body:
        if ch == "(":
            depth += 1
            buf += ch
        elif ch == ")":
            depth -= 1
            buf += ch
        elif ch == "," and depth == 0:
            fragments.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        fragments.append(buf)

    for frag in fragments:
        frag = frag.strip()
        if not frag:
            continue
        # Skip constraint declarations (PRIMARY KEY, FOREIGN KEY, etc.)
        upper = frag.upper()
        if upper.startswith(("PRIMARY KEY", "FOREIGN KEY", "UNIQUE",
                             "CHECK", "CONSTRAINT")):
            continue
        m = _COLUMN_RE.match(frag)
        if not m:
            continue
        name = m.group("name")
        # Normalize the type string: collapse internal whitespace so
        # `VARCHAR (11)` and `NUMERIC(16,5)` come out consistent.
        sql_type = re.sub(r"\s+", "", m.group("type"))
        rest_upper = m.group("rest").upper()
        nullable = "NOT NULL" not in rest_upper
        cols.append({
            "name": name,
            "sql_type": sql_type,
            "nullable": nullable,
        })
    return cols


def build_manifest(ddl_zip_path: Path) -> dict[str, dict[str, Any]]:
    """Read the DDL zip and return the per-table manifest dict."""
    manifest: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(ddl_zip_path) as z:
        ansi_files = sorted(n for n in z.namelist() if n.endswith("_ANSI.SQL"))
        for member in ansi_files:
            dataset = _dataset_from_path(member)
            body = z.read(member).decode("latin-1")
            for ct in _CREATE_TABLE_RE.finditer(body):
                table_name = ct.group(1)
                col_block = ct.group(2)
                columns = _parse_columns(col_block)
                if not columns:
                    continue
                manifest[table_name] = {
                    "dataset": dataset,
                    "columns": columns,
                }
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ddl-zip", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    if args.ddl_zip is None:
        args.ddl_zip = (
            repo_root / "data" / "reference" / "fdb" / "TEL251759D"
            / "Current" / "NDDF Plus DDL" / "NDDF PLUS DDL.zip"
        )
    if args.out is None:
        args.out = (
            repo_root / "infrastructure" / "scripts" / "lib"
            / "fdb_table_ddl_manifest.json"
        )
    if not args.ddl_zip.exists():
        print(f"FATAL: DDL zip not at {args.ddl_zip}", file=sys.stderr)
        return 1

    manifest = build_manifest(args.ddl_zip)
    # Sort keys for byte-stable output
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(manifest)} tables to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
