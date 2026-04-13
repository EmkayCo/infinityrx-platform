"""Reporting module constants."""

from decimal import Decimal

# Report categories
CATEGORY_CLAIMS = "claims"
CATEGORY_BILLING_AP = "billing_ap"
CATEGORY_BILLING_AR = "billing_ar"
CATEGORY_FINANCIAL = "financial"
CATEGORY_FWA = "fwa"
CATEGORY_UTILIZATION = "utilization"
CATEGORY_REGULATORY = "regulatory"
CATEGORY_QUALITY = "quality"
CATEGORY_ACTUARIAL = "actuarial"

ALL_CATEGORIES = [
    CATEGORY_CLAIMS,
    CATEGORY_BILLING_AP,
    CATEGORY_BILLING_AR,
    CATEGORY_FINANCIAL,
    CATEGORY_FWA,
    CATEGORY_UTILIZATION,
    CATEGORY_REGULATORY,
    CATEGORY_QUALITY,
    CATEGORY_ACTUARIAL,
]

# Output formats
FORMAT_EXCEL = "excel"
FORMAT_PDF = "pdf"
FORMAT_CSV = "csv"
FORMAT_API = "api_webhook"

ALL_FORMATS = [FORMAT_EXCEL, FORMAT_PDF, FORMAT_CSV, FORMAT_API]

# Delivery methods
DELIVERY_EMAIL = "email"
DELIVERY_PORTAL = "portal"
DELIVERY_SFTP = "sftp"
DELIVERY_WEBHOOK = "api_webhook"

ALL_DELIVERY_METHODS = [DELIVERY_EMAIL, DELIVERY_PORTAL, DELIVERY_SFTP, DELIVERY_WEBHOOK]

# Report frequencies
FREQ_DAILY = "daily"
FREQ_WEEKLY = "weekly"
FREQ_BIWEEKLY = "biweekly"
FREQ_MONTHLY = "monthly"
FREQ_QUARTERLY = "quarterly"
FREQ_ANNUALLY = "annually"
FREQ_ON_DEMAND = "on_demand"

ALL_FREQUENCIES = [
    FREQ_DAILY,
    FREQ_WEEKLY,
    FREQ_BIWEEKLY,
    FREQ_MONTHLY,
    FREQ_QUARTERLY,
    FREQ_ANNUALLY,
    FREQ_ON_DEMAND,
]

# Run statuses
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_QUEUED = "queued"
STATUS_CANCELLED = "cancelled"

# Regulatory report types
REG_CAA_TRANSPARENCY = "caa_transparency_semiannual"
REG_CMS_QUALITY = "cms_quality_measures"
REG_STAR_RATINGS = "star_ratings"
REG_STATE = "state_regulatory"
REG_DIR = "dir_reporting"
REG_PDE = "pde_summary"
REG_CUSTOM = "custom_regulatory"

# PHI masking levels
PHI_FULL_DETAIL = "full_detail"
PHI_PARTIAL = "partial"
PHI_REDACTED = "redacted"

ALL_MASKING_LEVELS = [PHI_FULL_DETAIL, PHI_PARTIAL, PHI_REDACTED]

# Regulatory submission statuses
REG_STATUS_DRAFT = "draft"
REG_STATUS_REVIEW = "in_review"
REG_STATUS_APPROVED = "approved"
REG_STATUS_SUBMITTED = "submitted"
REG_STATUS_ACCEPTED = "accepted"
REG_STATUS_REJECTED = "rejected"

# Actuarial model types
ACTUARIAL_COST_PROJECTION = "cost_projection"
ACTUARIAL_FORMULARY_IMPACT = "formulary_impact"
ACTUARIAL_NETWORK_SAVINGS = "network_savings"
ACTUARIAL_REBATE_OPT = "rebate_optimization"
ACTUARIAL_TREND = "trend_analysis"
ACTUARIAL_RISK = "risk_scoring"

# Star Ratings D-Star measures
DSTAR_MEASURES = {
    "D01": "statin_adherence",
    "D02": "diabetes_medication_adherence",
    "D03": "ras_antagonist_adherence",
    "D04": "mtm_completion_rate",
    "D05": "part_d_medication_safety",
    "D06": "high_risk_medication",
    "D07": "drug_drug_interaction",
    "D08": "statin_use_persons_with_diabetes",
    "D09": "follow_up_after_ed_alcohol",
    "D10": "follow_up_after_inpatient_alcohol",
    "D11": "antidepressant_medication_management_acute",
    "D12": "antidepressant_medication_management_cont",
}

# PDC threshold for adherence measures
PDC_ADHERENCE_THRESHOLD = Decimal("0.80")

# Max rows before warnings
EXCEL_WARN_ROWS = 500_000
EXCEL_MAX_ROWS = 1_000_000
CSV_WARN_ROWS = 5_000_000
CSV_MAX_ROWS = 10_000_000
PDF_WARN_PAGES = 5_000
PDF_MAX_PAGES = 10_000

# Default concurrent report limit per tenant
DEFAULT_CONCURRENT_REPORTS = 5

# Report priority levels (lower = higher priority)
PRIORITY_REGULATORY = 1
PRIORITY_SCHEDULED = 2
PRIORITY_AD_HOC = 3

# AR aging buckets (days)
AR_AGING_BUCKETS = [
    (0, 30, "0-30"),
    (31, 60, "31-60"),
    (61, 90, "61-90"),
    (91, 120, "91-120"),
    (121, None, "121+"),
]
