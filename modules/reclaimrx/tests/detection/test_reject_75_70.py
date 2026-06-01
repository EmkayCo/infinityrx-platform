"""Tests for Reject-75->70 fast-rebill rule (LOCKED: group_key=rx_number_hash).

Planted sequences at 6h, 18h, 30h. Asserts bucket classification.
"""
from __future__ import annotations
import pytest
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from sqlalchemy import select
from tests.conftest import TEST_TENANT_ID, TEST_USER_ID


def _ts(hours_offset: float) -> str:
    base = datetime(2026, 1, 15, 8, 0, 0, tzinfo=UTC)
    dt = base + timedelta(hours=hours_offset)
    return dt.isoformat()


def _make_reject_rebill_rows(db, run, rx_hash: str, reject_ts_hours: float,
                              rebill_ts_hours: float, reject_code: str = "75"):
    """Seed one reject (code 75) + one rebill (code 70) row pair."""
    from src.models.detection_run_models import CsvUploadRow
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=1,
        row_data={
            "rx_number_hash": rx_hash,
            "transaction_code": "B1",
            "transaction_status": "Rejected",
            "reject_code": reject_code,
            "date_added_timestamp": _ts(reject_ts_hours),
            "pharmacy_npi": "1234567890",
            "ndc": "12345678901",
            "patient_unique_hash": "patient-A",
            "ingredient_cost_paid": "0.00",
        },
        resolution_method="declared",
        resolved_pharmacy_npi="1234567890",
        resolved_ndc="12345678901",
    ))
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=2,
        row_data={
            "rx_number_hash": rx_hash,
            "transaction_code": "B1",
            "transaction_status": "Rejected",
            "reject_code": "70",
            "date_added_timestamp": _ts(rebill_ts_hours),
            "pharmacy_npi": "1234567890",
            "ndc": "12345678901",
            "patient_unique_hash": "patient-A",
            "ingredient_cost_paid": "0.00",
        },
        resolution_method="declared",
        resolved_pharmacy_npi="1234567890",
        resolved_ndc="12345678901",
    ))
    db.flush()


class TestReject7570:
    def test_le12h_fires_bucket_le12h(self, db):
        from src.detection.reject_rebill import evaluate_reject_75_70
        from src.models.detection_run_models import DetectionRun
        from datetime import date

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload", run_label="r75-test",
            status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 2, "expected_count": 2},
        )
        db.add(run)
        db.flush()
        _make_reject_rebill_rows(db, run, rx_hash="RX-HASH-001",
                                 reject_ts_hours=0, rebill_ts_hours=6)
        results = evaluate_reject_75_70(db, run)
        assert len(results) == 1
        assert results[0].finding_details["bucket"] == "le12h"
        assert results[0].finding_code == "REJECT-75-70"

    def test_12_24h_fires_bucket_12_24h(self, db):
        from src.detection.reject_rebill import evaluate_reject_75_70
        from src.models.detection_run_models import DetectionRun

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload", run_label="r75-test2",
            status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 2, "expected_count": 2},
        )
        db.add(run)
        db.flush()
        _make_reject_rebill_rows(db, run, rx_hash="RX-HASH-002",
                                 reject_ts_hours=0, rebill_ts_hours=18)
        results = evaluate_reject_75_70(db, run)
        assert len(results) == 1
        assert results[0].finding_details["bucket"] == "12_24h"

    def test_gt24h_excluded(self, db):
        from src.detection.reject_rebill import evaluate_reject_75_70
        from src.models.detection_run_models import DetectionRun

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload", run_label="r75-test3",
            status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 2, "expected_count": 2},
        )
        db.add(run)
        db.flush()
        _make_reject_rebill_rows(db, run, rx_hash="RX-HASH-003",
                                 reject_ts_hours=0, rebill_ts_hours=30)
        results = evaluate_reject_75_70(db, run)
        assert len(results) == 0

    def test_non_75_reject_not_flagged(self, db):
        from src.detection.reject_rebill import evaluate_reject_75_70
        from src.models.detection_run_models import DetectionRun

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload", run_label="r75-test4",
            status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 2, "expected_count": 2},
        )
        db.add(run)
        db.flush()
        # reject code 76 (not 75) -> should not fire
        _make_reject_rebill_rows(db, run, rx_hash="RX-HASH-004",
                                 reject_ts_hours=0, rebill_ts_hours=6,
                                 reject_code="76")
        results = evaluate_reject_75_70(db, run)
        assert len(results) == 0


def _count_reject_queries_for_n_groups(db, n: int) -> int:
    """Seed n distinct rx_number_hash groups and return DB query count for evaluate_reject_75_70.

    Used by the constant-query-count test: proves the implementation is O(1) queries,
    NOT O(N) (one query per group).
    """
    from src.detection.reject_rebill import evaluate_reject_75_70
    from src.models.detection_run_models import DetectionRun, CsvUploadRow
    from sqlalchemy import event as sa_event

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label=f"rq-count-{n}", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": n * 2, "expected_count": n * 2},
    )
    db.add(run)
    db.flush()

    row_num = 1
    for i in range(n):
        rx_hash = f"RX-QCOUNT-{i:04d}"
        # reject row (code 75)
        db.add(CsvUploadRow(
            tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=row_num,
            row_data={
                "rx_number_hash": rx_hash,
                "reject_code": "75",
                "date_added_timestamp": _ts(0),
                "transaction_code": "B1",
                "transaction_status": "Rejected",
            },
            resolution_method="declared",
            resolved_pharmacy_npi="1234567890",
        ))
        row_num += 1
        # rebill row (code 70, 6h later -> le12h bucket)
        db.add(CsvUploadRow(
            tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=row_num,
            row_data={
                "rx_number_hash": rx_hash,
                "reject_code": "70",
                "date_added_timestamp": _ts(6),
                "transaction_code": "B1",
                "transaction_status": "Rejected",
            },
            resolution_method="declared",
            resolved_pharmacy_npi="1234567890",
        ))
        row_num += 1
    db.flush()

    query_count = [0]

    @sa_event.listens_for(db.get_bind(), "before_cursor_execute")
    def _count(conn, cursor, statement, params, context, executemany):
        query_count[0] += 1

    evaluate_reject_75_70(db, run)
    return query_count[0]


def test_reject_7570_query_count_constant_not_linear(db):
    """Query count must be CONSTANT as the number of rx_number_hash groups grows.

    5 groups vs 50 groups must issue the same number of DB queries.
    Proves the set-based self-join (O(1) queries) vs the old N+1 loop (O(N) queries).
    """
    count_5 = _count_reject_queries_for_n_groups(db, 5)
    count_50 = _count_reject_queries_for_n_groups(db, 50)
    assert count_5 == count_50, (
        f"Query count is NOT constant: 5 groups={count_5}, 50 groups={count_50}. "
        f"N+1 pattern suspected -- implementation must use a single set-based self-join."
    )
    # Absolute ceiling: at most 3 queries (self-join pairs + ORM batch fetch + any flush)
    assert count_5 <= 3, f"Too many queries even for 5 groups: {count_5}"


def test_reject_7570_bucket_classification_6h_18h_30h(db):
    """Three planted sequences at 6h, 18h, 30h -> correct buckets and >24h exclusion.

    Sequence A: 0->6h   (elapsed 6h)  -> bucket le12h   (fires)
    Sequence B: 0->18h  (elapsed 18h) -> bucket 12_24h  (fires)
    Sequence C: 0->30h  (elapsed 30h) -> excluded (>24h, no anomaly)

    Asserts:
      len(results) == 2
      Sequence A anomaly -> bucket == "le12h"
      Sequence B anomaly -> bucket == "12_24h"
      No anomaly for rx_hash "RX-BUCKET-C" (30h -> excluded)
    """
    from src.detection.reject_rebill import evaluate_reject_75_70
    from src.models.detection_run_models import DetectionRun

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="r75-bucket-test", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": 6, "expected_count": 6},
    )
    db.add(run)
    db.flush()

    _make_reject_rebill_rows(db, run, rx_hash="RX-BUCKET-A", reject_ts_hours=0, rebill_ts_hours=6)
    _make_reject_rebill_rows(db, run, rx_hash="RX-BUCKET-B", reject_ts_hours=0, rebill_ts_hours=18)
    _make_reject_rebill_rows(db, run, rx_hash="RX-BUCKET-C", reject_ts_hours=0, rebill_ts_hours=30)

    results = evaluate_reject_75_70(db, run)
    assert len(results) == 2, (
        f"Expected 2 anomalies (6h+18h fire, 30h excluded), got {len(results)}: "
        f"{[r.finding_details for r in results]}"
    )
    bucket_by_hash = {r.finding_details["rx_number_hash"]: r.finding_details["bucket"]
                     for r in results}
    assert bucket_by_hash.get("RX-BUCKET-A") == "le12h", (
        f"6h sequence must classify as le12h, got {bucket_by_hash}"
    )
    assert bucket_by_hash.get("RX-BUCKET-B") == "12_24h", (
        f"18h sequence must classify as 12_24h, got {bucket_by_hash}"
    )
    assert "RX-BUCKET-C" not in bucket_by_hash, (
        "30h sequence must be excluded (>24h), but an anomaly was produced"
    )


def test_reject_7570_run_detection_integration(db):
    """run_detection integration: planted 75->70 at 6h + clean denominator.

    Setup:
      - 500 clean rows (no reject pattern) as denominator
      - 1 planted 75->70 pair with 6h elapsed (fires bucket le12h)
      - REJECT-75-70 rule type + enabled instance seeded via register_rule_types/instances
    Fire rate: 1 / 502 = 0.199% -- well under 0.5% per-rule ceiling.
    Expected outcome:
      - run.status == 'completed'
      - exactly 1 Anomaly with finding_code='REJECT-75-70', bucket='le12h'
    """
    from src.detection.batch_engine import run_detection
    from src.detection.rule_type_registry import register_rule_types, register_rule_instances
    from src.models.detection_run_models import DetectionRun, CsvUploadRow, Anomaly
    from sqlalchemy import select

    total_rows = 502  # 500 clean + 2 planted

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="reject-integration", status="in_progress",
        created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": total_rows, "expected_count": total_rows},
    )
    db.add(run)
    db.flush()

    # Seed the planted 75->70 pair FIRST (row_number 1 and 2) so that
    # _available_columns_for_run (LIMIT 1 sample) hits a row containing
    # rx_number_hash, reject_code, and date_added_timestamp.
    _make_reject_rebill_rows(
        db, run,
        rx_hash="RX-INTEGRATION-001",
        reject_ts_hours=0,
        rebill_ts_hours=6,
    )

    # Seed 500 clean rows as denominator (no reject pattern).
    # Fire rate: 1 anomaly / 502 total rows = 0.199% -- under 0.5% per-rule ceiling.
    for i in range(500):
        db.add(CsvUploadRow(
            tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i + 3,
            row_data={
                "patient_unique_hash": f"clean-patient-{i}",
                "ndc": "12345678901",
                "date_of_service": "2026-01-15",
            },
            resolution_method="declared",
        ))
    db.flush()

    # Register rule types + an enabled REJECT-75-70 instance
    register_rule_types(db)
    available_cols = {"rx_number_hash", "reject_code", "date_added_timestamp",
                      "patient_unique_hash", "ndc", "date_of_service"}
    register_rule_instances(db, TEST_TENANT_ID, available_cols, TEST_USER_ID)

    count = run_detection(db, run)

    db.refresh(run)
    assert run.status == "completed", (
        f"run.status should be 'completed', got {run.status!r}. "
        f"resolution_stats={run.resolution_stats}"
    )

    anomalies = db.execute(
        select(Anomaly).where(
            Anomaly.data_source_run_id == run.id,
            Anomaly.finding_code == "REJECT-75-70",
        )
    ).scalars().all()

    assert len(anomalies) == 1, (
        f"Expected 1 REJECT-75-70 anomaly, got {len(anomalies)}"
    )
    assert anomalies[0].finding_details["bucket"] == "le12h", (
        f"Expected bucket='le12h', got {anomalies[0].finding_details}"
    )
    assert anomalies[0].finding_details["rx_number_hash"] == "RX-INTEGRATION-001"
