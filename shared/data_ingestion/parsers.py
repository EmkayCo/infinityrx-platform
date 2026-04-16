"""Shared parsing primitives for reference-data loaders.

Reusable helpers so each loader doesn't re-implement its own CSV/TSV/pipe/XLSX
streaming, Decimal coercion, date parsing, or string normalisation. Every
loader built on :mod:`shared.data_ingestion.base` + :mod:`.batching` uses these
primitives so parsing behaviour is consistent and bug fixes (null handling,
BOM handling, quote handling, etc.) apply everywhere at once.

Design rules:
- Every parser is a streaming generator — we never load multi-GB files into RAM.
- Every value-coercer returns ``None`` on empty/null/invalid and raises only when
  the caller explicitly asked for a required field via a separate ``require_*``
  wrapper. This keeps the hot path branch-free and lets validation live in the
  loader's row-level ``validate()`` callback.
- Decimal uses ``ROUND_HALF_UP`` and coerces via ``str()`` to avoid IEEE-754
  contamination (see ``.claude/rules/financial-precision.md``).
- Regex patterns use ``\\A...\\Z`` anchors per LESSON-004.
"""

from __future__ import annotations

import csv
import logging
import re
from collections.abc import Iterator
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scalar parsers
# ---------------------------------------------------------------------------

_DEFAULT_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%Y%m%d",
    "%d-%b-%Y",   # 15-Jan-2026
    "%d-%b-%y",
)


def strip_or_none(value: Any) -> str | None:
    """Coerce to str, strip whitespace/BOM, return None for empty."""
    if value is None:
        return None
    s = str(value).strip().lstrip("\ufeff")
    return s or None


def parse_decimal(
    value: Any,
    *,
    quantize: str = "0.01",
    rounding: str = ROUND_HALF_UP,
) -> Decimal | None:
    """Coerce to ``Decimal`` with ROUND_HALF_UP quantization.

    Returns ``None`` on empty/null/unparseable. Always passes through ``str()``
    to avoid IEEE-754 float contamination.

    ``quantize`` defaults to ``"0.01"`` (2 decimal places). Pricing data that
    needs sub-cent precision (e.g., NADAC at Decimal(18,6)) should pass
    ``quantize="0.000001"``.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return Decimal(s).quantize(Decimal(quantize), rounding=rounding)
    except (InvalidOperation, ValueError):
        return None


def parse_int(value: Any) -> int | None:
    """Coerce to int, return None on empty/null/unparseable."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(float(s)) if "." in s else int(s)
    except (ValueError, TypeError):
        return None


def parse_bool(value: Any, *, truthy: tuple[str, ...] = ("y", "yes", "true", "t", "1")) -> bool | None:
    """Coerce to bool. Returns None on empty/null."""
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s:
        return None
    return s in truthy


def parse_date(
    value: Any,
    *,
    formats: tuple[str, ...] = _DEFAULT_DATE_FORMATS,
) -> date | None:
    """Parse a date string; returns None on empty/null/unparseable."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Row-yielding file parsers (streaming — never load entire file into RAM)
# ---------------------------------------------------------------------------


def parse_delimited(
    path: Path,
    *,
    delimiter: str = ",",
    quotechar: str | None = '"',
    encoding: str = "utf-8-sig",
    skip_lines: int = 0,
    fieldnames: list[str] | None = None,
    has_header: bool = True,
) -> Iterator[dict[str, str]]:
    """Stream a delimited file (CSV/TSV/pipe) yielding one dict per data row.

    Parameters
    ----------
    delimiter:
        ``","`` for CSV, ``"\\t"`` for TSV, ``"|"`` for pipe. RRF files use
        ``"|"`` with ``quotechar=None``.
    quotechar:
        ``None`` to disable quoting (required for RRF files which contain
        unescaped quotes in free-text columns).
    encoding:
        Default is ``utf-8-sig`` so UTF-8 BOMs are stripped automatically.
    skip_lines:
        Number of lines to skip BEFORE parsing (e.g., CMS ASP has a 3-line
        banner).
    fieldnames:
        Explicit column names. If ``has_header=True``, the file's header row is
        read and these are ignored. If ``has_header=False``, these are used
        (required for RRF files, which have no header row).
    has_header:
        If True, the first line after ``skip_lines`` is treated as the header.
    """
    with path.open("r", encoding=encoding, newline="") as fh:
        for _ in range(skip_lines):
            next(fh, None)

        kwargs: dict[str, Any] = {"delimiter": delimiter}
        if quotechar is None:
            kwargs["quoting"] = csv.QUOTE_NONE
        else:
            kwargs["quotechar"] = quotechar

        if has_header:
            reader = csv.DictReader(fh, **kwargs)
            for row in reader:
                yield {k: (v if v is not None else "") for k, v in row.items() if k is not None}
        else:
            if not fieldnames:
                raise ValueError("fieldnames required when has_header=False")
            reader = csv.reader(fh, **kwargs)
            for raw in reader:
                # Tolerate rows shorter or longer than expected — map what we can
                yield {
                    name: (raw[i] if i < len(raw) else "")
                    for i, name in enumerate(fieldnames)
                }


def parse_xlsx(
    path: Path,
    *,
    sheet: str | int | None = 0,
    header_row: int = 1,
) -> Iterator[dict[str, Any]]:
    """Stream an XLSX file yielding one dict per data row.

    Uses ``openpyxl`` in read-only mode so large files don't balloon RAM.
    ``header_row`` is 1-indexed (sheet row 1 is the default).
    """
    from openpyxl import load_workbook  # lazy — openpyxl is a heavy import

    wb = load_workbook(filename=str(path), read_only=True, data_only=True)
    try:
        ws = wb.worksheets[sheet] if isinstance(sheet, int) else wb[sheet]  # type: ignore[index]

        rows = ws.iter_rows(values_only=True)
        header: list[str] = []
        current_row = 0
        for row in rows:
            current_row += 1
            if current_row < header_row:
                continue
            if current_row == header_row:
                header = [str(c).strip() if c is not None else f"col{i}" for i, c in enumerate(row)]
                continue
            yield {header[i]: row[i] if i < len(row) else None for i in range(len(header))}
    finally:
        wb.close()


def parse_xls(
    path: Path,
    *,
    sheet: int = 0,
    header_row: int = 0,
) -> Iterator[dict[str, Any]]:
    """Stream a legacy .xls file yielding one dict per data row.

    Uses ``xlrd`` for the binary Excel 97-2003 format. ``header_row`` is
    0-indexed here because xlrd uses 0-based row indexing.
    """
    import xlrd  # lazy

    book = xlrd.open_workbook(str(path))
    try:
        ws = book.sheet_by_index(sheet)
        header = [str(ws.cell_value(header_row, c)).strip() for c in range(ws.ncols)]
        for row_idx in range(header_row + 1, ws.nrows):
            yield {header[c]: ws.cell_value(row_idx, c) for c in range(ws.ncols)}
    finally:
        book.release_resources()


__all__ = [
    "parse_bool",
    "parse_date",
    "parse_decimal",
    "parse_delimited",
    "parse_int",
    "parse_xls",
    "parse_xlsx",
    "strip_or_none",
]
