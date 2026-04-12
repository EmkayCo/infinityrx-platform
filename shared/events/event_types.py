"""Pre-built event type constants (PRD 4.2).

Every event_type string used by the platform is declared here so that
producers and consumers share a single source of truth.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------
CLAIM_SUBMITTED = "claim.submitted"
CLAIM_ADJUDICATED = "claim.adjudicated"
CLAIM_REVERSED = "claim.reversed"
CLAIM_REPROCESSED = "claim.reprocessed"

# ---------------------------------------------------------------------------
# Billing / Batches / Payments
# ---------------------------------------------------------------------------
BATCH_CREATED = "batch.created"
BATCH_RELEASED = "batch.released"
BATCH_FAILED = "batch.failed"

PAYMENT_GENERATED = "payment.generated"
PAYMENT_SETTLED = "payment.settled"
PAYMENT_RETURNED = "payment.returned"
PAYMENT_FAILED = "payment.failed"

INVOICE_GENERATED = "invoice.generated"

# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------
MEMBER_ENROLLED = "member.enrolled"
MEMBER_TERMINATED = "member.terminated"
MEMBER_ELIGIBILITY_CHANGED = "member.eligibility_changed"

# ---------------------------------------------------------------------------
# FWA
# ---------------------------------------------------------------------------
ANOMALY_DETECTED = "anomaly.detected"
RECOVERY_ESTIMATED = "recovery.estimated"
AUDIT_INITIATED = "audit.initiated"
AUDIT_WRITE_FAILED = "audit.write_failed"

# ---------------------------------------------------------------------------
# Exclusions
# ---------------------------------------------------------------------------
EXCLUSION_MATCH_FOUND = "exclusion.match_found"

# ---------------------------------------------------------------------------
# Jobs / Infrastructure
# ---------------------------------------------------------------------------
JOB_COMPLETED = "job.completed"
JOB_FAILED = "job.failed"
SFTP_DELIVERY_FAILED = "sftp.delivery_failed"

# ---------------------------------------------------------------------------
# Notifications (emitted by the notification service itself)
# ---------------------------------------------------------------------------
NOTIFICATION_CREATED = "notification.created"

ALL_EVENT_TYPES: tuple[str, ...] = (
    CLAIM_SUBMITTED,
    CLAIM_ADJUDICATED,
    CLAIM_REVERSED,
    CLAIM_REPROCESSED,
    BATCH_CREATED,
    BATCH_RELEASED,
    BATCH_FAILED,
    PAYMENT_GENERATED,
    PAYMENT_SETTLED,
    PAYMENT_RETURNED,
    PAYMENT_FAILED,
    INVOICE_GENERATED,
    MEMBER_ENROLLED,
    MEMBER_TERMINATED,
    MEMBER_ELIGIBILITY_CHANGED,
    ANOMALY_DETECTED,
    RECOVERY_ESTIMATED,
    AUDIT_INITIATED,
    AUDIT_WRITE_FAILED,
    EXCLUSION_MATCH_FOUND,
    JOB_COMPLETED,
    JOB_FAILED,
    SFTP_DELIVERY_FAILED,
    NOTIFICATION_CREATED,
)
