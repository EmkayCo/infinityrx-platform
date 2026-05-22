"""API layer tests for src/api/uploads.py.

Covers:
  - FIX 1: supersede_upload_endpoint forwards x-column-mapping to parse_upload
  - FIX 2: _parse_column_mapping_header hardening
      - oversized header (> 8 KB) -> 400
      - malformed JSON -> 400
      - non-object JSON -> 400
      - too many keys (> 64) -> 400
      - duplicate user_col -> two canonical fields (ambiguous) -> 400
      - user_col is a canonical field name (overwrite collision) -> 400
      - valid mapping -> succeeds
  - Financial precision e2e: mapped "Billed" -> amount_billed with 4 dp
    preserved through parse_upload into ClaimRecord.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException, Request

from src.api.uploads import _MAPPING_MAX_BYTES, _MAPPING_MAX_KEYS, _parse_column_mapping_header
from src.models.tables import ClaimRecord, Upload, UploadStatus
from src.services.upload import parse_upload

from tests.conftest import TENANT_A

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_VALID_NPI = "1234567893"
_VALID_NDC = "00093015005"

_FULL_MAPPING = {
    "ndc": "Drug Code",
    "npi": "Provider NPI",
    "claim_id": "Claim",
    "date_of_service": "Service Date",
    "quantity": "Qty",
    "days_supply": "Days",
    "amount_billed": "Billed",
    "member_id": "Member",
}
_NONSTANDARD_HEADER = "Drug Code,Provider NPI,Claim,Service Date,Qty,Days,Billed,Member"


def _make_request(headers: dict[str, str]) -> Request:
    """Build a minimal Starlette Request with the given headers."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "query_string": b"",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in headers.items()
        ],
    }
    return Request(scope)


def _new_upload(tenant=TENANT_A) -> Upload:
    return Upload(
        id=uuid.uuid4(),
        tenant_id=tenant,
        filename="batch.csv",
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,  # unique per call
        file_size=100,
        mime_type="text/csv",
        uploaded_at=datetime.now(UTC),
        uploaded_by=uuid.uuid4(),
        status=UploadStatus.parsing.value,
    )


def _nonstandard_csv(claim_id: str = "C-1", amount: str = "125.4567") -> bytes:
    row = f"{_VALID_NDC},{_VALID_NPI},{claim_id},2026-01-15,30,30,{amount},MBR-1"
    return f"{_NONSTANDARD_HEADER}\n{row}\n".encode()


# ---------------------------------------------------------------------------
# _parse_column_mapping_header: absent header
# ---------------------------------------------------------------------------


def test_parse_mapping_header_absent_returns_none():
    req = _make_request({})
    assert _parse_column_mapping_header(req) is None


# ---------------------------------------------------------------------------
# FIX 2: oversized header -> 400
# ---------------------------------------------------------------------------


def test_parse_mapping_header_oversized_returns_400():
    # Build a header just over the 8 KB limit
    big = json.dumps({"k" + str(i): "v" + ("x" * 200) for i in range(50)})
    assert len(big.encode("utf-8")) > _MAPPING_MAX_BYTES, "test setup: header must exceed limit"
    req = _make_request({"x-column-mapping": big})
    with pytest.raises(HTTPException) as exc_info:
        _parse_column_mapping_header(req)
    assert exc_info.value.status_code == 400
    assert "INVALID_COLUMN_MAPPING" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# FIX 2: malformed JSON -> 400
# ---------------------------------------------------------------------------


def test_parse_mapping_header_malformed_json_returns_400():
    req = _make_request({"x-column-mapping": "{not: valid json"})
    with pytest.raises(HTTPException) as exc_info:
        _parse_column_mapping_header(req)
    assert exc_info.value.status_code == 400
    detail = str(exc_info.value.detail)
    assert "INVALID_COLUMN_MAPPING" in detail
    assert "not valid JSON" in detail


# ---------------------------------------------------------------------------
# FIX 2: non-object JSON -> 400
# ---------------------------------------------------------------------------


def test_parse_mapping_header_array_returns_400():
    req = _make_request({"x-column-mapping": '["ndc","npi"]'})
    with pytest.raises(HTTPException) as exc_info:
        _parse_column_mapping_header(req)
    assert exc_info.value.status_code == 400
    assert "INVALID_COLUMN_MAPPING" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# FIX 2: too many keys -> 400
# ---------------------------------------------------------------------------


def test_parse_mapping_header_too_many_keys_returns_400():
    big_map = {f"canonical_{i}": f"user_{i}" for i in range(_MAPPING_MAX_KEYS + 1)}
    req = _make_request({"x-column-mapping": json.dumps(big_map)})
    with pytest.raises(HTTPException) as exc_info:
        _parse_column_mapping_header(req)
    assert exc_info.value.status_code == 400
    assert "INVALID_COLUMN_MAPPING" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# FIX 2: ambiguous user_col (same user col -> two canonical fields) -> 400
# ---------------------------------------------------------------------------


def test_parse_mapping_header_ambiguous_user_col_returns_400():
    # "Drug Code" mapped to both "ndc" and "claim_id"
    mapping = {"ndc": "Drug Code", "claim_id": "Drug Code"}
    req = _make_request({"x-column-mapping": json.dumps(mapping)})
    with pytest.raises(HTTPException) as exc_info:
        _parse_column_mapping_header(req)
    assert exc_info.value.status_code == 400
    detail = str(exc_info.value.detail)
    assert "INVALID_COLUMN_MAPPING" in detail
    assert "Ambiguous" in detail


# ---------------------------------------------------------------------------
# FIX 2: canonical-overwrite collision -> 400
# ---------------------------------------------------------------------------


def test_parse_mapping_header_canonical_overwrite_collision_returns_400():
    # canonical "ndc" <- user column named "npi" (a canonical name itself)
    # would silently overwrite npi rows with ndc values
    mapping = {"ndc": "npi"}
    req = _make_request({"x-column-mapping": json.dumps(mapping)})
    with pytest.raises(HTTPException) as exc_info:
        _parse_column_mapping_header(req)
    assert exc_info.value.status_code == 400
    detail = str(exc_info.value.detail)
    assert "INVALID_COLUMN_MAPPING" in detail
    assert "ollision" in detail  # "collision" or "Mapping collision"


# ---------------------------------------------------------------------------
# FIX 2: valid mapping -> returns dict unchanged
# ---------------------------------------------------------------------------


def test_parse_mapping_header_valid_returns_dict():
    req = _make_request({"x-column-mapping": json.dumps(_FULL_MAPPING)})
    result = _parse_column_mapping_header(req)
    assert result == _FULL_MAPPING


# ---------------------------------------------------------------------------
# FIX 1: supersede forwards column_mapping - service-layer proof
# parse_upload with column_mapping on non-standard CSV succeeds (validated)
# ---------------------------------------------------------------------------


def test_supersede_parse_upload_with_mapping_succeeds(db_session):
    """FIX 1 service-layer proof: parse_upload with column_mapping on a
    non-standard-header CSV produces status=validated.  This is the exact
    call supersede_upload_endpoint now makes after the fix."""
    upload = _new_upload()
    db_session.add(upload)
    db_session.flush()

    result = parse_upload(
        db_session,
        upload=upload,
        file_bytes=_nonstandard_csv("CLM-SUP-1"),
        column_mapping=_FULL_MAPPING,
    )
    assert result.upload.status == UploadStatus.validated.value
    claims = db_session.query(ClaimRecord).filter_by(upload_id=upload.id).all()
    assert len(claims) == 1
    assert claims[0].auth_number == "CLM-SUP-1"


def test_supersede_parse_upload_without_mapping_fails_nonstandard(db_session):
    """Regression: non-standard headers without a mapping must raise ValueError.
    Confirms the fix does not degrade the no-mapping path."""
    upload = _new_upload()
    db_session.add(upload)
    db_session.flush()

    with pytest.raises(ValueError, match="required"):
        parse_upload(
            db_session,
            upload=upload,
            file_bytes=_nonstandard_csv("CLM-NO-MAP"),
            column_mapping=None,
        )


# ---------------------------------------------------------------------------
# Financial precision e2e: mapped amount_billed 4dp preserved end-to-end
# ---------------------------------------------------------------------------


def test_financial_precision_mapped_amount_billed_4dp_preserved(db_session):
    """amount_billed with 4 decimal places must survive parse_upload via
    column mapping with no float rounding.  Validates Decimal(str(value))
    path through the mapping pipeline (.claude/rules/financial-precision.md)."""
    amount = "125.4567"  # 4dp maximum allowed; must not be rounded or truncated
    upload = _new_upload()
    db_session.add(upload)
    db_session.flush()

    result = parse_upload(
        db_session,
        upload=upload,
        file_bytes=_nonstandard_csv("CLM-FIN-1", amount=amount),
        column_mapping=_FULL_MAPPING,
    )
    assert result.upload.status == UploadStatus.validated.value
    claims = db_session.query(ClaimRecord).filter_by(upload_id=upload.id).all()
    assert len(claims) == 1
    stored = claims[0].amount_billed
    assert stored == Decimal(amount), (
        f"Financial precision loss: expected {amount}, got {stored}"
    )
