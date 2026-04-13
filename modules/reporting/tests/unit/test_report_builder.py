"""Unit tests for the report builder data source registry."""

from __future__ import annotations

from src.services.report_builder import get_all_data_sources, get_available_fields


class TestReportBuilderDataSources:
    def test_claims_fields_available(self) -> None:
        fields = get_available_fields("claims")
        field_names = {f["field"] for f in fields}
        assert "claim_id" in field_names
        assert "amount_paid" in field_names
        assert "fill_date" in field_names

    def test_unknown_source_returns_empty(self) -> None:
        fields = get_available_fields("nonexistent_source")
        assert fields == []

    def test_all_fields_have_field_and_label(self) -> None:
        for source in get_all_data_sources():
            fields = get_available_fields(source)
            for f in fields:
                assert "field" in f
                assert "label" in f

    def test_all_data_sources_available(self) -> None:
        sources = get_all_data_sources()
        expected = {
            "claims",
            "billing_ap",
            "billing_ar",
            "journal",
            "fwa",
            "members",
            "pharmacies",
            "prescribers",
            "programs",
        }
        assert expected.issubset(set(sources))

    def test_phi_fields_marked(self) -> None:
        fields = get_available_fields("claims")
        phi_fields = [f for f in fields if f.get("phi")]
        phi_names = {f["field"] for f in phi_fields}
        assert "member_name" in phi_names
        assert "ndc" in phi_names

    def test_no_float_type_fields(self) -> None:
        """No field should use float — only decimal for monetary."""
        for source in get_all_data_sources():
            for field in get_available_fields(source):
                assert field.get("type") != "float", (
                    f"Source '{source}', field '{field['field']}' uses float type"
                )
