"""Transparency report generation service (CAA 2026).

Generates semiannual / quarterly reports per plan sponsor:
  - Net drug spending
  - Rebates received and passed through
  - Spread pricing (should be zero in pass-through model)
  - Formulary rationale
  - Affiliated pharmacy utilization

PDF generation uses a minimal built-in writer (reportlab if available,
otherwise a pure-Python text/PDF writer).
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.models.tables import (
    PassThroughEntry,
    RebateTransaction,
    TransparencyReport,
)
from src.utils.money import ZERO, money


def _build_pdf_bytes(report_data: dict[str, Any]) -> bytes:
    """Generate a minimal PDF containing the transparency report data.

    Attempts to use reportlab. Falls back to a minimal hand-crafted PDF
    if reportlab is not installed.
    """
    try:
        from reportlab.lib.pagesizes import letter  # type: ignore[import-untyped]
        from reportlab.pdfgen import canvas  # type: ignore[import-untyped]

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        c.setTitle("CAA 2026 Transparency Report")
        y = 750
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "CAA 2026 Transparency Report")
        c.setFont("Helvetica", 10)
        y -= 30
        sponsor_id = report_data.get("sponsor_id", "")
        period = f"{report_data.get('period_start')} – {report_data.get('period_end')}"
        c.drawString(50, y, f"Sponsor: {sponsor_id}")
        y -= 20
        c.drawString(50, y, f"Period: {period}")
        y -= 30
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "CONFIDENTIAL — CONTAINS PHI")
        y -= 30
        c.setFont("Helvetica", 10)
        for k, v in report_data.items():
            if y < 50:
                c.showPage()
                y = 750
            c.drawString(50, y, f"{k}: {v}")
            y -= 18
        c.save()
        return buf.getvalue()
    except ImportError:
        # Minimal hand-crafted valid PDF
        content_lines = [f"{k}: {v}" for k, v in report_data.items()]
        content_lines.insert(0, "CONFIDENTIAL - CONTAINS PHI")
        content_lines.insert(0, "CAA 2026 Transparency Report")
        stream_text = "\n".join(content_lines)
        stream_bytes = stream_text.encode("latin-1", errors="replace")
        stream_len = len(stream_bytes)
        pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
            + b"4 0 obj\n<< /Length "
            + str(stream_len + 40).encode()
            + b" >>\nstream\nBT /F1 10 Tf 50 750 Td\n("
            + stream_bytes[:200]
            + b") Tj\nET\nendstream\nendobj\n"
            b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
            b"xref\n0 6\n0000000000 65535 f \n"
            b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n0\n%%EOF\n"
        )
        return pdf


class TransparencyReportService:
    """Generates and manages CAA 2026 transparency reports."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def generate_report(
        self,
        tenant_id: uuid.UUID,
        sponsor_id: uuid.UUID,
        report_type: str,
        period_start: date,
        period_end: date,
        generated_by: uuid.UUID | None = None,
        affiliated_pharmacy_utilization_pct: Decimal | None = None,
    ) -> TransparencyReport:
        """Generate a transparency report from pass-through ledger data.

        Aggregates rebates received / passed through for the period.
        Computes net drug spending from transactions.
        Generates a PDF with CONFIDENTIAL watermark.
        """
        from sqlalchemy import func

        # Aggregate rebates received (from rebate transactions)
        rebate_row = (
            self._db.query(
                func.sum(RebateTransaction.rebate_amount).label("total"),
                func.sum(RebateTransaction.gross_wac).label("gross_wac"),
            )
            .filter(
                RebateTransaction.tenant_id == tenant_id,
                RebateTransaction.sponsor_id == sponsor_id,
                RebateTransaction.period_start >= period_start,
                RebateTransaction.period_end <= period_end,
                RebateTransaction.transaction_type == "calculated",
            )
            .first()
        )

        total_rebates_received = money(
            Decimal(str(rebate_row.total)) if rebate_row.total else ZERO
        )
        gross_drug_costs = money(
            Decimal(str(rebate_row.gross_wac)) if rebate_row.gross_wac else ZERO
        )

        # Aggregate pass-through amounts
        pt_row = (
            self._db.query(
                func.sum(PassThroughEntry.manufacturer_received).label("received"),
                func.sum(PassThroughEntry.sponsor_passed).label("passed"),
            )
            .filter(
                PassThroughEntry.tenant_id == tenant_id,
                PassThroughEntry.sponsor_id == sponsor_id,
                PassThroughEntry.period_month >= period_start,
                PassThroughEntry.period_month <= period_end,
            )
            .first()
        )

        total_rebates_passed = money(
            Decimal(str(pt_row.passed)) if pt_row and pt_row.passed else ZERO
        )

        net_drug_spending = money(gross_drug_costs - total_rebates_passed)
        spread_pricing_amount = ZERO  # pass-through model: always zero

        report_data: dict[str, Any] = {
            "sponsor_id": str(sponsor_id),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "report_type": report_type,
            "net_drug_spending": str(net_drug_spending),
            "gross_drug_costs": str(gross_drug_costs),
            "total_rebates_received": str(total_rebates_received),
            "total_rebates_passed": str(total_rebates_passed),
            "spread_pricing_amount": str(spread_pricing_amount),
            "affiliated_pharmacy_utilization_pct": str(
                affiliated_pharmacy_utilization_pct or ZERO
            ),
            "generated_at": datetime.now(UTC).isoformat(),
        }

        pdf_bytes = _build_pdf_bytes(report_data)
        # In production, pdf_bytes would be written to object storage.
        # Here we store a placeholder path.
        pdf_path = f"transparency/{tenant_id}/{sponsor_id}/{period_start}_{period_end}.pdf"

        now = datetime.now(UTC)
        report = TransparencyReport(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            sponsor_id=sponsor_id,
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            status="ready",
            net_drug_spending=net_drug_spending,
            gross_drug_costs=gross_drug_costs,
            total_rebates_received=total_rebates_received,
            total_rebates_passed=total_rebates_passed,
            spread_pricing_amount=spread_pricing_amount,
            affiliated_pharmacy_utilization_pct=affiliated_pharmacy_utilization_pct,
            report_data=report_data,
            pdf_path=pdf_path,
            generated_by=generated_by,
            generated_at=now,
            created_at=now,
        )
        self._db.add(report)
        self._db.flush()
        return report, pdf_bytes

    def list_reports(
        self,
        tenant_id: uuid.UUID,
        sponsor_id: uuid.UUID | None = None,
    ) -> list[TransparencyReport]:
        q = self._db.query(TransparencyReport).filter(
            TransparencyReport.tenant_id == tenant_id
        )
        if sponsor_id:
            q = q.filter(TransparencyReport.sponsor_id == sponsor_id)
        return q.all()
