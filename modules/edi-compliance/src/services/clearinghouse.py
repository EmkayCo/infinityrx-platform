"""Clearinghouse adapter layer.

Provides normalized adapter interfaces for major clearinghouse partners:
  - Stedi (HIPAA API-first)
  - Availity (RESTful and legacy)
  - Change Healthcare / Optum (formerly Change Healthcare)
  - Waystar (formerly ZirMed + Navicure)

All adapters implement the ClearinghouseAdapter protocol.
No credentials hardcoded — all loaded from config.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ClearinghouseProvider(str, Enum):
    STEDI = "stedi"
    AVAILITY = "availity"
    CHANGE_HEALTHCARE = "change_healthcare"
    WAYSTAR = "waystar"
    GENERIC = "generic"


class SubmissionStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"


@dataclass
class ClearinghouseConfig:
    provider: ClearinghouseProvider
    base_url: str
    api_key: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    submitter_id: str = ""
    timeout_seconds: int = 30
    test_mode: bool = True


@dataclass
class SubmissionResult:
    submission_id: str
    status: SubmissionStatus
    clearinghouse_control_number: str = ""
    acknowledgment_type: str = ""       # 999, TA1, or clearinghouse-specific
    error_messages: List[str] = field(default_factory=list)
    raw_response: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""


@dataclass
class EligibilityResult:
    member_id: str
    payer_id: str
    eligible: bool
    coverage_active: bool
    plan_name: str = ""
    plan_begin_date: str = ""
    plan_end_date: str = ""
    copay: str = ""
    deductible: str = ""
    error: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_submission_result(
    submission_id: str,
    status: SubmissionStatus,
    control_number: str = "",
    ack_type: str = "999",
    errors: Optional[List[str]] = None,
    raw_response: Optional[Dict[str, Any]] = None,
) -> SubmissionResult:
    """Build a normalized SubmissionResult from clearinghouse response data."""
    return SubmissionResult(
        submission_id=submission_id,
        status=status,
        clearinghouse_control_number=control_number,
        acknowledgment_type=ack_type,
        error_messages=errors or [],
        raw_response=raw_response or {},
        timestamp=_now_iso(),
    )


def parse_stedi_response(response: Dict[str, Any]) -> SubmissionResult:
    """Parse a Stedi API response into a normalized SubmissionResult."""
    import uuid
    status_str = response.get("status", "").lower()
    if status_str == "accepted":
        status = SubmissionStatus.ACCEPTED
    elif status_str == "rejected":
        status = SubmissionStatus.REJECTED
    else:
        status = SubmissionStatus.PENDING

    errors = response.get("errors", [])
    if isinstance(errors, list):
        error_msgs = [str(e) for e in errors]
    else:
        error_msgs = [str(errors)] if errors else []

    return SubmissionResult(
        submission_id=response.get("submissionId", str(uuid.uuid4())),
        status=status,
        clearinghouse_control_number=response.get("controlNumber", ""),
        acknowledgment_type="999",
        error_messages=error_msgs,
        raw_response=response,
        timestamp=_now_iso(),
    )


def parse_availity_response(response: Dict[str, Any]) -> SubmissionResult:
    """Parse an Availity API response into a normalized SubmissionResult."""
    import uuid
    status_str = response.get("transactionStatus", "").upper()
    if status_str in ("ACCEPTED", "PROCESSED"):
        status = SubmissionStatus.ACCEPTED
    elif status_str in ("REJECTED", "DENIED"):
        status = SubmissionStatus.REJECTED
    elif status_str in ("ACKNOWLEDGED",):
        status = SubmissionStatus.ACKNOWLEDGED
    else:
        status = SubmissionStatus.PENDING

    errors = []
    for err in response.get("errorMessages", []):
        errors.append(err.get("message", str(err)) if isinstance(err, dict) else str(err))

    return SubmissionResult(
        submission_id=response.get("transactionId", str(uuid.uuid4())),
        status=status,
        clearinghouse_control_number=response.get("clearinghouseControlNumber", ""),
        acknowledgment_type=response.get("ackType", "999"),
        error_messages=errors,
        raw_response=response,
        timestamp=_now_iso(),
    )


def parse_change_healthcare_response(response: Dict[str, Any]) -> SubmissionResult:
    """Parse a Change Healthcare / Optum response into a normalized SubmissionResult."""
    import uuid
    edit_status = response.get("editStatus", "").lower()
    if edit_status in ("accepted", "forwarded"):
        status = SubmissionStatus.ACCEPTED
    elif edit_status in ("rejected", "denied"):
        status = SubmissionStatus.REJECTED
    else:
        status = SubmissionStatus.PENDING

    error_msgs = []
    for claim in response.get("claimStatus", []):
        for err in claim.get("errors", []):
            error_msgs.append(err.get("message", str(err)) if isinstance(err, dict) else str(err))

    return SubmissionResult(
        submission_id=response.get("submissionId", str(uuid.uuid4())),
        status=status,
        clearinghouse_control_number=response.get("controlNumber", ""),
        acknowledgment_type="999",
        error_messages=error_msgs,
        raw_response=response,
        timestamp=_now_iso(),
    )


def parse_waystar_response(response: Dict[str, Any]) -> SubmissionResult:
    """Parse a Waystar response into a normalized SubmissionResult."""
    import uuid
    status_code = response.get("statusCode", "").upper()
    if status_code in ("ACCEPTED", "A"):
        status = SubmissionStatus.ACCEPTED
    elif status_code in ("REJECTED", "R"):
        status = SubmissionStatus.REJECTED
    elif status_code in ("ACKNOWLEDGED",):
        status = SubmissionStatus.ACKNOWLEDGED
    else:
        status = SubmissionStatus.PENDING

    errors = [str(e) for e in response.get("errors", [])]

    return SubmissionResult(
        submission_id=response.get("transactionId", str(uuid.uuid4())),
        status=status,
        clearinghouse_control_number=response.get("controlNum", ""),
        acknowledgment_type="999",
        error_messages=errors,
        raw_response=response,
        timestamp=_now_iso(),
    )


def route_clearinghouse_response(
    provider: ClearinghouseProvider,
    response: Dict[str, Any],
) -> SubmissionResult:
    """Route a clearinghouse response to the appropriate parser."""
    if provider == ClearinghouseProvider.STEDI:
        return parse_stedi_response(response)
    if provider == ClearinghouseProvider.AVAILITY:
        return parse_availity_response(response)
    if provider == ClearinghouseProvider.CHANGE_HEALTHCARE:
        return parse_change_healthcare_response(response)
    if provider == ClearinghouseProvider.WAYSTAR:
        return parse_waystar_response(response)
    # Generic: treat as Stedi-format
    return parse_stedi_response(response)
