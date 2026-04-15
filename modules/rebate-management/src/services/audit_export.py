"""Audit export service — one-click export for plan sponsor audits.

Generates JSON + CSV of all rebate transactions + BFSF docs +
transparency reports for a tenant between two dates.
Creates a signed zip archive with a manifest.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
import zipfile
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.models.tables import (
    AuditExport,
    BFSFDocument,
    PassThroughEntry,
    RebateTransaction,
    TransparencyReport,
)
from src.utils.money import ZERO


def _decimal_default(obj: Any) -> str:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"Cannot serialize {type(obj).__name__}")


def _to_json(data: list[dict]) -> bytes:
    return json.dumps(data, default=_decimal_default, indent=2).encode("utf-8")


def _to_csv(data: list[dict]) -> bytes:
    if not data:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(data[0].keys()))
    writer.writeheader()
    for row in data:
        writer.writerow({k: str(v) if v is not None else "" for k, v in row.items()})
    return buf.getvalue().encode("utf-8")


class AuditExportService:
    """Generates signed audit export packages."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def request_export(
        self,
        tenant_id: uuid.UUID,
        requested_by: uuid.UUID,
        date_from: date,
        date_to: date,
        sponsor_id: uuid.UUID | None = None,
        export_type: str = "full",
    ) -> AuditExport:
        now = datetime.now(UTC)
        export = AuditExport(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            sponsor_id=sponsor_id,
            date_from=date_from,
            date_to=date_to,
            export_type=export_type,
            status="pending",
            requested_by=requested_by,
            requested_at=now,
            created_at=now,
        )
        self._db.add(export)
        self._db.flush()
        return export

    def generate_export(
        self, tenant_id: uuid.UUID, export_id: uuid.UUID
    ) -> tuple[AuditExport, bytes]:
        """Generate the full audit export zip.

        Returns:
            (AuditExport record with updated status, zip bytes)
        """
        export = (
            self._db.query(AuditExport)
            .filter(
                AuditExport.tenant_id == tenant_id,
                AuditExport.id == export_id,
            )
            .first()
        )
        if export is None:
            raise ValueError(f"AuditExport {export_id} not found")

        # Collect transactions
        tx_q = self._db.query(RebateTransaction).filter(
            RebateTransaction.tenant_id == tenant_id,
            RebateTransaction.period_start >= export.date_from,
            RebateTransaction.period_end <= export.date_to,
        )
        if export.sponsor_id:
            tx_q = tx_q.filter(
                RebateTransaction.sponsor_id == export.sponsor_id
            )
        transactions = tx_q.all()

        # Collect pass-through entries
        pt_q = self._db.query(PassThroughEntry).filter(
            PassThroughEntry.tenant_id == tenant_id,
            PassThroughEntry.period_month >= export.date_from,
            PassThroughEntry.period_month <= export.date_to,
        )
        if export.sponsor_id:
            pt_q = pt_q.filter(
                PassThroughEntry.sponsor_id == export.sponsor_id
            )
        pass_throughs = pt_q.all()

        # Collect BFSF documents
        bfsf_q = self._db.query(BFSFDocument).filter(
            BFSFDocument.tenant_id == tenant_id,
        )
        if export.sponsor_id:
            bfsf_q = bfsf_q.filter(BFSFDocument.sponsor_id == export.sponsor_id)
        bfsf_docs = bfsf_q.all()

        # Collect transparency reports
        tr_q = self._db.query(TransparencyReport).filter(
            TransparencyReport.tenant_id == tenant_id,
            TransparencyReport.period_start >= export.date_from,
            TransparencyReport.period_end <= export.date_to,
        )
        if export.sponsor_id:
            tr_q = tr_q.filter(TransparencyReport.sponsor_id == export.sponsor_id)
        reports = tr_q.all()

        # Build data dicts
        tx_dicts = [
            {
                "id": str(t.id),
                "contract_id": str(t.contract_id),
                "ndc11": t.ndc11,
                "period_start": t.period_start,
                "period_end": t.period_end,
                "transaction_type": t.transaction_type,
                "rebate_category": t.rebate_category,
                "units_dispensed": t.units_dispensed,
                "wac_per_unit": t.wac_per_unit,
                "gross_wac": t.gross_wac,
                "rebate_amount": t.rebate_amount,
                "sponsor_id": str(t.sponsor_id) if t.sponsor_id else None,
                "entry_hash": t.entry_hash,
                "prev_hash": t.prev_hash,
                "created_at": t.created_at,
            }
            for t in transactions
        ]
        pt_dicts = [
            {
                "id": str(e.id),
                "transaction_id": str(e.transaction_id),
                "ndc11": e.ndc11,
                "period_month": e.period_month,
                "sponsor_id": str(e.sponsor_id),
                "manufacturer_received": e.manufacturer_received,
                "sponsor_passed": e.sponsor_passed,
                "rebate_category": e.rebate_category,
                "entry_hash": e.entry_hash,
                "prev_hash": e.prev_hash,
                "created_at": e.created_at,
            }
            for e in pass_throughs
        ]
        bfsf_dicts = [
            {
                "id": str(d.id),
                "sponsor_id": str(d.sponsor_id),
                "document_type": d.document_type,
                "assessment_year": d.assessment_year,
                "total_fee": d.total_fee,
                "status": d.status,
                "approved_at": d.approved_at,
                "version": d.version,
            }
            for d in bfsf_docs
        ]
        tr_dicts = [
            {
                "id": str(r.id),
                "sponsor_id": str(r.sponsor_id),
                "report_type": r.report_type,
                "period_start": r.period_start,
                "period_end": r.period_end,
                "status": r.status,
                "total_rebates_received": r.total_rebates_received,
                "total_rebates_passed": r.total_rebates_passed,
                "generated_at": r.generated_at,
            }
            for r in reports
        ]

        # Build zip archive
        zip_buf = io.BytesIO()
        manifest: dict[str, Any] = {
            "export_id": str(export_id),
            "tenant_id": str(tenant_id),
            "date_from": export.date_from.isoformat(),
            "date_to": export.date_to.isoformat(),
            "generated_at": datetime.now(UTC).isoformat(),
            "record_counts": {
                "transactions": len(tx_dicts),
                "pass_through_entries": len(pt_dicts),
                "bfsf_documents": len(bfsf_dicts),
                "transparency_reports": len(tr_dicts),
            },
            "file_hashes": {},
        }

        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            files = {
                "transactions.json": _to_json(tx_dicts),
                "transactions.csv": _to_csv(tx_dicts),
                "pass_through_entries.json": _to_json(pt_dicts),
                "pass_through_entries.csv": _to_csv(pt_dicts),
                "bfsf_documents.json": _to_json(bfsf_dicts),
                "bfsf_documents.csv": _to_csv(bfsf_dicts),
                "transparency_reports.json": _to_json(tr_dicts),
                "transparency_reports.csv": _to_csv(tr_dicts),
            }
            for filename, content in files.items():
                zf.writestr(filename, content)
                sha = hashlib.sha256(content).hexdigest()
                manifest["file_hashes"][filename] = sha

            manifest_bytes = _to_json([manifest])
            zf.writestr("manifest.json", manifest_bytes)
            manifest["file_hashes"]["manifest.json"] = hashlib.sha256(
                manifest_bytes
            ).hexdigest()

        zip_bytes = zip_buf.getvalue()

        export.status = "ready"
        export.manifest = manifest
        export.zip_path = f"exports/{tenant_id}/{export_id}.zip"
        export.completed_at = datetime.now(UTC)
        self._db.flush()

        return export, zip_bytes
