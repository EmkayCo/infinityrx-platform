"""EDI-compliance event publishers and startup wiring.

EDI-compliance is primarily a publisher module (emits payment.auto_posted,
payment.unmatched_claim). It subscribes to no inbound events currently.

wire_consumers() is a no-op placeholder — included for architectural completeness
and to allow future consumer additions without changing the wiring contract.
"""
from __future__ import annotations

import logging

from shared.events.bus import EventBus

logger = logging.getLogger("edi-compliance.events")

# No consumers in edi-compliance currently — it publishes to billing.
CONSUMER_ROUTING: dict[str, str] = {}


async def wire_consumers(bus: EventBus) -> None:
    """No consumers to wire for edi-compliance (publisher-only module).

    Future consumers (e.g., member.enrolled to refresh eligibility snapshots)
    should be added here.
    """
    logger.info("edi-compliance.consumers_wired", extra={"svc_topics": "none"})
