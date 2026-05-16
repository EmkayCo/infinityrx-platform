"""Tests for shared.auth.dependencies — token handling, role/permission gates."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from shared.auth.dependencies import (
    CurrentUser,
    configure_auth,
    get_current_user,
    platform_admin_only,
    require_permissions,
    require_roles,
    tenant_admin_only,
)
from shared.auth.jwt_tokens import create_access_token, create_refresh_token
from shared.auth.tokens_repo import InMemoryRevokedTokenRepo


def _make_user(
    *,
    roles: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
    status: str = "active",
) -> tuple[uuid.UUID, uuid.UUID, CurrentUser]:
    uid = uuid.uuid4()
    tid = uuid.uuid4()
    return uid, tid, CurrentUser(
        id=uid,
        tenant_id=tid,
        email="u@example.com",
        status=status,
        roles=roles,
        permissions=permissions,
    )


@pytest.fixture
def repo() -> InMemoryRevokedTokenRepo:
    return InMemoryRevokedTokenRepo()


@pytest.fixture
def users() -> dict[uuid.UUID, CurrentUser]:
    return {}


@pytest.fixture(autouse=True)
def wire_auth(repo: InMemoryRevokedTokenRepo, users: dict[uuid.UUID, CurrentUser]):
    def loader(uid: uuid.UUID) -> CurrentUser | None:
        return users.get(uid)

    configure_auth(loader, repo)
    yield


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/me")
    def me(u: CurrentUser = Depends(get_current_user)) -> dict:
        return {"id": str(u.id), "tenant": str(u.tenant_id)}

    @app.get("/admin")
    def admin(u: CurrentUser = Depends(require_roles("tenant_admin"))) -> dict:
        return {"ok": True, "id": str(u.id)}

    @app.get("/platform")
    def platform(u: CurrentUser = Depends(platform_admin_only)) -> dict:
        return {"ok": True}

    @app.get("/tadmin")
    def tadmin(u: CurrentUser = Depends(tenant_admin_only)) -> dict:
        return {"ok": True}

    @app.get("/write")
    def write(u: CurrentUser = Depends(require_permissions("users:write"))) -> dict:
        return {"ok": True}

    return app


class TestGetCurrentUser:
    def test_missing_token_401(self, users) -> None:
        client = TestClient(_make_app())
        r = client.get("/me")
        assert r.status_code == 401

    def test_invalid_token_401(self, users) -> None:
        client = TestClient(_make_app())
        r = client.get("/me", headers={"Authorization": "Bearer garbage"})
        assert r.status_code == 401

    def test_expired_token_401(self, users) -> None:
        from shared.auth._settings import get_auth_settings
        import jwt as pyjwt

        s = get_auth_settings()
        past = datetime.now(tz=timezone.utc) - timedelta(hours=2)
        payload = {
            "sub": str(uuid.uuid4()),
            "tid": str(uuid.uuid4()),
            "roles": [],
            "typ": "access",
            "iat": int(past.timestamp()),
            "exp": int((past + timedelta(minutes=1)).timestamp()),
            "jti": str(uuid.uuid4()),
        }
        token = pyjwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)
        client = TestClient(_make_app())
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
        assert "expired" in r.json()["detail"]["message"]

    def test_refresh_token_rejected_as_access(self, users) -> None:
        uid, _tid, user = _make_user()
        users[uid] = user
        token = create_refresh_token(uid)
        client = TestClient(_make_app())
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    def test_revoked_jti_rejected(self, users, repo) -> None:
        uid, tid, user = _make_user()
        users[uid] = user
        token = create_access_token(uid, tid, [])
        from shared.auth.jwt_tokens import decode_token

        claims = decode_token(token)
        assert claims.tenant_id is not None
        repo.revoke(claims.jti, claims.tenant_id, claims.exp)
        client = TestClient(_make_app())
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
        assert "revoked" in r.json()["detail"]["message"]

    def test_unknown_user_rejected(self, users) -> None:
        # create token referring to a user not in the loader
        token = create_access_token(uuid.uuid4(), uuid.uuid4(), [])
        client = TestClient(_make_app())
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
        assert "not found" in r.json()["detail"]["message"]

    def test_inactive_user_rejected(self, users) -> None:
        uid, tid, user = _make_user(status="inactive")
        users[uid] = user
        token = create_access_token(uid, tid, [])
        client = TestClient(_make_app())
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    def test_locked_user_rejected(self, users) -> None:
        uid, tid, user = _make_user(status="locked")
        users[uid] = user
        token = create_access_token(uid, tid, [])
        client = TestClient(_make_app())
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    def test_active_user_ok(self, users) -> None:
        uid, tid, user = _make_user()
        users[uid] = user
        token = create_access_token(uid, tid, [])
        client = TestClient(_make_app())
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["id"] == str(uid)


class TestRequireRoles:
    def test_role_missing_403(self, users) -> None:
        uid, tid, user = _make_user(roles=("tenant_viewer",))
        users[uid] = user
        token = create_access_token(uid, tid, [])
        client = TestClient(_make_app())
        r = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403
        assert r.json()["detail"]["required"] == ["tenant_admin"]

    def test_role_present_ok(self, users) -> None:
        uid, tid, user = _make_user(roles=("tenant_admin",))
        users[uid] = user
        token = create_access_token(uid, tid, [])
        client = TestClient(_make_app())
        r = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200

    def test_platform_admin_shortcut(self, users) -> None:
        uid, tid, user = _make_user(roles=("platform_admin",))
        users[uid] = user
        token = create_access_token(uid, tid, [])
        client = TestClient(_make_app())
        assert client.get("/platform", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    def test_tenant_admin_shortcut_also_allows_platform(self, users) -> None:
        uid, tid, user = _make_user(roles=("platform_admin",))
        users[uid] = user
        token = create_access_token(uid, tid, [])
        client = TestClient(_make_app())
        assert client.get("/tadmin", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    def test_tenant_admin_shortcut_rejects_viewer(self, users) -> None:
        uid, tid, user = _make_user(roles=("tenant_viewer",))
        users[uid] = user
        token = create_access_token(uid, tid, [])
        client = TestClient(_make_app())
        assert client.get("/tadmin", headers={"Authorization": f"Bearer {token}"}).status_code == 403


class TestRequirePermissions:
    def test_missing_permission_403(self, users) -> None:
        uid, tid, user = _make_user(permissions=("users:read",))
        users[uid] = user
        token = create_access_token(uid, tid, [])
        client = TestClient(_make_app())
        r = client.get("/write", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403
        assert "users:write" in r.json()["detail"]["required"]

    def test_has_permission_200(self, users) -> None:
        uid, tid, user = _make_user(permissions=("users:write",))
        users[uid] = user
        token = create_access_token(uid, tid, [])
        client = TestClient(_make_app())
        r = client.get("/write", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200


class TestConfigureAuth:
    def test_raises_when_not_configured(self) -> None:
        from shared.auth import dependencies as d

        # simulate unconfigured state
        saved_loader = d._user_loader
        saved_repo = d._revoked_repo
        d._user_loader = None
        d._revoked_repo = None
        try:
            with pytest.raises(RuntimeError):
                d._get_user_loader()
            with pytest.raises(RuntimeError):
                d._get_revoked_repo()
        finally:
            d._user_loader = saved_loader
            d._revoked_repo = saved_repo


def test_current_user_helpers() -> None:
    u = CurrentUser(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        email="a@b.com",
        status="active",
        roles=("x",),
        permissions=("y:z",),
    )
    assert u.has_role("x") is True
    assert u.has_role("missing") is False
    assert u.has_permission("y:z") is True
    assert u.has_permission("nope") is False
