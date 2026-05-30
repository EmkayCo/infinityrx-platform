"""Tests for CSV row entity resolution in detection.csv_ingest.

TDD: tests written first (RED) before implementation exists.
"""
from __future__ import annotations


def test_resolve_row_declared_and_unmapped():
    from src.detection.csv_ingest import resolve_row

    # declared: pharmacy_npi is present and non-empty
    ok = resolve_row({"pharmacy_npi": "1497848832", "ndc": "71403000330", "client_id": "32"})
    assert ok.resolved_pharmacy_npi == "1497848832"
    assert ok.resolved_ndc == "71403000330"
    assert ok.resolved_client_id is None          # UUID col, no source->UUID map in v1
    assert ok.resolution_method == "declared"

    # unmapped: pharmacy_npi is empty
    bad = resolve_row({"pharmacy_npi": "", "ndc": "", "client_id": "32"})
    assert bad.resolution_method == "unmapped"


def test_resolve_row_ndc_stripped():
    """NDC value is stripped of surrounding whitespace."""
    from src.detection.csv_ingest import resolve_row

    row = resolve_row({"pharmacy_npi": "1234567890", "ndc": "  00069000105  "})
    assert row.resolved_ndc == "00069000105"
    assert row.resolution_method == "declared"


def test_resolve_row_missing_ndc_is_none():
    """Missing ndc key resolves to None resolved_ndc."""
    from src.detection.csv_ingest import resolve_row

    row = resolve_row({"pharmacy_npi": "1234567890"})
    assert row.resolved_ndc is None
    assert row.resolution_method == "declared"


def test_resolve_row_empty_ndc_is_none():
    """Empty-string ndc resolves to None resolved_ndc."""
    from src.detection.csv_ingest import resolve_row

    row = resolve_row({"pharmacy_npi": "1234567890", "ndc": ""})
    assert row.resolved_ndc is None


def test_resolve_row_resolved_program_id_always_none():
    """resolved_program_id is always None in v1 (UUID mapping not implemented)."""
    from src.detection.csv_ingest import resolve_row

    row = resolve_row({"pharmacy_npi": "1234567890", "program_id": "999"})
    assert row.resolved_program_id is None


def test_resolve_row_unmapped_has_note():
    """Unmapped rows carry an explanatory resolution_notes string."""
    from src.detection.csv_ingest import resolve_row

    row = resolve_row({"pharmacy_npi": "", "ndc": "12345678901"})
    assert row.resolution_method == "unmapped"
    assert row.resolution_notes is not None
    assert "pharmacy_npi" in row.resolution_notes


def test_resolve_row_whitespace_only_npi_is_unmapped():
    """Whitespace-only pharmacy_npi is treated as empty -> unmapped."""
    from src.detection.csv_ingest import resolve_row

    row = resolve_row({"pharmacy_npi": "   ", "ndc": "12345678901"})
    assert row.resolution_method == "unmapped"
    assert row.resolved_pharmacy_npi is None


def test_resolve_row_method_values_from_allowed_set():
    """resolution_method must be one of the DB CHECK-constraint values."""
    from src.detection.csv_ingest import resolve_row

    allowed = {"declared", "group_id_lookup", "ndc_lookup", "manual", "unmapped"}
    assert resolve_row({"pharmacy_npi": "1234567890"}).resolution_method in allowed
    assert resolve_row({"pharmacy_npi": ""}).resolution_method in allowed
