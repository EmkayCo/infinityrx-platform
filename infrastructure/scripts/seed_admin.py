"""Seed the InfinityRx tenant, platform_admin role, and admin users.

Local-dev only. The `core.users` table stores Azure AD OIDs — there is no
`password_hash` column. Production authenticates via Azure AD SSO; local
dev uses the JWT bypass (JWT_SECRET signs a token claiming one of these
user UUIDs) or the NEXT_PUBLIC_DEV_AUTH_BYPASS portal flag.

Idempotent: safe to re-run.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy import create_engine, text  # noqa: E402

# Force sync psycopg driver for this one-off script.
DB_URL = os.environ.get(
    "DATABASE_URL_SEED",
    "postgresql://infinityrx:infinityrx_dev@localhost:5432/infinityrx",
)

TENANT_ID = "a0000000-0000-0000-0000-000000000001"
ADMIN_ID = "b0000000-0000-0000-0000-000000000001"
MIKE_ID = "b0000000-0000-0000-0000-000000000002"
PLATFORM_ADMIN_ROLE_ID = "c0000000-0000-0000-0000-000000000001"


def seed() -> None:
    engine = create_engine(DB_URL, future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO core.tenants (id, name, slug, display_name)
                VALUES (:id, :name, :slug, :name)
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """
            ),
            {"id": TENANT_ID, "name": "InfinityRx", "slug": "infinityrx"},
        )

        conn.execute(
            text(
                """
                INSERT INTO core.roles (id, tenant_id, name, description, is_system)
                VALUES (:id, :tenant_id, 'platform_admin', 'Full platform administrator', true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": PLATFORM_ADMIN_ROLE_ID, "tenant_id": TENANT_ID},
        )

        for user_id, email, display_name in [
            (ADMIN_ID, "admin@infinityrx.com", "Platform Admin"),
            (MIKE_ID, "mike@emkayco.com", "Mike Kaplan"),
        ]:
            conn.execute(
                text(
                    """
                    INSERT INTO core.users (
                        id, tenant_id, email, display_name, status, mfa_enabled
                    ) VALUES (
                        :id, :tenant_id, :email, :display_name, 'active', false
                    )
                    ON CONFLICT (id) DO UPDATE
                        SET display_name = EXCLUDED.display_name,
                            email = EXCLUDED.email
                    """
                ),
                {
                    "id": user_id,
                    "tenant_id": TENANT_ID,
                    "email": email,
                    "display_name": display_name,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO core.user_roles (user_id, role_id)
                    VALUES (:user_id, :role_id)
                    ON CONFLICT (user_id, role_id) DO NOTHING
                    """
                ),
                {"user_id": user_id, "role_id": PLATFORM_ADMIN_ROLE_ID},
            )

    print("OK — seeded InfinityRx tenant + 2 admin users + platform_admin role")
    print(f"  Tenant:  {TENANT_ID}  InfinityRx (slug: infinityrx)")
    print(f"  User:    {ADMIN_ID}  admin@infinityrx.com")
    print(f"  User:    {MIKE_ID}  mike@emkayco.com")
    print("  Role:    platform_admin")
    print()
    print("Auth: core.users has no password column (Azure AD in prod).")
    print("Local dev: use NEXT_PUBLIC_DEV_AUTH_BYPASS=true in portal/.env.local")


if __name__ == "__main__":
    seed()
