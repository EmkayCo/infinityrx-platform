"""Tests for shared.auth.tokens_repo."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from shared.auth.tokens_repo import InMemoryRevokedTokenRepo


def _future() -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(hours=1)


def _past() -> datetime:
    return datetime.now(tz=timezone.utc) - timedelta(seconds=1)


class TestInMemoryRevokedTokenRepo:
    def test_not_revoked_by_default(self) -> None:
        repo = InMemoryRevokedTokenRepo()
        assert repo.is_revoked(uuid.uuid4()) is False

    def test_revoke_then_check(self) -> None:
        repo = InMemoryRevokedTokenRepo()
        jti = uuid.uuid4()
        repo.revoke(jti, _future())
        assert repo.is_revoked(jti) is True

    def test_expired_revocation_is_cleaned(self) -> None:
        repo = InMemoryRevokedTokenRepo()
        jti = uuid.uuid4()
        repo.revoke(jti, _past())
        assert repo.is_revoked(jti) is False
        # underlying dict should also be cleaned
        assert jti not in repo._revoked

    def test_clear(self) -> None:
        repo = InMemoryRevokedTokenRepo()
        jti = uuid.uuid4()
        repo.revoke(jti, _future())
        repo.clear()
        assert repo.is_revoked(jti) is False
