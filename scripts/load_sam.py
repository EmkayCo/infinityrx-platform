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
import json
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


def _poll_download(api_key: str, token: str) -> dict[str, Any]:
    """Poll the download endpoint until the file is ready. Returns parsed JSON."""
    params = {"api_key": api_key, "token": token}
    for attempt in range(1, POLL_MAX_ATTEMPTS + 1):
        resp = _get_with_retry(
            DOWNLOAD_URL, params, timeout=DOWNLOAD_TIMEOUT_SEC, accept_202=True
        )

        if resp.status_code == 202:
            log.info("file not ready (attempt %d/%d); sleeping %ds",
                     attempt, POLL_MAX_ATTEMPTS, POLL_INTERVAL_SEC)
            time.sleep(POLL_INTERVAL_SEC)
            continue

        # 200 — but SAM.gov sometimes returns 200 with a "still generating"
        # JSON envelope rather than 202. Check content for that.
        try:
            payload = resp.json()
        except json.JSONDecodeError:
            raise RuntimeError(f"download returned non-JSON (len={len(resp.content)})")

        if _is_not_ready(payload):
            log.info("file not ready per 200-envelope (attempt %d/%d); sleeping %ds",
                     attempt, POLL_MAX_ATTEMPTS, POLL_INTERVAL_SEC)
            time.sleep(POLL_INTERVAL_SEC)
            continue

        log.info("extract file downloaded on attempt %d", attempt)
        return payload

    raise TimeoutError(
        f"extract file not ready after {POLL_MAX_ATTEMPTS} polls "
        f"({POLL_MAX_ATTEMPTS * POLL_INTERVAL_SEC}s)"
    )


def _is_not_ready(payload: dict[str, Any]) -> bool:
    """Detect a 'still generating' envelope returned as 200."""
    if not isinstance(payload, dict):
        return False
    msg = (payload.get("message") or "").lower()
    return "not generated yet" in msg or "try again" in msg


# ---------------------------------------------------------------------------
# Record extraction
# ---------------------------------------------------------------------------


def _iter_records(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield raw v4 records from an extract payload.

    Handles both direct `excludedEntity` arrays and the occasional wrapping
    under `results` seen in some extract responses.
    """
    if "excludedEntity" in payload:
        yield from payload["excludedEntity"]
        return
    if "results" in payload and isinstance(payload["results"], list):
        for r in payload["results"]:
            if "excludedEntity" in r:
                yield from r["excludedEntity"]
            else:
                yield r
        return
    raise RuntimeError(f"extract payload has no excludedEntity key; top-level keys: {list(payload)}")


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
    payload = _poll_download(api_key, token)

    seen = 0
    upserted = 0
    max_update: date | None = None

    with get_db_connection() as conn:
        for raw in _iter_records(payload):
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
