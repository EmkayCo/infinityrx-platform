"""Tests for shared.auth._settings env fallback."""

from __future__ import annotations

import pytest

from shared.auth import _settings as mod


def test_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRES_MINUTES", "15")
    monkeypatch.setenv("JWT_REFRESH_EXPIRES_MINUTES", "30")
    s = mod._load_from_env()
    assert s.JWT_SECRET == "x" * 40
    assert s.JWT_ALGORITHM == "HS256"
    assert s.JWT_EXPIRES_MINUTES == 15
    assert s.JWT_REFRESH_EXPIRES_MINUTES == 30


def test_rejects_short_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "short")
    with pytest.raises(RuntimeError):
        mod._load_from_env()


def test_get_auth_settings_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure shared.config is not importable for this test
    import sys

    monkeypatch.delitem(sys.modules, "shared.config", raising=False)
    monkeypatch.setenv("JWT_SECRET", "y" * 40)
    s = mod.get_auth_settings()
    assert s.JWT_SECRET == "y" * 40
