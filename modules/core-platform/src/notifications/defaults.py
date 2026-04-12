"""The 19 pre-built notification types (PRD section 2.4 & 10).

Each type ships with sensible defaults:
    - severity: info / warning / critical
    - default_email_enabled: critical/warning → True, info → False
    - default_in_app_enabled: True (in-app is always on by default)
    - default_sms_enabled: False (SMS wiring is tracked in tasks/todo.md)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationType:
    key: str
    severity: str  # info | warning | critical
    default_email_enabled: bool
    default_in_app_enabled: bool = True
    default_sms_enabled: bool = False


DEFAULT_NOTIFICATION_TYPES: tuple[NotificationType, ...] = (
    NotificationType("batch_released", "info", default_email_enabled=False),
    NotificationType("batch_failed", "critical", default_email_enabled=True),
    NotificationType("payment_settled", "info", default_email_enabled=False),
    NotificationType("payment_failed", "critical", default_email_enabled=True),
    NotificationType("prefund_low", "warning", default_email_enabled=True),
    NotificationType("prefund_critical", "critical", default_email_enabled=True),
    NotificationType("exclusion_match", "critical", default_email_enabled=True),
    NotificationType("anomaly_detected", "warning", default_email_enabled=True),
    NotificationType("pa_decision", "info", default_email_enabled=False),
    NotificationType("cycle_reminder", "info", default_email_enabled=False),
    NotificationType("gate_review_complete", "info", default_email_enabled=False),
    NotificationType("gate_review_failed", "critical", default_email_enabled=True),
    NotificationType("member_enrolled", "info", default_email_enabled=False),
    NotificationType("member_terminated", "info", default_email_enabled=False),
    NotificationType("audit_initiated", "warning", default_email_enabled=True),
    NotificationType("dispute_submitted", "warning", default_email_enabled=True),
    NotificationType("report_ready", "info", default_email_enabled=False),
    NotificationType("sftp_delivery_failed", "critical", default_email_enabled=True),
    NotificationType("system_health_warning", "warning", default_email_enabled=True),
)


DEFAULT_TYPE_MAP: dict[str, NotificationType] = {t.key: t for t in DEFAULT_NOTIFICATION_TYPES}

# Guardrail: the PRD mandates exactly 19 default notification types.
assert len(DEFAULT_NOTIFICATION_TYPES) == 19
