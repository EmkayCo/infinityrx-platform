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
drug_name is always None (see implementation note below).
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

    drug_name is always None in the returned dict.  Fetching it requires a second
    FDW round-trip (reference.drugs) that the detection engine never uses; the key
    is kept in the result for API contract stability.
    """
    if not ndc_list:
        return {}

    # Use ph.ndc_11 = ANY(:ndc_array) instead of a JOIN on unnest() so that
    # postgres_fdw pushes the predicate to the remote server.
    # With the old unnest-JOIN pattern the planner cannot push the join
    # condition across the FDW boundary; it fetches the entire remote table
    # (15M+ rows) then filters locally -- 14s for 5 NDCs on a 15M-row table.
    # With = ANY(:ndc_array) the predicate is sent to the remote server and
    # only the matching price rows cross the wire -- ~500ms for 990 NDCs.
    #
    # drug_name is dropped from this query: fetching it requires a second FDW
    # round-trip (reference.drugs) that the detection engine never uses (the
    # _fdb_cache in batch_engine only reads "wac").  The key is kept in the
    # result dict as None for API contract stability.
    sql = text(
        "WITH latest_prices AS ("
        "    SELECT"
        "        ph.ndc_11,"
        "        ph.price_type,"
        "        ph.price,"
        "        ROW_NUMBER() OVER ("
        "            PARTITION BY ph.ndc_11, ph.price_type"
        "            ORDER BY ph.effective_date DESC"
        "        ) AS rn"
        "    FROM reference.fdb_ndc_price_history ph"
        "    WHERE ph.ndc_11 = ANY(:ndc_array)"
        "      AND ph.price_type = ANY(ARRAY[:wac, :swp, :nadac1, :nadac2]::text[])"
        "),"
        " current_prices AS ("
        "    SELECT ndc_11, price_type, price"
        "    FROM latest_prices"
        "    WHERE rn = 1"
        "),"
        " ndc_set AS ("
        "    SELECT unnest(:ndc_array) AS ndc_11"
        ")"
        " SELECT"
        "    ns.ndc_11,"
        "    MAX(CASE WHEN cp.price_type = :wac   THEN cp.price END) AS wac_price,"
        "    MAX(CASE WHEN cp.price_type = :swp   THEN cp.price END) AS swp_price,"
        "    MAX(CASE WHEN cp.price_type IN (:nadac1, :nadac2) THEN cp.price END) AS nadac_price,"
        "    NULL::text AS drug_name"
        " FROM ndc_set ns"
        " LEFT JOIN current_prices cp ON cp.ndc_11 = ns.ndc_11"
        " GROUP BY ns.ndc_11"
    )

    params = {
        "ndc_array": ndc_list,
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
