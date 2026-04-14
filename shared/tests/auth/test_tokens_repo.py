"""Tests for shared.auth.tokens_repo."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import fakeredis
import pytest

from shared.auth.tokens_repo import (
    InMemoryRevokedTokenRepo,
    RedisRevokedTokenRepo,
)


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


class TestRedisRevokedTokenRepo:
    @pytest.fixture
    def redis(self) -> fakeredis.FakeRedis:
        return fakeredis.FakeRedis()

    def test_not_revoked_by_default(self, redis) -> None:
        repo = RedisRevokedTokenRepo(redis)
        assert repo.is_revoked(uuid.uuid4()) is False

    def test_revoke_then_check(self, redis) -> None:
        repo = RedisRevokedTokenRepo(redis)
        jti = uuid.uuid4()
        repo.revoke(jti, _future())
        assert repo.is_revoked(jti) is True

    def test_revoke_writes_correct_key_with_ttl(self, redis) -> None:
        repo = RedisRevokedTokenRepo(redis)
        jti = uuid.uuid4()
        repo.revoke(jti, _future())
        key = f"revoked:jti:{jti}"
        assert redis.exists(key) == 1
        ttl = redis.ttl(key)
        # TTL should be approximately 3600s (1 hour), tolerate small clock drift
        assert 3590 <= ttl <= 3600

    def test_revoke_with_past_expiry_is_noop(self, redis) -> None:
        repo = RedisRevokedTokenRepo(redis)
        jti = uuid.uuid4()
        repo.revoke(jti, _past())
        # Key must NOT have been written — token is already expired by JWT
        assert redis.exists(f"revoked:jti:{jti}") == 0
        assert repo.is_revoked(jti) is False

    def test_revoke_with_exact_now_is_noop(self, redis) -> None:
        """ttl == 0 is also a no-op (SETEX rejects ttl<=0)."""
        repo = RedisRevokedTokenRepo(redis)
        jti = uuid.uuid4()
        # exp == now (within sub-second precision) → ttl=0 or negative
        repo.revoke(jti, datetime.now(tz=timezone.utc))
        assert repo.is_revoked(jti) is False

    def test_survives_repo_rebuild(self, redis) -> None:
        """Revocations persist across repo instances (simulates restart)."""
        jti = uuid.uuid4()
        RedisRevokedTokenRepo(redis).revoke(jti, _future())
        # New repo instance pointed at same Redis sees the revocation
        assert RedisRevokedTokenRepo(redis).is_revoked(jti) is True

    def test_custom_key_prefix(self, redis) -> None:
        repo = RedisRevokedTokenRepo(redis, key_prefix="tenant42:revoked:")
        jti = uuid.uuid4()
        repo.revoke(jti, _future())
        assert redis.exists(f"tenant42:revoked:{jti}") == 1
        assert repo.is_revoked(jti) is True
        # Default-prefix repo must NOT see it
        default = RedisRevokedTokenRepo(redis)
        assert default.is_revoked(jti) is False

    def test_is_revoked_returns_false_when_circuit_open(self) -> None:
        """H-10: When the circuit is open (Redis down), is_revoked fails-open."""
        broken_redis = BrokenRedis()
        # failure_threshold=1 so the first failure opens the circuit immediately.
        repo = RedisRevokedTokenRepo(broken_redis, failure_threshold=1)
        jti = uuid.uuid4()
        # First call: circuit trips on BrokenRedis exception.
        result = repo.is_revoked(jti)
        # Should fail-open (return False) rather than raising.
        assert result is False

    def test_revoke_does_not_raise_when_circuit_open(self) -> None:
        """H-10: revoke() is a no-op (logs) when the circuit is open."""
        broken_redis = BrokenRedis()
        repo = RedisRevokedTokenRepo(broken_redis, failure_threshold=1)
        jti = uuid.uuid4()
        # Should not raise; graceful degradation.
        repo.revoke(jti, _future())  # triggers failure, trips circuit
        repo.revoke(jti, _future())  # circuit open — should still not raise


class BrokenRedis:
    """Test double that always raises a Redis-like error."""

    def setex(self, *args, **kwargs):
        raise RuntimeError("Redis connection refused")

    def exists(self, *args, **kwargs):
        raise RuntimeError("Redis connection refused")
