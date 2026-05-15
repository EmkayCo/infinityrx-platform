"""Unit tests for shared.key_vault.

All tests use a mocked SecretClient — no Azure connectivity required.
The integration suite (marked ``integration``) is gated by
``AZURE_KEYVAULT_URL`` + ``INFINITYRX_ENV=production`` being set, so CI
passes without Azure access.
"""

from __future__ import annotations

import os
import time
from unittest.mock import MagicMock

import pytest

from shared.key_vault import (
    KeyVaultSecretLoader,
    MissingSecretError,
    _CacheEntry,
    get_secret,
    reset_loader_cache,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_loader(
    env: str = "development",
    vault_url: str = "",
    ttl: float = 300.0,
) -> KeyVaultSecretLoader:
    return KeyVaultSecretLoader(vault_url=vault_url, env=env, ttl=ttl)


def _mock_secret_bundle(value: str | None) -> MagicMock:
    bundle = MagicMock()
    bundle.value = value
    return bundle


# ---------------------------------------------------------------------------
# CacheEntry TTL
# ---------------------------------------------------------------------------


def test_cache_entry_not_expired_within_ttl() -> None:
    entry = _CacheEntry(value="v", fetched_at=time.monotonic())
    assert not entry.is_expired(300.0)


def test_cache_entry_expired_after_ttl() -> None:
    entry = _CacheEntry(value="v", fetched_at=time.monotonic() - 301.0)
    assert entry.is_expired(300.0)


def test_cache_entry_expires_exactly_at_boundary() -> None:
    # At exactly ttl the entry is expired (>=)
    entry = _CacheEntry(value="v", fetched_at=time.monotonic() - 300.0)
    assert entry.is_expired(300.0)


# ---------------------------------------------------------------------------
# Development mode — env-var fallback
# ---------------------------------------------------------------------------


def test_dev_mode_reads_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_SECRET_KV", "s3cr3t")
    loader = _make_loader(env="development")
    assert loader.get("MY_SECRET_KV") == "s3cr3t"


def test_dev_mode_returns_none_for_missing_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_SECRET_KV", raising=False)
    loader = _make_loader(env="development")
    result = loader.get("MISSING_SECRET_KV", required=False, default=None)
    assert result is None


def test_dev_mode_returns_default_for_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_SECRET_KV", raising=False)
    loader = _make_loader(env="development")
    result = loader.get("MISSING_SECRET_KV", required=True, default="fallback")
    assert result == "fallback"


def test_mock_mode_reads_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_MOCK_SECRET", "mock_val")
    loader = _make_loader(env="mock")
    assert loader.get("MY_MOCK_SECRET") == "mock_val"


# ---------------------------------------------------------------------------
# Production mode — strict Key Vault
# ---------------------------------------------------------------------------


def test_production_raises_missing_secret_when_no_vault_url() -> None:
    loader = _make_loader(env="production", vault_url="")
    with pytest.raises(MissingSecretError) as exc_info:
        loader.get("JWT_SECRET")
    assert "JWT_SECRET" in str(exc_info.value)
    assert exc_info.value.secret_name == "JWT_SECRET"


def test_production_raises_missing_secret_when_vault_returns_none() -> None:
    loader = _make_loader(env="production", vault_url="https://fake.vault.azure.net/")
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle(None)
    loader._client = mock_client

    with pytest.raises(MissingSecretError) as exc_info:
        loader.get("SOME_SECRET")
    assert "SOME_SECRET" in str(exc_info.value)


def test_production_raises_on_vault_exception() -> None:
    loader = _make_loader(env="production", vault_url="https://fake.vault.azure.net/")
    mock_client = MagicMock()
    mock_client.get_secret.side_effect = Exception("Network error")
    loader._client = mock_client

    with pytest.raises(MissingSecretError) as exc_info:
        loader.get("JWT_SECRET")
    assert "JWT_SECRET" in str(exc_info.value)
    # The network error message must not leak through
    assert "Network error" not in str(exc_info.value)


def test_production_does_not_fall_back_to_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """In production, env vars MUST NOT be used as a fallback."""
    monkeypatch.setenv("JWT_SECRET", "from_env_should_not_be_used")
    loader = _make_loader(env="production", vault_url="")
    with pytest.raises(MissingSecretError):
        loader.get("JWT_SECRET")


def test_production_returns_vault_secret() -> None:
    loader = _make_loader(env="production", vault_url="https://fake.vault.azure.net/")
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle("prod_secret_value")
    loader._client = mock_client

    result = loader.get("JWT_SECRET")
    assert result == "prod_secret_value"
    # Key Vault name mapping: underscores → hyphens, lowercase
    mock_client.get_secret.assert_called_once_with("jwt-secret")


# ---------------------------------------------------------------------------
# Caching behavior
# ---------------------------------------------------------------------------


def test_cache_hit_avoids_vault_call() -> None:
    loader = _make_loader(env="production", vault_url="https://fake.vault.azure.net/", ttl=300.0)
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle("cached_value")
    loader._client = mock_client

    v1 = loader.get("JWT_SECRET")
    v2 = loader.get("JWT_SECRET")

    assert v1 == "cached_value"
    assert v2 == "cached_value"
    # Second call hits cache — vault called only once
    mock_client.get_secret.assert_called_once()


def test_cache_miss_after_ttl_expiry() -> None:
    loader = _make_loader(env="production", vault_url="https://fake.vault.azure.net/", ttl=1.0)
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle("rotated_value")
    loader._client = mock_client

    # Manually insert an expired entry
    loader._cache["JWT_SECRET"] = _CacheEntry(
        value="old_value", fetched_at=time.monotonic() - 2.0
    )

    result = loader.get("JWT_SECRET")
    assert result == "rotated_value"
    mock_client.get_secret.assert_called_once_with("jwt-secret")


def test_invalidate_single_entry() -> None:
    loader = _make_loader(env="production", vault_url="https://fake.vault.azure.net/")
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle("value")
    loader._client = mock_client

    loader.get("SECRET_A")
    loader.get("SECRET_B")
    assert "SECRET_A" in loader._cache
    assert "SECRET_B" in loader._cache

    loader.invalidate("SECRET_A")
    assert "SECRET_A" not in loader._cache
    assert "SECRET_B" in loader._cache


def test_invalidate_all() -> None:
    loader = _make_loader(env="production", vault_url="https://fake.vault.azure.net/")
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle("value")
    loader._client = mock_client

    loader.get("SECRET_A")
    loader.get("SECRET_B")

    loader.invalidate()
    assert loader._cache == {}


# ---------------------------------------------------------------------------
# Secret name mapping (underscore → hyphen)
# ---------------------------------------------------------------------------


def test_underscore_to_hyphen_mapping() -> None:
    loader = _make_loader(env="production", vault_url="https://fake.vault.azure.net/")
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle("enc_key")
    loader._client = mock_client

    loader.get("ENCRYPTION_KEY_ACTIVE")
    mock_client.get_secret.assert_called_once_with("encryption-key-active")


# ---------------------------------------------------------------------------
# TTL configured via env var
# ---------------------------------------------------------------------------


def test_ttl_configured_from_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEY_VAULT_CACHE_TTL_SECONDS", "60")
    monkeypatch.setenv("INFINITYRX_ENV", "development")
    monkeypatch.delenv("AZURE_KEYVAULT_URL", raising=False)
    loader = KeyVaultSecretLoader()
    assert loader._ttl == 60.0


# ---------------------------------------------------------------------------
# Module-level get_secret() / reset_loader_cache()
# ---------------------------------------------------------------------------


def test_module_level_get_secret_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_loader_cache()
    monkeypatch.setenv("INFINITYRX_ENV", "development")
    monkeypatch.setenv("MODULE_SECRET_KV_TEST", "hello")
    monkeypatch.delenv("AZURE_KEYVAULT_URL", raising=False)
    result = get_secret("MODULE_SECRET_KV_TEST")
    assert result == "hello"
    reset_loader_cache()


def test_module_level_get_secret_prod_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_loader_cache()
    monkeypatch.setenv("INFINITYRX_ENV", "production")
    monkeypatch.delenv("AZURE_KEYVAULT_URL", raising=False)
    monkeypatch.delenv("MISSING_PROD_SECRET_KV", raising=False)

    with pytest.raises(MissingSecretError):
        get_secret("MISSING_PROD_SECRET_KV")
    reset_loader_cache()


def test_reset_loader_cache_creates_new_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_loader_cache()
    monkeypatch.setenv("INFINITYRX_ENV", "development")
    monkeypatch.setenv("SOME_SEC_KV", "v1")
    monkeypatch.delenv("AZURE_KEYVAULT_URL", raising=False)

    import shared.key_vault as kv_mod

    get_secret("SOME_SEC_KV")
    loader_before = kv_mod._loader

    reset_loader_cache()
    get_secret("SOME_SEC_KV")
    loader_after = kv_mod._loader

    assert loader_before is not loader_after
    reset_loader_cache()


# ---------------------------------------------------------------------------
# repr — must not expose vault URL or secrets
# ---------------------------------------------------------------------------


def test_repr_does_not_expose_vault_url() -> None:
    loader = _make_loader(env="production", vault_url="https://secret-org.vault.azure.net/")
    r = repr(loader)
    assert "secret-org" not in r
    assert "vault.azure.net" not in r


# ---------------------------------------------------------------------------
# MissingSecretError attributes
# ---------------------------------------------------------------------------


def test_missing_secret_error_has_secret_name() -> None:
    err = MissingSecretError("MY_KEY", "production")
    assert err.secret_name == "MY_KEY"
    assert "MY_KEY" in str(err)
    assert "production" in str(err)


# ---------------------------------------------------------------------------
# Audit log emission (no value leakage)
# ---------------------------------------------------------------------------


def test_audit_log_emitted_on_access(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    loader = _make_loader(env="development")
    with caplog.at_level(logging.INFO, logger="shared.key_vault"):
        loader._store_cache("LOGGED_SECRET", "do_not_log_this")
        loader._log_access("LOGGED_SECRET", source="cache")

    records = [r for r in caplog.records if r.getMessage() == "vault_secret_accessed"]
    assert len(records) == 1
    r = records[0]
    assert r.__dict__["vault_secret_name"] == "LOGGED_SECRET"
    # The actual secret value must not appear anywhere in the log record
    assert "do_not_log_this" not in str(r.__dict__)


def test_audit_log_does_not_contain_secret_value(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    loader = _make_loader(env="production", vault_url="https://fake.vault.azure.net/")
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle("super_secret_value_xyz")
    loader._client = mock_client

    with caplog.at_level(logging.INFO, logger="shared.key_vault"):
        loader.get("JWT_SECRET")

    full_log_text = " ".join(r.getMessage() for r in caplog.records)
    assert "super_secret_value_xyz" not in full_log_text


# ---------------------------------------------------------------------------
# Integration tests (gated — require Azure access)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_integration_production_vault_reachable() -> None:
    """Requires AZURE_KEYVAULT_URL set and valid AKS/CLI credentials."""
    vault_url = os.environ.get("AZURE_KEYVAULT_URL")
    if not vault_url:
        pytest.skip("AZURE_KEYVAULT_URL not set — skipping integration test")

    loader = KeyVaultSecretLoader(vault_url=vault_url, env="production")
    # Verify the client initializes without error.
    client = loader._get_client()
    assert client is not None
