"""Small targeted tests to pin coverage on narrow branches."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from shared.auth.passwords import hash_password, verify_password
from src.auth._models import GUID, Role
from src.auth.deps import get_audit_sink
from src.auth.audit_sink import InMemoryAuditSink
from src.auth.service import (
    ForbiddenError,
    NotFoundError,
    update_role,
)
from src.auth.wiring import build_user_loader


class TestDeps:
    def test_default_audit_sink_instance(self) -> None:
        sink = get_audit_sink()
        assert hasattr(sink, "emit")


class TestPasswordLengthLimit:
    def test_hash_rejects_over_72_bytes(self) -> None:
        with pytest.raises(ValueError):
            hash_password("a" * 73)

    def test_verify_rejects_over_72_bytes(self) -> None:
        h = hash_password("short")
        assert verify_password("a" * 73, h) is False

    def test_verify_returns_false_on_malformed_hash_error(self) -> None:
        # Triggers the TypeError branch in verify_password when bcrypt
        # receives a hash bytes-payload it cannot parse.
        assert verify_password("abc", "$2b$12$not-really-a-valid-bcrypt-hash") is False


class TestGUIDType:
    def test_process_bind_accepts_string(self) -> None:
        g = GUID()
        out = g.process_bind_param(str(uuid.uuid4()), None)
        assert isinstance(out, str)

    def test_process_bind_accepts_uuid(self) -> None:
        g = GUID()
        val = uuid.uuid4()
        assert g.process_bind_param(val, None) == str(val)

    def test_process_bind_none(self) -> None:
        assert GUID().process_bind_param(None, None) is None

    def test_process_result_none(self) -> None:
        assert GUID().process_result_value(None, None) is None

    def test_process_result_uuid_passthrough(self) -> None:
        val = uuid.uuid4()
        assert GUID().process_result_value(val, None) == val

    def test_process_result_string(self) -> None:
        val = uuid.uuid4()
        assert GUID().process_result_value(str(val), None) == val


class TestServiceEdgeCases:
    def test_update_role_cross_tenant_raises_notfound(
        self, db, tenant_a, tenant_b, seeded_roles
    ) -> None:
        # custom role owned by tenant_b
        other = Role(tenant_id=tenant_b.id, name="foreign", is_system=False)
        db.add(other)
        db.commit()
        with pytest.raises(NotFoundError):
            update_role(
                db,
                tenant_id=tenant_a.id,
                role_id=other.id,
                description="x",
                actor_id=None,
                audit=InMemoryAuditSink(),
            )

    def test_update_system_role_forbidden(self, db, tenant_a, seeded_roles) -> None:
        sys_role = db.scalars(select(Role).where(Role.name == "tenant_viewer")).one()
        with pytest.raises(ForbiddenError):
            update_role(
                db,
                tenant_id=tenant_a.id,
                role_id=sys_role.id,
                description="x",
                actor_id=None,
                audit=InMemoryAuditSink(),
            )

    def test_update_missing_role_notfound(self, db, tenant_a) -> None:
        with pytest.raises(NotFoundError):
            update_role(
                db,
                tenant_id=tenant_a.id,
                role_id=uuid.uuid4(),
                description="x",
                actor_id=None,
                audit=InMemoryAuditSink(),
            )


class TestWiringLoader:
    def test_loader_returns_none_for_unknown_user(self, SessionLocal) -> None:
        loader = build_user_loader(SessionLocal)
        assert loader(uuid.uuid4()) is None


class TestUpdateMeNoDisplayName:
    def test_me_put_with_null_display_name_is_noop(self, client, admin_a) -> None:
        token = client.post(
            "/api/v1/auth/login",
            json={"email": "admin-a@example.com", "password": "password123!"},
        ).json()["access_token"]
        r = client.put(
            "/api/v1/auth/me",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["display_name"] == "admin-a"
