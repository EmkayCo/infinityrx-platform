"""Tests for src.auth.wiring._default_revoked_repo."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shared.auth.tokens_repo import InMemoryRevokedTokenRepo, RedisRevokedTokenRepo
from src.auth import wiring


def test_default_repo_without_redis_url_returns_in_memory(monkeypatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    repo = wiring._default_revoked_repo()
    assert isinstance(repo, InMemoryRevokedTokenRepo)


def test_default_repo_empty_redis_url_returns_in_memory(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "   ")
    repo = wiring._default_revoked_repo()
    assert isinstance(repo, InMemoryRevokedTokenRepo)


def test_default_repo_with_redis_url_returns_redis_backed(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://fake:6379/0")
    fake_client = MagicMock(name="redis.Redis")
    fake_redis_module = MagicMock()
    fake_redis_module.Redis.from_url.return_value = fake_client
    with patch.dict("sys.modules", {"redis": fake_redis_module}):
        repo = wiring._default_revoked_repo()
    assert isinstance(repo, RedisRevokedTokenRepo)
    fake_redis_module.Redis.from_url.assert_called_once_with(
        "redis://fake:6379/0", decode_responses=False
    )


def test_configure_core_auth_uses_default_when_no_repo(monkeypatch) -> None:
    """configure_core_auth should route through _default_revoked_repo."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    session_local = MagicMock()
    with patch.object(wiring, "configure_auth") as fake_configure:
        repo = wiring.configure_core_auth(session_local)
    assert isinstance(repo, InMemoryRevokedTokenRepo)
    fake_configure.assert_called_once()


def test_configure_core_auth_respects_explicit_repo() -> None:
    explicit = InMemoryRevokedTokenRepo()
    session_local = MagicMock()
    with patch.object(wiring, "configure_auth"):
        returned = wiring.configure_core_auth(session_local, repo=explicit)
    assert returned is explicit
