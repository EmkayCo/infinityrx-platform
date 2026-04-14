"""Pydantic request/response schemas for the auth module."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    tenant_slug: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class MfaChallengeResponse(BaseModel):
    """Returned from /auth/login with status 202 when MFA is required."""

    mfa_required: bool = True
    method: str  # "totp" | "fido2"
    challenge_token: str
    expires_in: int = 300  # seconds


class MfaVerifyRequest(BaseModel):
    challenge_token: str = Field(min_length=1)
    code: str = Field(min_length=1, max_length=16)


class MeUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=72)
    role_names: list[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, pattern="^(active|inactive|locked)$")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    display_name: str
    status: str
    last_login_at: datetime | None
    failed_login_count: int
    roles: list[str] = Field(default_factory=list)


class RoleAssignment(BaseModel):
    role_names: list[str] = Field(min_length=0)


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class RoleUpdate(BaseModel):
    description: str | None = None


class RolePermissions(BaseModel):
    permissions: list[str] = Field(
        description="List of 'module:action' permission codes",
    )


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID | None
    name: str
    description: str | None
    is_system: bool
    permissions: list[str] = Field(default_factory=list)


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    module: str
    action: str
    description: str | None
    code: str
