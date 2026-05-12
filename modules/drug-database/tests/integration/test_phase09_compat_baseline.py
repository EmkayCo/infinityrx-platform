"""B9.A C12 — Phase 09 compatibility baseline integration test.

LOCKED VALUES (see waves/B9/phase09_compat_baseline.md):
  fdb_ndc_price_history: 15,635,770 rows (lower bound — delta growth allowed)
  fdb_price_type_desc:   23 rows (exact match — static reference)
  representative NDC query: < 50 ms (index hit)

Every B9.B-G phase mini-GATE-CLOSE re-runs these assertions. A
regression here means B9's extension touched pricing data — hard
stop.

The test skips when no live reference DB is available (development
machines without Docker up). CI mode pins the assertion to live
Postgres via the standard DATABASE_URL_SYNC_REFERENCE env var.
"""
from __future__ import annotations

import os
import time
from decimal import Decimal

import pytest


# Hard-coded baseline numbers per waves/B9/phase09_compat_baseline.md.
PHASE09_BASELINE_PRICE_HISTORY_MIN_ROWS = 15_635_770
PHASE09_BASELINE_PRICE_TYPE_DESC_ROWS = 23
PHASE09_BASELINE_QUERY_LATENCY_MAX_MS = 50  # generous ceiling; index hit is ~2ms


def _live_reference_db_url() -> str | None:
    """Return the env-resolved reference DB URL, or None if unset."""
    return os.environ.get("DATABASE_URL_SYNC_REFERENCE", "").strip() or None


# All tests in this module skip when no live DB — CI enables it by
# exporting the env var; developer machines without Docker skip cleanly.
pytestmark = pytest.mark.skipif(
    _live_reference_db_url() is None,
    reason=(
        "DATABASE_URL_SYNC_REFERENCE not set — Phase 09 compat baseline "
        "requires a live infinityrx_reference DB. Run "
        "`source infrastructure/scripts/switch_env.sh dev` first."
    ),
)


@pytest.fixture(scope="module")
def reference_db_connection():
    """Single SQLAlchemy connection bound to the reference DB."""
    from sqlalchemy import create_engine
    url = _live_reference_db_url()
    assert url is not None  # skip already handled at module level
    # async driver doesn't work for sync engine — mirror load_fdb.py
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(url)
    with engine.connect() as conn:
        yield conn
    engine.dispose()


# ---------------------------------------------------------------------------
# Row-count baselines
# ---------------------------------------------------------------------------


def test_fdb_ndc_price_history_row_count_above_baseline(
    reference_db_connection,
) -> None:
    """Lower-bound assertion — weekly delta growth allowed, shrinkage forbidden."""
    from sqlalchemy import text
    result = reference_db_connection.execute(
        text("SELECT count(*) FROM drug_database.fdb_ndc_price_history")
    ).scalar()
    assert result >= PHASE09_BASELINE_PRICE_HISTORY_MIN_ROWS, (
        f"fdb_ndc_price_history shrank: {result} < baseline "
        f"{PHASE09_BASELINE_PRICE_HISTORY_MIN_ROWS}. B9 must not have "
        f"removed pricing rows."
    )


def test_fdb_price_type_desc_row_count_exact(
    reference_db_connection,
) -> None:
    """Static reference — exact 23 rows."""
    from sqlalchemy import text
    result = reference_db_connection.execute(
        text("SELECT count(*) FROM drug_database.fdb_price_type_desc")
    ).scalar()
    assert result == PHASE09_BASELINE_PRICE_TYPE_DESC_ROWS, (
        f"fdb_price_type_desc: {result} rows; expected exactly "
        f"{PHASE09_BASELINE_PRICE_TYPE_DESC_ROWS} (static reference). "
        f"B9 must not have inserted into this table."
    )


# ---------------------------------------------------------------------------
# Query-latency baseline (index health)
# ---------------------------------------------------------------------------


def test_representative_ndc_query_uses_index(
    reference_db_connection,
) -> None:
    """Index hit — query completes well under the latency ceiling.

    A regression to sequential scan would be visible as latency jumping
    into the hundreds-of-milliseconds range. 50 ms ceiling is generous
    (baseline was ~2ms) but tolerates noisy test infrastructure.
    """
    from sqlalchemy import text
    start = time.perf_counter()
    result = reference_db_connection.execute(
        text(
            "SELECT ndc_11, price_type "
            "FROM drug_database.fdb_ndc_price_history "
            "WHERE ndc_11 = '00781153910' LIMIT 5"
        )
    ).fetchall()
    elapsed_ms = (time.perf_counter() - start) * 1000
    # Result content irrelevant (0 rows is fine — the query plan is
    # what matters); only the latency proves index health.
    assert elapsed_ms < PHASE09_BASELINE_QUERY_LATENCY_MAX_MS, (
        f"Representative NDC lookup took {elapsed_ms:.1f} ms; ceiling "
        f"{PHASE09_BASELINE_QUERY_LATENCY_MAX_MS} ms. Likely index "
        f"regression — inspect EXPLAIN ANALYZE before continuing."
    )
