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


def _tid() -> uuid.UUID:
    return uuid.uuid4()


class TestInMemoryRevokedTokenRepo:
    def test_not_revoked_by_default(self) -> None:
        repo = InMemoryRevokedTokenRepo()
        assert repo.is_revoked(uuid.uuid4(), _tid()) is False

    def test_revoke_then_check(self) -> None:
        repo = InMemoryRevokedTokenRepo()
        jti = uuid.uuid4()
        tid = _tid()
        repo.revoke(jti, tid, _future())
        assert repo.is_revoked(jti, tid) is True

    def test_expired_revocation_is_cleaned(self) -> None:
        repo = InMemoryRevokedTokenRepo()
        jti = uuid.uuid4()
        tid = _tid()
        repo.revoke(jti, tid, _past())
        assert repo.is_revoked(jti, tid) is False
        # underlying dict should also be cleaned
        assert (tid, jti) not in repo._revoked

    def test_clear(self) -> None:
        repo = InMemoryRevokedTokenRepo()
        jti = uuid.uuid4()
        tid = _tid()
        repo.revoke(jti, tid, _future())
        repo.clear()
        assert repo.is_revoked(jti, tid) is False

    def test_tenant_isolation(self) -> None:
        """Revocation for tenant A must not affect tenant B."""
        repo = InMemoryRevokedTokenRepo()
        jti = uuid.uuid4()
        tid_a = _tid()
        tid_b = _tid()
        repo.revoke(jti, tid_a, _future())
        assert repo.is_revoked(jti, tid_a) is True
        assert repo.is_revoked(jti, tid_b) is False

    def test_revoke_all_for_user(self) -> None:
        """All tracked JTIs for a user must be revoked by revoke_all_for_user."""
        repo = InMemoryRevokedTokenRepo()
        uid = uuid.uuid4()
        tid = _tid()
        jtis = [uuid.uuid4() for _ in range(3)]
        for jti in jtis:
            repo._track_user_jti(uid, tid, jti)
        repo.revoke_all_for_user(uid, tid)
        for jti in jtis:
            assert repo.is_revoked(jti, tid) is True

    def test_revoke_all_for_user_does_not_affect_other_tenant(self) -> None:
        repo = InMemoryRevokedTokenRepo()
        uid = uuid.uuid4()
        tid_a = _tid()
        tid_b = _tid()
        jti = uuid.uuid4()
        repo._track_user_jti(uid, tid_a, jti)
        repo.revoke_all_for_user(uid, tid_a)
        # Same JTI, different tenant — must not be revoked
        assert repo.is_revoked(jti, tid_b) is False


class TestRedisRevokedTokenRepo:
    @pytest.fixture
    def redis(self) -> fakeredis.FakeRedis:
        return fakeredis.FakeRedis()

    def test_not_revoked_by_default(self, redis) -> None:
        repo = RedisRevokedTokenRepo(redis)
        assert repo.is_revoked(uuid.uuid4(), _tid()) is False

    def test_revoke_then_check(self, redis) -> None:
        repo = RedisRevokedTokenRepo(redis)
        jti = uuid.uuid4()
        tid = _tid()
        repo.revoke(jti, tid, _future())
        assert repo.is_revoked(jti, tid) is True

    def test_revoke_writes_tenant_prefixed_key_with_ttl(self, redis) -> None:
        repo = RedisRevokedTokenRepo(redis)
        jti = uuid.uuid4()
        tid = _tid()
        repo.revoke(jti, tid, _future())
        key = f"tenant:{tid}:revoked:{jti}"
        assert redis.exists(key) == 1
        ttl = redis.ttl(key)
        # TTL should be approximately 3600s (1 hour), tolerate small clock drift
        assert 3590 <= ttl <= 3600

    def test_revoke_with_past_expiry_is_noop(self, redis) -> None:
        repo = RedisRevokedTokenRepo(redis)
        jti = uuid.uuid4()
        tid = _tid()
        repo.revoke(jti, tid, _past())
        # Key must NOT have been written — token is already expired by JWT
        assert redis.exists(f"tenant:{tid}:revoked:{jti}") == 0
        assert repo.is_revoked(jti, tid) is False

    def test_revoke_with_exact_now_is_noop(self, redis) -> None:
        """ttl == 0 is also a no-op (SETEX rejects ttl<=0)."""
        repo = RedisRevokedTokenRepo(redis)
        jti = uuid.uuid4()
        tid = _tid()
        repo.revoke(jti, tid, datetime.now(tz=timezone.utc))
        assert repo.is_revoked(jti, tid) is False

    def test_survives_repo_rebuild(self, redis) -> None:
        """Revocations persist across repo instances (simulates process restart)."""
        jti = uuid.uuid4()
        tid = _tid()
        RedisRevokedTokenRepo(redis).revoke(jti, tid, _future())
        # New repo instance pointed at same Redis sees the revocation
        assert RedisRevokedTokenRepo(redis).is_revoked(jti, tid) is True

    def test_tenant_isolation(self, redis) -> None:
        """Revoking for tenant A must not affect tenant B for the same JTI."""
        repo = RedisRevokedTokenRepo(redis)
        jti = uuid.uuid4()
        tid_a = _tid()
        tid_b = _tid()
        repo.revoke(jti, tid_a, _future())
        assert repo.is_revoked(jti, tid_a) is True
        assert repo.is_revoked(jti, tid_b) is False

    def test_is_revoked_returns_false_when_circuit_open(self) -> None:
        """H-10: When the circuit is open (Redis down), is_revoked fails-open."""
        broken_redis = BrokenRedis()
        # failure_threshold=1 so the first failure opens the circuit immediately.
        repo = RedisRevokedTokenRepo(broken_redis, failure_threshold=1)
        jti = uuid.uuid4()
        # First call: circuit trips on BrokenRedis exception.
        result = repo.is_revoked(jti, _tid())
        # Should fail-open (return False) rather than raising.
        assert result is False

    def test_revoke_does_not_raise_when_circuit_open(self) -> None:
        """H-10: revoke() is a no-op (logs) when the circuit is open."""
        broken_redis = BrokenRedis()
        repo = RedisRevokedTokenRepo(broken_redis, failure_threshold=1)
        jti = uuid.uuid4()
        tid = _tid()
        # Should not raise; graceful degradation.
        repo.revoke(jti, tid, _future())  # triggers failure, trips circuit
        repo.revoke(jti, tid, _future())  # circuit open — should still not raise

    def test_revoke_all_for_user(self, redis) -> None:
        """revoke_all_for_user must revoke all JTIs in the user index."""
        repo = RedisRevokedTokenRepo(redis)
        uid = uuid.uuid4()
        tid = _tid()
        jtis = [uuid.uuid4() for _ in range(3)]
        for jti in jtis:
            repo.track_user_jti(uid, tid, jti, ttl=3600)

        repo.revoke_all_for_user(uid, tid)

        for jti in jtis:
            assert repo.is_revoked(jti, tid) is True

    def test_revoke_all_for_user_does_not_affect_other_tenant(self, redis) -> None:
        """revoke_all_for_user for tenant A must not affect tenant B."""
        repo = RedisRevokedTokenRepo(redis)
        uid = uuid.uuid4()
        tid_a = _tid()
        tid_b = _tid()
        jti = uuid.uuid4()
        repo.track_user_jti(uid, tid_a, jti, ttl=3600)
        repo.revoke_all_for_user(uid, tid_a)
        # Same JTI, different tenant — no revocation record
        assert repo.is_revoked(jti, tid_b) is False

    def test_revoke_all_for_user_noop_when_no_index(self, redis) -> None:
        """revoke_all_for_user with no tracked JTIs must not raise."""
        repo = RedisRevokedTokenRepo(redis)
        repo.revoke_all_for_user(uuid.uuid4(), _tid())  # must not raise


class BrokenRedis:
    """Test double that always raises a Redis-like error."""

    def setex(self, *args, **kwargs):
        raise RuntimeError("Redis connection refused")

    def exists(self, *args, **kwargs):
        raise RuntimeError("Redis connection refused")

    def smembers(self, *args, **kwargs):
        raise RuntimeError("Redis connection refused")

    def pipeline(self, *args, **kwargs):
        raise RuntimeError("Redis connection refused")
