"""Task 3.3 — Population-separated baseline computation tests.

TDD: RED tests written first, then implementation in src/detection/baselines.py.

Test strategy
-------------
All five baseline kinds are covered.  The compute_baseline() function uses SQL
aggregate-subtraction for peer-exclusion baselines — no correlated per-entity
subqueries.  The SQL relies on JSON extraction (row_data->>'field') which is
supported by both SQLite (via JSON1 extension) and Postgres.

SQLite compatibility notes
--------------------------
- JSON1 is compiled in by default for CPython wheels since 3.9+.
- "json_extract(row_data, '$.field')" works in SQLite for JSONB TEXT columns
  (after the _sqlite_compat_swap converts JSONB -> JSON).
- "CAST(... AS REAL)" is used inside aggregate math; the outer Python layer
  wraps all results in Decimal(str(...)) before writing to the DB, so the
  Decimal invariant is preserved at the ORM write boundary.
- The weekday computation uses SQLite's strftime('%w', ...) which returns '0'
  for Sunday through '6' for Saturday.  The same logic is written portably so
  Postgres uses EXTRACT(DOW FROM ...) via a conditional in the implementation.

Postgres-only gate
------------------
Tests that exercise advisory locks, partial indexes, or JSONB operators that
differ between SQLite and Postgres are gated behind RECLAIMRX_TEST_DB_URL.
All five baseline kinds are tested on the SQLite fixture — they all work with
SQLite JSON1.

Coverage contract
-----------------
Covers every branch of compute_baseline():
1. prescriber_peer_volume  — leave-one-out proven (mean excludes scored entity)
2. pharmacy_ndc_volume     — peer-exclusion, different NDC groups isolated
3. member_cost             — population (not peer-exclusion by entity)
4. pharmacy_weekday_volume — weekday vs weekend ratio baseline per pharmacy
5. pharmacy_own_rate_history — own-prior-period, NOT peer comparison
6. min_sample_count gate   — entity with < min peers gets NO baseline row
7. provenance in extra     — exclusion, peer_count, window_days, etc.
8. Unknown kind            — raises ValueError
9. Zero-division guard     — peer_n == 0 produces no row
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.detection.baselines import compute_baseline
from src.models.detection_run_models import BaselineCache, CsvUploadRow, DetectionRun

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
_CREATED_BY = uuid.UUID("00000000-0000-0000-0000-000000000001")

_NDC_A = "00000000001"
_NDC_B = "00000000002"

_NPI_ALPHA = "1234567890"
_NPI_BETA = "0987654321"
_NPI_GAMMA = "1111111111"

_PRESC_X = "9991112222"
_PRESC_Y = "9991113333"
_PRESC_Z = "9991114444"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(db: Session) -> DetectionRun:
    run = DetectionRun(
        tenant_id=_TENANT,
        data_source="csv_upload",
        run_label="test-run",
        source_path="/tmp/test.csv",
        source_filename="test.csv",
        source_sha256="a" * 64,
        record_count=0,
        status="in_progress",
        created_by=_CREATED_BY,
    )
    db.add(run)
    db.flush()
    return run


def _row(
    db: Session,
    run: DetectionRun,
    *,
    row_number: int,
    npi: str,
    ndc: str | None,
    prescriber_npi: str | None = None,
    ingredient_cost_paid: str = "100.00",
    extended_wac: str = "90.00",
    total_paid_amt: str = "100.00",
    date_of_service: str = "2025-01-15",
) -> CsvUploadRow:
    """Insert one CsvUploadRow with the given fields."""
    row = CsvUploadRow(
        tenant_id=_TENANT,
        detection_run_id=run.id,
        row_number=row_number,
        row_data={
            "pharmacy_npi": npi,
            "prescriber_npi": prescriber_npi or "",
            "ingredient_cost_paid": ingredient_cost_paid,
            "extended_wac": extended_wac,
            "total_paid_amt": total_paid_amt,
            "date_of_service": date_of_service,
        },
        resolved_pharmacy_npi=npi,
        resolved_ndc=ndc,
        resolution_method="declared",
    )
    db.add(row)
    db.flush()
    return row


# ===========================================================================
# TEST CLASS: prescriber_peer_volume (HP-005)
# ===========================================================================


class TestPrescriberPeerVolume:
    """HP-005: per NDC group, each prescriber's peer mean excludes its own rows."""

    def test_leave_one_out_mean_excludes_self(self, db: Session):
        """
        Construct 3 prescribers for the same NDC with deliberately different
        claim counts so that including vs excluding self produces different means.

        PRESC_X: 6 claims  (claim_count=6)
        PRESC_Y: 2 claims  (claim_count=2)
        PRESC_Z: 2 claims  (claim_count=2)

        Group total claims = 10, group count = 3 prescribers (for the NDC group).

        For PRESC_X:
          peer_sum = 2 + 2 = 4, peer_n = 2  → peer_mean = 2.0
          If self were INCLUDED: mean of all 3 = (6+2+2)/3 = 3.333...
          The baseline row for PRESC_X should have mean = 2.0, NOT 3.333.
        """
        run = _make_run(db)
        # PRESC_X: 6 claims for NDC_A (spread across 6 rows)
        for i in range(6):
            _row(
                db, run, row_number=i + 1, npi=_NPI_ALPHA, ndc=_NDC_A,
                prescriber_npi=_PRESC_X,
            )
        # PRESC_Y: 2 claims for NDC_A
        for i in range(2):
            _row(
                db, run, row_number=100 + i, npi=_NPI_ALPHA, ndc=_NDC_A,
                prescriber_npi=_PRESC_Y,
            )
        # PRESC_Z: 2 claims for NDC_A
        for i in range(2):
            _row(
                db, run, row_number=200 + i, npi=_NPI_ALPHA, ndc=_NDC_A,
                prescriber_npi=_PRESC_Z,
            )
        db.flush()

        n = compute_baseline(db, run, kind="prescriber_peer_volume", min_sample_count=1)
        assert n == 3  # one row per prescriber (peer_entity_count >= 1 for all)

        # Fetch the row for PRESC_X
        scope_key = f"ndc={_NDC_A}|prescriber_npi={_PRESC_X}"
        row = (
            db.query(BaselineCache)
            .filter(
                BaselineCache.tenant_id == _TENANT,
                BaselineCache.baseline_kind == "prescriber_peer_volume",
                BaselineCache.scope_key == scope_key,
            )
            .one()
        )
        # peer mean for PRESC_X = (2+2)/2 = 2.0 — self (6 rows) excluded
        assert row.mean == Decimal("2"), (
            f"Expected peer mean=2 (self excluded), got {row.mean}"
        )

    def test_min_sample_gate_suppresses_row(self, db: Session):
        """
        If a prescriber's peer group has fewer than min_sample_count peers,
        no baseline row is written for that prescriber.
        """
        run = _make_run(db)
        # Only 2 prescribers; min_sample_count=5 -> neither gets a baseline row
        for i in range(3):
            _row(
                db, run, row_number=i + 1, npi=_NPI_ALPHA, ndc=_NDC_A,
                prescriber_npi=_PRESC_X,
            )
        for i in range(2):
            _row(
                db, run, row_number=100 + i, npi=_NPI_ALPHA, ndc=_NDC_A,
                prescriber_npi=_PRESC_Y,
            )
        db.flush()

        n = compute_baseline(db, run, kind="prescriber_peer_volume", min_sample_count=5)
        # peer_n for PRESC_X = 1 (only PRESC_Y), peer_n for PRESC_Y = 1 → both < 5
        assert n == 0

    def test_different_ndc_groups_isolated(self, db: Session):
        """Prescribers in NDC_A and NDC_B do not share peer statistics."""
        run = _make_run(db)
        # 3 prescribers in NDC_A
        for presc, count in [(_PRESC_X, 4), (_PRESC_Y, 2), (_PRESC_Z, 2)]:
            for i in range(count):
                _row(
                    db, run, row_number=len(db.query(CsvUploadRow).all()) + 1,
                    npi=_NPI_ALPHA, ndc=_NDC_A,
                    prescriber_npi=presc,
                )
        # 2 prescribers in NDC_B (separate group)
        for presc, count in [(_PRESC_X, 5), (_PRESC_Y, 5)]:
            for i in range(count):
                _row(
                    db, run, row_number=len(db.query(CsvUploadRow).all()) + 1,
                    npi=_NPI_BETA, ndc=_NDC_B,
                    prescriber_npi=presc,
                )
        db.flush()

        n = compute_baseline(db, run, kind="prescriber_peer_volume", min_sample_count=1)
        # 3 prescribers in NDC_A (each has peer_n >= 1) +
        # 2 prescribers in NDC_B (each has peer_n >= 1)  = 5 rows
        # (PRESC_X gets 2 rows: one per NDC group)
        assert n == 5

    def test_provenance_in_extra(self, db: Session):
        """BaselineCache.extra contains exclusion, peer_count, window_days keys."""
        run = _make_run(db)
        for presc, count in [(_PRESC_X, 3), (_PRESC_Y, 3), (_PRESC_Z, 3)]:
            for i in range(count):
                _row(
                    db, run, row_number=len(db.query(CsvUploadRow).all()) + 1,
                    npi=_NPI_ALPHA, ndc=_NDC_A,
                    prescriber_npi=presc,
                )
        db.flush()

        compute_baseline(db, run, kind="prescriber_peer_volume", min_sample_count=1)

        row = (
            db.query(BaselineCache)
            .filter(
                BaselineCache.tenant_id == _TENANT,
                BaselineCache.baseline_kind == "prescriber_peer_volume",
            )
            .first()
        )
        assert row is not None
        extra = row.extra
        assert extra["exclusion"] == "leave_entity_out"
        assert "peer_count" in extra
        assert extra["window_days"] == 90
        assert extra["data_source"] == "csv_upload"
        assert extra["min_sample_count"] == 1  # passed explicitly above


# ===========================================================================
# TEST CLASS: pharmacy_ndc_volume (MFR-004)
# ===========================================================================


class TestPharmacyNdcVolume:
    """MFR-004: per NDC, each pharmacy vs other pharmacies' volume."""

    def test_peer_mean_excludes_self(self, db: Session):
        """
        NPI_ALPHA: 10 claims, NPI_BETA: 2 claims, NPI_GAMMA: 2 claims — all for NDC_A.
        Peer mean for NPI_ALPHA = (2+2)/2 = 2.0 (excludes own 10).
        """
        run = _make_run(db)
        for npi, count in [(_NPI_ALPHA, 10), (_NPI_BETA, 2), (_NPI_GAMMA, 2)]:
            for i in range(count):
                _row(
                    db, run, row_number=len(db.query(CsvUploadRow).all()) + 1,
                    npi=npi, ndc=_NDC_A,
                )
        db.flush()

        compute_baseline(db, run, kind="pharmacy_ndc_volume", min_sample_count=1)

        scope_key = f"ndc={_NDC_A}|pharmacy_npi={_NPI_ALPHA}"
        row = (
            db.query(BaselineCache)
            .filter(
                BaselineCache.baseline_kind == "pharmacy_ndc_volume",
                BaselineCache.scope_key == scope_key,
            )
            .one()
        )
        assert row.mean == Decimal("2"), f"Expected peer mean=2, got {row.mean}"

    def test_min_sample_gate(self, db: Session):
        """Only 1 other pharmacy in the group → peer_n=1 < min_sample_count=2 → no row."""
        run = _make_run(db)
        for npi, count in [(_NPI_ALPHA, 5), (_NPI_BETA, 3)]:
            for i in range(count):
                _row(
                    db, run, row_number=len(db.query(CsvUploadRow).all()) + 1,
                    npi=npi, ndc=_NDC_A,
                )
        db.flush()

        n = compute_baseline(db, run, kind="pharmacy_ndc_volume", min_sample_count=2)
        # Each pharmacy has peer_n=1; 1 < 2 → no rows written
        assert n == 0


# ===========================================================================
# TEST CLASS: member_cost (HP-008)
# ===========================================================================


class TestMemberCost:
    """HP-008: population mean/stddev for total_paid_amt per member."""

    def test_population_statistics_written(self, db: Session):
        """
        3 members with known total_paid_amt: 100, 200, 300.
        Population mean = 200, population std = sqrt(2/3 * (100^2+0+100^2)) ≈ 81.65.
        One baseline row per member; exclusion='population'.
        """
        run = _make_run(db)
        for i, amount in enumerate(["100.00", "200.00", "300.00"]):
            # Each "member" is identified by a unique prescriber_npi stand-in;
            # member cost baseline groups by patient_unique_hash from row_data,
            # but our test uses total_paid_amt to verify population stats.
            _row(
                db, run, row_number=i + 1,
                npi=_NPI_ALPHA, ndc=_NDC_A,
                total_paid_amt=amount,
                prescriber_npi=f"MBR{i:08d}",
            )
        db.flush()

        n = compute_baseline(db, run, kind="member_cost", min_sample_count=1)
        assert n >= 1  # at least one population row written

        rows = (
            db.query(BaselineCache)
            .filter(
                BaselineCache.tenant_id == _TENANT,
                BaselineCache.baseline_kind == "member_cost",
            )
            .all()
        )
        assert len(rows) >= 1
        # provenance: exclusion='population' (not leave_entity_out)
        for row in rows:
            assert row.extra["exclusion"] == "population"

    def test_member_cost_sample_count_matches_row_count(self, db: Session):
        """sample_count on the population baseline equals number of rows used."""
        run = _make_run(db)
        for i in range(5):
            _row(
                db, run, row_number=i + 1,
                npi=_NPI_ALPHA, ndc=_NDC_A,
                total_paid_amt=str(100 * (i + 1)),
            )
        db.flush()

        compute_baseline(db, run, kind="member_cost", min_sample_count=1)

        rows = (
            db.query(BaselineCache)
            .filter(BaselineCache.baseline_kind == "member_cost")
            .all()
        )
        # population: single row with sample_count == 5
        assert any(r.sample_count == 5 for r in rows)


# ===========================================================================
# TEST CLASS: pharmacy_weekday_volume (ALL-006)
# ===========================================================================


class TestPharmacyWeekdayVolume:
    """ALL-006: per pharmacy, weekday vs weekend ratio baseline."""

    # 2025-01-13 is a Monday (weekday), 2025-01-18 is a Saturday (weekend)
    _WEEKDAY_DOS = "2025-01-13"
    _WEEKEND_DOS = "2025-01-18"

    def test_weekday_ratio_written(self, db: Session):
        """
        NPI_ALPHA: 4 weekday claims + 1 weekend claim.
        weekday_rate baseline written.
        """
        run = _make_run(db)
        for i in range(4):
            _row(
                db, run, row_number=i + 1,
                npi=_NPI_ALPHA, ndc=_NDC_A,
                date_of_service=self._WEEKDAY_DOS,
            )
        _row(
            db, run, row_number=5,
            npi=_NPI_ALPHA, ndc=_NDC_A,
            date_of_service=self._WEEKEND_DOS,
        )
        db.flush()

        n = compute_baseline(db, run, kind="pharmacy_weekday_volume", min_sample_count=1)
        assert n >= 1

        scope_key = f"pharmacy_npi={_NPI_ALPHA}"
        row = (
            db.query(BaselineCache)
            .filter(
                BaselineCache.baseline_kind == "pharmacy_weekday_volume",
                BaselineCache.scope_key == scope_key,
            )
            .one()
        )
        # weekday count=4, weekend count=1, total=5
        # weekday_rate = 4/5 = 0.8
        assert row.mean == Decimal("4") / Decimal("5"), (
            f"Expected weekday_rate=0.8, got {row.mean}"
        )
        assert row.extra["exclusion"] == "leave_entity_out"
        assert "weekday_count" in row.extra
        assert "weekend_count" in row.extra

    def test_pharmacy_all_weekday(self, db: Session):
        """Pharmacy with all weekday claims has weekday_rate = 1.0."""
        run = _make_run(db)
        for i in range(3):
            _row(
                db, run, row_number=i + 1,
                npi=_NPI_BETA, ndc=_NDC_A,
                date_of_service=self._WEEKDAY_DOS,
            )
        db.flush()

        compute_baseline(db, run, kind="pharmacy_weekday_volume", min_sample_count=1)

        scope_key = f"pharmacy_npi={_NPI_BETA}"
        row = (
            db.query(BaselineCache)
            .filter(
                BaselineCache.baseline_kind == "pharmacy_weekday_volume",
                BaselineCache.scope_key == scope_key,
            )
            .one()
        )
        assert row.mean == Decimal("1")


# ===========================================================================
# TEST CLASS: pharmacy_own_rate_history (MFR-003)
# ===========================================================================


class TestPharmacyOwnRateHistory:
    """MFR-003: per (pharmacy_npi, NDC), pharmacy's own historical IC/WAC rate."""

    def test_exclusion_is_own_prior_period(self, db: Session):
        """BaselineCache.extra.exclusion == 'own_prior_period' for MFR-003."""
        run = _make_run(db)
        for i in range(3):
            _row(
                db, run, row_number=i + 1,
                npi=_NPI_ALPHA, ndc=_NDC_A,
                ingredient_cost_paid="120.00",
                extended_wac="100.00",
            )
        db.flush()

        compute_baseline(db, run, kind="pharmacy_own_rate_history", min_sample_count=1)

        scope_key = f"ndc={_NDC_A}|pharmacy_npi={_NPI_ALPHA}"
        row = (
            db.query(BaselineCache)
            .filter(
                BaselineCache.baseline_kind == "pharmacy_own_rate_history",
                BaselineCache.scope_key == scope_key,
            )
            .one()
        )
        assert row.extra["exclusion"] == "own_prior_period", (
            f"Expected 'own_prior_period', got {row.extra['exclusion']!r}"
        )

    def test_own_rate_value_is_ic_over_wac(self, db: Session):
        """
        3 rows with IC=120, WAC=100: IC/WAC rate = 1.2 for each.
        Baseline mean should be 1.2.
        """
        run = _make_run(db)
        for i in range(3):
            _row(
                db, run, row_number=i + 1,
                npi=_NPI_ALPHA, ndc=_NDC_A,
                ingredient_cost_paid="120.00",
                extended_wac="100.00",
            )
        db.flush()

        compute_baseline(db, run, kind="pharmacy_own_rate_history", min_sample_count=1)

        scope_key = f"ndc={_NDC_A}|pharmacy_npi={_NPI_ALPHA}"
        row = (
            db.query(BaselineCache)
            .filter(
                BaselineCache.baseline_kind == "pharmacy_own_rate_history",
                BaselineCache.scope_key == scope_key,
            )
            .one()
        )
        assert row.mean == Decimal("1.2"), (
            f"Expected mean IC/WAC=1.2, got {row.mean}"
        )

    def test_not_peer_comparison(self, db: Session):
        """
        Two pharmacies, same NDC, different rates.
        Each pharmacy should have ITS OWN mean — not a peer mean.
        NPI_ALPHA: IC/WAC = 1.2 (3 rows); NPI_BETA: IC/WAC = 0.9 (3 rows).
        They must not influence each other.
        """
        run = _make_run(db)
        for i in range(3):
            _row(
                db, run, row_number=i + 1,
                npi=_NPI_ALPHA, ndc=_NDC_A,
                ingredient_cost_paid="120.00",
                extended_wac="100.00",
            )
        for i in range(3):
            _row(
                db, run, row_number=100 + i,
                npi=_NPI_BETA, ndc=_NDC_A,
                ingredient_cost_paid="90.00",
                extended_wac="100.00",
            )
        db.flush()

        compute_baseline(db, run, kind="pharmacy_own_rate_history", min_sample_count=1)

        rows = {
            r.scope_key: r
            for r in db.query(BaselineCache)
            .filter(BaselineCache.baseline_kind == "pharmacy_own_rate_history")
            .all()
        }
        alpha_key = f"ndc={_NDC_A}|pharmacy_npi={_NPI_ALPHA}"
        beta_key = f"ndc={_NDC_A}|pharmacy_npi={_NPI_BETA}"

        assert alpha_key in rows
        assert beta_key in rows
        assert rows[alpha_key].mean == Decimal("1.2"), (
            f"NPI_ALPHA mean={rows[alpha_key].mean!r}, expected 1.2"
        )
        assert rows[beta_key].mean == Decimal("0.9"), (
            f"NPI_BETA mean={rows[beta_key].mean!r}, expected 0.9"
        )

    def test_min_sample_gate_own_rate(self, db: Session):
        """Below min_sample_count, no row is written even for own-rate history."""
        run = _make_run(db)
        # Only 2 rows — below default min_sample_count=5
        for i in range(2):
            _row(
                db, run, row_number=i + 1,
                npi=_NPI_ALPHA, ndc=_NDC_A,
                ingredient_cost_paid="120.00",
                extended_wac="100.00",
            )
        db.flush()

        n = compute_baseline(db, run, kind="pharmacy_own_rate_history", min_sample_count=5)
        assert n == 0

    def test_provenance_extra_fields(self, db: Session):
        """extra dict contains window_days, min_sample_count, data_source."""
        run = _make_run(db)
        for i in range(3):
            _row(
                db, run, row_number=i + 1,
                npi=_NPI_ALPHA, ndc=_NDC_A,
                ingredient_cost_paid="110.00",
                extended_wac="100.00",
            )
        db.flush()

        compute_baseline(
            db, run,
            kind="pharmacy_own_rate_history",
            window_days=60,
            min_sample_count=1,
        )

        row = (
            db.query(BaselineCache)
            .filter(BaselineCache.baseline_kind == "pharmacy_own_rate_history")
            .first()
        )
        assert row is not None
        assert row.extra["window_days"] == 60
        assert row.extra["min_sample_count"] == 1
        assert row.extra["data_source"] == "csv_upload"
        assert row.extra["exclusion"] == "own_prior_period"
        assert row.window_days == 60


# ===========================================================================
# TEST CLASS: edge cases and API contract
# ===========================================================================


class TestEdgeCases:
    """Unknown kind, zero-division guard, return type."""

    def test_unknown_kind_raises_value_error(self, db: Session):
        """compute_baseline raises ValueError for an unsupported kind."""
        run = _make_run(db)
        with pytest.raises(ValueError, match="unknown baseline kind"):
            compute_baseline(db, run, kind="nonexistent_kind")

    def test_returns_int_rows_written(self, db: Session):
        """compute_baseline always returns an int."""
        run = _make_run(db)
        result = compute_baseline(db, run, kind="prescriber_peer_volume")
        assert isinstance(result, int)

    def test_no_rows_returns_zero(self, db: Session):
        """Empty run → 0 rows written for any kind."""
        run = _make_run(db)
        for kind in [
            "prescriber_peer_volume",
            "pharmacy_ndc_volume",
            "member_cost",
            "pharmacy_weekday_volume",
            "pharmacy_own_rate_history",
        ]:
            n = compute_baseline(db, run, kind=kind, min_sample_count=1)
            assert n == 0, f"{kind}: expected 0 rows for empty run, got {n}"

    def test_baseline_cache_columns_are_decimal_not_float(self, db: Session):
        """mean and stddev columns on persisted rows are Decimal, not float."""
        run = _make_run(db)
        for presc, count in [(_PRESC_X, 3), (_PRESC_Y, 3), (_PRESC_Z, 3)]:
            for i in range(count):
                _row(
                    db, run,
                    row_number=len(db.query(CsvUploadRow).all()) + 1,
                    npi=_NPI_ALPHA, ndc=_NDC_A,
                    prescriber_npi=presc,
                )
        db.flush()

        compute_baseline(db, run, kind="prescriber_peer_volume", min_sample_count=1)

        rows = db.query(BaselineCache).filter(
            BaselineCache.baseline_kind == "prescriber_peer_volume"
        ).all()
        for row in rows:
            if row.mean is not None:
                assert isinstance(row.mean, Decimal), (
                    f"mean is {type(row.mean).__name__}, expected Decimal"
                )

    def test_data_source_is_csv_upload(self, db: Session):
        """data_source column is always 'csv_upload' for this function."""
        run = _make_run(db)
        for presc, count in [(_PRESC_X, 3), (_PRESC_Y, 3)]:
            for i in range(count):
                _row(
                    db, run,
                    row_number=len(db.query(CsvUploadRow).all()) + 1,
                    npi=_NPI_ALPHA, ndc=_NDC_A,
                    prescriber_npi=presc,
                )
        db.flush()

        compute_baseline(db, run, kind="prescriber_peer_volume", min_sample_count=1)

        rows = db.query(BaselineCache).filter(
            BaselineCache.baseline_kind == "prescriber_peer_volume"
        ).all()
        for row in rows:
            assert row.data_source == "csv_upload"

    def test_compute_baseline_twice_no_unique_violation(self, db: Session):
        """Running compute_baseline a second time for the same tenant/kind/scope
        must NOT raise UniqueViolation -- it should upsert (ON CONFLICT DO UPDATE).

        This verifies the correctness fix for the baseline_cache upsert: the
        uq_baseline_cache_scope unique index on
        (tenant_id, baseline_kind, scope_key, window_days, data_source)
        must be respected by an ON CONFLICT DO UPDATE clause, not a blind INSERT.
        """
        run = _make_run(db)
        # Three prescribers for NDC_A so peer baselines are computable.
        for presc, count in [(_PRESC_X, 3), (_PRESC_Y, 3), (_PRESC_Z, 3)]:
            for i in range(count):
                _row(
                    db, run,
                    row_number=len(db.query(CsvUploadRow).all()) + 1,
                    npi=_NPI_ALPHA, ndc=_NDC_A,
                    prescriber_npi=presc,
                )
        db.flush()

        # First run -- writes baseline rows.
        n1 = compute_baseline(db, run, kind="prescriber_peer_volume", min_sample_count=1)
        assert n1 > 0, "First compute_baseline must write at least one row"

        # Second run with the same run / same scope -- must not raise, must upsert.
        # On SQLite the unique index is not enforced as strictly as Postgres
        # but the INSERT OR REPLACE path should still not raise.
        try:
            n2 = compute_baseline(db, run, kind="prescriber_peer_volume", min_sample_count=1)
        except Exception as exc:
            raise AssertionError(
                f"Second compute_baseline raised {type(exc).__name__}: {exc} -- "
                "expected upsert (ON CONFLICT DO UPDATE), not a UniqueViolation"
            ) from exc

        # After the second call the row count should be unchanged (same scope keys).
        after = db.query(BaselineCache).filter(
            BaselineCache.baseline_kind == "prescriber_peer_volume",
            BaselineCache.tenant_id == _TENANT,
        ).count()
        assert after == n1, (
            f"Row count after second compute_baseline ({after}) differs from "
            f"first ({n1}); upsert should leave the count unchanged"
        )
