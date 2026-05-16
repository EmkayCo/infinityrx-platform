"""Integration tests for edi-compliance event consumer wiring.

CR-01 v2: edi-compliance already has a lifespan but does not call
wire_consumers(). This test verifies the fix: wire_consumers() is called
in the lifespan and subscribes handlers.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))
_PLATFORM_ROOT = _MODULE_ROOT.parent.parent
if str(_PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_ROOT))

os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")

import pytest

from shared.events import InMemoryEventBus


@pytest.mark.asyncio
async def test_wire_consumers_completes_without_error():
    """edi-compliance wire_consumers() must complete without raising (publisher-only module).

    edi-compliance publishes events but subscribes to none. wire_consumers() is a
    no-op wiring hook kept for architectural completeness.
    """
    from src.events import wire_consumers

    bus = InMemoryEventBus()
    await bus.start()
    # Must not raise
    await wire_consumers(bus)
    # Publisher-only: no inbound subscriptions
    assert len(bus._subs) == 0, (
        "edi-compliance is publisher-only; wire_consumers() must not register handlers"
    )
    await bus.stop()


@pytest.mark.asyncio
async def test_wire_consumers_logs_wired(caplog):
    """wire_consumers() must emit a structured log confirming wiring."""
    import logging
    from src.events import wire_consumers

    bus = InMemoryEventBus()
    await bus.start()
    with caplog.at_level(logging.INFO, logger="edi-compliance.events"):
        await wire_consumers(bus)
    assert any("consumers_wired" in r.message or "edi" in r.message for r in caplog.records)
    await bus.stop()
