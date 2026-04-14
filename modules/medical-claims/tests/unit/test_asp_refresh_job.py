"""Unit tests for ASP refresh job."""
from __future__ import annotations


import pytest

from src.jobs.asp_refresh_job import AspRefreshJob


class TestAspRefreshJob:
    def test_valid_records_loaded(self, db_session):
        job = AspRefreshJob(db_session)
        records = [
            {"hcpcs_code": "J0135", "asp_per_unit": "12.500000", "effective_date": "2026-01-01"},
            {"hcpcs_code": "J9035", "asp_per_unit": "200.000000", "effective_date": "2026-01-01"},
        ]
        result = job.run("2026-Q1", records)
        assert result["loaded"] == 2
        assert result["skipped"] == 0

    def test_invalid_quarter_raises(self, db_session):
        job = AspRefreshJob(db_session)
        with pytest.raises(ValueError, match="Invalid quarter"):
            job.run("2026-Q5", [])

    def test_missing_asp_per_unit_skipped(self, db_session):
        job = AspRefreshJob(db_session)
        records = [{"hcpcs_code": "J1000"}]  # no asp_per_unit
        result = job.run("2026-Q2", records)
        assert result["skipped"] == 1
        assert result["loaded"] == 0

    def test_missing_hcpcs_code_skipped(self, db_session):
        job = AspRefreshJob(db_session)
        records = [{"asp_per_unit": "50.00"}]  # no hcpcs_code
        result = job.run("2026-Q2", records)
        assert result["skipped"] == 1

    def test_empty_records_returns_zero(self, db_session):
        job = AspRefreshJob(db_session)
        result = job.run("2026-Q3", [])
        assert result["loaded"] == 0
        assert result["skipped"] == 0

    def test_idempotent_reload(self, db_session):
        job = AspRefreshJob(db_session)
        records = [{"hcpcs_code": "J1111", "asp_per_unit": "10.000000", "effective_date": "2026-01-01"}]
        job.run("2026-Q1", records)
        result = job.run("2026-Q1", records)  # second run
        assert result["loaded"] == 1  # upsert, not error
