"""Tests for shared.auth.jwt_tokens."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

from shared.auth._settings import get_auth_settings
from shared.auth.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    WrongTokenTypeError,
)
from shared.auth.jwt_tokens import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token_type,
)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.uuid4()


class TestCreateAccessToken:
    def test_round_trip(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        token = create_access_token(user_id, tenant_id, ["tenant_admin", "user"])
        claims = decode_token(token)
        assert claims.user_id == user_id
        assert claims.tenant_id == tenant_id
        assert claims.typ == TOKEN_TYPE_ACCESS
        assert claims.roles == ("tenant_admin", "user")
        assert isinstance(claims.jti, uuid.UUID)
        assert claims.exp > claims.iat

    def test_rejects_non_uuid(self) -> None:
        with pytest.raises(ValueError):
            create_access_token("not-uuid", uuid.uuid4(), [])  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            create_access_token(uuid.uuid4(), "not-uuid", [])  # type: ignore[arg-type]

    def test_unique_jti_per_token(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> None:
        a = decode_token(create_access_token(user_id, tenant_id, []))
        b = decode_token(create_access_token(user_id, tenant_id, []))
        assert a.jti != b.jti


class TestCreateRefreshToken:
    def test_round_trip(self, user_id: uuid.UUID) -> None:
        token = create_refresh_token(user_id)
        claims = decode_token(token)
        assert claims.user_id == user_id
        assert claims.typ == TOKEN_TYPE_REFRESH
        assert claims.tenant_id is None
        assert claims.roles == ()

    def test_refresh_exp_longer_than_access(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> None:
        access = decode_token(create_access_token(user_id, tenant_id, []))
        refresh = decode_token(create_refresh_token(user_id))
        assert refresh.exp > access.exp

    def test_rejects_non_uuid(self) -> None:
        with pytest.raises(ValueError):
            create_refresh_token("nope")  # type: ignore[arg-type]


class TestDecodeToken:
    def test_empty_token_raises_invalid(self) -> None:
        with pytest.raises(InvalidTokenError):
            decode_token("")

    def test_non_string_raises_invalid(self) -> None:
        with pytest.raises(InvalidTokenError):
            decode_token(None)  # type: ignore[arg-type]

    def test_tampered_signature(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> None:
        token = create_access_token(user_id, tenant_id, [])
        tampered = token[:-4] + ("AAAA" if token[-4:] != "AAAA" else "BBBB")
        with pytest.raises(InvalidTokenError):
            decode_token(tampered)

    def test_wrong_secret(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        s = get_auth_settings()
        now = int(datetime.now(tz=timezone.utc).timestamp())
        payload = {
            "sub": str(user_id),
            "tid": str(tenant_id),
            "roles": [],
            "typ": "access",
            "iat": now,
            "exp": now + 60,
            "jti": str(uuid.uuid4()),
        }
        bad = pyjwt.encode(payload, "a-different-secret-of-sufficient-length!", algorithm=s.JWT_ALGORITHM)
        with pytest.raises(InvalidTokenError):
            decode_token(bad)

    def test_expired_token(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        s = get_auth_settings()
        past = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        payload = {
            "sub": str(user_id),
            "tid": str(tenant_id),
            "roles": [],
            "typ": "access",
            "iat": int(past.timestamp()),
            "exp": int((past + timedelta(minutes=1)).timestamp()),
            "jti": str(uuid.uuid4()),
        }
        token = pyjwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)
        with pytest.raises(ExpiredTokenError):
            decode_token(token)

    def test_missing_required_claim(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> None:
        s = get_auth_settings()
        now = int(datetime.now(tz=timezone.utc).timestamp())
        payload = {
            "sub": str(user_id),
            "iat": now,
            "exp": now + 60,
            # no 'typ', no 'jti'
        }
        token = pyjwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)
        with pytest.raises(InvalidTokenError):
            decode_token(token)

    def test_malformed_sub_claim(self) -> None:
        s = get_auth_settings()
        now = int(datetime.now(tz=timezone.utc).timestamp())
        payload = {
            "sub": "not-a-uuid",
            "tid": str(uuid.uuid4()),
            "roles": [],
            "typ": "access",
            "iat": now,
            "exp": now + 60,
            "jti": str(uuid.uuid4()),
        }
        token = pyjwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)
        with pytest.raises(InvalidTokenError):
            decode_token(token)

    def test_malformed_tid_claim(self, user_id: uuid.UUID) -> None:
        s = get_auth_settings()
        now = int(datetime.now(tz=timezone.utc).timestamp())
        payload = {
            "sub": str(user_id),
            "tid": "not-a-uuid",
            "roles": [],
            "typ": "access",
            "iat": now,
            "exp": now + 60,
            "jti": str(uuid.uuid4()),
        }
        token = pyjwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)
        with pytest.raises(InvalidTokenError):
            decode_token(token)

    def test_malformed_jti_claim(self, user_id: uuid.UUID) -> None:
        s = get_auth_settings()
        now = int(datetime.now(tz=timezone.utc).timestamp())
        payload = {
            "sub": str(user_id),
            "tid": str(uuid.uuid4()),
            "roles": [],
            "typ": "access",
            "iat": now,
            "exp": now + 60,
            "jti": "nope",
        }
        token = pyjwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)
        with pytest.raises(InvalidTokenError):
            decode_token(token)

    def test_unknown_token_type(self, user_id: uuid.UUID) -> None:
        s = get_auth_settings()
        now = int(datetime.now(tz=timezone.utc).timestamp())
        payload = {
            "sub": str(user_id),
            "tid": str(uuid.uuid4()),
            "roles": [],
            "typ": "magic",
            "iat": now,
            "exp": now + 60,
            "jti": str(uuid.uuid4()),
        }
        token = pyjwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)
        with pytest.raises(InvalidTokenError):
            decode_token(token)

    def test_roles_claim_wrong_type(self, user_id: uuid.UUID) -> None:
        s = get_auth_settings()
        now = int(datetime.now(tz=timezone.utc).timestamp())
        payload = {
            "sub": str(user_id),
            "tid": str(uuid.uuid4()),
            "roles": "admin",  # should be list
            "typ": "access",
            "iat": now,
            "exp": now + 60,
            "jti": str(uuid.uuid4()),
        }
        token = pyjwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)
        with pytest.raises(InvalidTokenError):
            decode_token(token)


class TestVerifyTokenType:
    def test_match(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        claims = decode_token(create_access_token(user_id, tenant_id, []))
        verify_token_type(claims, TOKEN_TYPE_ACCESS)  # no raise

    def test_mismatch(self, user_id: uuid.UUID) -> None:
        claims = decode_token(create_refresh_token(user_id))
        with pytest.raises(WrongTokenTypeError):
            verify_token_type(claims, TOKEN_TYPE_ACCESS)
