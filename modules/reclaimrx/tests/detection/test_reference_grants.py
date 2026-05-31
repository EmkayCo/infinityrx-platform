"""Test that ifx_dev_app role can SELECT from the FDW reference.* foreign tables.

Migration 0010 verifies access to the pre-existing postgres_fdw `reference` schema
(provisioned by infrastructure/scripts/setup_fdw.sh). It grants nothing — access is
provided by the FDW user mapping ifx_dev_app -> ifx_ref_reader established at setup time.

These tests confirm that the three core reference tables used by detection rules are
readable via the FDW foreign-table schema `reference`:
  - reference.dataq_master       (82,643 rows; pharmacy registry)
  - reference.prescribers        (9,494,438 rows; prescriber registry)
  - reference.fdb_ndc_price_history (15,637,974 rows; FDB pricing)
"""
import os
import pytest
import sqlalchemy as sa

REAL_DB = os.environ.get("RECLAIMRX_DB_URL", "")


@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with FDW reference schema (ifx_dev_app role)")
def test_fdw_reference_dataq_master_selectable():
    """reference.dataq_master must be selectable by ifx_dev_app (FDW foreign table)."""
    engine = sa.create_engine(REAL_DB)
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT COUNT(*) FROM reference.dataq_master")).fetchone()
    assert row is not None
    assert row[0] >= 0


@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with FDW reference schema (ifx_dev_app role)")
def test_fdw_reference_prescribers_selectable():
    """reference.prescribers must be selectable by ifx_dev_app (FDW foreign table)."""
    engine = sa.create_engine(REAL_DB)
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT COUNT(*) FROM reference.prescribers LIMIT 1")).fetchone()
    assert row is not None


@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with FDW reference schema (ifx_dev_app role)")
def test_fdw_reference_fdb_ndc_price_history_selectable():
    """reference.fdb_ndc_price_history must be selectable by ifx_dev_app (FDW foreign table)."""
    engine = sa.create_engine(REAL_DB)
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT COUNT(*) FROM reference.fdb_ndc_price_history LIMIT 1")).fetchone()
    assert row is not None
