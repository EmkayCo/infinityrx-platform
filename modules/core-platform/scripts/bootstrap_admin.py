"""Bootstrap the first platform admin (and Mike's account).

One-time CLI run against a fresh core-platform database. Creates a
tenant, seeds the system roles, and inserts the first ``platform_admin``
user so the operator portal has something to log in with. Refuses to
run if the ``users`` table already contains any rows — this is a first-
run tool, not a user-management command.

Usage
-----

    DATABASE_URL=postgresql://... \
        python modules/core-platform/scripts/bootstrap_admin.py \
        --email admin@infinityrx.com \
        --tenant-name InfinityRx

If ``--password`` / ``--mike-password`` are omitted the script prompts
for them (no echo, confirms by re-entry). Minimum length enforced by
``UserCreate`` and bcrypt is 8 characters.

Why a CLI and not an HTTP endpoint
----------------------------------

``POST /users`` on core-platform requires a ``tenant_admin_only``
caller, so there is a chicken-and-egg problem: no admin exists to
create the first admin. A self-bootstrap HTTP endpoint would need a
"no users yet" guard that is bulletproof even under replay, which is
riskier than running a script once against the database directly.

Scope
-----

- Creates or reuses a tenant with the given name.
- Seeds the 10 system roles (idempotent; safe on reruns).
- Creates the primary admin and mike@emkayco.com, both with the
  ``platform_admin`` role.
- Prints a summary with tenant/user IDs and next-step commands.

This does not emit audit events. The audit middleware only runs inside
a live FastAPI request, and the bootstrap happens before anyone can
authenticate, so there is nothing meaningful to write to an audit log
that itself has no actor.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
import uuid
from pathlib import Path

# Path setup: the script is invoked directly from the repo root
# (``python modules/core-platform/scripts/bootstrap_admin.py``), so we need
# both the repo root (for ``shared.*``) and the module root (for ``src.*``)
# on sys.path before any project imports. The existing
# ``python -m src.auth.seed.system_roles`` entrypoint assumes cwd is the
# module root; we replicate that plus the sibling ``shared/`` package.
_MODULE_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _MODULE_ROOT.parent.parent
for _p in (_REPO_ROOT, _MODULE_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

# Import the leaf modules directly to avoid pulling in the FastAPI router
# graph (``src.auth.__init__`` imports ``auth_api_router`` which drags in
# the whole app). The bootstrap runs against an ORM session, not a request.
from src.auth._models import Base, Tenant, User  # noqa: E402
from src.auth.audit_sink import InMemoryAuditSink  # noqa: E402
from src.auth.seed.system_roles import seed_system_roles  # noqa: E402
from src.auth.service import ConflictError, create_user  # noqa: E402

MIKE_EMAIL = "mike@emkayco.com"
DEFAULT_ADMIN_EMAIL = "admin@infinityrx.com"
DEFAULT_TENANT_NAME = "InfinityRx"
PLATFORM_ADMIN_ROLE = "platform_admin"
MIN_PASSWORD_LENGTH = 8


class BootstrapError(RuntimeError):
    """Raised when the bootstrap cannot proceed. Always fatal."""


def _slugify(name: str) -> str:
    """Lowercase, alphanumeric + dashes. Falls back to 'tenant' if empty."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "tenant"


def _prompt_password(label: str) -> str:
    """Prompt with confirmation. Non-interactive sessions raise."""
    if not sys.stdin.isatty():
        raise BootstrapError(
            f"{label} not provided and stdin is not a TTY. "
            f"Pass the password via the matching --*password flag."
        )
    while True:
        p1 = getpass.getpass(f"{label}: ")
        if len(p1) < MIN_PASSWORD_LENGTH:
            print(
                f"  password must be at least {MIN_PASSWORD_LENGTH} characters",
                file=sys.stderr,
            )
            continue
        p2 = getpass.getpass(f"{label} (confirm): ")
        if p1 != p2:
            print("  passwords did not match", file=sys.stderr)
            continue
        return p1


def _resolve_password(flag_value: str | None, label: str) -> str:
    if flag_value is None:
        return _prompt_password(label)
    if len(flag_value) < MIN_PASSWORD_LENGTH:
        raise BootstrapError(
            f"{label} must be at least {MIN_PASSWORD_LENGTH} characters"
        )
    return flag_value


def _ensure_users_table_empty(session: Session) -> None:
    count = session.scalar(select(func.count()).select_from(User))
    if count and count > 0:
        raise BootstrapError(
            f"refusing to bootstrap: users table already has {count} row(s). "
            f"This script only runs on a fresh database. Use the portal or "
            f"POST /users to create additional accounts."
        )


def _ensure_tenant(session: Session, *, name: str, slug: str) -> Tenant:
    existing = session.scalars(
        select(Tenant).where(Tenant.name == name)
    ).one_or_none()
    if existing is not None:
        return existing
    # Slug must be unique — if a tenant with this slug already exists under
    # a different name, surface a clear error instead of raising a cryptic
    # integrity error on flush.
    slug_collision = session.scalars(
        select(Tenant).where(Tenant.slug == slug)
    ).one_or_none()
    if slug_collision is not None:
        raise BootstrapError(
            f"tenant slug '{slug}' is already in use by tenant "
            f"'{slug_collision.name}'. Pass --tenant-slug to disambiguate."
        )
    tenant = Tenant(
        id=uuid.uuid4(),
        name=name,
        slug=slug,
        status="active",
        mfa_required=False,
    )
    session.add(tenant)
    session.flush()
    return tenant


def _create_admin(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    email: str,
    display_name: str,
    password: str,
) -> User:
    audit = InMemoryAuditSink()
    try:
        return create_user(
            session,
            tenant_id=tenant_id,
            email=email,
            display_name=display_name,
            password=password,
            role_names=[PLATFORM_ADMIN_ROLE],
            actor_id=None,
            audit=audit,
        )
    except ConflictError as exc:
        # Should be unreachable because of the empty-table guard, but if the
        # same CLI is invoked twice within the same transaction this is the
        # safest way to fail.
        raise BootstrapError(str(exc)) from exc


def bootstrap(
    *,
    database_url: str,
    admin_email: str,
    admin_password: str,
    admin_display_name: str,
    tenant_name: str,
    tenant_slug: str,
    mike_password: str,
) -> dict[str, str]:
    """Run the full bootstrap against the given database URL.

    Returns a summary dict with stringified IDs. Raises
    :class:`BootstrapError` on any safety violation.
    """
    connect_args = (
        {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
    engine = create_engine(database_url, future=True, connect_args=connect_args)

    # On Postgres this is a no-op if the schema already exists. On SQLite
    # (used for local smoke-testing the script itself) it creates the
    # tables. Alembic migrations remain the source of truth in production.
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with SessionLocal() as session:
        _ensure_users_table_empty(session)

        tenant = _ensure_tenant(session, name=tenant_name, slug=tenant_slug)
        session.commit()

        seed_system_roles(session)

        primary = _create_admin(
            session,
            tenant_id=tenant.id,
            email=admin_email,
            display_name=admin_display_name,
            password=admin_password,
        )

        mike = _create_admin(
            session,
            tenant_id=tenant.id,
            email=MIKE_EMAIL,
            display_name="Mike Konstantinides",
            password=mike_password,
        )

    return {
        "tenant_id": str(tenant.id),
        "tenant_name": tenant.name,
        "tenant_slug": tenant.slug,
        "admin_id": str(primary.id),
        "admin_email": primary.email,
        "mike_id": str(mike.id),
        "mike_email": mike.email,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bootstrap_admin",
        description="Create the first platform_admin user on a fresh core-platform DB.",
    )
    parser.add_argument(
        "--email",
        default=DEFAULT_ADMIN_EMAIL,
        help=f"primary admin email (default: {DEFAULT_ADMIN_EMAIL})",
    )
    parser.add_argument(
        "--display-name",
        default="Platform Admin",
        help="primary admin display name (default: 'Platform Admin')",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="primary admin password. If omitted, you will be prompted.",
    )
    parser.add_argument(
        "--mike-password",
        default=None,
        help="password for the seeded mike@emkayco.com account. If omitted, prompted.",
    )
    parser.add_argument(
        "--tenant-name",
        default=DEFAULT_TENANT_NAME,
        help=f"tenant name (default: {DEFAULT_TENANT_NAME})",
    )
    parser.add_argument(
        "--tenant-slug",
        default=None,
        help="tenant slug. Derived from --tenant-name if omitted.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy database URL. Falls back to $DATABASE_URL.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "error: DATABASE_URL env var or --database-url flag is required",
            file=sys.stderr,
        )
        return 2

    tenant_slug = args.tenant_slug or _slugify(args.tenant_name)

    try:
        admin_password = _resolve_password(args.password, "Admin password")
        mike_password = _resolve_password(args.mike_password, "Mike's password")

        summary = bootstrap(
            database_url=database_url,
            admin_email=args.email,
            admin_password=admin_password,
            admin_display_name=args.display_name,
            tenant_name=args.tenant_name,
            tenant_slug=tenant_slug,
            mike_password=mike_password,
        )
    except BootstrapError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print()
    print("Bootstrap complete.")
    print(f"  tenant      {summary['tenant_name']} ({summary['tenant_slug']})")
    print(f"              id: {summary['tenant_id']}")
    print(f"  admin       {summary['admin_email']}")
    print(f"              id: {summary['admin_id']}")
    print(f"              role: {PLATFORM_ADMIN_ROLE}")
    print(f"  mike        {summary['mike_email']}")
    print(f"              id: {summary['mike_id']}")
    print(f"              role: {PLATFORM_ADMIN_ROLE}")
    print()
    print("Next: log in at /login with the admin email and password you just set.")
    print("Create additional users from /admin/users in the portal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
