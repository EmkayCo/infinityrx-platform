"""Decorator metadata tests."""

from __future__ import annotations

from src.audit import phi_access
from src.audit.decorators import auditable


def test_auditable_attaches_metadata():
    @auditable(action="approve", entity_type="batch", entity_id_param="batch_id")
    def handler(batch_id: str):
        return {"batch_id": batch_id}

    meta = handler.__audit__
    assert meta["action"] == "approve"
    assert meta["entity_type"] == "batch"
    assert meta["entity_id_param"] == "batch_id"
    assert meta["capture_before"] is None


def test_phi_access_attaches_field_list():
    @phi_access(fields=["first_name", "ssn"])
    def handler():
        return {}

    assert handler.__phi_access__ == ["first_name", "ssn"]


def test_auditable_with_capture_before():
    def _capture(req):
        return {"state": "before"}

    @auditable(action="update", capture_before=_capture)
    def handler():
        return {}

    assert handler.__audit__["capture_before"] is _capture
