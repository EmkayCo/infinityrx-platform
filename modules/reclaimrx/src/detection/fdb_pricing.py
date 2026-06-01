"""FDB pricing enrichment: fetch current WAC, NADAC, and SWP-as-AWP for a set of NDCs.

PRICING SIGN-OFF (2026-05-31, Mike K):
  WAC  = price_type '09' -- LIVE
  NADAC = price_type '24' or '25' -- LIVE (informational)
  SWP-as-AWP = price_type '07' -- LIVE (sign-off granted; deviation from section 12 H6 deferred state)

FDW REFERENCE SCHEMA: reads reference.fdb_ndc_price_history, reference.drugs
via the pre-existing postgres_fdw `reference` foreign-table schema
(provisioned by infrastructure/scripts/setup_fdw.sh). No module-owned grants needed.

Set-based: ONE query for all NDCs. Never per-row.
Returns: {ndc_11: {"wac": Decimal|None, "swp": Decimal|None, "nadac": Decimal|None,
                    "drug_name": str|None}}
wac=None when the NDC has no WAC record -- key is always present.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

_PRICE_TYPE_WAC = "09"
_PRICE_TYPE_SWP = "07"
_PRICE_TYPE_NADAC_1 = "24"
_PRICE_TYPE_NADAC_2 = "25"


def fetch_current_prices_for_ndcs(
    db: Session,
    ndc_list: list[str],
) -> dict[str, dict[str, Any]]:
    """Fetch current WAC, NADAC, SWP prices for a list of NDC-11 values.

    Issues exactly ONE SQL query (CTE pivot). Returns empty dict if ndc_list is empty.
    Prices are Decimal or None. Never float.

    Returns an entry for every NDC in ndc_list that appears in fdb_ndc_price_history;
    NDCs with no price records are absent from the result (not present with wac=None).
    NDCs with price records but no WAC entry have wac=None in their entry.
    """
    if not ndc_list:
        return {}

    placeholders = ", ".join([f":ndc_{i}" for i in range(len(ndc_list))])
    ndc_params = {f"ndc_{i}": ndc for i, ndc in enumerate(ndc_list)}

    sql = text(
        f"WITH ndc_set AS ("
        f"    SELECT unnest(ARRAY[{placeholders}]::text[]) AS ndc_11"
        f"),"
        f" latest_prices AS ("
        f"    SELECT"
        f"        ph.ndc_11,"
        f"        ph.price_type,"
        f"        ph.price,"
        f"        ph.effective_date,"
        f"        ROW_NUMBER() OVER ("
        f"            PARTITION BY ph.ndc_11, ph.price_type"
        f"            ORDER BY ph.effective_date DESC"
        f"        ) AS rn"
        f"    FROM reference.fdb_ndc_price_history ph"
        f"    JOIN ndc_set ns ON ns.ndc_11 = ph.ndc_11"
        f"    WHERE ph.price_type IN (:wac, :swp, :nadac1, :nadac2)"
        f"),"
        f" current_prices AS ("
        f"    SELECT ndc_11, price_type, price"
        f"    FROM latest_prices"
        f"    WHERE rn = 1"
        f"),"
        f" drug_names AS ("
        f"    SELECT d.ndc_11, d.proprietary_name"
        f"    FROM reference.drugs d"
        f"    JOIN ndc_set ns ON ns.ndc_11 = d.ndc_11"
        f")"
        f" SELECT"
        f"    ns.ndc_11,"
        f"    MAX(CASE WHEN cp.price_type = :wac   THEN cp.price END) AS wac_price,"
        f"    MAX(CASE WHEN cp.price_type = :swp   THEN cp.price END) AS swp_price,"
        f"    MAX(CASE WHEN cp.price_type IN (:nadac1, :nadac2) THEN cp.price END) AS nadac_price,"
        f"    dn.proprietary_name AS drug_name"
        f" FROM ndc_set ns"
        f" LEFT JOIN current_prices cp ON cp.ndc_11 = ns.ndc_11"
        f" LEFT JOIN drug_names dn ON dn.ndc_11 = ns.ndc_11"
        f" GROUP BY ns.ndc_11, dn.proprietary_name"
    )

    params = {
        **ndc_params,
        "wac": _PRICE_TYPE_WAC,
        "swp": _PRICE_TYPE_SWP,
        "nadac1": _PRICE_TYPE_NADAC_1,
        "nadac2": _PRICE_TYPE_NADAC_2,
    }

    rows = db.execute(sql, params).fetchall()
    result: dict[str, dict[str, Any]] = {}
    for r in rows:
        def _to_decimal(v: Any) -> Decimal | None:
            if v is None:
                return None
            return Decimal(str(v)).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)

        result[r.ndc_11] = {
            "wac": _to_decimal(r.wac_price),
            "swp": _to_decimal(r.swp_price),
            "nadac": _to_decimal(r.nadac_price),
            "drug_name": r.drug_name,
        }
    return result