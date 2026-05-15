"""Azure Key Vault secret adapter for InfinityRx production deployments.

Design (CR-10, HIPAA-2026):

  - development / mock  → env-var fallback; no Azure SDK required
  - production          → REQUIRES Azure Key Vault; MissingSecretError on
                          absent secret — no silent env-var fallback

Loading is lazy: the vault client is created on the first get_secret() call,
not at import time. This keeps local dev bootstraps working even when the
azure-identity package is not installed.

Cache: secrets are held in process memory with a configurable TTL (default 5
minutes, KEY_VAULT_CACHE_TTL_SECONDS env var). Rotation is picked up within
one TTL window without a restart.

Audit: every secret access emits a structured log entry with the secret name
only — never the value. The log key is ``vault_secret_name`` so the audit
ingestion pipeline can index it without triggering PHI scrubbers.

HIPAA rule: secret values MUST NOT appear in:
  - log messages
  - exception messages
  - audit trail value fields
  - any string representation of this module's objects
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Type-only import so the azure SDK absence never causes an ImportError
    # in dev/mock environments where it may not be installed.
    from azure.keyvault.secrets import SecretClient  # type: ignore[import-untyped]

logger = logging.getLogger("shared.key_vault")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_TTL_SECONDS = 300  # 5 minutes
_ENV_PRODUCTION = frozenset({"production", "prod"})

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MissingSecretError(RuntimeError):
    """Raised when a required secret is absent and no fallback is permitted.

    The message includes the secret *name* only — never the value.
    """

    def __init__(self, name: str, env: str) -> None:
        super().__init__(
            f"Required secret '{name}' is not available "
            f"(env={env!r}). "
            "Ensure the secret is present in Azure Key Vault or, for local "
            "development, set the corresponding environment variable."
        )
        self.secret_name = name


# ---------------------------------------------------------------------------
# Cache entry
# ---------------------------------------------------------------------------


@dataclass
class _CacheEntry:
    value: str
    fetched_at: float = field(default_factory=time.monotonic)

    def is_expired(self, ttl: float) -> bool:
        return (time.monotonic() - self.fetched_at) >= ttl


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class KeyVaultSecretLoader:
    """Loads secrets from Azure Key Vault in production; env vars otherwise.

    Args:
        vault_url: Azure Key Vault URL, e.g.
            ``https://infinityrx-prod.vault.azure.net/``.
            Defaults to ``AZURE_KEYVAULT_URL`` env var.
        env: Active environment name. Defaults to ``INFINITYRX_ENV`` env var.
        ttl: Cache TTL in seconds. Defaults to ``KEY_VAULT_CACHE_TTL_SECONDS``
            env var, then 300.
    """

    def __init__(
        self,
        vault_url: str | None = None,
        env: str | None = None,
        ttl: float | None = None,
    ) -> None:
        self._vault_url: str = (
            vault_url
            or os.environ.get("AZURE_KEYVAULT_URL", "").strip()
        )
        raw_env = (env or os.environ.get("INFINITYRX_ENV", "")).strip().lower()
        self._env: str = raw_env
        self._is_production: bool = raw_env in _ENV_PRODUCTION

        raw_ttl = os.environ.get("KEY_VAULT_CACHE_TTL_SECONDS", "")
        self._ttl: float = ttl if ttl is not None else (
            float(raw_ttl) if raw_ttl.strip() else float(_DEFAULT_TTL_SECONDS)
        )

        self._cache: dict[str, _CacheEntry] = {}
        self._client: SecretClient | None = None  # lazy-init

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, name: str, *, required: bool = True, default: str | None = None) -> str | None:
        """Return the named secret value.

        In production the secret MUST come from Key Vault.
        In development/mock an env-var fallback is tried first, then Key Vault
        if configured, then ``default``.

        Args:
            name: Secret name (maps directly to Key Vault secret name and
                environment variable name).
            required: If True and the secret is absent in production, raises
                MissingSecretError. Ignored in dev/mock.
            default: Value returned when secret is absent in dev/mock and no
                env var is set. Ignored in production (MissingSecretError is
                raised instead).

        Returns:
            Secret value string, or None / default in dev/mock when absent.

        Raises:
            MissingSecretError: In production when the secret is absent.
        """
        # 1. Try cache first (all environments).
        cached = self._cache.get(name)
        if cached is not None and not cached.is_expired(self._ttl):
            self._log_access(name, source="cache")
            return cached.value

        # 2. In production: vault is authoritative. No env-var fallback.
        if self._is_production:
            return self._get_from_vault_strict(name, required=required)

        # 3. Dev / mock: env var wins, then vault if configured, then default.
        env_val = os.environ.get(name)
        if env_val is not None:
            self._store_cache(name, env_val)
            self._log_access(name, source="env")
            return env_val

        if self._vault_url:
            vault_val = self._get_from_vault_optional(name)
            if vault_val is not None:
                return vault_val

        if required and default is None:
            # In dev we log a warning rather than crash — local dev often
            # runs without all secrets set.
            logger.warning(
                "vault_secret_missing_dev",
                extra={"vault_secret_name": name, "vault_env": self._env},
            )
            return None

        if default is not None:
            self._store_cache(name, default)
            self._log_access(name, source="default")
        return default

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_from_vault_strict(self, name: str, *, required: bool) -> str | None:
        """Production path: Key Vault is the only source; fail fast if absent."""
        if not self._vault_url:
            if required:
                raise MissingSecretError(name, self._env)
            return None

        try:
            client = self._get_client()
            # Key Vault secret names use hyphens, not underscores.
            kv_name = name.replace("_", "-").lower()
            bundle = client.get_secret(kv_name)
            value = bundle.value
            if value is None:
                raise MissingSecretError(name, self._env)
            self._store_cache(name, value)
            self._log_access(name, source="vault")
            return value
        except MissingSecretError:
            raise
        except Exception as exc:
            # Mask the exception message to avoid any value leakage in tracebacks.
            raise MissingSecretError(name, self._env) from RuntimeError(
                f"Key Vault lookup failed for secret '{name}' "
                f"(vault={self._vault_url!r}): {type(exc).__name__}"
            )

    def _get_from_vault_optional(self, name: str) -> str | None:
        """Dev/mock path: try vault, return None on any failure."""
        try:
            client = self._get_client()
            kv_name = name.replace("_", "-").lower()
            bundle = client.get_secret(kv_name)
            value = bundle.value
            if value is not None:
                self._store_cache(name, value)
                self._log_access(name, source="vault")
            return value
        except Exception:
            return None

    def _get_client(self) -> SecretClient:
        """Return the SecretClient singleton, creating it on first call."""
        if self._client is None:
            # Import here so missing azure-identity/azure-keyvault-secrets
            # in dev environments never causes an ImportError at module load.
            try:
                from azure.identity import DefaultAzureCredential  # type: ignore[import-untyped]
                from azure.keyvault.secrets import SecretClient  # type: ignore[import-untyped]
            except ImportError as exc:
                raise RuntimeError(
                    "azure-identity and azure-keyvault-secrets packages are "
                    "required for Key Vault access. "
                    "Add them to pyproject.toml dependencies."
                ) from exc

            credential = DefaultAzureCredential()
            self._client = SecretClient(
                vault_url=self._vault_url,
                credential=credential,
            )
            logger.info(
                "vault_client_initialized",
                extra={
                    "vault_url": self._vault_url,
                    "vault_env": self._env,
                },
            )
        return self._client  # type: ignore[return-value]

    def _store_cache(self, name: str, value: str) -> None:
        self._cache[name] = _CacheEntry(value=value)

    def _log_access(self, name: str, source: str) -> None:
        """Emit a structured audit log for secret access.

        HIPAA rule: the secret *value* is NEVER included in any log field.
        """
        logger.info(
            "vault_secret_accessed",
            extra={
                "vault_secret_name": name,
                "vault_source": source,
                "vault_env": self._env,
                "auth_user_id": "system",
            },
        )

    def invalidate(self, name: str | None = None) -> None:
        """Invalidate cache for one or all secrets.

        Used by rotation tests and by signal handlers that want to force
        an immediate re-fetch without waiting for TTL expiry.
        """
        if name is None:
            self._cache.clear()
        else:
            self._cache.pop(name, None)

    def __repr__(self) -> str:
        # Deliberately omit vault URL (could contain tenant info).
        return (
            f"KeyVaultSecretLoader(env={self._env!r}, "
            f"ttl={self._ttl}s, "
            f"cached={len(self._cache)})"
        )


# ---------------------------------------------------------------------------
# Module-level singleton + convenience accessor
# ---------------------------------------------------------------------------

_loader: KeyVaultSecretLoader | None = None


def _get_loader() -> KeyVaultSecretLoader:
    global _loader
    if _loader is None:
        _loader = KeyVaultSecretLoader()
    return _loader


def reset_loader_cache() -> None:
    """Discard the singleton and its cache. Tests use this for isolation."""
    global _loader
    _loader = None


def get_secret(
    name: str,
    *,
    required: bool = True,
    default: str | None = None,
) -> str | None:
    """Module-level accessor — thin wrapper over the singleton loader.

    Drop-in replacement for ``os.getenv(name)`` at secret call sites.

    In production, ``required=True`` (the default) raises MissingSecretError
    if the secret is absent.  In development the same call returns None with
    a warning log so local bootstraps are not broken by missing optional keys.

    Args:
        name: Secret / env-var name (e.g. ``"JWT_SECRET"``).
        required: Raise MissingSecretError in production if absent.
        default: Returned in dev/mock when the secret is absent.

    Returns:
        Secret value string, or None / default in dev/mock.
    """
    return _get_loader().get(name, required=required, default=default)
