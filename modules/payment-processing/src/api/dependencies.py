"""FastAPI dependency injection for payment-processing."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from .._shim.auth import CurrentUser, current_user, require_role
from .._shim.db import get_session


def get_db() -> Generator[Session]:
    yield from get_session()


def get_current_user() -> CurrentUser:
    return current_user()


require_payment_role = require_role("tenant_admin", "payment_manager")
require_readonly = require_role("tenant_admin", "payment_manager", "payment_viewer")
