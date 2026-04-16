"""Tests for BRD template engine — validate schemas, submissions, and diff."""

from __future__ import annotations

import uuid
from datetime import datetime, UTC

import pytest

from src.services.brd_engine import (
    build_default_template_schema,
    validate_brd_submission,
    compute_brd_diff,
    compute_brd_signature_hash,
    PROGRAM_TYPE_SLUGS,
)


class TestDefaultTemplateSchemas:
    def test_all_program_types_have_templates(self):
        for slug in PROGRAM_TYPE_SLUGS:
            schema = build_default_template_schema(slug)
            assert "sections" in schema
            assert len(schema["sections"]) > 0

    def test_copay_template_has_sections(self):
        schema = build_default_template_schema("copay")
        assert len(schema["sections"]) >= 1
        # Sections have ids
        for s in schema["sections"]:
            assert "id" in s

    def test_unknown_program_type_raises(self):
        with pytest.raises(ValueError, match="Unknown program_type"):
            build_default_template_schema("unknown_type_xyz")


class TestBRDSubmissionValidation:
    def test_valid_submission_no_errors(self):
        schema = build_default_template_schema("copay")
        # Build a valid submission with all required fields by section id
        data: dict = {}
        for section in schema["sections"]:
            section_data: dict = {}
            for field in section.get("fields", []):
                if field.get("required", False):
                    ftype = field["type"]
                    fid = field["id"]
                    validation = field.get("validation", {})
                    if ftype == "text_list":
                        section_data[fid] = ["12345678901"]
                    elif ftype == "money":
                        section_data[fid] = "10.00"
                    elif "email" in fid:
                        section_data[fid] = "test@example.com"
                    elif ftype == "text":
                        section_data[fid] = "Test Value"
                    elif ftype == "number":
                        section_data[fid] = "100"
                    elif ftype == "date":
                        section_data[fid] = "2026-01-01"
                    elif ftype == "dropdown":
                        opts = validation.get("options", field.get("options", ["default"]))
                        section_data[fid] = opts[0] if opts else "default"
                    elif ftype == "checkbox":
                        section_data[fid] = True
                    else:
                        section_data[fid] = "test"
            data[section["id"]] = section_data

        result = validate_brd_submission(schema, data)
        assert result["valid"] is True, f"Errors: {result.get('errors', {})}"
        assert len(result.get("errors", {})) == 0

    def test_missing_required_field_fails(self):
        schema = build_default_template_schema("copay")
        result = validate_brd_submission(schema, {})
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_duplicate_ndcs_produce_warning(self):
        schema = build_default_template_schema("copay")
        data = {"drug_list": {"ndcs": ["12345678901", "12345678901", "98765432109"]}}
        result = validate_brd_submission(schema, data)
        assert "ndcs" in result.get("warnings", {})


class TestBRDSignatureHash:
    def test_deterministic(self):
        sid = uuid.uuid4()
        signer = uuid.uuid4()
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        data = {"section": {"field": "value"}}
        h1 = compute_brd_signature_hash(sid, data, signer, ts)
        h2 = compute_brd_signature_hash(sid, data, signer, ts)
        assert h1 == h2
        assert len(h1) == 64

    def test_different_data_different_hash(self):
        sid = uuid.uuid4()
        signer = uuid.uuid4()
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        h1 = compute_brd_signature_hash(sid, {"a": "1"}, signer, ts)
        h2 = compute_brd_signature_hash(sid, {"a": "2"}, signer, ts)
        assert h1 != h2

    def test_different_signer_different_hash(self):
        sid = uuid.uuid4()
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        data = {"a": "1"}
        h1 = compute_brd_signature_hash(sid, data, uuid.uuid4(), ts)
        h2 = compute_brd_signature_hash(sid, data, uuid.uuid4(), ts)
        assert h1 != h2


class TestBRDDiff:
    def test_diff_detects_drug_additions(self):
        current = {"drug_entries": [], "bin_pcn": {}}
        proposed = {"drug_entries": [{"ndc": "12345678901", "tier": 1}], "bin_pcn": {}}
        diff = compute_brd_diff(current, proposed)
        assert "drugs" in diff["added"]
        assert len(diff["added"]["drugs"]) == 1

    def test_diff_detects_drug_removals(self):
        current = {"drug_entries": [{"ndc": "12345678901", "tier": 1}], "bin_pcn": {}}
        proposed = {"drug_entries": [], "bin_pcn": {}}
        diff = compute_brd_diff(current, proposed)
        assert "drugs" in diff["removed"]

    def test_diff_no_changes(self):
        config = {"drug_entries": [{"ndc": "12345678901", "tier": 1}], "bin_pcn": {"bin": "610341"}}
        diff = compute_brd_diff(config, config)
        assert diff["added"] == {}
        assert diff["modified"] == {}
        assert diff["removed"] == {}

    def test_diff_detects_bin_pcn_change(self):
        current = {"drug_entries": [], "bin_pcn": {"bin": "610341", "pcn": "OLD"}}
        proposed = {"drug_entries": [], "bin_pcn": {"bin": "610341", "pcn": "NEW"}}
        diff = compute_brd_diff(current, proposed)
        assert "bin_pcn" in diff["modified"]

    def test_diff_detects_drug_modification(self):
        current = {"drug_entries": [{"ndc": "12345678901", "tier": 1}], "bin_pcn": {}}
        proposed = {"drug_entries": [{"ndc": "12345678901", "tier": 3}], "bin_pcn": {}}
        diff = compute_brd_diff(current, proposed)
        assert "drugs" in diff["modified"]
