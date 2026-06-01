"""Reference-data-backed detection rules: ALL-002, ALL-003.

FDW REFERENCE SCHEMA: This module reads from the postgres_fdw reference foreign-table
schema (provisioned by infrastructure/scripts/setup_fdw.sh). No module-owned grants needed.
Tables used: reference.dataq_master, reference.oig_leie_exclusions, reference.sam_exclusions,
reference.prescribers.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from sqlalchemy import select as sa_select
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.detection.batch_engine import _make_anomaly  # noqa: F401
from src.models.detection_run_models import (
    Anomaly,
    CsvUploadRow,
    DetectionRun,
    DetectionRuleInstance,
)

_NPI_RE = re.compile(r"^\d{10}$")


def _is_valid_npi(value: Any) -> bool:
    if value is None:
        return False
    return bool(_NPI_RE.fullmatch(str(value)))


def _stub_instance() -> DetectionRuleInstance:
    inst = DetectionRuleInstance.__new__(DetectionRuleInstance)
    inst.id = None
    inst.parameters = {}
    return inst


def _json_extract(db, col: str, field: str) -> str:
    """Dialect-aware JSON extraction: Postgres row_data->>'field', SQLite json_extract."""
    if db.get_bind().dialect.name == 'postgresql':
        return f"{col}->>'" + field + "'"
    return f"json_extract({col}, '$." + field + "')"


def evaluate_all002_phantom_pharmacy(
    db: Session,
    run: DetectionRun,
    instance: DetectionRuleInstance | None = None,
) -> tuple[list[Anomaly], dict]:
    """ALL-002: Phantom/Excluded Pharmacy."""
    anomalies: list[Anomaly] = []
    _dq: dict[str, int] = {"missing_pharmacy_npi": 0, "invalid_pharmacy_npi": 0}
    _inst = instance or _stub_instance()
    _inst.rule_type_code = "ALL-002"

    missing_count_row = db.execute(
        text("""
            SELECT COUNT(*) AS cnt
            FROM reclaimrx.csv_upload_rows
            WHERE detection_run_id = :run_id
              AND tenant_id = :tenant_id
              AND (resolved_pharmacy_npi IS NULL OR resolved_pharmacy_npi = '')
        """),
        {"run_id": str(run.id), "tenant_id": str(run.tenant_id)},
    ).fetchone()
    _dq["missing_pharmacy_npi"] = int(missing_count_row.cnt or 0) if missing_count_row else 0

    npi_candidate_rows = db.execute(
        text("""
            SELECT resolved_pharmacy_npi AS npi
            FROM reclaimrx.csv_upload_rows
            WHERE detection_run_id = :run_id
              AND tenant_id = :tenant_id
              AND resolved_pharmacy_npi IS NOT NULL
              AND resolved_pharmacy_npi != '' 
        """),
        {"run_id": str(run.id), "tenant_id": str(run.tenant_id)},
    ).fetchall()
    all_candidate_npis = [r.npi for r in npi_candidate_rows if r.npi]

    _dq["invalid_pharmacy_npi"] = len([v for v in all_candidate_npis if not _is_valid_npi(v)])
    valid_npis = list({v for v in all_candidate_npis if _is_valid_npi(v)})

    if not valid_npis:
        return anomalies, _dq

    # Step 2: ONE CTE lookup vs dataq_master + oig/sam. nl.npi = claim-side key.
    ph = ", ".join([f":npi_{i}" for i in range(len(valid_npis))])
    np_ = {f"npi_{i}": npi for i, npi in enumerate(valid_npis)}
    ref_sql = text(
        f"WITH npi_list AS (SELECT unnest(ARRAY[{ph}]::text[]) AS npi),"
        f" dataq AS ("
        f"   SELECT nl.npi AS npi, dm.npi AS dm_npi, dm.deactivation_code, dm.legal_business_name"
        f"   FROM npi_list nl LEFT JOIN reference.dataq_master dm ON dm.npi = nl.npi"
        f"), excl AS ("
        f"   SELECT nl.npi, oig.excldate AS oig_excldate, sam.active_date AS sam_active_date"
        f"   FROM npi_list nl"
        f"   LEFT JOIN reference.oig_leie_exclusions oig ON oig.npi = nl.npi"
        f"   LEFT JOIN reference.sam_exclusions sam ON sam.npi = nl.npi"
        f")"
        f" SELECT d.npi, d.deactivation_code, d.legal_business_name,"
        f"        e.oig_excldate, e.sam_active_date, (d.dm_npi IS NULL) AS is_phantom"
        f" FROM dataq d JOIN excl e ON e.npi = d.npi"
    )
    ref_rows = db.execute(ref_sql, np_).fetchall()
    ref_by_npi = {r.npi: r for r in ref_rows}
    flagged = {}
    for npi, ref in ref_by_npi.items():
        if ref.is_phantom:
            flagged[npi] = ("phantom_not_in_dataq_master",
                            {"table": "reference.dataq_master", "npi": npi},
                            ref.legal_business_name)
        elif ref.deactivation_code:
            flagged[npi] = ("deactivated",
                            {"table": "reference.dataq_master",
                             "deactivation_code": ref.deactivation_code},
                            ref.legal_business_name)
        elif ref.oig_excldate:
            flagged[npi] = ("oig_excluded",
                            {"table": "reference.oig_leie_exclusions",
                             "exclusion_date": str(ref.oig_excldate)},
                            ref.legal_business_name)
        elif ref.sam_active_date:
            flagged[npi] = ("sam_excluded",
                            {"table": "reference.sam_exclusions",
                             "active_date": str(ref.sam_active_date)},
                            ref.legal_business_name)
    if not flagged:
        return anomalies, _dq
    fl = list(flagged.keys())
    fp = ", ".join([f":fp_{i}" for i in range(len(fl))])
    fpp = {f"fp_{i}": n for i, n in enumerate(fl)}
    reps = db.execute(
        text(
            f"SELECT DISTINCT ON (resolved_pharmacy_npi) id, resolved_pharmacy_npi"
            f" FROM reclaimrx.csv_upload_rows"
            f" WHERE detection_run_id = :run_id AND tenant_id = :tenant_id"
            f" AND resolved_pharmacy_npi IN ({fp})"
            f" ORDER BY resolved_pharmacy_npi, id"
        ),
        {"run_id": str(run.id), "tenant_id": str(run.tenant_id), **fpp},
    ).fetchall()
    rid_by_npi = {r.resolved_pharmacy_npi: r.id for r in reps}
    orm_rows = {}
    if rid_by_npi:
        for r in db.execute(
            sa_select(CsvUploadRow).where(CsvUploadRow.id.in_(list(rid_by_npi.values())))
        ).scalars().all():
            orm_rows[r.resolved_pharmacy_npi] = r
    for npi, (reason, provenance, entity_name) in flagged.items():
        csv_row = orm_rows.get(npi)
        if csv_row is None:
            continue
        anomalies.append(_make_anomaly(
            run=run, instance=_inst, csv_row=csv_row,
            finding_code="ALL-002",
            finding_summary=f"Phantom/excluded pharmacy NPI {npi}: {reason}",
            finding_details={"pharmacy_npi": npi, "reason": reason,
                             "provenance": provenance, "entity_name": entity_name},
            severity="critical", confidence_num=Decimal("0.90"),
        ))
    return anomalies, _dq


def evaluate_all003_phantom_prescriber(
    db: Session,
    run: DetectionRun,
    instance: DetectionRuleInstance | None = None,
) -> tuple[list[Anomaly], dict]:
    """ALL-003: Phantom/Excluded Prescriber. Set-based, at most 4 queries."""
    anomalies: list[Anomaly] = []
    _dq: dict[str, int] = {"missing_prescriber_npi": 0, "invalid_prescriber_npi": 0}
    _inst = instance or _stub_instance()
    _inst.rule_type_code = "ALL-003"
    jf = _json_extract(db, "row_data", "prescriber_npi")
    _miss = db.execute(
        text(
            f"SELECT COUNT(*) AS cnt FROM reclaimrx.csv_upload_rows"
            f" WHERE detection_run_id = :run_id AND tenant_id = :tenant_id"
            f" AND ({jf} IS NULL OR {jf} = '')"
        ),
        {"run_id": str(run.id), "tenant_id": str(run.tenant_id)},
    ).fetchone()
    _dq["missing_prescriber_npi"] = int(_miss.cnt or 0) if _miss else 0
    _cands = db.execute(
        text(
            f"SELECT {jf} AS npi FROM reclaimrx.csv_upload_rows"
            f" WHERE detection_run_id = :run_id AND tenant_id = :tenant_id"
            f" AND {jf} IS NOT NULL AND {jf} != ''"
        ),
        {"run_id": str(run.id), "tenant_id": str(run.tenant_id)},
    ).fetchall()
    all_cands = [r.npi for r in _cands if r.npi]
    _dq["invalid_prescriber_npi"] = sum(1 for v in all_cands if not _is_valid_npi(v))
    valid_npis = list({v for v in all_cands if _is_valid_npi(v)})
    if not valid_npis:
        return anomalies, _dq
    ph = ", ".join([f":npi_{i}" for i in range(len(valid_npis))])
    np_ = {f"npi_{i}": npi for i, npi in enumerate(valid_npis)}
    ref_sql = text(
        f"WITH npi_list AS (SELECT unnest(ARRAY[{ph}]::text[]) AS npi),"
        f" presc AS ("
        f"   SELECT nl.npi AS npi, p.npi AS p_npi, p.status, p.deactivation_date, p.display_name"
        f"   FROM npi_list nl LEFT JOIN reference.prescribers p ON p.npi = nl.npi"
        f"), excl AS ("
        f"   SELECT nl.npi, oig.excldate AS oig_excldate, sam.active_date AS sam_active_date"
        f"   FROM npi_list nl"
        f"   LEFT JOIN reference.oig_leie_exclusions oig ON oig.npi = nl.npi"
        f"   LEFT JOIN reference.sam_exclusions sam ON sam.npi = nl.npi"
        f")"
        f" SELECT pr.npi, pr.status, pr.deactivation_date, pr.display_name,"
        f"        ex.oig_excldate, ex.sam_active_date, (pr.p_npi IS NULL) AS is_phantom"
        f" FROM presc pr JOIN excl ex ON ex.npi = pr.npi"
    )
    ref_rows = db.execute(ref_sql, np_).fetchall()
    flagged_p = {}
    for ref in ref_rows:
        if ref.is_phantom:
            flagged_p[ref.npi] = ("phantom_not_in_prescribers",
                                   {"table": "reference.prescribers", "npi": ref.npi},
                                   ref.display_name)
        elif ref.status == "deactivated" or ref.deactivation_date:
            flagged_p[ref.npi] = ("deactivated",
                                   {"table": "reference.prescribers",
                                    "deactivation_date": str(ref.deactivation_date)},
                                   ref.display_name)
        elif ref.oig_excldate:
            flagged_p[ref.npi] = ("oig_excluded",
                                   {"table": "reference.oig_leie_exclusions",
                                    "exclusion_date": str(ref.oig_excldate)},
                                   ref.display_name)
        elif ref.sam_active_date:
            flagged_p[ref.npi] = ("sam_excluded",
                                   {"table": "reference.sam_exclusions",
                                    "active_date": str(ref.sam_active_date)},
                                   ref.display_name)
    if not flagged_p:
        return anomalies, _dq
    fl = list(flagged_p.keys())
    fp = ", ".join([f":fp_{i}" for i in range(len(fl))])
    fpp = {f"fp_{i}": n for i, n in enumerate(fl)}
    jf2 = _json_extract(db, "row_data", "prescriber_npi")
    reps = db.execute(
        text(
            f"SELECT DISTINCT ON ({jf2}) id, {jf2} AS prescriber_npi"
            f" FROM reclaimrx.csv_upload_rows"
            f" WHERE detection_run_id = :run_id AND tenant_id = :tenant_id"
            f" AND {jf2} IN ({fp})"
            f" ORDER BY {jf2}, id"
        ),
        {"run_id": str(run.id), "tenant_id": str(run.tenant_id), **fpp},
    ).fetchall()
    rid_by_presc = {r.prescriber_npi: r.id for r in reps}
    orm_by_presc = {}
    for r in db.execute(
        sa_select(CsvUploadRow).where(CsvUploadRow.id.in_(list(rid_by_presc.values())))
    ).scalars().all():
        pnpi = str(r.row_data.get("prescriber_npi", "") or "").strip()
        if pnpi:
            orm_by_presc[pnpi] = r
    for npi, (reason, provenance, entity_name) in flagged_p.items():
        csv_row = orm_by_presc.get(npi)
        if csv_row is None:
            continue
        anomalies.append(_make_anomaly(
            run=run, instance=_inst, csv_row=csv_row,
            finding_code="ALL-003",
            finding_summary=f"Phantom/excluded prescriber NPI {npi}: {reason}",
            finding_details={"prescriber_npi": npi, "reason": reason,
                             "provenance": provenance, "entity_name": entity_name},
            severity="critical", confidence_num=Decimal("0.90"),
        ))
    return anomalies, _dq
