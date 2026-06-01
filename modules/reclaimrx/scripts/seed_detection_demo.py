"""Seed script: insert 1 completed detection_run + ~50 anomalies for demo tenant.

Demo tenant: a0000000-0000-0000-0000-000000000001
Finding codes: >=6 codes, 4 severities, pharmacy + prescriber entities, varied amounts.

Idempotent: if the run already exists (checked by run_label), it is skipped.
Run with: python -m scripts.seed_detection_demo (from modules/reclaimrx/)
          or: python scripts/seed_detection_demo.py

Requires:
    RECLAIMRX_DB_URL=postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev

All monetary amounts are Python Decimal, stored as sa.Numeric -- never float.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

# Ensure src/ is on sys.path when run as a script
_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.models.detection_run_models import Anomaly, DetectionRun

DEMO_TENANT_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")
SEED_RUN_LABEL = "demo-seed-v1"
SEED_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Six finding codes across the detection rule families
_FINDING_CODES: list[dict] = [
    {"code": "MFR-001", "summary": "NQ inflation above WAC threshold", "severity": "high"},
    {"code": "MFR-002", "summary": "Manufacturer rebate manipulation", "severity": "critical"},
    {"code": "HP-005", "summary": "High-volume dispense vs peer baseline", "severity": "medium"},
    {"code": "ALL-001", "summary": "Duplicate claim submission", "severity": "high"},
    {"code": "ALL-006", "summary": "Statistical outlier accumulation", "severity": "medium"},
    {"code": "REJECT-75", "summary": "Rapid rebill after rejection", "severity": "low"},
    {"code": "TH-002", "summary": "Multi-state prescriber distribution", "severity": "medium"},
]

_PHARMACY_NPIS = [
    "1497848832",
    "1234567890",
    "9876543210",
    "1122334455",
]

_PRESCRIBER_NPIS = [
    "1234567893",
    "9876543219",
    "5544332211",
    "6655443322",
]

_NDCS = [
    "71403020530",
    "00093015401",
    "00071015523",
    "00378181977",
    "00093083905",
]


def _amount(dollars: str) -> Decimal:
    return Decimal(dollars)


def _make_anomaly(
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    finding_code: str,
    finding_summary: str,
    severity: str,
    pharmacy_npi: str | None = None,
    prescriber_npi: str | None = None,
    ndc: str | None = None,
    amount_paid: Decimal,
    amount_billed: Decimal,
    recovery_amount: Decimal,
    date_of_service: date,
    confidence: Decimal = Decimal("0.8500"),
) -> Anomaly:
    return Anomaly(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        data_source="csv_upload",
        data_source_run_id=run_id,
        source_table="csv_upload_rows",
        source_row_id=uuid.uuid4(),
        detection_kind="rule",
        severity=severity,
        confidence=confidence,
        finding_code=finding_code,
        finding_summary=finding_summary,
        finding_details={
            "seed": True,
            "demo": True,
        },
        status="open",
        pharmacy_npi=pharmacy_npi,
        prescriber_npi=prescriber_npi,
        ndc=ndc,
        amount_paid=amount_paid,
        amount_billed=amount_billed,
        recovery_amount=recovery_amount,
        date_of_service=date_of_service,
    )


def seed(db: Session) -> None:
    """Insert demo run and anomalies. Idempotent -- skips if run_label already exists."""
    existing = db.execute(
        select(DetectionRun).where(
            DetectionRun.tenant_id == DEMO_TENANT_ID,
            DetectionRun.run_label == SEED_RUN_LABEL,
        )
    ).scalar_one_or_none()

    if existing is not None:
        print(f"[seed] Demo run already exists ({existing.id}). Skipping.")
        return

    run = DetectionRun(
        id=uuid.uuid4(),
        tenant_id=DEMO_TENANT_ID,
        data_source="csv_upload",
        run_label=SEED_RUN_LABEL,
        source_filename="demo_claims.csv",
        source_sha256="0" * 64,
        status="completed",
        record_count=1200,
        anomaly_count=0,  # updated after inserting anomalies
        period_start=date(2024, 1, 1),
        period_end=date(2024, 6, 30),
        started_at=datetime(2026, 6, 1, 9, 0, 0, tzinfo=UTC),
        completed_at=datetime(2026, 6, 1, 9, 4, 37, tzinfo=UTC),
        created_by=SEED_USER_ID,
        resolution_stats={
            "expected_count": 1200,
            "inserted_count": 1200,
            "declared": 1180,
            "unmapped": 20,
            "by_reason": {"missing pharmacy_npi": 20},
            "data_quality": {
                "no_fdb_wac": 42,
                "missing_pharmacy_npi": 20,
                "invalid_dos": 3,
            },
        },
    )
    db.add(run)
    db.flush()

    anomalies: list[Anomaly] = []

    # -- MFR-001: NQ inflation (pharmacy entities) -- 10 anomalies
    for i, pharm in enumerate(_PHARMACY_NPIS * 3):
        if i >= 10:
            break
        anomalies.append(_make_anomaly(
            tenant_id=DEMO_TENANT_ID,
            run_id=run.id,
            finding_code="MFR-001",
            finding_summary="NQ inflation above WAC threshold (ratio 1.23)",
            severity="high",
            pharmacy_npi=pharm,
            prescriber_npi=None,
            ndc=_NDCS[i % len(_NDCS)],
            amount_paid=_amount(str(100 + i * 15)) + Decimal("0.00"),
            amount_billed=_amount(str(120 + i * 18)) + Decimal("0.00"),
            recovery_amount=_amount(str(20 + i * 3)) + Decimal("0.00"),
            date_of_service=date(2024, 1 + (i % 6), 10 + i),
            confidence=Decimal("0.9100"),
        ))

    # -- MFR-002: Rebate manipulation (pharmacy entities, critical) -- 5 anomalies
    for i in range(5):
        anomalies.append(_make_anomaly(
            tenant_id=DEMO_TENANT_ID,
            run_id=run.id,
            finding_code="MFR-002",
            finding_summary="Manufacturer rebate submission exceeds program limit",
            severity="critical",
            pharmacy_npi=_PHARMACY_NPIS[i % len(_PHARMACY_NPIS)],
            prescriber_npi=None,
            ndc=_NDCS[i % len(_NDCS)],
            amount_paid=_amount(str(500 + i * 100)),
            amount_billed=_amount(str(600 + i * 120)),
            recovery_amount=_amount(str(100 + i * 20)),
            date_of_service=date(2024, 2 + (i % 4), 5 + i),
            confidence=Decimal("0.9500"),
        ))

    # -- HP-005: High-volume dispense (pharmacy entities, medium) -- 8 anomalies
    for i in range(8):
        anomalies.append(_make_anomaly(
            tenant_id=DEMO_TENANT_ID,
            run_id=run.id,
            finding_code="HP-005",
            finding_summary="Dispense volume 3.2 standard deviations above peer baseline",
            severity="medium",
            pharmacy_npi=_PHARMACY_NPIS[i % len(_PHARMACY_NPIS)],
            prescriber_npi=None,
            ndc=_NDCS[i % len(_NDCS)],
            amount_paid=_amount(str(75 + i * 10)),
            amount_billed=_amount(str(85 + i * 12)),
            recovery_amount=_amount(str(10 + i * 2)),
            date_of_service=date(2024, 3 + (i % 3), 8 + i),
            confidence=Decimal("0.7500"),
        ))

    # -- ALL-001: Duplicate claims (pharmacy entities, high) -- 7 anomalies
    for i in range(7):
        anomalies.append(_make_anomaly(
            tenant_id=DEMO_TENANT_ID,
            run_id=run.id,
            finding_code="ALL-001",
            finding_summary="Duplicate claim for same member/drug/DOS cluster",
            severity="high",
            pharmacy_npi=_PHARMACY_NPIS[i % len(_PHARMACY_NPIS)],
            prescriber_npi=None,
            ndc=_NDCS[i % len(_NDCS)],
            amount_paid=_amount(str(50 + i * 8)),
            amount_billed=_amount(str(60 + i * 10)),
            recovery_amount=_amount(str(50 + i * 8)),
            date_of_service=date(2024, 4 + (i % 2), 1 + i),
            confidence=Decimal("0.9800"),
        ))

    # -- ALL-006: Statistical outlier (prescriber entities, medium) -- 8 anomalies
    for i in range(8):
        anomalies.append(_make_anomaly(
            tenant_id=DEMO_TENANT_ID,
            run_id=run.id,
            finding_code="ALL-006",
            finding_summary="Prescriber accumulation score 4.1 SD above cohort mean",
            severity="medium",
            pharmacy_npi=None,
            prescriber_npi=_PRESCRIBER_NPIS[i % len(_PRESCRIBER_NPIS)],
            ndc=_NDCS[i % len(_NDCS)],
            amount_paid=_amount(str(200 + i * 25)),
            amount_billed=_amount(str(240 + i * 30)),
            recovery_amount=_amount(str(40 + i * 5)),
            date_of_service=date(2024, 1 + (i % 5), 15 + i),
            confidence=Decimal("0.7800"),
        ))

    # -- REJECT-75: Rapid rebill (pharmacy entities, low) -- 7 anomalies
    for i in range(7):
        anomalies.append(_make_anomaly(
            tenant_id=DEMO_TENANT_ID,
            run_id=run.id,
            finding_code="REJECT-75",
            finding_summary="Claim resubmitted within 12h of rejection code 75",
            severity="low",
            pharmacy_npi=_PHARMACY_NPIS[i % len(_PHARMACY_NPIS)],
            prescriber_npi=None,
            ndc=_NDCS[i % len(_NDCS)],
            amount_paid=_amount(str(30 + i * 5)),
            amount_billed=_amount(str(35 + i * 6)),
            recovery_amount=_amount(str(5 + i)),
            date_of_service=date(2024, 5 + (i % 1), 20 + i % 8),
            confidence=Decimal("0.6500"),
        ))

    # -- TH-002: Multi-state prescriber (prescriber entities, medium) -- 5 anomalies
    for i in range(5):
        anomalies.append(_make_anomaly(
            tenant_id=DEMO_TENANT_ID,
            run_id=run.id,
            finding_code="TH-002",
            finding_summary="Prescriber active in 12 states -- exceeds 10-state threshold",
            severity="medium",
            pharmacy_npi=None,
            prescriber_npi=_PRESCRIBER_NPIS[i % len(_PRESCRIBER_NPIS)],
            ndc=None,
            amount_paid=_amount(str(350 + i * 40)),
            amount_billed=_amount(str(400 + i * 45)),
            recovery_amount=_amount(str(50 + i * 5)),
            date_of_service=date(2024, 6, 1 + i),
            confidence=Decimal("0.8000"),
        ))

    for a in anomalies:
        db.add(a)

    db.flush()

    # Update anomaly_count on the run
    run.anomaly_count = len(anomalies)
    db.flush()
    db.commit()

    print(f"[seed] Inserted demo run {run.id} with {len(anomalies)} anomalies.")
    print(f"       Finding codes: {sorted({a.finding_code for a in anomalies})}")
    print(f"       Severities:    {sorted({a.severity for a in anomalies})}")


def main() -> None:
    db_url = os.environ.get("RECLAIMRX_DB_URL")
    if not db_url:
        print("ERROR: RECLAIMRX_DB_URL not set.")
        print("Usage: RECLAIMRX_DB_URL=postgresql://... python scripts/seed_detection_demo.py")
        sys.exit(1)

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as db:
        seed(db)


if __name__ == "__main__":
    main()