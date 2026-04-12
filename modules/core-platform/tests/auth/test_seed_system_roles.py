"""Tests for the system-roles seeder."""

from __future__ import annotations

from sqlalchemy import select

from src.auth._models import Permission, Role, RolePermission
from src.auth.seed.system_roles import (
    DEFAULT_PERMISSIONS,
    ROLE_PERMISSION_MATRIX,
    SYSTEM_ROLE_NAMES,
    seed_system_roles,
)


def test_creates_all_10_system_roles(db) -> None:
    seed_system_roles(db)
    names = [r.name for r in db.scalars(select(Role).where(Role.is_system.is_(True))).all()]
    assert sorted(names) == sorted(SYSTEM_ROLE_NAMES)
    assert len(names) == 10


def test_creates_all_default_permissions(db) -> None:
    seed_system_roles(db)
    codes = {f"{p.module}:{p.action}" for p in db.scalars(select(Permission)).all()}
    expected = {f"{m}:{a}" for (m, a, _) in DEFAULT_PERMISSIONS}
    assert codes == expected


def test_platform_admin_has_every_permission(db) -> None:
    seed_system_roles(db)
    role = db.scalars(select(Role).where(Role.name == "platform_admin")).one()
    codes = {p.code for p in role.permissions}
    assert codes == {f"{m}:{a}" for (m, a, _) in DEFAULT_PERMISSIONS}


def test_member_has_minimal_permissions(db) -> None:
    seed_system_roles(db)
    role = db.scalars(select(Role).where(Role.name == "member")).one()
    assert {p.code for p in role.permissions} == {"core:read"}


def test_idempotent(db) -> None:
    seed_system_roles(db)
    first_roles = db.scalars(select(Role)).all()
    first_perms = db.scalars(select(Permission)).all()
    first_rp = db.scalars(select(RolePermission)).all()

    seed_system_roles(db)
    second_roles = db.scalars(select(Role)).all()
    second_perms = db.scalars(select(Permission)).all()
    second_rp = db.scalars(select(RolePermission)).all()

    assert len(first_roles) == len(second_roles)
    assert len(first_perms) == len(second_perms)
    assert len(first_rp) == len(second_rp)


def test_all_roles_are_tenant_null(db) -> None:
    seed_system_roles(db)
    for r in db.scalars(select(Role).where(Role.is_system.is_(True))).all():
        assert r.tenant_id is None


def test_matrix_covers_all_system_role_names() -> None:
    assert set(ROLE_PERMISSION_MATRIX.keys()) == set(SYSTEM_ROLE_NAMES)
