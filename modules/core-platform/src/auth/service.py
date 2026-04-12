"""Auth service layer — login, user CRUD, role management.

Pure functions over a SQLAlchemy ``Session``; the HTTP layer in
``src.auth.api`` is a thin adapter. All mutations emit audit events via
the injected ``AuditSink`` so audit logging is enforced at the service
boundary rather than scattered across route handlers.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.auth.passwords import hash_password, verify_password
from src.auth._models import Permission, Role, User, UserRole
from src.auth.audit_sink import AuditSink, make_event

MAX_FAILED_LOGINS = 5


class AuthServiceError(Exception):
    """Base class for service-layer errors."""


class InvalidCredentialsError(AuthServiceError):
    """Generic login failure — message must not leak which field was wrong."""


class AccountLockedError(AuthServiceError):
    pass


class AccountInactiveError(AuthServiceError):
    pass


class NotFoundError(AuthServiceError):
    pass


class ConflictError(AuthServiceError):
    pass


class ForbiddenError(AuthServiceError):
    pass


@dataclass(frozen=True)
class AuthenticatedUser:
    user: User
    roles: list[str]
    permissions: list[str]


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _user_roles(user: User) -> list[str]:
    return sorted(r.name for r in user.roles)


def _user_permissions(user: User) -> list[str]:
    codes: set[str] = set()
    for role in user.roles:
        for perm in role.permissions:
            codes.add(perm.code)
    return sorted(codes)


# ---------------------------------------------------------------------------
# Login / authentication
# ---------------------------------------------------------------------------


def authenticate(
    session: Session,
    *,
    email: str,
    password: str,
    tenant_slug: str | None,
    audit: AuditSink,
) -> AuthenticatedUser:
    """Resolve credentials to an AuthenticatedUser or raise.

    Always raises the same ``InvalidCredentialsError`` for unknown email,
    wrong password, locked, or inactive accounts to avoid user
    enumeration. The underlying failure mode is captured in the audit
    event so operators can still see why a login failed.
    """
    email_norm = email.strip().lower()

    q = select(User).where(User.email == email_norm)
    if tenant_slug:
        from src.auth._models import Tenant

        q = q.join(Tenant, Tenant.id == User.tenant_id).where(Tenant.slug == tenant_slug)

    users = session.scalars(q).all()
    if len(users) != 1:
        audit.emit(
            make_event(
                tenant_id=None,
                user_id=None,
                action="login.failed",
                entity_type="user",
                entity_id=email_norm,
                after={"reason": "not_found"},
            )
        )
        raise InvalidCredentialsError("invalid credentials")
    user = users[0]

    if user.status == "locked":
        audit.emit(
            make_event(
                tenant_id=user.tenant_id,
                user_id=user.id,
                action="login.failed",
                entity_type="user",
                entity_id=str(user.id),
                after={"reason": "locked"},
            )
        )
        raise InvalidCredentialsError("invalid credentials")
    if user.status != "active":
        audit.emit(
            make_event(
                tenant_id=user.tenant_id,
                user_id=user.id,
                action="login.failed",
                entity_type="user",
                entity_id=str(user.id),
                after={"reason": "inactive"},
            )
        )
        raise InvalidCredentialsError("invalid credentials")

    if not verify_password(password, user.password_hash):
        user.failed_login_count = (user.failed_login_count or 0) + 1
        reason = "bad_password"
        if user.failed_login_count >= MAX_FAILED_LOGINS:
            user.status = "locked"
            reason = "locked_after_failures"
        session.commit()
        audit.emit(
            make_event(
                tenant_id=user.tenant_id,
                user_id=user.id,
                action="login.failed",
                entity_type="user",
                entity_id=str(user.id),
                after={"reason": reason, "failed_count": user.failed_login_count},
            )
        )
        raise InvalidCredentialsError("invalid credentials")

    user.failed_login_count = 0
    user.last_login_at = _now()
    session.commit()

    audit.emit(
        make_event(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="login.success",
            entity_type="user",
            entity_id=str(user.id),
        )
    )

    return AuthenticatedUser(
        user=user,
        roles=_user_roles(user),
        permissions=_user_permissions(user),
    )


def load_authenticated(session: Session, user_id: uuid.UUID) -> AuthenticatedUser | None:
    """Load a user + roles + permissions for the get_current_user dep."""
    user = session.get(User, user_id)
    if user is None:
        return None
    return AuthenticatedUser(
        user=user,
        roles=_user_roles(user),
        permissions=_user_permissions(user),
    )


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------


def create_user(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    email: str,
    display_name: str,
    password: str,
    role_names: list[str],
    actor_id: uuid.UUID | None,
    audit: AuditSink,
) -> User:
    email_norm = email.strip().lower()
    existing = session.scalars(
        select(User).where(User.tenant_id == tenant_id, User.email == email_norm)
    ).one_or_none()
    if existing is not None:
        raise ConflictError(f"user with email {email_norm} already exists")
    user = User(
        tenant_id=tenant_id,
        email=email_norm,
        display_name=display_name,
        password_hash=hash_password(password),
        status="active",
    )
    session.add(user)
    session.flush()

    if role_names:
        _assign_roles(session, user, role_names)
    session.commit()

    audit.emit(
        make_event(
            tenant_id=tenant_id,
            user_id=actor_id,
            action="user.created",
            entity_type="user",
            entity_id=str(user.id),
            after={"email": user.email, "roles": _user_roles(user)},
        )
    )
    return user


def list_users(session: Session, tenant_id: uuid.UUID) -> list[User]:
    return list(
        session.scalars(
            select(User).where(User.tenant_id == tenant_id).order_by(User.created_at)
        ).all()
    )


def get_user(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User:
    user = session.get(User, user_id)
    if user is None or user.tenant_id != tenant_id:
        raise NotFoundError("user not found")
    return user


def update_user(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    display_name: str | None,
    status: str | None,
    actor_id: uuid.UUID | None,
    audit: AuditSink,
) -> User:
    user = get_user(session, tenant_id, user_id)
    before = {"display_name": user.display_name, "status": user.status}
    if display_name is not None:
        user.display_name = display_name
    if status is not None:
        user.status = status
    session.commit()
    audit.emit(
        make_event(
            tenant_id=tenant_id,
            user_id=actor_id,
            action="user.updated",
            entity_type="user",
            entity_id=str(user.id),
            before=before,
            after={"display_name": user.display_name, "status": user.status},
        )
    )
    return user


def update_me(
    session: Session,
    *,
    user: User,
    display_name: str | None,
    audit: AuditSink,
) -> User:
    before = {"display_name": user.display_name}
    if display_name is not None:
        user.display_name = display_name
    session.commit()
    audit.emit(
        make_event(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="user.self_updated",
            entity_type="user",
            entity_id=str(user.id),
            before=before,
            after={"display_name": user.display_name},
        )
    )
    return user


def _assign_roles(session: Session, user: User, role_names: list[str]) -> None:
    session.query(UserRole).filter(UserRole.user_id == user.id).delete()
    session.flush()
    for name in role_names:
        role = session.scalars(
            select(Role).where(
                Role.name == name,
                (Role.tenant_id == user.tenant_id) | (Role.tenant_id.is_(None)),
            )
        ).first()
        if role is None:
            raise NotFoundError(f"role '{name}' not found")
        session.add(UserRole(user_id=user.id, role_id=role.id))
    session.flush()
    session.refresh(user)


def assign_user_roles(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role_names: list[str],
    actor_id: uuid.UUID | None,
    audit: AuditSink,
) -> User:
    user = get_user(session, tenant_id, user_id)
    before = _user_roles(user)
    _assign_roles(session, user, role_names)
    session.commit()
    audit.emit(
        make_event(
            tenant_id=tenant_id,
            user_id=actor_id,
            action="user.roles_changed",
            entity_type="user",
            entity_id=str(user.id),
            before={"roles": before},
            after={"roles": _user_roles(user)},
        )
    )
    return user


def lock_user(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    audit: AuditSink,
) -> User:
    user = get_user(session, tenant_id, user_id)
    before = {"status": user.status}
    user.status = "locked"
    session.commit()
    audit.emit(
        make_event(
            tenant_id=tenant_id,
            user_id=actor_id,
            action="user.locked",
            entity_type="user",
            entity_id=str(user.id),
            before=before,
            after={"status": user.status},
        )
    )
    return user


def unlock_user(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    audit: AuditSink,
) -> User:
    user = get_user(session, tenant_id, user_id)
    before = {"status": user.status, "failed_login_count": user.failed_login_count}
    user.status = "active"
    user.failed_login_count = 0
    session.commit()
    audit.emit(
        make_event(
            tenant_id=tenant_id,
            user_id=actor_id,
            action="user.unlocked",
            entity_type="user",
            entity_id=str(user.id),
            before=before,
            after={"status": user.status, "failed_login_count": 0},
        )
    )
    return user


# ---------------------------------------------------------------------------
# Roles & permissions
# ---------------------------------------------------------------------------


def list_roles(session: Session, tenant_id: uuid.UUID) -> list[Role]:
    stmt = select(Role).where((Role.tenant_id == tenant_id) | (Role.tenant_id.is_(None)))
    return list(session.scalars(stmt).all())


def create_role(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    name: str,
    description: str | None,
    actor_id: uuid.UUID | None,
    audit: AuditSink,
) -> Role:
    existing = session.scalars(
        select(Role).where(Role.tenant_id == tenant_id, Role.name == name)
    ).one_or_none()
    if existing is not None:
        raise ConflictError(f"role '{name}' already exists")
    role = Role(
        tenant_id=tenant_id,
        name=name,
        description=description,
        is_system=False,
    )
    session.add(role)
    session.commit()
    audit.emit(
        make_event(
            tenant_id=tenant_id,
            user_id=actor_id,
            action="role.created",
            entity_type="role",
            entity_id=str(role.id),
            after={"name": name},
        )
    )
    return role


def update_role(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    role_id: uuid.UUID,
    description: str | None,
    actor_id: uuid.UUID | None,
    audit: AuditSink,
) -> Role:
    role = session.get(Role, role_id)
    if role is None:
        raise NotFoundError("role not found")
    if role.is_system:
        raise ForbiddenError("system roles cannot be modified")
    if role.tenant_id != tenant_id:
        raise NotFoundError("role not found")
    before = {"description": role.description}
    role.description = description
    session.commit()
    audit.emit(
        make_event(
            tenant_id=tenant_id,
            user_id=actor_id,
            action="role.updated",
            entity_type="role",
            entity_id=str(role.id),
            before=before,
            after={"description": role.description},
        )
    )
    return role


def assign_role_permissions(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    role_id: uuid.UUID,
    permission_codes: list[str],
    actor_id: uuid.UUID | None,
    audit: AuditSink,
) -> Role:
    role = session.get(Role, role_id)
    if role is None:
        raise NotFoundError("role not found")
    if role.is_system:
        raise ForbiddenError("system role permissions cannot be modified")
    if role.tenant_id != tenant_id:
        raise NotFoundError("role not found")
    before = sorted(p.code for p in role.permissions)

    perms: list[Permission] = []
    for code in permission_codes:
        try:
            module, action = code.split(":", 1)
        except ValueError as exc:
            raise NotFoundError(f"invalid permission code '{code}'") from exc
        perm = session.scalars(
            select(Permission).where(Permission.module == module, Permission.action == action)
        ).one_or_none()
        if perm is None:
            raise NotFoundError(f"permission '{code}' not found")
        perms.append(perm)

    role.permissions = perms
    session.commit()
    audit.emit(
        make_event(
            tenant_id=tenant_id,
            user_id=actor_id,
            action="role.permissions_changed",
            entity_type="role",
            entity_id=str(role.id),
            before={"permissions": before},
            after={"permissions": sorted(p.code for p in role.permissions)},
        )
    )
    return role


def list_permissions(session: Session) -> list[Permission]:
    return list(session.scalars(select(Permission).order_by(Permission.module, Permission.action)).all())
