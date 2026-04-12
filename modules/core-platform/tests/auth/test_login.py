"""Login, refresh, logout, /auth/me end-to-end tests."""

from __future__ import annotations

import jwt as pyjwt

from shared.auth._settings import get_auth_settings
from shared.auth.jwt_tokens import create_refresh_token
from src.auth.service import MAX_FAILED_LOGINS


def _login(client, email: str, password: str, tenant_slug: str | None = None):
    body = {"email": email, "password": password}
    if tenant_slug:
        body["tenant_slug"] = tenant_slug
    return client.post("/api/v1/auth/login", json=body)


class TestLogin:
    def test_valid_credentials_return_tokens(self, client, admin_a) -> None:
        r = _login(client, "admin-a@example.com", "password123!")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0
        assert body["access_token"]
        assert body["refresh_token"]

    def test_invalid_password_returns_generic_401(self, client, admin_a) -> None:
        r = _login(client, "admin-a@example.com", "wrong")
        assert r.status_code == 401
        assert r.json()["detail"]["error"] == "invalid_credentials"

    def test_unknown_email_returns_generic_401(self, client) -> None:
        r = _login(client, "nobody@example.com", "whatever")
        assert r.status_code == 401
        assert r.json()["detail"]["error"] == "invalid_credentials"

    def test_locked_account_cannot_login(self, client, db, admin_a) -> None:
        admin_a.status = "locked"
        db.commit()
        r = _login(client, "admin-a@example.com", "password123!")
        assert r.status_code == 401

    def test_inactive_account_cannot_login(self, client, db, admin_a) -> None:
        admin_a.status = "inactive"
        db.commit()
        r = _login(client, "admin-a@example.com", "password123!")
        assert r.status_code == 401

    def test_failed_counter_increments(self, client, db, admin_a) -> None:
        for _ in range(3):
            _login(client, "admin-a@example.com", "wrong")
        db.refresh(admin_a)
        assert admin_a.failed_login_count == 3
        assert admin_a.status == "active"

    def test_fifth_failure_locks_account(self, client, db, admin_a) -> None:
        for _ in range(MAX_FAILED_LOGINS):
            _login(client, "admin-a@example.com", "wrong")
        db.refresh(admin_a)
        assert admin_a.failed_login_count == MAX_FAILED_LOGINS
        assert admin_a.status == "locked"

    def test_successful_login_resets_failed_counter(
        self, client, db, admin_a
    ) -> None:
        _login(client, "admin-a@example.com", "wrong")
        _login(client, "admin-a@example.com", "wrong")
        r = _login(client, "admin-a@example.com", "password123!")
        assert r.status_code == 200
        db.refresh(admin_a)
        assert admin_a.failed_login_count == 0
        assert admin_a.last_login_at is not None

    def test_tenant_slug_selects_tenant(self, client, admin_a, admin_b) -> None:
        r = _login(client, "admin-a@example.com", "password123!", tenant_slug="alpha")
        assert r.status_code == 200

    def test_tenant_slug_mismatch_401(self, client, admin_a, admin_b) -> None:
        r = _login(client, "admin-a@example.com", "password123!", tenant_slug="beta")
        assert r.status_code == 401


class TestMeEndpoints:
    def test_me_returns_current_user(self, client, admin_a) -> None:
        token = _login(client, "admin-a@example.com", "password123!").json()["access_token"]
        r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "admin-a@example.com"
        assert "tenant_admin" in body["roles"]

    def test_me_update_display_name(self, client, admin_a) -> None:
        token = _login(client, "admin-a@example.com", "password123!").json()["access_token"]
        r = client.put(
            "/api/v1/auth/me",
            json={"display_name": "Admin One"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["display_name"] == "Admin One"

    def test_me_requires_auth(self, client) -> None:
        assert client.get("/api/v1/auth/me").status_code == 401


class TestRefresh:
    def test_valid_refresh_issues_new_access_token(self, client, admin_a) -> None:
        tokens = _login(client, "admin-a@example.com", "password123!").json()
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert r.status_code == 200
        new_tokens = r.json()
        assert new_tokens["access_token"] != tokens["access_token"]
        assert new_tokens["refresh_token"] != tokens["refresh_token"]

    def test_refresh_rotates_and_revokes_old(self, client, admin_a) -> None:
        tokens = _login(client, "admin-a@example.com", "password123!").json()
        client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert r2.status_code == 401
        assert r2.json()["detail"]["error"] == "token_revoked"

    def test_access_token_cannot_be_used_as_refresh(self, client, admin_a) -> None:
        tokens = _login(client, "admin-a@example.com", "password123!").json()
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
        assert r.status_code == 401

    def test_expired_refresh_rejected(self, client, db, admin_a) -> None:
        s = get_auth_settings()
        import uuid as _uuid
        from datetime import datetime, timedelta, timezone

        past = datetime.now(tz=timezone.utc) - timedelta(days=30)
        payload = {
            "sub": str(admin_a.id),
            "typ": "refresh",
            "iat": int(past.timestamp()),
            "exp": int((past + timedelta(minutes=1)).timestamp()),
            "jti": str(_uuid.uuid4()),
        }
        token = pyjwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert r.status_code == 401
        assert r.json()["detail"]["error"] == "token_expired"

    def test_garbage_refresh_rejected(self, client) -> None:
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage"})
        assert r.status_code == 401

    def test_refresh_for_inactive_user(self, client, db, admin_a) -> None:
        tokens = _login(client, "admin-a@example.com", "password123!").json()
        admin_a.status = "inactive"
        db.commit()
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert r.status_code == 401

    def test_refresh_for_unknown_user(self, client, admin_a) -> None:
        import uuid as _uuid

        bad = create_refresh_token(_uuid.uuid4())
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": bad})
        assert r.status_code == 401


class TestLogout:
    def test_logout_revokes_refresh(self, client, admin_a) -> None:
        tokens = _login(client, "admin-a@example.com", "password123!").json()
        r = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert r.status_code == 204
        # subsequent refresh attempt with the revoked token fails
        r2 = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert r2.status_code == 401
        assert r2.json()["detail"]["error"] == "token_revoked"

    def test_logout_requires_auth(self, client, admin_a) -> None:
        tokens = _login(client, "admin-a@example.com", "password123!").json()
        r = client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
        assert r.status_code == 401

    def test_logout_rejects_non_refresh_token(self, client, admin_a) -> None:
        tokens = _login(client, "admin-a@example.com", "password123!").json()
        r = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["access_token"]},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert r.status_code == 400

    def test_logout_rejects_foreign_refresh_token(self, client, admin_a, admin_b) -> None:
        tokens_a = _login(client, "admin-a@example.com", "password123!").json()
        tokens_b = _login(client, "admin-b@example.com", "password123!").json()
        r = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens_b["refresh_token"]},
            headers={"Authorization": f"Bearer {tokens_a['access_token']}"},
        )
        assert r.status_code == 400

    def test_logout_rejects_garbage_refresh(self, client, admin_a) -> None:
        tokens = _login(client, "admin-a@example.com", "password123!").json()
        r = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "garbage"},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert r.status_code == 400
