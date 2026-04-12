"""Idempotent seeder for the 10 default system roles and their permissions.

The 10 system roles are defined by PRD section 2.2 (comment block). Each
is created with ``is_system=True`` and ``tenant_id=NULL``. Permissions
follow a curated matrix — each role receives the minimum set of
``module:action`` codes needed to perform its job. The matrix lives in
this module so tenants inherit sensible defaults; platform operators may
clone a system role into a tenant-local custom role for finer tuning.

Run as a CLI:

    python -m src.auth.seed.system_roles

or programmatically via ``seed_system_roles(session)``. The operation is
idempotent: running it twice produces the same row set.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth._models import Permission, Role, RolePermission

SYSTEM_ROLE_NAMES: tuple[str, ...] = (
    "platform_admin",
    "tenant_admin",
    "tenant_operator",
    "tenant_viewer",
    "client_admin",
    "client_viewer",
    "pharmacy_admin",
    "pharmacy_viewer",
    "provider_admin",
    "member",
)

ROLE_DESCRIPTIONS: dict[str, str] = {
    "platform_admin": "InfinityRx super admin — all tenants, all modules",
    "tenant_admin": "Admin for a tenant — all modules within tenant",
    "tenant_operator": "Runs operations (billing, imports) within tenant",
    "tenant_viewer": "Read-only access within tenant",
    "client_admin": "External client admin — their data only",
    "client_viewer": "External client viewer — read-only",
    "pharmacy_admin": "Pharmacy user — their claims/payments",
    "pharmacy_viewer": "Pharmacy read-only",
    "provider_admin": "Medical provider — their claims",
    "member": "Patient/member — their own data only",
}

# (module, action, description)
DEFAULT_PERMISSIONS: tuple[tuple[str, str, str], ...] = (
    ("core", "read", "Read core platform data"),
    ("core", "write", "Modify core platform data"),
    ("core", "admin", "Administer core platform"),
    ("users", "read", "Read user accounts"),
    ("users", "write", "Create/update/delete users"),
    ("audit", "read", "Query audit log"),
    ("audit", "export", "Export audit log"),
    ("jobs", "read", "View scheduled jobs"),
    ("jobs", "run", "Trigger job runs"),
    ("files", "read", "Download files"),
    ("files", "write", "Upload/delete files"),
    ("exclusions", "read", "View exclusion matches"),
    ("exclusions", "review", "Review and dispose exclusion matches"),
)

# Matrix of role -> set of (module:action) codes.
ROLE_PERMISSION_MATRIX: dict[str, frozenset[str]] = {
    "platform_admin": frozenset(
        f"{m}:{a}" for (m, a, _) in DEFAULT_PERMISSIONS
    ),
    "tenant_admin": frozenset(
        {
            "core:read",
            "core:write",
            "users:read",
            "users:write",
            "audit:read",
            "audit:export",
            "jobs:read",
            "jobs:run",
            "files:read",
            "files:write",
            "exclusions:read",
            "exclusions:review",
        }
    ),
    "tenant_operator": frozenset(
        {
            "core:read",
            "core:write",
            "users:read",
            "audit:read",
            "jobs:read",
            "jobs:run",
            "files:read",
            "files:write",
            "exclusions:read",
        }
    ),
    "tenant_viewer": frozenset(
        {"core:read", "users:read", "audit:read", "jobs:read", "files:read", "exclusions:read"}
    ),
    "client_admin": frozenset(
        {"core:read", "users:read", "files:read", "files:write", "audit:read"}
    ),
    "client_viewer": frozenset({"core:read", "files:read"}),
    "pharmacy_admin": frozenset(
        {"core:read", "users:read", "files:read", "files:write"}
    ),
    "pharmacy_viewer": frozenset({"core:read", "files:read"}),
    "provider_admin": frozenset(
        {"core:read", "users:read", "files:read", "files:write"}
    ),
    "member": frozenset({"core:read"}),
}


def _ensure_permissions(session: Session) -> dict[str, Permission]:
    existing: dict[str, Permission] = {
        p.code: p for p in session.scalars(select(Permission)).all()
    }
    for module, action, desc in DEFAULT_PERMISSIONS:
        code = f"{module}:{action}"
        if code in existing:
            continue
        perm = Permission(module=module, action=action, description=desc)
        session.add(perm)
        session.flush()
        existing[code] = perm
    return existing


def _ensure_role(session: Session, name: str) -> Role:
    role = session.scalars(
        select(Role).where(Role.name == name, Role.tenant_id.is_(None))
    ).one_or_none()
    if role is None:
        role = Role(
            tenant_id=None,
            name=name,
            description=ROLE_DESCRIPTIONS[name],
            is_system=True,
        )
        session.add(role)
        session.flush()
    return role


def _ensure_role_permissions(
    session: Session, role: Role, perm_codes: frozenset[str], perms: dict[str, Permission]
) -> None:
    existing_ids = {rp.permission_id for rp in session.scalars(
        select(RolePermission).where(RolePermission.role_id == role.id)
    ).all()}
    for code in perm_codes:
        perm = perms[code]
        if perm.id in existing_ids:
            continue
        session.add(RolePermission(role_id=role.id, permission_id=perm.id))


def seed_system_roles(session: Session) -> dict[str, Role]:
    """Create default permissions, system roles, and role-permission links.

    Returns a mapping of role name -> Role. Idempotent: safe to run
    repeatedly; no rows are duplicated.
    """
    perms = _ensure_permissions(session)
    roles: dict[str, Role] = {}
    for name in SYSTEM_ROLE_NAMES:
        role = _ensure_role(session, name)
        _ensure_role_permissions(session, role, ROLE_PERMISSION_MATRIX[name], perms)
        roles[name] = role
    session.commit()
    return roles


def main() -> None:  # pragma: no cover - CLI entrypoint exercised at integration
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.auth._models import Base

    url = os.environ.get("DATABASE_URL", "sqlite:///./seed.sqlite")
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with SessionLocal() as session:
        seed_system_roles(session)
        print(f"Seeded {len(SYSTEM_ROLE_NAMES)} system roles")


if __name__ == "__main__":  # pragma: no cover
    main()
