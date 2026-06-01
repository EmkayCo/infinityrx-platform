"""Tests for FDB pricing enrichment (WAC type 09, NADAC 24/25, SWP-as-AWP 07).

Skipped on SQLite (no reference tables).
Runs on live Postgres after migration 0010 (FDW reference.* access verified).

PRICING SIGN-OFF (2026-05-31, Mike K):
  WAC  = price_type '09' -- LIVE
  NADAC = price_type '24' or '25' -- LIVE (informational)
  SWP-as-AWP = price_type '07' -- LIVE (sign-off granted; deviation from section 12 H6)
"""
from __future__ import annotations

import os

import pytest

REAL_DB = os.environ.get("RECLAIMRX_DB_URL", "")


class TestFDBPricingEnrichment:
    @pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with FDB grants")
    def test_wac_lookup_returns_decimal_or_none(self):
        """fetch_current_prices_for_ndcs returns Decimal wac or None -- never float."""
        import sqlalchemy as sa
        from decimal import Decimal

        from sqlalchemy.orm import Session

        from src.detection.fdb_pricing import fetch_current_prices_for_ndcs

        engine = sa.create_engine(REAL_DB)
        with engine.connect() as conn:
            db = Session(bind=conn)
            result = fetch_current_prices_for_ndcs(db, ["00000000000"])
            for ndc, prices in result.items():
                wac = prices.get("wac")
                assert wac is None or isinstance(wac, Decimal), (
                    f"wac must be Decimal or None, got {type(wac)}: {wac!r}"
                )

    @pytest.mark.skipif(not REAL_DB, reason="requires live Postgres")
    def test_empty_ndc_list_returns_empty_dict(self):
        """fetch_current_prices_for_ndcs([]) -> {} (zero queries)."""
        import sqlalchemy as sa
        from sqlalchemy.orm import Session

        from src.detection.fdb_pricing import fetch_current_prices_for_ndcs

        engine = sa.create_engine(REAL_DB)
        with engine.connect() as conn:
            db = Session(bind=conn)
            result = fetch_current_prices_for_ndcs(db, [])
            assert result == {}, f"Expected empty dict, got {result!r}"

    @pytest.mark.skipif(not REAL_DB, reason="requires live Postgres")
    def test_no_n_plus_1_for_multiple_ndcs(self):
        """fetch_current_prices_for_ndcs issues exactly ONE SQL query regardless of NDC count."""
        import sqlalchemy as sa
        from sqlalchemy import event
        from sqlalchemy.orm import Session

        from src.detection.fdb_pricing import fetch_current_prices_for_ndcs

        engine = sa.create_engine(REAL_DB)
        with engine.connect() as conn:
            db = Session(bind=conn)
            ndcs = [f"0000000{i:04d}" for i in range(10)]
            query_count = [0]

            @event.listens_for(conn, "before_cursor_execute")
            def _count(c, cursor, stmt, params, ctx, many):
                query_count[0] += 1

            fetch_current_prices_for_ndcs(db, ndcs)
            assert query_count[0] == 1, (
                f"fetch_current_prices_for_ndcs must issue exactly 1 query, issued {query_count[0]}"
            )

    @pytest.mark.skipif(not REAL_DB, reason="requires live Postgres")
    def test_result_dict_has_all_required_keys(self):
        """Each entry in result has wac, swp, nadac, drug_name keys."""
        import sqlalchemy as sa
        from sqlalchemy.orm import Session

        from src.detection.fdb_pricing import fetch_current_prices_for_ndcs

        engine = sa.create_engine(REAL_DB)
        with engine.connect() as conn:
            db = Session(bind=conn)
            result = fetch_current_prices_for_ndcs(db, ["00000000000"])
            for ndc, prices in result.items():
                for key in ("wac", "swp", "nadac", "drug_name"):
                    assert key in prices, (
                        f"Result entry for NDC {ndc!r} missing key {key!r}: {prices!r}"
                    )

    @pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with FDB data")
    def test_wac_none_when_ndc_not_in_fdb(self):
        """An NDC absent from fdb_ndc_price_history returns wac=None (not KeyError, not float)."""
        import sqlalchemy as sa
        from sqlalchemy.orm import Session

        from src.detection.fdb_pricing import fetch_current_prices_for_ndcs

        engine = sa.create_engine(REAL_DB)
        with engine.connect() as conn:
            db = Session(bind=conn)
            # Use all-nines NDC guaranteed absent from FDB history
            result = fetch_current_prices_for_ndcs(db, ["99999999999"])
            # Either key absent (empty dict) or wac=None -- both are acceptable
            if "99999999999" in result:
                assert result["99999999999"].get("wac") is None, (
                    "wac must be None for an absent NDC, not a float or Decimal"
                )
