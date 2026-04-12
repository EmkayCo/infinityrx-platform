"""Shim auth: current_user dependency returning a test user.

Real implementation lives in shared/auth/ (T2).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List


@dataclass
class CurrentUser:
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str = "dev@example.com"
    roles: List[str] = field(default_factory=lambda: ["tenant_admin"])

    def has_role(self, role: str) -> bool:
        return role in self.roles


_override: CurrentUser | None = None


def set_current_user(user: CurrentUser | None) -> None:
    global _override
    _override = user


def current_user() -> CurrentUser:
    if _override is None:
        raise RuntimeError("current_user not set; call set_current_user() in tests")
    return _override


def require_role(*roles: str):
    def _dep() -> CurrentUser:
        user = current_user()
        if not any(user.has_role(r) for r in roles):
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail={"error": "forbidden", "required": list(roles)})
        return user

    return _dep
