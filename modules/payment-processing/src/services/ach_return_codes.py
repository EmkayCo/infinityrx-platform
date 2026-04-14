"""Full R01-R85 ACH return code table with default actions.

Pre-loaded defaults. Actions configurable per tenant via DB.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReturnCodeDef:
    code: str
    description: str
    category: str
    is_retryable: bool
    default_action: str
    retry_delay_days: int | None
    triggers_fwa_alert: bool = False


# Full R01-R85 table (researched defaults per NACHA rules)
ACH_RETURN_CODES: list[ReturnCodeDef] = [
    ReturnCodeDef("R01", "Insufficient Funds", "insufficient_funds", True, "auto_retry", 3),
    ReturnCodeDef("R02", "Account Closed", "account_closed", False, "carryover", None),
    ReturnCodeDef("R03", "No Account / Unable to Locate Account", "account_closed", False, "carryover", None),
    ReturnCodeDef("R04", "Invalid Account Number Structure", "administrative", False, "carryover", None),
    ReturnCodeDef("R05", "Unauthorized Debit to Consumer Account Using Corporate SEC Code", "unauthorized", False, "manual_review", None, True),
    ReturnCodeDef("R06", "Returned per ODFI's Request", "administrative", False, "manual_review", None),
    ReturnCodeDef("R07", "Authorization Revoked by Customer", "unauthorized", False, "manual_review", None, True),
    ReturnCodeDef("R08", "Payment Stopped", "unauthorized", False, "manual_review", None),
    ReturnCodeDef("R09", "Uncollected Funds", "insufficient_funds", True, "auto_retry", 5),
    ReturnCodeDef("R10", "Customer Advises Originator Not Known to Receiver or Not Authorized", "unauthorized", False, "manual_review", None, True),
    ReturnCodeDef("R11", "Customer Advises Entry Not in Accordance with the Terms of the Authorization", "unauthorized", False, "manual_review", None),
    ReturnCodeDef("R12", "Branch Sold to Another DFI", "administrative", False, "carryover", None),
    ReturnCodeDef("R13", "RDFI Not Qualified to Participate", "administrative", False, "carryover", None),
    ReturnCodeDef("R14", "Representative Payee Deceased or Unable to Continue in that Capacity", "administrative", False, "manual_review", None),
    ReturnCodeDef("R15", "Beneficiary or Account Holder (Other Than a Representative Payee) Deceased", "administrative", False, "manual_review", None),
    ReturnCodeDef("R16", "Account Frozen / Ofac Hold", "administrative", False, "carryover", None),
    ReturnCodeDef("R17", "File Record Edit Criteria", "administrative", False, "manual_review", None),
    ReturnCodeDef("R18", "Improper Effective Entry Date", "administrative", False, "manual_review", None),
    ReturnCodeDef("R19", "Amount Field Error", "administrative", False, "manual_review", None),
    ReturnCodeDef("R20", "Non-Transaction Account", "administrative", False, "carryover", None),
    ReturnCodeDef("R21", "Invalid Company Identification", "administrative", False, "manual_review", None),
    ReturnCodeDef("R22", "Invalid Individual ID Number", "administrative", False, "manual_review", None),
    ReturnCodeDef("R23", "Credit Entry Refused by Receiver", "unauthorized", False, "manual_review", None),
    ReturnCodeDef("R24", "Duplicate Entry", "administrative", False, "manual_review", None),
    ReturnCodeDef("R25", "Addenda Error", "administrative", False, "manual_review", None),
    ReturnCodeDef("R26", "Mandatory Field Error", "administrative", False, "manual_review", None),
    ReturnCodeDef("R27", "Trace Number Error", "administrative", False, "manual_review", None),
    ReturnCodeDef("R28", "Transit Routing Number Check Digit Error", "administrative", False, "manual_review", None),
    ReturnCodeDef("R29", "Corporate Customer Advises Not Authorized", "unauthorized", False, "manual_review", None, True),
    ReturnCodeDef("R30", "RDFI Not Participant in Check Truncation Program", "administrative", False, "manual_review", None),
    ReturnCodeDef("R31", "Permissible Return Entry (CCD and CTX Only)", "administrative", False, "manual_review", None),
    ReturnCodeDef("R32", "RDFI Non-Settlement", "administrative", False, "manual_review", None),
    ReturnCodeDef("R33", "Return of XCK Entry", "administrative", False, "manual_review", None),
    ReturnCodeDef("R34", "Limited Participation DFI", "administrative", False, "manual_review", None),
    ReturnCodeDef("R35", "Return of Improper Debit Entry", "administrative", False, "manual_review", None),
    ReturnCodeDef("R36", "Return of Improper Credit Entry", "administrative", False, "manual_review", None),
    ReturnCodeDef("R37", "Source Document Presented for Payment", "administrative", False, "manual_review", None),
    ReturnCodeDef("R38", "Stop Payment on Source Document", "unauthorized", False, "manual_review", None),
    ReturnCodeDef("R39", "Improper Source Document / Source Document Presented for Payment", "administrative", False, "manual_review", None),
    ReturnCodeDef("R40", "Return of ENR Entry by Federal Government Agency", "administrative", False, "manual_review", None),
    ReturnCodeDef("R41", "Invalid Transaction Code", "administrative", False, "manual_review", None),
    ReturnCodeDef("R42", "Routing Transit Number / Check Digit Error", "administrative", False, "manual_review", None),
    ReturnCodeDef("R43", "Invalid DFI Account Number", "administrative", False, "manual_review", None),
    ReturnCodeDef("R44", "Invalid Individual ID Number / Identification Number", "administrative", False, "manual_review", None),
    ReturnCodeDef("R45", "Invalid Individual Name / Company Name", "administrative", False, "manual_review", None),
    ReturnCodeDef("R46", "Invalid Representative Payee Indicator", "administrative", False, "manual_review", None),
    ReturnCodeDef("R47", "Duplicate Enrollment", "administrative", False, "manual_review", None),
    ReturnCodeDef("R50", "State Law Affecting RCK Acceptance", "administrative", False, "manual_review", None),
    ReturnCodeDef("R51", "Item Related to RCK Entry is Ineligible or RCK Entry is Improper", "administrative", False, "manual_review", None),
    ReturnCodeDef("R52", "Stop Payment on Item Related to RCK Entry", "unauthorized", False, "manual_review", None),
    ReturnCodeDef("R53", "Item and ACH Entry Presented for Payment", "administrative", False, "manual_review", None),
    ReturnCodeDef("R61", "Misrouted Return", "administrative", False, "manual_review", None),
    ReturnCodeDef("R67", "Duplicate Return", "administrative", False, "manual_review", None),
    ReturnCodeDef("R68", "Untimely Return", "administrative", False, "manual_review", None),
    ReturnCodeDef("R69", "Field Error(s)", "administrative", False, "manual_review", None),
    ReturnCodeDef("R70", "Permissible Return Entry Not Accepted / Return Not Requested by ODFI", "administrative", False, "manual_review", None),
    ReturnCodeDef("R71", "Misrouted Dishonored Return", "administrative", False, "manual_review", None),
    ReturnCodeDef("R72", "Untimely Dishonored Return", "administrative", False, "manual_review", None),
    ReturnCodeDef("R73", "Timely Original Return", "administrative", False, "manual_review", None),
    ReturnCodeDef("R74", "Corrected Return", "administrative", False, "manual_review", None),
    ReturnCodeDef("R75", "Return Not a Duplicate", "administrative", False, "manual_review", None),
    ReturnCodeDef("R76", "No Errors Found", "administrative", False, "manual_review", None),
    ReturnCodeDef("R77", "Non-Acceptance of R62 Dishonored Return", "administrative", False, "manual_review", None),
    ReturnCodeDef("R80", "Cross-Border Payment Coding Error", "administrative", False, "manual_review", None),
    ReturnCodeDef("R81", "Non-Participant in Cross-Border Program", "administrative", False, "manual_review", None),
    ReturnCodeDef("R82", "Invalid Foreign Receiving DFI Identification", "administrative", False, "manual_review", None),
    ReturnCodeDef("R83", "Foreign Receiving DFI Unable to Settle", "administrative", False, "manual_review", None),
    ReturnCodeDef("R84", "Entry Not Processed by Gateway", "administrative", False, "manual_review", None),
    ReturnCodeDef("R85", "Incorrectly Coded Outbound International Payment", "administrative", False, "manual_review", None),
]

# Fast lookup by code
ACH_RETURN_CODE_MAP: dict[str, ReturnCodeDef] = {r.code: r for r in ACH_RETURN_CODES}


def get_return_code(code: str) -> ReturnCodeDef | None:
    return ACH_RETURN_CODE_MAP.get(code)


def is_suspicious_return(code: str) -> bool:
    """Return True for codes that trigger FWA alert (R10, R07, R29, R05)."""
    rc = get_return_code(code)
    return rc is not None and rc.triggers_fwa_alert
