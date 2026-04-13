"""Report builder: data source field discovery and query construction."""

from __future__ import annotations

from typing import Any

_DATA_SOURCE_FIELDS: dict[str, list[dict[str, Any]]] = {
    "claims": [
        {"field": "claim_id", "label": "Claim ID", "type": "string"},
        {"field": "rx_number", "label": "Rx Number", "type": "string", "phi": True},
        {"field": "fill_date", "label": "Fill Date", "type": "date"},
        {"field": "ndc", "label": "NDC", "type": "string", "phi": True},
        {"field": "drug_name", "label": "Drug Name", "type": "string"},
        {"field": "quantity", "label": "Quantity", "type": "decimal"},
        {"field": "days_supply", "label": "Days Supply", "type": "integer"},
        {"field": "amount_paid", "label": "Amount Paid", "type": "currency"},
        {"field": "plan_paid", "label": "Plan Paid", "type": "currency"},
        {"field": "member_pay", "label": "Member Pay", "type": "currency"},
        {"field": "pharmacy_npi", "label": "Pharmacy NPI", "type": "string"},
        {"field": "pharmacy_name", "label": "Pharmacy Name", "type": "string"},
        {"field": "prescriber_npi", "label": "Prescriber NPI", "type": "string"},
        {"field": "member_id", "label": "Member ID", "type": "string", "phi": True},
        {"field": "member_name", "label": "Member Name", "type": "string", "phi": True},
        {"field": "program_id", "label": "Program ID", "type": "string"},
        {"field": "therapeutic_class", "label": "Therapeutic Class", "type": "string"},
        {"field": "status", "label": "Status", "type": "string"},
        {"field": "reversal_flag", "label": "Reversal", "type": "boolean"},
    ],
    "billing_ap": [
        {"field": "ap_record_id", "label": "AP Record ID", "type": "string"},
        {"field": "pay_to_npi", "label": "Pay-To NPI", "type": "string"},
        {"field": "pay_to_name", "label": "Pay-To Name", "type": "string"},
        {"field": "amount", "label": "Amount", "type": "currency"},
        {"field": "payment_method", "label": "Payment Method", "type": "string"},
        {"field": "status", "label": "Status", "type": "string"},
        {"field": "batch_id", "label": "Batch ID", "type": "string"},
        {"field": "billing_period", "label": "Billing Period", "type": "string"},
        {"field": "created_at", "label": "Created Date", "type": "date"},
    ],
    "billing_ar": [
        {"field": "invoice_id", "label": "Invoice ID", "type": "string"},
        {"field": "client_name", "label": "Client Name", "type": "string"},
        {"field": "invoice_date", "label": "Invoice Date", "type": "date"},
        {"field": "due_date", "label": "Due Date", "type": "date"},
        {"field": "total_amount", "label": "Total Amount", "type": "currency"},
        {"field": "amount_paid", "label": "Amount Paid", "type": "currency"},
        {"field": "amount_due", "label": "Amount Due", "type": "currency"},
        {"field": "status", "label": "Status", "type": "string"},
        {"field": "days_outstanding", "label": "Days Outstanding", "type": "integer"},
    ],
    "journal": [
        {"field": "entry_id", "label": "Entry ID", "type": "string"},
        {"field": "entry_date", "label": "Entry Date", "type": "date"},
        {"field": "category", "label": "Category", "type": "string"},
        {"field": "description", "label": "Description", "type": "string"},
        {"field": "debit", "label": "Debit", "type": "currency"},
        {"field": "credit", "label": "Credit", "type": "currency"},
        {"field": "net", "label": "Net", "type": "currency"},
        {"field": "program_id", "label": "Program ID", "type": "string"},
        {"field": "reference_id", "label": "Reference ID", "type": "string"},
    ],
    "fwa": [
        {"field": "flag_id", "label": "Flag ID", "type": "string"},
        {"field": "claim_id", "label": "Claim ID", "type": "string"},
        {"field": "rule_id", "label": "Rule ID", "type": "string"},
        {"field": "rule_name", "label": "Rule Name", "type": "string"},
        {"field": "severity", "label": "Severity", "type": "string"},
        {"field": "entity_type", "label": "Entity Type", "type": "string"},
        {"field": "entity_id", "label": "Entity ID", "type": "string"},
        {"field": "flagged_at", "label": "Flagged Date", "type": "date"},
        {"field": "status", "label": "Status", "type": "string"},
        {"field": "estimated_recovery", "label": "Est. Recovery", "type": "currency"},
    ],
    "members": [
        {"field": "member_id", "label": "Member ID", "type": "string", "phi": True},
        {"field": "member_name", "label": "Member Name", "type": "string", "phi": True},
        {"field": "dob", "label": "Date of Birth", "type": "date", "phi": True},
        {"field": "plan_id", "label": "Plan ID", "type": "string"},
        {"field": "enrollment_date", "label": "Enrollment Date", "type": "date"},
        {"field": "status", "label": "Status", "type": "string"},
    ],
    "pharmacies": [
        {"field": "npi", "label": "NPI", "type": "string"},
        {"field": "name", "label": "Pharmacy Name", "type": "string"},
        {"field": "address", "label": "Address", "type": "string"},
        {"field": "city", "label": "City", "type": "string"},
        {"field": "state", "label": "State", "type": "string"},
        {"field": "pharmacy_type", "label": "Type", "type": "string"},
        {"field": "network_status", "label": "Network Status", "type": "string"},
    ],
    "prescribers": [
        {"field": "npi", "label": "NPI", "type": "string"},
        {"field": "name", "label": "Prescriber Name", "type": "string"},
        {"field": "specialty", "label": "Specialty", "type": "string"},
        {"field": "state", "label": "State", "type": "string"},
    ],
    "programs": [
        {"field": "program_id", "label": "Program ID", "type": "string"},
        {"field": "program_name", "label": "Program Name", "type": "string"},
        {"field": "client_name", "label": "Client Name", "type": "string"},
        {"field": "status", "label": "Status", "type": "string"},
        {"field": "start_date", "label": "Start Date", "type": "date"},
    ],
}


def get_available_fields(data_source: str) -> list[dict[str, Any]]:
    """Return available fields for a given data source."""
    return _DATA_SOURCE_FIELDS.get(data_source, [])


def get_all_data_sources() -> list[str]:
    """Return all available data source names."""
    return list(_DATA_SOURCE_FIELDS.keys())
