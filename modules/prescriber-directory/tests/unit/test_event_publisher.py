"""Tests for prescriber-directory event publisher."""
from __future__ import annotations

import uuid

from src.events.publisher import (
    build_dea_expired_event,
    build_excluded_event,
    build_prescriber_created_event,
    build_prescriber_deactivated_event,
    build_prescriber_updated_event,
    build_relationship_updated_event,
)

TENANT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CORRELATION = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
NPI = "1000000012"


def _assert_envelope(evt, event_type: str, action: str):
    if isinstance(evt, dict):
        assert evt["event_type"] == event_type
        assert evt["ordering_key"] == NPI
        assert evt["idempotency_key"] == f"prescriber:{NPI}:{action}"
        assert evt["schema_version"] == "1.0"
        assert evt["source_module"] == "prescriber-directory"
    else:
        assert evt.event_type == event_type
        assert evt.ordering_key == NPI
        assert evt.idempotency_key == f"prescriber:{NPI}:{action}"
        assert evt.schema_version == "1.0"
        assert evt.source_module == "prescriber-directory"


def test_build_prescriber_created_event():
    evt = build_prescriber_created_event(NPI, TENANT, CORRELATION, {"last_name": "DOE"})
    _assert_envelope(evt, "prescriber.created", "created")
    payload = evt["payload"] if isinstance(evt, dict) else evt.payload
    assert payload["npi"] == NPI
    assert payload["last_name"] == "DOE"


def test_build_prescriber_updated_event():
    evt = build_prescriber_updated_event(NPI, TENANT, CORRELATION, {"last_name": "NEWDOE"})
    _assert_envelope(evt, "prescriber.updated", "updated")
    payload = evt["payload"] if isinstance(evt, dict) else evt.payload
    assert payload["npi"] == NPI
    assert "changes" in payload


def test_build_prescriber_deactivated_event():
    evt = build_prescriber_deactivated_event(NPI, TENANT, CORRELATION, "voluntary")
    _assert_envelope(evt, "prescriber.deactivated", "deactivated")
    payload = evt["payload"] if isinstance(evt, dict) else evt.payload
    assert payload["reason"] == "voluntary"


def test_build_dea_expired_event():
    evt = build_dea_expired_event(NPI, TENANT, CORRELATION, "2026-01-15")
    _assert_envelope(evt, "prescriber.dea_expired", "dea_expired")
    payload = evt["payload"] if isinstance(evt, dict) else evt.payload
    assert payload["expiry_date"] == "2026-01-15"


def test_build_excluded_event():
    evt = build_excluded_event(NPI, TENANT, CORRELATION, "OIG")
    _assert_envelope(evt, "prescriber.excluded", "excluded")
    payload = evt["payload"] if isinstance(evt, dict) else evt.payload
    assert payload["exclusion_type"] == "OIG"


def test_build_relationship_updated_event():
    pharmacy_npi = "2000000010"
    period = "2026-03"
    evt = build_relationship_updated_event(NPI, TENANT, CORRELATION, pharmacy_npi, period, 42)
    expected_action = f"relationship_updated:{pharmacy_npi}:{period}"
    if isinstance(evt, dict):
        assert evt["event_type"] == "prescriber.relationship_updated"
        assert evt["ordering_key"] == NPI
        assert evt["idempotency_key"] == f"prescriber:{NPI}:{expected_action}"
        payload = evt["payload"]
    else:
        assert evt.event_type == "prescriber.relationship_updated"
        assert evt.ordering_key == NPI
        assert evt.idempotency_key == f"prescriber:{NPI}:{expected_action}"
        payload = evt.payload
    assert payload["prescriber_npi"] == NPI
    assert payload["pharmacy_npi"] == pharmacy_npi
    assert payload["period_month"] == period
    assert payload["claim_count"] == 42
