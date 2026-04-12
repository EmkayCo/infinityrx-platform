"""Role and permission endpoint tests."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from src.auth._models import Role
from tests.auth.conftest import auth_header_for


class TestListRoles:
    def test_list_includes_system_roles(self, client, admin_a) -> None:
        r = client.get("/api/v1/roles", headers=auth_header_for(admin_a))
        assert r.status_code == 200
        names = {x["name"] for x in r.json()}
        assert "platform_admin" in names
        assert "tenant_admin" in names

    def test_list_excludes_other_tenants_custom_roles(
        self, client, db, admin_a, admin_b
    ) -> None:
        custom = Role(tenant_id=admin_b.tenant_id, name="custom_b", is_system=False)
        db.add(custom)
        db.commit()
        r = client.get("/api/v1/roles", headers=auth_header_for(admin_a))
        names = {x["name"] for x in r.json()}
        assert "custom_b" not in names


class TestCreateRole:
    def test_create_ok(self, client, admin_a) -> None:
        r = client.post(
            "/api/v1/roles",
            json={"name": "custom_a", "description": "A"},
            headers=auth_header_for(admin_a),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["is_system"] is False
        assert body["name"] == "custom_a"

    def test_duplicate_409(self, client, admin_a) -> None:
        p = {"name": "dup", "description": None}
        client.post("/api/v1/roles", json=p, headers=auth_header_for(admin_a))
        r = client.post("/api/v1/roles", json=p, headers=auth_header_for(admin_a))
        assert r.status_code == 409

    def test_non_admin_forbidden(self, client, viewer_a) -> None:
        r = client.post(
            "/api/v1/roles",
            json={"name": "x", "description": None},
            headers=auth_header_for(viewer_a),
        )
        assert r.status_code == 403


class TestUpdateRole:
    def test_update_custom_role(self, client, db, admin_a) -> None:
        r = client.post(
            "/api/v1/roles",
            json={"name": "custom_u", "description": "A"},
            headers=auth_header_for(admin_a),
        )
        rid = r.json()["id"]
        r2 = client.put(
            f"/api/v1/roles/{rid}",
            json={"description": "B"},
            headers=auth_header_for(admin_a),
        )
        assert r2.status_code == 200
        assert r2.json()["description"] == "B"

    def test_cannot_modify_system_role(self, client, db, admin_a) -> None:
        sys_role = db.scalars(select(Role).where(Role.name == "tenant_admin")).one()
        r = client.put(
            f"/api/v1/roles/{sys_role.id}",
            json={"description": "nope"},
            headers=auth_header_for(admin_a),
        )
        assert r.status_code == 403

    def test_update_missing_404(self, client, admin_a) -> None:
        r = client.put(
            f"/api/v1/roles/{uuid.uuid4()}",
            json={"description": "x"},
            headers=auth_header_for(admin_a),
        )
        assert r.status_code == 404

    def test_cannot_update_other_tenant_role(self, client, db, admin_a, admin_b) -> None:
        other = Role(tenant_id=admin_b.tenant_id, name="crossed", is_system=False)
        db.add(other)
        db.commit()
        r = client.put(
            f"/api/v1/roles/{other.id}",
            json={"description": "x"},
            headers=auth_header_for(admin_a),
        )
        assert r.status_code == 404


class TestRolePermissions:
    def test_assign_permissions(self, client, admin_a) -> None:
        r = client.post(
            "/api/v1/roles",
            json={"name": "perm_role", "description": None},
            headers=auth_header_for(admin_a),
        )
        rid = r.json()["id"]
        r2 = client.put(
            f"/api/v1/roles/{rid}/permissions",
            json={"permissions": ["users:read", "audit:read"]},
            headers=auth_header_for(admin_a),
        )
        assert r2.status_code == 200
        assert sorted(r2.json()["permissions"]) == ["audit:read", "users:read"]

    def test_unknown_permission_404(self, client, admin_a) -> None:
        r = client.post(
            "/api/v1/roles",
            json={"name": "perm_role2", "description": None},
            headers=auth_header_for(admin_a),
        )
        rid = r.json()["id"]
        r2 = client.put(
            f"/api/v1/roles/{rid}/permissions",
            json={"permissions": ["fake:thing"]},
            headers=auth_header_for(admin_a),
        )
        assert r2.status_code == 404

    def test_malformed_permission_404(self, client, admin_a) -> None:
        r = client.post(
            "/api/v1/roles",
            json={"name": "perm_role3", "description": None},
            headers=auth_header_for(admin_a),
        )
        rid = r.json()["id"]
        r2 = client.put(
            f"/api/v1/roles/{rid}/permissions",
            json={"permissions": ["malformed"]},
            headers=auth_header_for(admin_a),
        )
        assert r2.status_code == 404

    def test_cannot_assign_to_system_role(self, client, db, admin_a) -> None:
        sys_role = db.scalars(select(Role).where(Role.name == "tenant_viewer")).one()
        r = client.put(
            f"/api/v1/roles/{sys_role.id}/permissions",
            json={"permissions": ["core:read"]},
            headers=auth_header_for(admin_a),
        )
        assert r.status_code == 403

    def test_perms_missing_role_404(self, client, admin_a) -> None:
        r = client.put(
            f"/api/v1/roles/{uuid.uuid4()}/permissions",
            json={"permissions": ["core:read"]},
            headers=auth_header_for(admin_a),
        )
        assert r.status_code == 404

    def test_perms_other_tenant_role_404(self, client, db, admin_a, admin_b) -> None:
        other = Role(tenant_id=admin_b.tenant_id, name="cross_perm", is_system=False)
        db.add(other)
        db.commit()
        r = client.put(
            f"/api/v1/roles/{other.id}/permissions",
            json={"permissions": ["core:read"]},
            headers=auth_header_for(admin_a),
        )
        assert r.status_code == 404


class TestListPermissions:
    def test_lists_default_permissions(self, client, admin_a) -> None:
        r = client.get("/api/v1/permissions", headers=auth_header_for(admin_a))
        assert r.status_code == 200
        codes = {p["code"] for p in r.json()}
        assert "core:read" in codes
        assert "users:write" in codes
