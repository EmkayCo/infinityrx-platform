"""User CRUD / role assignment / lock-unlock HTTP tests."""

from __future__ import annotations

import uuid

from tests.auth.conftest import auth_header_for


class TestCreateUser:
    def test_create_user_ok(self, client, admin_a) -> None:
        r = client.post(
            "/api/v1/users",
            json={
                "email": "new@example.com",
                "display_name": "New User",
                "password": "abcd1234",
                "role_names": ["tenant_viewer"],
            },
            headers=auth_header_for(admin_a),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["email"] == "new@example.com"
        assert "tenant_viewer" in body["roles"]
        assert "password" not in body
        assert "password_hash" not in body

    def test_conflict_on_duplicate_email(self, client, admin_a) -> None:
        payload = {
            "email": "dup@example.com",
            "display_name": "D",
            "password": "abcd1234",
            "role_names": [],
        }
        r1 = client.post("/api/v1/users", json=payload, headers=auth_header_for(admin_a))
        assert r1.status_code == 201
        r2 = client.post("/api/v1/users", json=payload, headers=auth_header_for(admin_a))
        assert r2.status_code == 409

    def test_unknown_role_is_400(self, client, admin_a) -> None:
        r = client.post(
            "/api/v1/users",
            json={
                "email": "xx@example.com",
                "display_name": "x",
                "password": "abcd1234",
                "role_names": ["does-not-exist"],
            },
            headers=auth_header_for(admin_a),
        )
        assert r.status_code == 400

    def test_non_admin_forbidden(self, client, viewer_a) -> None:
        r = client.post(
            "/api/v1/users",
            json={"email": "a@b.com", "display_name": "x", "password": "abcd1234", "role_names": []},
            headers=auth_header_for(viewer_a),
        )
        assert r.status_code == 403


class TestListAndGet:
    def test_list_users_tenant_scoped(self, client, admin_a, admin_b) -> None:
        r = client.get("/api/v1/users", headers=auth_header_for(admin_a))
        assert r.status_code == 200
        emails = {u["email"] for u in r.json()}
        assert "admin-a@example.com" in emails
        assert "admin-b@example.com" not in emails

    def test_get_user_ok(self, client, admin_a) -> None:
        r = client.get(f"/api/v1/users/{admin_a.id}", headers=auth_header_for(admin_a))
        assert r.status_code == 200

    def test_get_user_missing_404(self, client, admin_a) -> None:
        r = client.get(f"/api/v1/users/{uuid.uuid4()}", headers=auth_header_for(admin_a))
        assert r.status_code == 404


class TestUpdate:
    def test_update_display_name(self, client, admin_a, viewer_a) -> None:
        r = client.put(
            f"/api/v1/users/{viewer_a.id}",
            json={"display_name": "Renamed"},
            headers=auth_header_for(admin_a),
        )
        assert r.status_code == 200
        assert r.json()["display_name"] == "Renamed"

    def test_update_status(self, client, admin_a, viewer_a) -> None:
        r = client.put(
            f"/api/v1/users/{viewer_a.id}",
            json={"status": "inactive"},
            headers=auth_header_for(admin_a),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "inactive"

    def test_update_missing_user_404(self, client, admin_a) -> None:
        r = client.put(
            f"/api/v1/users/{uuid.uuid4()}",
            json={"display_name": "x"},
            headers=auth_header_for(admin_a),
        )
        assert r.status_code == 404


class TestRoleAssignment:
    def test_assign_roles_replaces_set(self, client, admin_a, viewer_a) -> None:
        r = client.put(
            f"/api/v1/users/{viewer_a.id}/roles",
            json={"role_names": ["tenant_operator"]},
            headers=auth_header_for(admin_a),
        )
        assert r.status_code == 200
        assert r.json()["roles"] == ["tenant_operator"]

    def test_assign_unknown_role_404(self, client, admin_a, viewer_a) -> None:
        r = client.put(
            f"/api/v1/users/{viewer_a.id}/roles",
            json={"role_names": ["nope"]},
            headers=auth_header_for(admin_a),
        )
        assert r.status_code == 404


class TestLockUnlock:
    def test_lock(self, client, admin_a, viewer_a) -> None:
        r = client.post(f"/api/v1/users/{viewer_a.id}/lock", headers=auth_header_for(admin_a))
        assert r.status_code == 200
        assert r.json()["status"] == "locked"

    def test_unlock_resets_counter(self, client, db, admin_a, viewer_a) -> None:
        viewer_a.failed_login_count = 4
        viewer_a.status = "locked"
        db.commit()
        r = client.post(f"/api/v1/users/{viewer_a.id}/unlock", headers=auth_header_for(admin_a))
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "active"
        assert body["failed_login_count"] == 0

    def test_lock_missing_404(self, client, admin_a) -> None:
        r = client.post(f"/api/v1/users/{uuid.uuid4()}/lock", headers=auth_header_for(admin_a))
        assert r.status_code == 404

    def test_unlock_missing_404(self, client, admin_a) -> None:
        r = client.post(f"/api/v1/users/{uuid.uuid4()}/unlock", headers=auth_header_for(admin_a))
        assert r.status_code == 404


class TestAuditHooks:
    def test_create_emits_audit_event(self, client, admin_a, audit_sink) -> None:
        client.post(
            "/api/v1/users",
            json={"email": "e@f.com", "display_name": "E", "password": "abcd1234", "role_names": []},
            headers=auth_header_for(admin_a),
        )
        assert audit_sink.by_action("user.created")

    def test_login_success_and_failure_emit_events(
        self, client, admin_a, audit_sink
    ) -> None:
        client.post(
            "/api/v1/auth/login",
            json={"email": "admin-a@example.com", "password": "password123!"},
        )
        client.post(
            "/api/v1/auth/login",
            json={"email": "admin-a@example.com", "password": "wrong"},
        )
        assert audit_sink.by_action("login.success")
        assert audit_sink.by_action("login.failed")
