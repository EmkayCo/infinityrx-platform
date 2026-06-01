"""Dev-only auth wiring: trust JWT claims directly, no DB user lookup.

Used by directory backends (prescriber-directory, pharmacy-directory,
drug-database) which do NOT have a local ``users`` table — their schemas
own reference data (NPI, NPPES, NDC, FDB, etc.), not identity. The JWT
has already been cryptographically validated against ``JWT_SECRET`` by
``decode_token`` before the user-loader is called, so the ``user_id``
in ``sub`` and the ``tenant_id`` in ``tid`` are trusted.

``get_current_user`` (shared/auth/dependencies.py) calls the loader as
``loader(claims.user_id)`` and only uses the returned ``CurrentUser`` to
check ``status == "active"`` and to attach the user to the request.
Tenant scoping happens via ``_set_tenant_context(claims.tenant_id)``
which reads the JWT directly — independent of the loader output.

**tenant_id threading fix (B10-w5):** get_current_user() now sets
``_current_request_tenant_id`` from the JWT ``tid`` claim BEFORE calling
the loader.  This loader reads that contextvar so CurrentUser.tenant_id
matches the real tenant.  Without this, billing's validate_tenant_id()
compared x-tenant-id (correct) against CurrentUser.tenant_id=user_id
(wrong) → HTTP 403.

Production refuses to enable this path: ``configure_auth_trust_jwt``
raises ``RuntimeError`` if ``INFINITYRX_ENV`` is ``production``. Every
production deployment of a directory backend must wire a real
``UserLoader`` against a real users table (or upstream identity API)
instead.
"""

from __future__ import annotations

import os
import uuid

from shared.auth.dependencies import (
    CurrentUser,
    _current_request_tenant_id,
    configure_auth,
)
from shared.auth.tokens_repo import InMemoryRevokedTokenRepo


def configure_auth_trust_jwt(default_email: str = "dev@infinityrx.local") -> None:
    """Bind a no-DB user-loader for dev/test directory backends.

    Refuses to run in production (raises ``RuntimeError``).
    """
    env = os.getenv("INFINITYRX_ENV", "development").strip().lower()
    if env == "production":
        raise RuntimeError(
            "configure_auth_trust_jwt() must not run in production. "
            "Wire configure_auth() with a real UserLoader instead."
        )

    def loader(user_id: uuid.UUID) -> CurrentUser:
        # Read the JWT tid claim from the request-scoped contextvar set by
        # get_current_user() before calling this loader.  Falls back to
        # user_id only when the contextvar is unset (e.g. direct unit-test
        # calls that don't go through get_current_user).
        tid = _current_request_tenant_id.get()
        tenant_id = tid if tid is not None else user_id

        # Include module-specific roles so the dev user passes per-module RBAC
        # gates: operator/approver for billing's upload gate; reclaimrx.admin
        # (top of the reclaimrx.admin > investigator > viewer hierarchy) for the
        # reclaimrx detection console read/write gates.
        return CurrentUser(
            id=user_id,
            tenant_id=tenant_id,
            email=default_email,
            status="active",
            roles=("platform_admin", "operator", "approver", "reclaimrx.admin"),
            permissions=("*",),
        )

    configure_auth(loader, InMemoryRevokedTokenRepo())


__all__ = ["configure_auth_trust_jwt"]
