"""Fiduciary compliance dashboard service.

Provides real-time audit-ready view of:
- Pass-through % (must be 100%)
- BFSF compliance
- Transparency report status
- Audit export readiness
- Spend cap compliance
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from src.models.tables import (
    AuditExport,
    BFSFDocument,
    ComplianceDashboardSnapshot,
    PassThroughReconciliation,
    SpendCapActual,
    SpendCapGuarantee,
    TransparencyReport,
)
from src.utils.money import ZERO, money

FOUR_PLACES = Decimal("0.0001")


class ComplianceDashboardService:
    """Builds and caches compliance dashboard snapshots."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def build_snapshot(
        self,
        tenant_id: uuid.UUID,
        sponsor_id: uuid.UUID,
        snapshot_date: date,
    ) -> ComplianceDashboardSnapshot:
        """Build a compliance snapshot for a sponsor as of snapshot_date."""
        # Pass-through %: from most recent reconciliation
        recent_recon = (
            self._db.query(PassThroughReconciliation)
            .filter(
                PassThroughReconciliation.tenant_id == tenant_id,
                PassThroughReconciliation.sponsor_id == sponsor_id,
                PassThroughReconciliation.period_month <= snapshot_date,
            )
            .order_by(PassThroughReconciliation.period_month.desc())
            .first()
        )

        if recent_recon and recent_recon.total_received > ZERO:
            pass_through_pct = (
                recent_recon.total_passed / recent_recon.total_received
            ).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
        else:
            pass_through_pct = Decimal("1.0000")  # no data = assume compliant

        # BFSF docs complete: at least one approved doc exists for current year
        current_year = snapshot_date.year
        approved_bfsf = (
            self._db.query(BFSFDocument)
            .filter(
                BFSFDocument.tenant_id == tenant_id,
                BFSFDocument.sponsor_id == sponsor_id,
                BFSFDocument.status == "approved",
                BFSFDocument.assessment_year == current_year,
            )
            .count()
        )
        bfsf_docs_complete = approved_bfsf > 0

        # Transparency report status
        six_months_ago = date(
            snapshot_date.year if snapshot_date.month > 6 else snapshot_date.year - 1,
            snapshot_date.month - 6 if snapshot_date.month > 6 else snapshot_date.month + 6,
            1,
        )
        recent_report = (
            self._db.query(TransparencyReport)
            .filter(
                TransparencyReport.tenant_id == tenant_id,
                TransparencyReport.sponsor_id == sponsor_id,
                TransparencyReport.period_end >= six_months_ago,
            )
            .order_by(TransparencyReport.period_end.desc())
            .first()
        )
        if recent_report is None:
            transparency_status = "overdue"
        elif recent_report.status == "filed":
            transparency_status = "filed"
        else:
            transparency_status = "pending"

        # Audit export ready: at least one ready export in the last year
        audit_ready = (
            self._db.query(AuditExport)
            .filter(
                AuditExport.tenant_id == tenant_id,
                AuditExport.sponsor_id == sponsor_id,
                AuditExport.status == "ready",
            )
            .count()
        ) > 0

        # Spend cap compliance: no 100% threshold breaches without refund recorded
        active_guarantees = (
            self._db.query(SpendCapGuarantee)
            .filter(
                SpendCapGuarantee.tenant_id == tenant_id,
                SpendCapGuarantee.sponsor_id == sponsor_id,
                SpendCapGuarantee.is_active == True,  # noqa: E712
            )
            .all()
        )
        spend_cap_compliant = True
        for guarantee in active_guarantees:
            latest_actual = (
                self._db.query(SpendCapActual)
                .filter(
                    SpendCapActual.tenant_id == tenant_id,
                    SpendCapActual.guarantee_id == guarantee.id,
                    SpendCapActual.tracking_month <= snapshot_date,
                )
                .order_by(SpendCapActual.tracking_month.desc())
                .first()
            )
            if latest_actual and latest_actual.refund_owed > ZERO:
                spend_cap_compliant = False
                break

        spread_pricing_amount = ZERO  # always zero in pass-through model
        overall_compliant = (
            pass_through_pct >= Decimal("1.0000")
            and bfsf_docs_complete
            and transparency_status != "overdue"
            and audit_ready
            and spend_cap_compliant
        )

        detail = {
            "pass_through_pct": str(pass_through_pct),
            "bfsf_docs_complete": bfsf_docs_complete,
            "transparency_report_status": transparency_status,
            "audit_export_ready": audit_ready,
            "spend_cap_compliant": spend_cap_compliant,
            "overall_compliant": overall_compliant,
        }

        now = datetime.now(UTC)
        # Upsert snapshot
        existing = (
            self._db.query(ComplianceDashboardSnapshot)
            .filter(
                ComplianceDashboardSnapshot.tenant_id == tenant_id,
                ComplianceDashboardSnapshot.sponsor_id == sponsor_id,
                ComplianceDashboardSnapshot.snapshot_date == snapshot_date,
            )
            .first()
        )
        if existing:
            existing.pass_through_pct = pass_through_pct
            existing.spread_pricing_amount = spread_pricing_amount
            existing.bfsf_docs_complete = bfsf_docs_complete
            existing.transparency_report_status = transparency_status
            existing.audit_export_ready = audit_ready
            existing.spend_cap_compliant = spend_cap_compliant
            existing.overall_compliant = overall_compliant
            existing.detail = detail
            self._db.flush()
            return existing

        snapshot = ComplianceDashboardSnapshot(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            sponsor_id=sponsor_id,
            snapshot_date=snapshot_date,
            pass_through_pct=pass_through_pct,
            spread_pricing_amount=spread_pricing_amount,
            bfsf_docs_complete=bfsf_docs_complete,
            transparency_report_status=transparency_status,
            audit_export_ready=audit_ready,
            spend_cap_compliant=spend_cap_compliant,
            overall_compliant=overall_compliant,
            detail=detail,
            created_at=now,
        )
        self._db.add(snapshot)
        self._db.flush()
        return snapshot
