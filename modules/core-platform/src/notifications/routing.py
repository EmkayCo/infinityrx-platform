"""Event-bus → notification routing.

Data-driven mapping: each rule binds an ``event_type`` pattern to a
``notification_type`` plus a recipient selector. Selectors receive the
envelope and return the list of (tenant_id, user_id, email?) tuples to
notify.

The default config below covers the five events demanded by the
deliverables: exclusion.match_found, job.failed, sftp.delivery_failed,
anomaly.detected, batch.failed. Additional rules are trivial to append.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from shared.events import EventBus, EventEnvelope
from shared.events import event_types as et
from src.notifications.service import NotificationService

RecipientSelector = Callable[[EventEnvelope], list["Recipient"]]
ServiceFactory = Callable[[], "ServiceContext"]


@dataclass
class Recipient:
    tenant_id: uuid.UUID
    user_id: uuid.UUID


@dataclass
class ServiceContext:
    """A session + service pair with a commit/close lifecycle."""

    service: NotificationService
    close: Callable[[], None]


@dataclass(frozen=True)
class Rule:
    event_pattern: str
    notification_type: str
    title: str
    message_template: str  # supports ``{field}`` from envelope.payload
    severity: str
    select_recipients: RecipientSelector


DEFAULT_RULES: tuple[Rule, ...] = (
    Rule(
        event_pattern=et.EXCLUSION_MATCH_FOUND,
        notification_type="exclusion_match",
        title="Government exclusion match found",
        message_template="Entity {entity_type} {entity_id} matched an exclusion list.",
        severity="critical",
        select_recipients=lambda env: [],
    ),
    Rule(
        event_pattern=et.JOB_FAILED,
        notification_type="system_health_warning",
        title="Scheduled job failed",
        message_template="Job {job_name} failed: {error}",
        severity="warning",
        select_recipients=lambda env: [],
    ),
    Rule(
        event_pattern=et.SFTP_DELIVERY_FAILED,
        notification_type="sftp_delivery_failed",
        title="SFTP delivery failed",
        message_template="Delivery to {destination} failed: {error}",
        severity="critical",
        select_recipients=lambda env: [],
    ),
    Rule(
        event_pattern=et.ANOMALY_DETECTED,
        notification_type="anomaly_detected",
        title="Anomaly detected",
        message_template="{description}",
        severity="warning",
        select_recipients=lambda env: [],
    ),
    Rule(
        event_pattern=et.BATCH_FAILED,
        notification_type="batch_failed",
        title="Billing batch failed",
        message_template="Batch {batch_id} failed: {reason}",
        severity="critical",
        select_recipients=lambda env: [],
    ),
    # HIPAA 2026 H-07: audit chain integrity violation — CRITICAL severity.
    # entry_id and hash metadata only — audit entry content is never included.
    Rule(
        event_pattern=et.AUDIT_CHAIN_BROKEN,
        notification_type="audit_chain_integrity_violation",
        title="Audit chain integrity violation (HIPAA H-07)",
        message_template="Audit chain broken at entry {entry_id} for tenant {tenant_id}. Immediate investigation required.",
        severity="critical",
        select_recipients=lambda env: [],
    ),
)


def _render(template: str, payload: dict) -> str:
    try:
        return template.format(**payload)
    except (KeyError, IndexError):
        return template


async def register_event_routing(
    bus: EventBus,
    *,
    service_factory: ServiceFactory,
    recipient_selector: RecipientSelector,
    rules: tuple[Rule, ...] = DEFAULT_RULES,
) -> None:
    """Subscribe the notification dispatcher to the event bus.

    ``recipient_selector`` overrides each rule's default empty selector
    so the caller supplies the real "who gets alerted" logic (typically:
    all tenant_admins for the envelope's tenant).
    """

    for rule in rules:
        async def handler(env: EventEnvelope, rule: Rule = rule) -> None:
            recipients = recipient_selector(env)
            if not recipients:
                return
            ctx = service_factory()
            try:
                message = _render(rule.message_template, env.payload)
                for r in recipients:
                    await ctx.service.create(
                        tenant_id=r.tenant_id,
                        user_id=r.user_id,
                        notification_type=rule.notification_type,
                        title=rule.title,
                        message=message,
                        severity=rule.severity,
                    )
            finally:
                ctx.close()

        await bus.subscribe(rule.event_pattern, handler)


__all__ = [
    "DEFAULT_RULES",
    "Recipient",
    "Rule",
    "ServiceContext",
    "register_event_routing",
]
