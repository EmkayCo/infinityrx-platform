"""Unit tests for event consumers."""
from __future__ import annotations

import pytest

from src.events.consumers import (
    dispatch,
    handle_fwa_hold_placed,
    handle_fwa_hold_released,
    handle_payment_batch_submitted,
    register_handler,
)


class TestDispatch:
    def test_dispatch_unknown_topic_is_noop(self):
        dispatch("nonexistent.topic", {"key": "value"})

    def test_dispatch_calls_registered_handler(self):
        called = []

        def handler(payload):
            called.append(payload)

        register_handler("test.topic.dispatch", handler)
        dispatch("test.topic.dispatch", {"data": 1})
        assert len(called) == 1
        assert called[0] == {"data": 1}

    def test_dispatch_handler_exception_propagates(self):
        def bad_handler(payload):
            raise RuntimeError("handler error")

        register_handler("test.topic.bad", bad_handler)
        with pytest.raises(RuntimeError, match="handler error"):
            dispatch("test.topic.bad", {})


class TestHandlers:
    def test_handle_payment_batch_submitted_logs(self):
        handle_payment_batch_submitted({"batch_id": "BATCH-001", "tenant_id": "TENANT-001"})

    def test_handle_fwa_hold_placed_logs(self):
        handle_fwa_hold_placed({"entity_id": "ENT-001", "tenant_id": "T-001", "reason": "fraud"})

    def test_handle_fwa_hold_released_logs(self):
        handle_fwa_hold_released({"entity_id": "ENT-001", "tenant_id": "T-001"})
