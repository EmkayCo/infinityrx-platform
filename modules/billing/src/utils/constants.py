"""Billing module constants."""

from __future__ import annotations

from decimal import Decimal

BILLING_SCHEMA = "billing"

# Claim statuses
CLAIM_STATUS_INGESTED = "ingested"
CLAIM_STATUS_CLASSIFIED = "classified"
CLAIM_STATUS_EXCLUDED = "excluded"

# Payment routes
ROUTE_DIRECT_ACH = "direct_ach"
ROUTE_ECHO = "echo"
ROUTE_ZELIS = "zelis"
ROUTE_CHECK = "check"
ROUTE_EXCLUDED = "excluded"
ROUTE_STATEMENT = "statement"

# AP statuses
AP_STATUS_CREATED = "created"
AP_STATUS_SCHEDULED = "scheduled"
AP_STATUS_SUBMITTED = "submitted"
AP_STATUS_SETTLED = "settled"
AP_STATUS_RETURNED = "returned"
AP_STATUS_FAILED = "failed"
AP_STATUS_VOIDED = "voided"

# Payment batch statuses
BATCH_STATUS_GENERATED = "generated"
BATCH_STATUS_VALIDATED = "validated"
BATCH_STATUS_APPROVED = "approved"
BATCH_STATUS_SUBMITTED = "submitted"
BATCH_STATUS_SETTLED = "settled"
BATCH_STATUS_VOIDED = "voided"

# AR / Invoice statuses
INVOICE_STATUS_DRAFT = "draft"
INVOICE_STATUS_APPROVED = "approved"
INVOICE_STATUS_SENT = "sent"
INVOICE_STATUS_VOIDED = "voided"

AR_STATUS_OPEN = "open"
AR_STATUS_PARTIALLY_PAID = "partially_paid"
AR_STATUS_PAID = "paid"
AR_STATUS_OVERDUE = "overdue"
AR_STATUS_DISPUTED = "disputed"
AR_STATUS_WRITTEN_OFF = "written_off"
AR_STATUS_VOIDED = "voided"

# Aging buckets
AGING_CURRENT = "current"
AGING_30 = "30"
AGING_60 = "60"
AGING_90 = "90"
AGING_120_PLUS = "120_plus"

# Funding models
FUNDING_PREFUND = "prefund"
FUNDING_CLAIMS_FUND = "claims_fund"
FUNDING_PASS_THROUGH = "pass_through"

# Journal entry types
JOURNAL_AP_CREATED = "ap_created"
JOURNAL_AP_SETTLED = "ap_settled"
JOURNAL_AP_RETURNED = "ap_returned"
JOURNAL_AP_VOIDED = "ap_voided"
JOURNAL_PAYMENT_SUBMITTED = "payment_submitted"
JOURNAL_PAYMENT_SETTLED = "payment_settled"
JOURNAL_PAYMENT_RETURNED = "payment_returned"
JOURNAL_INVOICE_GENERATED = "invoice_generated"
JOURNAL_INVOICE_SENT = "invoice_sent"
JOURNAL_INVOICE_VOIDED = "invoice_voided"
JOURNAL_AR_CREATED = "ar_created"
JOURNAL_AR_PAYMENT_RECEIVED = "ar_payment_received"
JOURNAL_AR_WRITTEN_OFF = "ar_written_off"
JOURNAL_PREFUND_DEPOSIT = "prefund_deposit"
JOURNAL_PREFUND_DEDUCTION = "prefund_deduction"
JOURNAL_FEE_CALCULATED = "fee_calculated"
JOURNAL_ADJUSTMENT = "adjustment"
JOURNAL_CREDIT_MEMO = "credit_memo"
JOURNAL_LATE_FEE_APPLIED = "late_fee_applied"
JOURNAL_DIR_FEE_ASSESSED = "dir_fee_assessed"

# Journal categories
CATEGORY_CLAIMS_PAYABLE = "claims_payable"
CATEGORY_CLAIMS_RECEIVABLE = "claims_receivable"
CATEGORY_PROCESSING_FEE = "processing_fee"
CATEGORY_ADMIN_FEE = "admin_fee"
CATEGORY_PREFUND = "prefund"
CATEGORY_ADJUSTMENT = "adjustment"
CATEGORY_LATE_FEE = "late_fee"

# Fee calculation types
FEE_PER_CLAIM_FLAT = "per_claim_flat"
FEE_PER_CLAIM_PERCENTAGE = "per_claim_percentage"
FEE_TIERED_VOLUME = "tiered_volume"
FEE_FLAT_MONTHLY = "flat_monthly"
FEE_PER_MEMBER_PER_MONTH = "per_member_per_month"
FEE_PER_TRANSACTION = "per_transaction"
FEE_PERCENTAGE_OF_INGREDIENT_COST = "percentage_of_ingredient_cost"
FEE_CUSTOM = "custom"

# Budget types
BUDGET_ANNUAL = "annual"
BUDGET_QUARTERLY = "quarterly"
BUDGET_MONTHLY = "monthly"
BUDGET_TOTAL_CAP = "total_cap"
BUDGET_UNLIMITED = "unlimited"

# Alert severities
SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"

# Budget alert types
ALERT_SPEND_RATE_INCREASE = "spend_rate_increase"
ALERT_BUDGET_LOW = "budget_low"
ALERT_BUDGET_CRITICAL = "budget_critical"
ALERT_PROJECTED_DEPLETION = "projected_depletion"
ALERT_OVER_BUDGET = "over_budget"
ALERT_UNUSUAL_ACTIVITY = "unusual_activity"

# Automation levels
AUTOMATION_MANUAL = "manual"
AUTOMATION_SEMI_AUTOMATIC = "semi_automatic"
AUTOMATION_AUTOMATIC = "automatic"

# Delivery methods
DELIVERY_EMAIL = "email"
DELIVERY_SFTP = "sftp"
DELIVERY_PORTAL = "portal"
DELIVERY_API = "api"

# File types
FILE_TYPE_CSV = "csv"
FILE_TYPE_FIXED_WIDTH = "fixed_width"
FILE_TYPE_EXCEL = "excel"

# Data retention default (years)
DEFAULT_RETENTION_YEARS = 7

# Duplicate detection window (days)
DUPLICATE_FILE_WINDOW_DAYS = 90

# Prefund alert thresholds (percentage)
BUDGET_CRITICAL_FLOOR_PCT = Decimal("10")

# Late payment defaults
DEFAULT_PAYMENT_TERMS_DAYS = 30

# NACHA constants
NACHA_SAME_DAY_ACH_LIMIT = Decimal("1000000.00")
