"""
scripts/load_sam.py — SAM.gov exclusions loader (Wave 8).

Strategy: hybrid bulk-extract seed + delta updates.

  - seed:     one async extract request → one download → ~167k records in a
              single round trip. Used for initial load and full rebuilds.
  - delta:    async extract scoped by updateDate=[since,today]. Used for
              incremental daily runs.
  - backfill: same as delta but with an explicit --since date (manual
              re-sync).

Mode is auto-selected based on whether shared.sam_exclusions has any rows
(empty → seed, non-empty → delta). Override with --mode.

The `since` watermark for delta is persisted to
  data/reference/sam_exclusions/.last_run
after every successful run. It holds the MAX(updateDate) actually observed
in that run's records (not today's date), so gaps in SAM.gov's own ingest
pipeline don't cause us to skip records.

Why this replaces paginated JSON crawls: the synchronous JSON endpoint
caps `size` at 10 records/page. At 167k records that's ~16,724 requests,
which exceeds the 1,000-req/day public-API quota by 16x. The async
extract endpoint produces the full dataset in a single request.

Endpoints (all v4):
  GET /entity-information/v4/exclusions?format=JSON[&updateDate=...]
      → { token: "..." }  (async job submitted)
  GET /entity-information/v4/download-exclusions?token=...
      → JSON file once ready; 202/empty while still generating

Downstream parse/flatten/upsert path (_flatten_v4_record → _upsert_row) is
unchanged from Wave 7. Records from the extract file have the same
`excludedEntity[*]` shape as paginated responses.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

import requests

# The script is executed directly from the repo, so wire sys.path
# the same way every other loader script does before we hit the shared modules.
_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (_REPO_ROOT, _REPO_ROOT / "modules" / "prescriber-directory",
           _REPO_ROOT / "modules" / "pharmacy-directory"):
    sp = str(_p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

# Shared primitives (Wave 9 extraction) and SAM-specific helpers (Wave 7).
from shared.data_ingestion.common import (  # noqa: E402
    StateFile,
    get_db_connection,
    get_with_retry as _get_with_retry,
)
from shared.data_ingestion.sources.sam_exclusions import (  # noqa: E402
    _flatten_v4_record,
    _parse_sam_date,
    _upsert_row,
)

log = logging.getLogger("load_sam")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://api.sam.gov/entity-information/v4"
EXTRACT_URL = f"{BASE_URL}/exclusions"
DOWNLOAD_URL = f"{BASE_URL}/download-exclusions"

CACHE_DIR = Path("data/reference/sam_exclusions")
STATE_FILE = CACHE_DIR / ".last_run"

# Token-polling: 30s intervals, 45 min cap. Tuned for ~20-40MB extract files
# which typically ready in 2-10 min but can stall to 20-30 min under load.
POLL_INTERVAL_SEC = 30
POLL_MAX_ATTEMPTS = 90

# Initial extract-submission request: short timeout since this just queues a job.
SUBMIT_TIMEOUT_SEC = 60
# Download request: longer timeout since this streams the generated file.
DOWNLOAD_TIMEOUT_SEC = 300

# Retry/backoff for transient 5xx / 429 lives in shared.data_ingestion.common.
# Override by passing max_retries / backoff_base_sec to get_with_retry if needed.

TABLE = "shared.sam_exclusions"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class LoadResult:
    mode: str
    records_seen: int
    records_upserted: int
    max_update_date: date | None
    since: date | None  # window lower bound (None for seed)


# ---------------------------------------------------------------------------
# Extract submission + polling
# ---------------------------------------------------------------------------


def _submit_extract(api_key: str, since: date | None) -> str:
    """Submit an async extract job. Returns the token."""
    params: dict[str, Any] = {"api_key": api_key, "format": "JSON"}
    if since is not None:
        # v4 requires MM/DD/YYYY and a closed range. End bound is "today"
        # in UTC so we don't miss records updated after the submit moment;
        # SAM.gov treats updateDate as update-day, not update-timestamp.
        today = datetime.utcnow().date()
        params["updateDate"] = f"[{since.strftime('%m/%d/%Y')},{today.strftime('%m/%d/%Y')}]"

    log.info("submitting extract job: since=%s", since)
    resp = _get_with_retry(EXTRACT_URL, params, timeout=SUBMIT_TIMEOUT_SEC)

    # Spec: response is a small JSON envelope containing the download URL
    # with a REPLACE_WITH_API_KEY placeholder and a token param.
    # Reality (v4): SAM.gov returns text/plain with the URL embedded in an
    # English sentence; _extract_token's fallback handles both shapes.
    try:
        body = resp.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        body = {"message": resp.text}
    token = _extract_token(body)
    if not token:
        raise RuntimeError(f"no token in submit response: {body}")
    log.info("extract job submitted: token=%s", token)
    return token


def _extract_token(body: dict[str, Any]) -> str | None:
    """Pull the download token from the submit response.

    The documented shape varies across SAM.gov API docs; we handle both
    a direct `token` field and parsing it out of a download URL string.
    """
    if isinstance(body, dict) and body.get("token"):
        return str(body["token"])

    # Fallback: scan string values for "token=...". SAM.gov often embeds
    # the download URL inside a longer message ("... with url: <url> in
    # some time."), so we stop at the first character that can't be in a
    # URL token — '&' for more query params, or whitespace for the
    # message tail.
    import re
    for val in (body.values() if isinstance(body, dict) else []):
        if isinstance(val, str) and "token=" in val:
            tail = val.split("token=", 1)[1]
            match = re.match(r"[^\s&]+", tail)
            if match:
                return match.group(0)
    return None


def _poll_download(api_key: str, token: str) -> Path:
    """Poll the download endpoint until the file is ready; stream to local gzip.

    Live v4 behavior (verified 2026-04-16):
      - While the extract is still generating, SAM returns HTTP 400. Docs
        suggested 202; reality is 400. Treat both identically.
      - When ready, SAM returns HTTP 302 → presigned S3 URL whose body is
        ``application/gzip`` containing the JSON extract. ``requests`` with
        ``allow_redirects=True`` follows the redirect to a 200 from S3.
      - We stream the gzip bytes into CACHE_DIR/<token>.json.gz and return
        the path. Downstream parse runs on the gzip file directly.

    NOT using ``get_with_retry`` here because that helper treats 400 as
    fatal. 4xx during async-extract polling is load-bearing status, not
    an error.
    """
    params = {"api_key": api_key, "token": token}
    for attempt in range(1, POLL_MAX_ATTEMPTS + 1):
        resp = requests.get(
            DOWNLOAD_URL,
            params=params,
            timeout=DOWNLOAD_TIMEOUT_SEC,
            allow_redirects=True,
            stream=True,
        )

        if resp.status_code in (400, 202):
            resp.close()
            log.info("file not ready (HTTP %d, attempt %d/%d); sleeping %ds",
                     resp.status_code, attempt, POLL_MAX_ATTEMPTS, POLL_INTERVAL_SEC)
            time.sleep(POLL_INTERVAL_SEC)
            continue

        if resp.status_code != 200:
            resp.close()
            resp.raise_for_status()

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        extract_path = CACHE_DIR / f"extract_{token}.json.gz"
        with extract_path.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                if chunk:
                    fh.write(chunk)
        resp.close()
        log.info("extract downloaded on attempt %d: %s (%d bytes gz)",
                 attempt, extract_path, extract_path.stat().st_size)
        return extract_path

    raise TimeoutError(
        f"extract file not ready after {POLL_MAX_ATTEMPTS} polls "
        f"({POLL_MAX_ATTEMPTS * POLL_INTERVAL_SEC}s)"
    )


# ---------------------------------------------------------------------------
# Record extraction
# ---------------------------------------------------------------------------


def _iter_records(file_path: Path) -> Iterator[dict[str, Any]]:
    """Stream raw v4 records from a gzipped extract file at *file_path*.

    SAM v4 payload shape: ``{"totalRecords": N, "excludedEntity": [...]}``.
    Uses ijson with prefix ``excludedEntity.item`` so peak memory is the
    size of one record, not the whole 167k-row payload. Wave 9e-lite's
    ``stream_json_array`` hardcodes the top-level-array prefix so isn't
    reusable here — this ijson call is intentionally inlined rather than
    extending the shared primitive for one caller.
    """
    import gzip

    import ijson

    with gzip.open(file_path, "rb") as fh:
        yield from ijson.items(fh, "excludedEntity.item")


# ---------------------------------------------------------------------------
# State file — thin wrappers around the shared StateFile class so existing
# tests that monkeypatch STATE_FILE or _read_state / _write_state on the
# load_sam module still resolve. New code should prefer StateFile(path).
# ---------------------------------------------------------------------------


def _read_state() -> date | None:
    return StateFile(STATE_FILE).read()


def _write_state(d: date) -> None:
    StateFile(STATE_FILE).write(d)


# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------


def _table_is_empty() -> bool:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT 1 FROM {TABLE} LIMIT 1")
        return cur.fetchone() is None


def _resolve_mode(cli_mode: str | None) -> str:
    if cli_mode:
        return cli_mode
    if _table_is_empty():
        log.info("auto-mode: table empty → seed")
        return "seed"
    log.info("auto-mode: table populated → delta")
    return "delta"


def _resolve_since(mode: str, cli_since: date | None) -> date | None:
    if mode == "seed":
        return None
    if mode == "backfill":
        if cli_since is None:
            raise SystemExit("--mode backfill requires --since YYYY-MM-DD")
        return cli_since
    # delta
    if cli_since is not None:
        return cli_since
    state = _read_state()
    if state is None:
        raise SystemExit(
            "delta mode but no state file at data/reference/sam_exclusions/.last_run. "
            "Run --mode seed first, or pass --since YYYY-MM-DD, or use --mode backfill."
        )
    # Start one day before last run to absorb any same-day late-arriving updates.
    return state - timedelta(days=1)


# ---------------------------------------------------------------------------
# Main load
# ---------------------------------------------------------------------------


def load(mode: str, since: date | None, api_key: str) -> LoadResult:
    token = _submit_extract(api_key, since)
    extract_path = _poll_download(api_key, token)

    seen = 0
    upserted = 0
    max_update: date | None = None

    with get_db_connection() as conn:
        for raw in _iter_records(extract_path):
            seen += 1
            try:
                flat = _flatten_v4_record(raw)
            except Exception as e:
                log.warning("flatten failed for record %d: %s", seen, e)
                continue

            try:
                _upsert_row(conn, flat)
                upserted += 1
            except Exception as e:
                log.error("upsert failed for record %d (%s): %s",
                          seen, flat.get("ueiSAM") or flat.get("entityName"), e)
                continue

            upd = flat.get("updateDate")
            if upd:
                parsed = _parse_sam_date(upd)
                if parsed and (max_update is None or parsed > max_update):
                    max_update = parsed

        conn.commit()

    return LoadResult(
        mode=mode,
        records_seen=seen,
        records_upserted=upserted,
        max_update_date=max_update,
        since=since,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main() -> int:
    parser = argparse.ArgumentParser(description="Load SAM.gov exclusions (Wave 8).")
    parser.add_argument(
        "--mode",
        choices=["seed", "delta", "backfill"],
        default=None,
        help="Load mode. Default: auto (seed if table empty, else delta).",
    )
    parser.add_argument(
        "--since",
        type=_parse_date,
        default=None,
        help="YYYY-MM-DD lower bound for updateDate. Required for backfill; "
             "optional override for delta.",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("LOG_LEVEL", "INFO"),
        help="Log level (default INFO).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    api_key = os.environ.get("SAM_API_KEY")
    if not api_key:
        print("error: SAM_API_KEY not set in environment", file=sys.stderr)
        return 1

    mode = _resolve_mode(args.mode)
    since = _resolve_since(mode, args.since)

    log.info("starting: mode=%s since=%s", mode, since)
    result = load(mode, since, api_key)

    log.info(
        "completed: seen=%d upserted=%d max_update=%s",
        result.records_seen, result.records_upserted, result.max_update_date,
    )

    # Only advance the watermark if we actually loaded something with a real
    # updateDate. Empty delta runs leave state untouched.
    if result.max_update_date is not None:
        _write_state(result.max_update_date)
    else:
        log.info("no records with updateDate observed; state file untouched")

    # Non-zero exit if nothing was upserted despite seeing records — signals
    # an upstream parse regression to the caller.
    if result.records_seen > 0 and result.records_upserted == 0:
        log.error("saw %d records but upserted 0 — check logs for flatten/upsert errors",
                  result.records_seen)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
