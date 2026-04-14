"""Constants for payment-processing."""
from __future__ import annotations

from decimal import Decimal

# NACHA limits
SAME_DAY_ACH_MAX_AMOUNT: Decimal = Decimal("1000000.00")

# Retry backoff schedule in hours
RETRY_BACKOFF_HOURS: list[int] = [1, 4, 12]

# Vendor status thresholds
HEALTH_DEGRADED_MS = 500
HEALTH_DOWN_ERROR_COUNT = 3

# Vendor types
VENDOR_TYPE_DIRECT_ACH = "direct_ach"
VENDOR_TYPE_ECHO = "echo"
VENDOR_TYPE_ZELIS = "zelis"
VENDOR_TYPE_CHECK = "check_issuing"

# Connection types
CONN_TYPE_API = "api"
CONN_TYPE_SFTP = "sftp"
CONN_TYPE_MANUAL = "manual"

# Submission statuses
SUB_PENDING = "pending"
SUB_SUBMITTED = "submitted"
SUB_ACKNOWLEDGED = "acknowledged"
SUB_PROCESSING = "processing"
SUB_COMPLETED = "completed"
SUB_PARTIALLY_COMPLETED = "partially_completed"
SUB_FAILED = "failed"
SUB_REJECTED = "rejected"

# Settlement statuses
SETTLE_PENDING = "pending"
SETTLE_SETTLED = "settled"
SETTLE_RETURNED = "returned"
SETTLE_REJECTED = "rejected"
SETTLE_CANCELLED = "cancelled"

# Enrollment statuses
ENROLL_NOT_ENROLLED = "not_enrolled"
ENROLL_PENDING = "pending"
ENROLL_ENROLLED = "enrolled"
ENROLL_SUSPENDED = "suspended"
ENROLL_TERMINATED = "terminated"

# Vendor health statuses
VH_HEALTHY = "healthy"
VH_DEGRADED = "degraded"
VH_DOWN = "down"

# ACH entry class codes
NACHA_CCD = "CCD"
NACHA_PPD = "PPD"
NACHA_CTX = "CTX"

# NACHA 2026 Company Entry Description
NACHA_COMPANY_ENTRY_DESC_BUSINESS = "PAYMT"

# OFAC screening result
OFAC_CLEAR = "clear"
OFAC_BLOCKED = "blocked"

# Event topics — consumed
EVENT_PAYMENT_BATCH_SUBMITTED = "payment_batch.submitted"
EVENT_FWA_HOLD_PLACED = "fwa.payment_hold_placed"
EVENT_FWA_HOLD_RELEASED = "fwa.payment_hold_released"

# Event topics — published
EVENT_FILE_GENERATED = "payment.file_generated"
EVENT_SUBMITTED = "payment.submitted"
EVENT_ACKNOWLEDGED = "payment.acknowledged"
EVENT_SETTLED = "payment.settled"
EVENT_RETURNED = "payment.returned"
EVENT_FAILED = "payment.failed"
EVENT_RETURN_SUSPICIOUS = "payment.return_suspicious"
EVENT_VENDOR_STATUS_CHANGED = "vendor.status_changed"
