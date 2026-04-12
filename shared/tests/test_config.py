"""Tests for the settings loader."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared import config as config_mod


BASE_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://u:p@h/d",
    "DATABASE_URL_SYNC": "postgresql+asyncpg://u:p@h/d",
    "REDIS_URL": "redis://h/0",
    "RABBITMQ_URL": "amqp://u:p@h/",
    "JWT_SECRET": "x" * 32,
}


@pytest.fixture(autouse=True)
def _clear_cache():
    config_mod.reset_settings_cache()
    yield
    config_mod.reset_settings_cache()


def _apply_env(monkeypatch, overrides=None):
    # Clear any env_file to avoid leakage from .env.local.
    monkeypatch.setattr(
        config_mod.Settings,
        "model_config",
        {**config_mod.Settings.model_config, "env_file": None},
    )
    env = {**BASE_ENV, **(overrides or {})}
    for k, v in env.items():
        monkeypatch.setenv(k, v)


def test_get_settings_loads_and_caches(monkeypatch) -> None:
    _apply_env(monkeypatch)
    # Reset the Settings.model_config env_file to None via a fresh class eval.
    s1 = config_mod.Settings()  # type: ignore[call-arg]
    s2 = config_mod.get_settings()
    assert s1.JWT_SECRET == "x" * 32
    assert s2.JWT_ALGORITHM == "HS256"


def test_jwt_secret_too_short_is_rejected(monkeypatch) -> None:
    _apply_env(monkeypatch, {"JWT_SECRET": "short"})
    with pytest.raises(ValidationError):
        config_mod.Settings()  # type: ignore[call-arg]


def test_invalid_jwt_algorithm_rejected(monkeypatch) -> None:
    _apply_env(monkeypatch, {"JWT_ALGORITHM": "NONE"})
    with pytest.raises(ValidationError):
        config_mod.Settings()  # type: ignore[call-arg]


def test_cache_reset_rebuilds_settings(monkeypatch) -> None:
    _apply_env(monkeypatch)
    s1 = config_mod.get_settings()
    config_mod.reset_settings_cache()
    s2 = config_mod.get_settings()
    assert s1 is not s2
