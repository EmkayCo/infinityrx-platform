"""Payment reconciliation service.

Compares expected payments (from submissions) vs actual settlements.
Returns match/discrepancy/unmatched rows for the dashboard.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.schemas.payment import ReconciliationRow
from ..models import Settlement, Submission
from .decimal_utils import money


class ReconciliationService:
    """Reconciliation data for the payment dashboard API."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_reconciliation_rows(
        self,
        tenant_id: str,
        submission_ids: list[str] | None = None,
    ) -> list[ReconciliationRow]:
        """Compare submitted payments against settled amounts."""
        query = select(Settlement).where(Settlement.tenant_id == tenant_id)
        if submission_ids:
            query = query.where(Settlement.submission_id.in_(submission_ids))

        settlements = self._session.execute(query).scalars().all()
        rows = []
        today = date.today()

        for s in settlements:
            expected = s.amount
            actual = s.amount if s.status == "settled" else None
            discrepancy = None
            if actual is not None:
                discrepancy = money(actual - expected)

            days_outstanding: int | None = None
            if s.status == "pending":
                created_dt = s.created_at
                if created_dt:
                    created_date = created_dt.date() if hasattr(created_dt, "date") else created_dt
                    days_outstanding = (today - created_date).days

            rows.append(
                ReconciliationRow(
                    submission_id=s.submission_id,
                    billing_payment_id=s.billing_payment_id,
                    expected_amount=expected,
                    actual_amount=actual,
                    status=s.status,
                    discrepancy=discrepancy,
                    days_outstanding=days_outstanding,
                )
            )
        return rows

    def get_dashboard_summary(self, tenant_id: str) -> dict:
        """Return aggregated stats for the payment dashboard."""
        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)

        submissions = self._session.execute(
            select(Submission).where(
                Submission.tenant_id == tenant_id,
                Submission.created_at >= thirty_days_ago,
            )
        ).scalars().all()

        settlements = self._session.execute(
            select(Settlement).where(
                Settlement.tenant_id == tenant_id,
                Settlement.created_at >= thirty_days_ago,
            )
        ).scalars().all()

        total_submitted = money(sum(s.total_amount for s in submissions))
        total_settled = money(
            sum(s.amount for s in settlements if s.status == "settled")
        )
        total_returned = money(
            sum(s.amount for s in settlements if s.status == "returned")
        )

        pending = [s for s in settlements if s.status == "pending"]
        pending_amount = money(sum(s.amount for s in pending))

        denom = money(total_submitted)
        rate = money(
            (total_settled / denom * 100) if denom > Decimal("0") else Decimal("0")
        )

        return {
            "total_submitted_30d": total_submitted,
            "total_settled_30d": total_settled,
            "total_returned_30d": total_returned,
            "submission_count_30d": len(submissions),
            "settlement_rate_pct": rate,
            "pending_settlement_count": len(pending),
            "pending_settlement_amount": pending_amount,
        }
