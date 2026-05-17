"""E2E-only test-auth shortcut endpoint.

POST /api/v1/core/test-auth/token
  Accepts a fixture user_id and returns a signed JWT for that user.
  Used exclusively by Playwright E2E tests to switch roles without going
  through the full login+MFA flow.

Production guard: returns 403 when INFINITYRX_ENV=production.
The endpoint must be mounted in create_app() alongside the other routers
so the integration test in tests/test_test_auth.py exercises it through
the real app factory (LESSON-006).

Fixture users are the canonical set from
  packages/modules/paysync/fixtures/seeds/users.json
"""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from shared.auth.jwt_tokens import create_access_token

logger = logging.getLogger("core-platform.test_auth")

router = APIRouter(prefix="/api/v1/core/test-auth", tags=["test-auth"])

# Fixture users from packages/modules/paysync/fixtures/seeds/users.json
# Role map: user_id -> (role, tenant_id)
_FIXTURE_USERS: dict[str, tuple[str, str]] = {
    "usr-00000000-0000-0000-0000-000000000001": (
        "operator",
        "t0000000-0000-0000-0000-000000000001",
    ),
    "usr-00000000-0000-0000-0000-000000000002": (
        "approver",
        "t0000000-0000-0000-0000-000000000001",
    ),
    "usr-00000000-0000-0000-0000-000000000003": (
        "auditor",
        "t0000000-0000-0000-0000-000000000001",
    ),
    "usr-00000000-0000-0000-0000-000000000004": (
        "operator",
        "t0000000-0000-0000-0000-000000000001",
    ),
    "usr-00000000-0000-0000-0000-000000000005": (
        "operator",
        "t0000000-0000-0000-0000-000000000001",
    ),
    "usr-00000000-0000-0000-0000-000000000006": (
        "approver",
        "t0000000-0000-0000-0000-000000000001",
    ),
    "usr-00000000-0000-0000-0000-000000000007": (
        "approver",
        "t0000000-0000-0000-0000-000000000001",
    ),
    "usr-00000000-0000-0000-0000-000000000008": (
        "auditor",
        "t0000000-0000-0000-0000-000000000001",
    ),
    "usr-00000000-0000-0000-0000-000000000009": (
        "auditor",
        "t0000000-0000-0000-0000-000000000001",
    ),
}


def _is_production() -> bool:
    return os.getenv("INFINITYRX_ENV", "development").lower() == "production"


class TestAuthRequest(BaseModel):
    user_id: str
    tenant_id: str = "t0000000-0000-0000-0000-000000000001"


class TestAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/token", response_model=TestAuthResponse, status_code=status.HTTP_200_OK)
async def issue_test_token(body: TestAuthRequest) -> TestAuthResponse:
    """Issue a JWT for a fixture user.

    Blocked in production. Intended for Playwright E2E role-switching.
    The returned token is a real HS256-signed JWT accepted by every module
    that uses shared.auth.dependencies.get_current_user.
    """
    if _is_production():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "test-auth endpoint is not available in production environments."
            ),
        )

    user_entry = _FIXTURE_USERS.get(body.user_id)
    if user_entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown fixture user_id: {body.user_id}",
        )

    role, fixture_tenant_id = user_entry
    # Allow the caller to override tenant_id (e.g. for multi-tenant E2E tests).
    effective_tenant = body.tenant_id or fixture_tenant_id

    try:
        # Strip the non-UUID prefix from fixture user IDs.
        # IDs in users.json are "usr-00000000-..." — strip the "usr-" prefix.
        raw_uid = body.user_id
        if raw_uid.startswith("usr-"):
            raw_uid = raw_uid[4:]
        user_uuid = uuid.UUID(raw_uid)
        tenant_uuid = uuid.UUID(effective_tenant)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid UUID in user_id or tenant_id: {exc}",
        ) from exc

    token = create_access_token(
        user_id=user_uuid,
        tenant_id=tenant_uuid,
        roles=[role],
    )

    logger.info(
        "test_auth.token_issued",
        extra={
            "auth_user_id": str(user_uuid),
            "svc_tenant_id": str(tenant_uuid),
            "svc_role": role,
        },
    )

    return TestAuthResponse(access_token=token, token_type="bearer")
