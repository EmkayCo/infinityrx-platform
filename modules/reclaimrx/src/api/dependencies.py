"""FastAPI dependencies for ReclaimRx module."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from src._shim.auth import CurrentUser, current_user, require_role
from src._shim.db import get_session


def get_db() -> Generator[Session]:
    yield from get_session()


def get_current_user() -> CurrentUser:
    return current_user()


def require_investigator() -> CurrentUser:
    return require_role("investigator", "tenant_admin", "super_admin")()


def require_admin() -> CurrentUser:
    return require_role("tenant_admin", "super_admin")()
