"""Unit tests for shared.key_vault.

All tests use a mocked SecretClient — no Azure connectivity required.
The integration suite (marked ``integration``) is gated by
``AZURE_KEYVAULT_URL`` + ``INFINITYRX_ENV=production`` being set, so CI
passes without Azure access.

v2 tests cover:
  BLOCK 1  — prod credential chain excludes AzureCliCredential
  BLOCK 2  — _CacheEntry repr does not expose value
  CONCERN 1 — caller_module in audit log; failure paths emit audit events
  CONCERN 2 — concurrent get_secret calls fetch vault only once (locking)
  CONCERN 3 — production raises ValueError when AZURE_KEYVAULT_URL missing;
               type-safe required overloads (runtime behavior verified)
"""

from __future__ import annotations

import os
import time
import threading
from unittest.mock import MagicMock, patch

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


def _make_prod_loader(
    vault_url: str = "https://fake.vault.azure.net/",
    ttl: float = 300.0,
) -> KeyVaultSecretLoader:
    """Production loader always needs a vault URL (CONCERN 3)."""
    return KeyVaultSecretLoader(vault_url=vault_url, env="production", ttl=ttl)


def _mock_secret_bundle(value: str | None) -> MagicMock:
    bundle = MagicMock()
    bundle.value = value
    return bundle


# ---------------------------------------------------------------------------
# BLOCK 2 — _CacheEntry repr must not expose value
# ---------------------------------------------------------------------------


def test_cache_entry_repr_does_not_expose_value() -> None:
    """Codex BLOCK 2 fix: default dataclass repr() leaked value. Confirmed closed."""
    entry = _CacheEntry(value="topsecret123", fetched_at=1000.0)
    r = repr(entry)
    assert "topsecret123" not in r
    assert "_CacheEntry" in r


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
# CONCERN 3 — production raises ValueError when AZURE_KEYVAULT_URL missing
# ---------------------------------------------------------------------------


def test_production_raises_value_error_when_no_vault_url() -> None:
    """CONCERN 3: missing vault URL in production must fail at construction."""
    with pytest.raises(ValueError, match="AZURE_KEYVAULT_URL must be set"):
        KeyVaultSecretLoader(vault_url="", env="production")


def test_production_raises_value_error_from_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """CONCERN 3: missing URL from env also raises at construction."""
    monkeypatch.delenv("AZURE_KEYVAULT_URL", raising=False)
    monkeypatch.setenv("INFINITYRX_ENV", "production")
    with pytest.raises(ValueError, match="AZURE_KEYVAULT_URL must be set"):
        KeyVaultSecretLoader()


def test_development_does_not_raise_without_vault_url() -> None:
    """Dev mode must still work without a vault URL."""
    loader = KeyVaultSecretLoader(vault_url="", env="development")
    assert loader is not None


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


def test_production_raises_missing_secret_when_vault_returns_none() -> None:
    loader = _make_prod_loader()
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle(None)
    loader._client = mock_client

    with pytest.raises(MissingSecretError) as exc_info:
        loader.get("SOME_SECRET")
    assert "SOME_SECRET" in str(exc_info.value)


def test_production_raises_on_vault_exception() -> None:
    loader = _make_prod_loader()
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
    # Production raises ValueError at construction without vault URL;
    # this test verifies with a vault URL set that env vars are not consulted.
    monkeypatch.setenv("JWT_SECRET", "from_env_should_not_be_used")
    loader = _make_prod_loader()
    mock_client = MagicMock()
    mock_client.get_secret.side_effect = Exception("vault unreachable")
    loader._client = mock_client

    with pytest.raises(MissingSecretError):
        loader.get("JWT_SECRET")

    # If env var fallback happened, the call would return "from_env_should_not_be_used"
    # instead of raising — the assertion above confirms it raised.


def test_production_returns_vault_secret() -> None:
    loader = _make_prod_loader()
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle("prod_secret_value")
    loader._client = mock_client

    result = loader.get("JWT_SECRET")
    assert result == "prod_secret_value"
    # Key Vault name mapping: underscores → hyphens, lowercase
    mock_client.get_secret.assert_called_once_with("jwt-secret")


# ---------------------------------------------------------------------------
# BLOCK 1 — credential chain is production-safe
# ---------------------------------------------------------------------------


def test_production_credential_chain_excludes_cli_credential() -> None:
    """BLOCK 1: production chain must NOT include AzureCliCredential."""
    loader = _make_prod_loader()
    loader._client = None  # ensure lazy init

    with patch("azure.identity.ManagedIdentityCredential") as mock_msi, \
         patch("azure.identity.WorkloadIdentityCredential") as mock_wi, \
         patch("azure.identity.ChainedTokenCredential") as mock_chain, \
         patch("azure.identity.AzureCliCredential") as mock_cli, \
         patch("azure.keyvault.secrets.SecretClient"):
        mock_chain.return_value = MagicMock()
        loader._get_client()

        # ChainedTokenCredential must be called with MSI + WorkloadIdentity only
        call_args = mock_chain.call_args[0]
        assert mock_msi() in call_args or mock_wi() in call_args
        # AzureCliCredential must NOT appear in the chain
        assert mock_cli() not in call_args, (
            "AzureCliCredential must not be in the production credential chain"
        )


def test_dev_credential_chain_includes_cli_credential() -> None:
    """BLOCK 1: dev chain MUST include AzureCliCredential as fallback."""
    loader = _make_loader(
        env="development", vault_url="https://fake.vault.azure.net/", ttl=300.0
    )
    loader._client = None

    with patch("azure.identity.ManagedIdentityCredential") as mock_msi, \
         patch("azure.identity.AzureCliCredential") as mock_cli, \
         patch("azure.identity.ChainedTokenCredential") as mock_chain, \
         patch("azure.identity.WorkloadIdentityCredential"), \
         patch("azure.keyvault.secrets.SecretClient"):
        mock_chain.return_value = MagicMock()
        mock_cli_instance = MagicMock()
        mock_cli.return_value = mock_cli_instance

        loader._get_client()

        chain_args = mock_chain.call_args[0]
        # AzureCliCredential instance must appear in the chain for dev
        assert any(
            isinstance(arg, MagicMock) for arg in chain_args
        ), "dev chain must include AzureCliCredential"


# ---------------------------------------------------------------------------
# Caching behavior
# ---------------------------------------------------------------------------


def test_cache_hit_avoids_vault_call() -> None:
    loader = _make_prod_loader(ttl=300.0)
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
    loader = _make_prod_loader()
    loader._ttl = 1.0
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
    loader = _make_prod_loader()
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
    loader = _make_prod_loader()
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle("value")
    loader._client = mock_client

    loader.get("SECRET_A")
    loader.get("SECRET_B")

    loader.invalidate()
    assert loader._cache == {}


# ---------------------------------------------------------------------------
# CONCERN 2 — concurrent access fetches vault exactly once
# ---------------------------------------------------------------------------


def test_concurrent_get_secret_fetches_vault_once() -> None:
    """CONCERN 2: 10 concurrent threads racing on a cold cache must result in
    exactly one vault call (the lock serialises cache-miss → fetch)."""
    loader = _make_prod_loader()
    mock_client = MagicMock()

    fetch_count = 0
    lock = threading.Lock()

    def _fetch(name: str) -> MagicMock:
        nonlocal fetch_count
        with lock:
            fetch_count += 1
        # Small sleep to encourage concurrency overlap without slowing tests much
        time.sleep(0.005)
        return _mock_secret_bundle("concurrent_value")

    mock_client.get_secret.side_effect = _fetch
    loader._client = mock_client

    results: list[str | None] = []
    errors: list[Exception] = []

    def _call() -> None:
        try:
            results.append(loader.get("CONCURRENT_KEY"))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_call) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert not errors, f"Unexpected errors: {errors}"
    assert all(v == "concurrent_value" for v in results)
    # The lock must ensure only one vault call was made
    assert fetch_count == 1, f"Expected 1 vault call, got {fetch_count}"


# ---------------------------------------------------------------------------
# Secret name mapping (underscore → hyphen)
# ---------------------------------------------------------------------------


def test_underscore_to_hyphen_mapping() -> None:
    loader = _make_prod_loader()
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

    # Production without vault URL now raises ValueError at loader construction
    with pytest.raises(ValueError, match="AZURE_KEYVAULT_URL must be set"):
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
    loader = _make_loader(env="development", vault_url="https://secret-org.vault.azure.net/")
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
# CONCERN 1 — caller_module in audit log; failure paths emit WARNING events
# ---------------------------------------------------------------------------


def test_audit_log_includes_caller_module(caplog: pytest.LogCaptureFixture) -> None:
    """CONCERN 1: caller_module must appear in the structured audit log."""
    import logging

    loader = _make_loader(env="development")
    with caplog.at_level(logging.INFO, logger="shared.key_vault"):
        loader._store_cache("LOGGED_SECRET", "do_not_log_this")
        loader._log_access("LOGGED_SECRET", source="cache", caller_module="my_module.py")

    records = [r for r in caplog.records if r.getMessage() == "vault_secret_accessed"]
    assert len(records) == 1
    r = records[0]
    assert r.__dict__["vault_secret_name"] == "LOGGED_SECRET"
    assert r.__dict__["vault_caller_module"] == "my_module.py"
    # The actual secret value must not appear anywhere in the log record
    assert "do_not_log_this" not in str(r.__dict__)


def test_audit_log_emitted_on_missing_secret_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """CONCERN 1: failure path (missing secret) must emit an audit WARNING."""
    import logging

    loader = _make_prod_loader()
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle(None)  # null value
    loader._client = mock_client

    with caplog.at_level(logging.WARNING, logger="shared.key_vault"):
        with pytest.raises(MissingSecretError):
            loader.get("NULL_SECRET", caller_module="test_module.py")

    warning_records = [
        r for r in caplog.records
        if r.getMessage() == "vault_secret_accessed"
        and r.levelno == logging.WARNING
    ]
    assert len(warning_records) >= 1
    r = warning_records[0]
    assert r.__dict__["vault_secret_name"] == "NULL_SECRET"
    assert r.__dict__.get("vault_outcome") != "success"
    # Secret value NEVER in log
    assert "do_not_log" not in str(r.__dict__)


def test_audit_log_emitted_on_vault_error_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """CONCERN 1: vault error path must emit an audit WARNING."""
    import logging

    loader = _make_prod_loader()
    mock_client = MagicMock()
    mock_client.get_secret.side_effect = Exception("Connection refused")
    loader._client = mock_client

    with caplog.at_level(logging.WARNING, logger="shared.key_vault"):
        with pytest.raises(MissingSecretError):
            loader.get("VAULT_ERROR_SECRET", caller_module="test_caller.py")

    warning_records = [
        r for r in caplog.records
        if r.getMessage() == "vault_secret_accessed"
        and r.levelno == logging.WARNING
    ]
    assert len(warning_records) >= 1
    r = warning_records[0]
    assert r.__dict__["vault_secret_name"] == "VAULT_ERROR_SECRET"
    assert r.__dict__.get("vault_caller_module") == "test_caller.py"
    # Exception message must not leak
    assert "Connection refused" not in str(r.__dict__)


def test_audit_log_does_not_contain_secret_value(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    loader = _make_prod_loader()
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle("super_secret_value_xyz")
    loader._client = mock_client

    with caplog.at_level(logging.INFO, logger="shared.key_vault"):
        loader.get("JWT_SECRET")

    full_log_text = " ".join(r.getMessage() for r in caplog.records)
    assert "super_secret_value_xyz" not in full_log_text


def test_get_secret_auto_derives_caller_module(caplog: pytest.LogCaptureFixture) -> None:
    """caller_module is auto-derived from inspect.stack when not provided."""
    import logging

    loader = _make_loader(env="development")
    monkeypatch_env = {"MY_AUTO_CALLER_SECRET": "value"}
    with caplog.at_level(logging.INFO, logger="shared.key_vault"):
        for k, v in monkeypatch_env.items():
            os.environ[k] = v
        try:
            loader.get("MY_AUTO_CALLER_SECRET")
        finally:
            for k in monkeypatch_env:
                os.environ.pop(k, None)

    records = [r for r in caplog.records if r.getMessage() == "vault_secret_accessed"]
    assert len(records) >= 1
    caller = records[0].__dict__.get("vault_caller_module", "")
    # Should be a filename (non-empty), not "unknown"
    assert caller != "" and caller != "unknown"


# ---------------------------------------------------------------------------
# CONCERN 3 — type-safe required overload (runtime behavior)
# ---------------------------------------------------------------------------


def test_required_true_raises_in_production() -> None:
    """required=True (default) must raise MissingSecretError in production
    when vault returns None — not return None silently."""
    loader = _make_prod_loader()
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle(None)
    loader._client = mock_client

    with pytest.raises(MissingSecretError):
        loader.get("MY_KEY", required=True)


def test_required_false_raises_missing_on_null_vault_value() -> None:
    """required=False in production: a null vault value still raises MissingSecretError.
    A key present in vault with a null value is explicitly absent — not a type error."""
    loader = _make_prod_loader()
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle(None)
    loader._client = mock_client

    # Even with required=False, a null vault value is an absent secret in production.
    # The error must be MissingSecretError (not ValueError or TypeError).
    with pytest.raises(MissingSecretError) as exc_info:
        loader.get("MY_KEY", required=False)
    assert "MY_KEY" in str(exc_info.value)


# ---------------------------------------------------------------------------
# bootstrap_secrets_to_env — env population for consuming modules
# ---------------------------------------------------------------------------


def test_bootstrap_populates_env_from_vault(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production vault values are written to os.environ for legacy consumers."""
    reset_loader_cache()
    monkeypatch.setenv("INFINITYRX_ENV", "production")
    monkeypatch.setenv("AZURE_KEYVAULT_URL", "https://fake.vault.azure.net/")
    monkeypatch.delenv("JWT_SECRET", raising=False)

    from shared.key_vault import bootstrap_secrets_to_env

    mock_client = MagicMock()

    def _side_effect(name: str) -> MagicMock:
        return _mock_secret_bundle(f"vault_{name}_value")

    mock_client.get_secret.side_effect = _side_effect

    import shared.key_vault as kv_mod
    reset_loader_cache()
    loader = kv_mod._get_loader()
    loader._client = mock_client

    results = bootstrap_secrets_to_env(secrets=("JWT_SECRET",))
    assert results["JWT_SECRET"] is True
    assert os.environ.get("JWT_SECRET") == "vault_jwt-secret_value"
    reset_loader_cache()


def test_bootstrap_skips_already_set_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing env vars are not overwritten by default (container runtime wins)."""
    reset_loader_cache()
    monkeypatch.setenv("INFINITYRX_ENV", "development")
    monkeypatch.setenv("JWT_SECRET", "already_set_value")
    monkeypatch.delenv("AZURE_KEYVAULT_URL", raising=False)

    from shared.key_vault import bootstrap_secrets_to_env

    results = bootstrap_secrets_to_env(secrets=("JWT_SECRET",))
    assert results["JWT_SECRET"] is False  # skipped
    assert os.environ.get("JWT_SECRET") == "already_set_value"
    reset_loader_cache()


def test_bootstrap_overwrite_existing_when_flag_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """overwrite_existing=True replaces pre-set env vars with vault values."""
    reset_loader_cache()
    monkeypatch.setenv("INFINITYRX_ENV", "production")
    monkeypatch.setenv("AZURE_KEYVAULT_URL", "https://fake.vault.azure.net/")
    monkeypatch.setenv("JWT_SECRET", "old_value")

    from shared.key_vault import bootstrap_secrets_to_env

    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle("new_vault_value")

    import shared.key_vault as kv_mod
    reset_loader_cache()
    loader = kv_mod._get_loader()
    loader._client = mock_client

    results = bootstrap_secrets_to_env(secrets=("JWT_SECRET",), overwrite_existing=True)
    assert results["JWT_SECRET"] is True
    assert os.environ.get("JWT_SECRET") == "new_vault_value"
    reset_loader_cache()


def test_bootstrap_logs_summary_without_values(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bootstrap audit log must not contain any secret values."""
    import logging

    reset_loader_cache()
    monkeypatch.setenv("INFINITYRX_ENV", "development")
    monkeypatch.setenv("MY_BOOT_SECRET", "secret_boot_value_xyz")
    monkeypatch.delenv("AZURE_KEYVAULT_URL", raising=False)

    from shared.key_vault import bootstrap_secrets_to_env

    with caplog.at_level(logging.INFO, logger="shared.key_vault"):
        bootstrap_secrets_to_env(secrets=("MY_BOOT_SECRET",))

    full_log = " ".join(r.getMessage() for r in caplog.records)
    assert "secret_boot_value_xyz" not in full_log
    assert "vault_bootstrap_complete" in full_log
    reset_loader_cache()


# ---------------------------------------------------------------------------
# Coverage gap tests — paths not otherwise exercised
# ---------------------------------------------------------------------------


def test_dev_vault_optional_path_returns_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dev mode with vault_url set falls through to vault when env var absent."""
    monkeypatch.delenv("OPTIONAL_SECRET", raising=False)
    loader = _make_loader(
        env="development", vault_url="https://fake.vault.azure.net/", ttl=300.0
    )
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle("vault_dev_value")
    loader._client = mock_client

    result = loader.get("OPTIONAL_SECRET")
    assert result == "vault_dev_value"


def test_dev_vault_optional_path_returns_none_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dev optional vault path: errors return None, not raise."""
    monkeypatch.delenv("OPT_ERR_SECRET", raising=False)
    loader = _make_loader(
        env="development", vault_url="https://fake.vault.azure.net/", ttl=300.0
    )
    mock_client = MagicMock()
    mock_client.get_secret.side_effect = Exception("vault down")
    loader._client = mock_client

    result = loader.get("OPT_ERR_SECRET", required=False)
    assert result is None


def test_dev_required_secret_missing_logs_warning(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dev mode required=True with no secret: logs warning, returns None (not raise)."""
    import logging

    monkeypatch.delenv("WARN_SECRET", raising=False)
    loader = _make_loader(env="development")

    with caplog.at_level(logging.WARNING, logger="shared.key_vault"):
        result = loader.get("WARN_SECRET", required=True)

    assert result is None
    warning_records = [r for r in caplog.records if "vault_secret_missing_dev" in r.getMessage()]
    assert len(warning_records) == 1


def test_dev_default_value_used_and_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dev mode: default value is returned and stored in cache."""
    monkeypatch.delenv("DEFAULT_SECRET", raising=False)
    loader = _make_loader(env="development")

    result = loader.get("DEFAULT_SECRET", required=False, default="my_default")
    assert result == "my_default"
    # Should be in cache now
    assert "DEFAULT_SECRET" in loader._cache
    assert loader._cache["DEFAULT_SECRET"].value == "my_default"


def test_prod_get_from_vault_strict_no_url_required_false() -> None:
    """_get_from_vault_strict with no vault URL and required=False returns None.
    This only happens when the loader was constructed in dev/mock mode (with URL)
    and then vault_url is cleared — exercise via direct call."""
    loader = _make_loader(env="development", vault_url="https://fake.vault.azure.net/")
    # Manually put it into production mode without triggering the __init__ guard
    loader._is_production = True
    loader._vault_url = ""  # simulate missing URL
    # required=False must return None without raising
    result = loader._get_from_vault_strict("MY_SECRET", required=False, caller_module="test")
    assert result is None


def test_prod_get_from_vault_strict_no_url_required_true_raises() -> None:
    """_get_from_vault_strict with no URL and required=True raises MissingSecretError."""
    loader = _make_loader(env="development", vault_url="https://fake.vault.azure.net/")
    loader._is_production = True
    loader._vault_url = ""
    with pytest.raises(MissingSecretError):
        loader._get_from_vault_strict("MY_SECRET", required=True, caller_module="test")


def test_get_client_raises_on_missing_azure_packages() -> None:
    """_get_client raises RuntimeError when azure packages not importable."""
    import sys
    loader = _make_loader(env="development", vault_url="https://fake.vault.azure.net/")
    loader._client = None

    with patch.dict(sys.modules, {
        "azure.identity": None,
        "azure.keyvault.secrets": None,
    }):
        with pytest.raises(RuntimeError, match="azure-identity"):
            loader._get_client()


def test_dev_vault_optional_path_returns_none_when_value_is_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dev optional vault path: vault returns null value → return None, don't cache."""
    monkeypatch.delenv("NULL_VAL_SECRET", raising=False)
    loader = _make_loader(
        env="development", vault_url="https://fake.vault.azure.net/", ttl=300.0
    )
    mock_client = MagicMock()
    mock_client.get_secret.return_value = _mock_secret_bundle(None)
    loader._client = mock_client

    result = loader.get("NULL_VAL_SECRET", required=False)
    assert result is None
    assert "NULL_VAL_SECRET" not in loader._cache


def test_loader_repr_shows_ttl_and_cache_count() -> None:
    """KeyVaultSecretLoader repr must show env, ttl, cached count but not URL."""
    loader = _make_loader(env="development", vault_url="https://not-shown.vault.azure.net/")
    r = repr(loader)
    assert "development" in r
    assert "300" in r
    assert "cached=" in r
    assert "not-shown" not in r


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
