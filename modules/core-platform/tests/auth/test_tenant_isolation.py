"""Tenant isolation end-to-end checks over every /users endpoint."""

from __future__ import annotations

import pytest

from tests.auth.conftest import auth_header_for


@pytest.fixture
def tenant_b_viewer(db, tenant_b):
    from src.auth._models import User
    from shared.auth.passwords import hash_password
    from src.auth.service import _assign_roles

    u = User(
        tenant_id=tenant_b.id,
        email="view-b@example.com",
        display_name="Viewer B",
        password_hash=hash_password("password123!"),
        status="active",
    )
    db.add(u)
    db.flush()
    _assign_roles(db, u, ["tenant_viewer"])
    db.commit()
    return u


def test_admin_a_list_hides_tenant_b(client, admin_a, admin_b) -> None:
    r = client.get("/api/v1/users", headers=auth_header_for(admin_a))
    emails = {u["email"] for u in r.json()}
    assert "admin-b@example.com" not in emails


def test_admin_a_cannot_get_tenant_b_user(client, admin_a, admin_b) -> None:
    r = client.get(f"/api/v1/users/{admin_b.id}", headers=auth_header_for(admin_a))
    assert r.status_code == 404


def test_admin_a_cannot_update_tenant_b_user(client, admin_a, admin_b) -> None:
    r = client.put(
        f"/api/v1/users/{admin_b.id}",
        json={"display_name": "Pwned"},
        headers=auth_header_for(admin_a),
    )
    assert r.status_code == 404


def test_admin_a_cannot_assign_roles_in_tenant_b(client, admin_a, admin_b) -> None:
    r = client.put(
        f"/api/v1/users/{admin_b.id}/roles",
        json={"role_names": ["tenant_viewer"]},
        headers=auth_header_for(admin_a),
    )
    assert r.status_code == 404


def test_admin_a_cannot_lock_tenant_b_user(client, admin_a, admin_b) -> None:
    r = client.post(
        f"/api/v1/users/{admin_b.id}/lock",
        headers=auth_header_for(admin_a),
    )
    assert r.status_code == 404


def test_admin_a_cannot_unlock_tenant_b_user(client, admin_a, admin_b) -> None:
    r = client.post(
        f"/api/v1/users/{admin_b.id}/unlock",
        headers=auth_header_for(admin_a),
    )
    assert r.status_code == 404


def test_admin_a_viewer_b_invisible_to_lists(client, admin_a, tenant_b_viewer) -> None:
    r = client.get("/api/v1/users", headers=auth_header_for(admin_a))
    assert all(u["email"] != "view-b@example.com" for u in r.json())
