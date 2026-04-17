"""Shared loader primitives.

Extracted from scripts/load_sam.py (Wave 8) so every loader can share one
implementation of the pieces that are not source-specific. Source-specific
logic (flatten, upsert row shape, mode resolver, response-envelope
detection, natural-key selection) stays in the per-source ingester.

Contents:

- ``get_with_retry(url, params, *, timeout, accept_202=False)``
    requests.get with exponential backoff on 429 / 5xx / transport
    errors. Honours the Retry-After header on 429, falling back to
    exponential-by-attempt otherwise. ``accept_202=True`` returns 202
    as-is (used by async-job pollers that treat 202 as "not ready yet").

- ``parse_retry_after(value)``
    Parse HTTP Retry-After. Accepts an integer-seconds string
    ("120") or an HTTP-date ("Fri, 17 Apr 2026 00:00:00 GMT"). Returns
    seconds as int, or None when the value is empty/unparseable.

- ``get_db_connection()``
    psycopg2 connection factory from DATABASE_URL_SYNC (falls back to
    DATABASE_URL). Strips SQLAlchemy driver prefixes. Caller owns
    commit/close; psycopg2.connection is usable as a context manager
    (commits on success, rolls back on exception).

- ``StateFile(path)``
    Per-source watermark file, one date per line (YYYY-MM-DD). Used by
    incremental loaders to persist the last-successful-run watermark
    across invocations. ``read()`` returns None when the file is absent
    or malformed so callers can branch to "prompt for seed".

- ``stream_json_array(source)``
    Memory-bounded iterator over a top-level JSON array. Accepts either
    a path string / Path or a file-like object (so gzip.open or any
    in-memory BytesIO works without a second wrapper). Uses ijson under
    the hood — peak memory stays at O(single record) regardless of file
    size, critical for the 3.26 GB Part D snapshot.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests

log = logging.getLogger(__name__)

# Defaults tuned for the SAM.gov crawler's workload; every loader can override.
DEFAULT_MAX_RETRIES = 5
DEFAULT_BACKOFF_BASE_SEC = 2


def parse_retry_after(value: str | None) -> int | None:
    """Parse HTTP Retry-After (RFC 7231). Returns seconds or None."""
    if not value:
        return None
    # Integer seconds form.
    try:
        return max(1, int(value))
    except ValueError:
        pass
    # HTTP-date form.
    try:
        dt = datetime.strptime(value, "%a, %d %b %Y %H:%M:%S GMT")
        delta = (dt - datetime.utcnow()).total_seconds()
        return max(1, int(delta))
    except ValueError:
        return None


def get_with_retry(
    url: str,
    params: dict[str, Any],
    *,
    timeout: int,
    accept_202: bool = False,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base_sec: int = DEFAULT_BACKOFF_BASE_SEC,
) -> requests.Response:
    """GET with exponential backoff on 429 / 5xx / transport errors.

    Honours the ``Retry-After`` header on 429; otherwise exponential by
    attempt index (capped implicitly by ``max_retries``).

    ``accept_202=True`` returns the 202 response as-is so async-job
    pollers can detect "file not ready" and sleep themselves rather
    than retrying here. Everything else is treated as an error.

    4xx other than 429 are non-retryable and re-raised via
    ``raise_for_status``.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException as e:
            last_exc = e
            wait = backoff_base_sec * (2**attempt)
            log.warning("request error (attempt %d): %s; sleeping %ds",
                        attempt + 1, e, wait)
            time.sleep(wait)
            continue

        if resp.status_code == 200:
            return resp
        if resp.status_code == 202 and accept_202:
            return resp
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "")
            wait = parse_retry_after(retry_after) or backoff_base_sec * (2**attempt)
            log.warning("429 rate limited; Retry-After=%r; sleeping %ds",
                        retry_after, wait)
            time.sleep(wait)
            continue
        if 500 <= resp.status_code < 600:
            wait = backoff_base_sec * (2**attempt)
            log.warning("%d server error; sleeping %ds", resp.status_code, wait)
            time.sleep(wait)
            continue

        # 4xx other than 429 — not retryable.
        resp.raise_for_status()

    if last_exc:
        raise last_exc
    raise RuntimeError(f"exhausted {max_retries} retries for {url}")


def get_db_connection():
    """Return a new psycopg2 connection using DATABASE_URL_SYNC.

    Strips SQLAlchemy-style driver prefixes so the URL psycopg2 expects.
    Caller owns commit/close.
    """
    import psycopg2  # local import so this module doesn't hard-depend on it

    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL_SYNC / DATABASE_URL not set — cannot connect to Postgres."
        )
    url = url.replace("postgresql+psycopg2://", "postgresql://")
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return psycopg2.connect(url)


def stream_json_array(
    source: str | Path | Any,
) -> Iterator[dict[str, Any]]:
    """Yield items from a top-level JSON array without materialising the file.

    Accepts either:
      - a ``str`` or ``pathlib.Path`` (opened in binary mode internally), or
      - a binary file-like object (``gzip.open(...)``, ``BytesIO``, any
        readable that yields bytes).

    Peak memory is bounded by the size of the largest single record, not
    the total file. Critical for the 3.26 GB Part D snapshot — a plain
    ``json.load(fh)`` OOMs there.

    ijson's ``items(fh, 'item')`` matches every direct child of the
    top-level array. Anything else (object at root, nested array of
    arrays) would silently yield nothing — callers should assert the
    expected record count after consumption, not trust silence.

    The caller is responsible for closing file-like inputs it opened
    itself; when given a path we open and close internally.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        fh = path.open("rb")
        close_on_exit = True
    else:
        fh = source
        close_on_exit = False

    try:
        import ijson  # local import — only pulled in when streaming is actually used
        yield from ijson.items(fh, "item")
    finally:
        if close_on_exit:
            fh.close()


class StateFile:
    """Per-source watermark, persisted as a single YYYY-MM-DD line.

    Used by delta/incremental loaders. ``read()`` returns None when the
    file is absent or malformed so callers can branch to "run a seed
    first" without special-casing FileNotFoundError.
    """

    def __init__(self, path: Path):
        self.path = Path(path)

    def read(self) -> date | None:
        if not self.path.exists():
            return None
        try:
            raw = self.path.read_text().strip()
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except (OSError, ValueError) as e:
            log.warning("state file at %s unreadable (%s); treating as absent",
                        self.path, e)
            return None

    def write(self, d: date) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(d.strftime("%Y-%m-%d"))
        log.info("wrote state: %s=%s", self.path, d)


__all__ = [
    "DEFAULT_BACKOFF_BASE_SEC",
    "DEFAULT_MAX_RETRIES",
    "StateFile",
    "get_db_connection",
    "get_with_retry",
    "parse_retry_after",
    "stream_json_array",
]
