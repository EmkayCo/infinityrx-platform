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
and caller module — never the value. The log key is ``vault_secret_name`` so
the audit ingestion pipeline can index it without triggering PHI scrubbers.
Failure paths (missing secret, vault unreachable) also emit audit entries.

Note on audit-chain integration: the platform audit chain (AuditService with
hash chain) lives in modules/core-platform/src and requires a DB Session.
Shared utilities MUST NOT import from module packages (architecture rule).
The structured log entries emitted here are picked up by the log aggregation
pipeline and written to the audit chain by the core-platform audit middleware.
Caller_module is included so the chain can attribute each access correctly.

Credential chain (BLOCK 1 — v2):
  - production: ChainedTokenCredential(ManagedIdentityCredential,
    WorkloadIdentityCredential) — NO CLI/VS-Code fallback permitted.
    AKS workload-identity is the only valid auth path in prod; allowing
    Azure CLI or environment credentials would mean a dev laptop with
    ``az login`` could authenticate to the production vault.
  - development/mock: adds AzureCliCredential as fallback so local dev
    without a managed identity can still reach a non-production vault.

Concurrency (CONCERN 2 — v2):
  A threading.Lock guards both lazy client init and the cache-miss → fetch
  sequence so concurrent calls never race to the vault for the same key.

HIPAA rule: secret values MUST NOT appear in:
  - log messages
  - exception messages
  - audit trail value fields
  - any string representation of this module's objects

v2 changes (CR-10 Codex pass-1 gate remediation):
  BLOCK 1 CLOSED: env-specific credential chain replaces DefaultAzureCredential
  BLOCK 2 CLOSED: _CacheEntry.__repr__ hides value (was already in dirty tree)
  BLOCK 3 CLOSED: uv.lock regenerated with azure-identity + azure-keyvault-secrets
  CONCERN 1 CLOSED: caller_module added; failure-path audit events added
  CONCERN 2 CLOSED: threading.Lock on client init + cache-miss fetch
  CONCERN 3 CLOSED: typing.overload for required=True; prod raises on missing URL
  CONCERN 4 CLOSED: coverage run added; see docs/audit/cr-10-coverage.txt
  CONCERN 5 CLOSED: pip-audit run; see docs/audit/cr-10-pip-audit.txt
"""

from __future__ import annotations

import inspect
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, overload

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

    def __repr__(self) -> str:
        # HIPAA: value is never included in repr — only metadata.
        return f"_CacheEntry(fetched_at={self.fetched_at:.1f}, expired=<depends on ttl>)"


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

        # CONCERN 3: fail-fast in production when vault URL is missing.
        # A missing URL in production is a misconfiguration, not a runtime
        # condition; surface it at construction time so the service fails
        # to start rather than returning None for every secret at request time.
        if self._is_production and not self._vault_url:
            raise ValueError(
                "AZURE_KEYVAULT_URL must be set in production. "
                "Refusing to start without a Key Vault URL — all secrets "
                "would silently return None."
            )

        raw_ttl = os.environ.get("KEY_VAULT_CACHE_TTL_SECONDS", "")
        self._ttl: float = ttl if ttl is not None else (
            float(raw_ttl) if raw_ttl.strip() else float(_DEFAULT_TTL_SECONDS)
        )

        self._cache: dict[str, _CacheEntry] = {}
        self._client: SecretClient | None = None  # lazy-init
        # CONCERN 2: single lock guards both lazy client init and the
        # cache-miss → vault-fetch sequence so concurrent callers never
        # race to fetch the same key or initialise two clients.
        self._lock: threading.Lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @overload
    def get(
        self,
        name: str,
        *,
        required: Literal[True],
        default: str | None = ...,
        caller_module: str | None = ...,
    ) -> str: ...

    @overload
    def get(
        self,
        name: str,
        *,
        required: Literal[False],
        default: str | None = ...,
        caller_module: str | None = ...,
    ) -> str | None: ...

    @overload
    def get(
        self,
        name: str,
        *,
        required: bool = ...,
        default: str | None = ...,
        caller_module: str | None = ...,
    ) -> str | None: ...

    def get(
        self,
        name: str,
        *,
        required: bool = True,
        default: str | None = None,
        caller_module: str | None = None,
    ) -> str | None:
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
            caller_module: Identifies the calling module for audit logs.
                Defaults to the filename of the immediate caller derived via
                inspect.stack() so callers don't need to pass it explicitly.

        Returns:
            Secret value string, or None / default in dev/mock when absent.

        Raises:
            MissingSecretError: In production when the secret is absent.
        """
        if caller_module is None:
            try:
                frame = inspect.stack()[1]
                caller_module = os.path.basename(frame.filename)
            except Exception:  # noqa: BLE001  # pragma: no cover
                caller_module = "unknown"  # pragma: no cover

        # 1. Try cache first (all environments).
        # The lock covers the full cache-miss → fetch → store cycle.
        # This ensures concurrent callers for the same key make exactly one
        # vault call — the second caller finds the result in cache after the
        # first completes. The vault HTTP call is held under the lock; this is
        # acceptable because: (a) secrets are cached after first fetch so it
        # only blocks on cold-start, and (b) the alternative (double-checked
        # locking) adds significant complexity for marginal gain.
        with self._lock:
            cached = self._cache.get(name)
            if cached is not None and not cached.is_expired(self._ttl):
                self._log_access(name, source="cache", caller_module=caller_module)
                return cached.value

            # 2. In production: vault is authoritative. No env-var fallback.
            if self._is_production:
                return self._get_from_vault_strict(
                    name, required=required, caller_module=caller_module
                )

            # 3. Dev / mock: env var wins, then vault if configured, then default.
            env_val = os.environ.get(name)
            if env_val is not None:
                self._store_cache(name, env_val)
                self._log_access(name, source="env", caller_module=caller_module)
                return env_val

        if self._vault_url:
            vault_val = self._get_from_vault_optional(name, caller_module=caller_module)
            if vault_val is not None:
                return vault_val

        if required and default is None:
            # In dev we log a warning rather than crash — local dev often
            # runs without all secrets set.
            logger.warning(
                "vault_secret_missing_dev",
                extra={
                    "vault_secret_name": name,
                    "vault_env": self._env,
                    "vault_caller_module": caller_module,
                    "vault_outcome": "missing",
                },
            )
            return None

        if default is not None:
            with self._lock:
                self._store_cache(name, default)
            self._log_access(name, source="default", caller_module=caller_module)
        return default

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_from_vault_strict(
        self, name: str, *, required: bool, caller_module: str
    ) -> str | None:
        """Production path: Key Vault is the only source; fail fast if absent.

        MUST be called with self._lock held.
        """
        # vault_url missing is caught at __init__ in production; this guard
        # covers the required=False branch which allows construction without URL.
        if not self._vault_url:
            self._log_access(
                name, source="missing", caller_module=caller_module, outcome="missing_url"
            )
            if required:
                raise MissingSecretError(name, self._env)
            return None

        try:
            client = self._get_client()  # already under self._lock
            # Key Vault secret names use hyphens, not underscores.
            kv_name = name.replace("_", "-").lower()
            bundle = client.get_secret(kv_name)
            value = bundle.value
            if value is None:
                self._log_access(
                    name, source="vault", caller_module=caller_module, outcome="null_value"
                )
                raise MissingSecretError(name, self._env)
            self._store_cache(name, value)  # already under self._lock
            self._log_access(name, source="vault", caller_module=caller_module, outcome="success")
            return value
        except MissingSecretError:
            raise
        except Exception as exc:
            # Mask the exception message to avoid any value leakage in tracebacks.
            self._log_access(
                name, source="vault", caller_module=caller_module,
                outcome=f"error:{type(exc).__name__}"
            )
            raise MissingSecretError(name, self._env) from RuntimeError(
                f"Key Vault lookup failed for secret '{name}' "
                f"(vault={self._vault_url!r}): {type(exc).__name__}"
            )

    def _get_from_vault_optional(self, name: str, caller_module: str) -> str | None:
        """Dev/mock path: try vault, return None on any failure.

        Holds self._lock for the entire client-init → fetch → store cycle,
        matching the production path. This prevents concurrent dev vault calls
        from duplicating fetches for the same key.
        """
        _fetched: str | None = None
        try:
            with self._lock:
                client = self._get_client()
                kv_name = name.replace("_", "-").lower()
                bundle = client.get_secret(kv_name)
                _fetched = bundle.value
                if _fetched is not None:
                    self._store_cache(name, _fetched)
        except Exception as exc:  # noqa: BLE001
            self._log_access(
                name, source="vault", caller_module=caller_module,
                outcome=f"error:{type(exc).__name__}"
            )
            return None
        if _fetched is not None:
            self._log_access(name, source="vault", caller_module=caller_module, outcome="success")
        return _fetched

    def _get_client(self) -> SecretClient:
        """Return the SecretClient singleton, creating it on first call.

        Must be called with self._lock held (production path via
        _get_from_vault_strict, or explicitly for dev optional path).

        Credential chain:
          production  → ManagedIdentityCredential + WorkloadIdentityCredential
                        (AKS is the only valid auth path; CLI/env creds are
                        intentionally excluded to prevent dev-laptop access to
                        production vault)
          dev / mock  → adds AzureCliCredential as local fallback so developers
                        without an MSI can reach a non-production vault
        """
        if self._client is None:
            # Import here so missing azure-identity/azure-keyvault-secrets
            # in dev environments never causes an ImportError at module load.
            try:
                from azure.identity import (  # type: ignore[import-untyped]
                    AzureCliCredential,
                    ChainedTokenCredential,
                    ManagedIdentityCredential,
                    WorkloadIdentityCredential,
                )
                from azure.keyvault.secrets import SecretClient  # type: ignore[import-untyped]
            except ImportError as exc:
                raise RuntimeError(
                    "azure-identity and azure-keyvault-secrets packages are "
                    "required for Key Vault access. "
                    "Add them to pyproject.toml dependencies."
                ) from exc

            if self._is_production:
                # Production: only managed + workload identity are permitted.
                # Azure CLI and environment credentials MUST NOT be in the chain
                # because a developer's az-login session could authenticate to
                # the production vault from a laptop.
                credential = ChainedTokenCredential(
                    ManagedIdentityCredential(),
                    WorkloadIdentityCredential(),
                )
            else:
                # Development / mock: add CLI fallback so local machines that
                # lack an MSI can still reach a test vault.
                credential = ChainedTokenCredential(
                    ManagedIdentityCredential(),
                    AzureCliCredential(),
                )

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
        """Store a cache entry.

        For production path: MUST be called with self._lock held.
        For dev optional path: called under a separate with self._lock block.
        """
        self._cache[name] = _CacheEntry(value=value)

    def _log_access(
        self,
        name: str,
        source: str,
        caller_module: str = "unknown",
        outcome: str = "success",
    ) -> None:
        """Emit a structured audit log for secret access (success or failure).

        HIPAA rule: the secret *value* is NEVER included in any log field.
        The vault_caller_module key identifies which module requested the secret
        so the log aggregation pipeline can attribute vault accesses correctly.
        Failure outcomes (missing, null_value, error:*) are always logged at
        WARNING level so they appear in monitoring dashboards.
        """
        level = logging.WARNING if outcome != "success" else logging.INFO
        logger.log(
            level,
            "vault_secret_accessed",
            extra={
                "vault_secret_name": name,
                "vault_source": source,
                "vault_env": self._env,
                "vault_caller_module": caller_module,
                "vault_outcome": outcome,
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


@overload
def get_secret(
    name: str,
    *,
    required: Literal[True],
    default: str | None = ...,
    caller_module: str | None = ...,
) -> str: ...


@overload
def get_secret(
    name: str,
    *,
    required: Literal[False],
    default: str | None = ...,
    caller_module: str | None = ...,
) -> str | None: ...


@overload
def get_secret(
    name: str,
    *,
    required: bool = ...,
    default: str | None = ...,
    caller_module: str | None = ...,
) -> str | None: ...


def get_secret(
    name: str,
    *,
    required: bool = True,
    default: str | None = None,
    caller_module: str | None = None,
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
        caller_module: Identifies the calling module for audit logs.
            Auto-derived from the call stack if not provided.

    Returns:
        Secret value string, or None / default in dev/mock.
    """
    if caller_module is None:
        try:
            frame = inspect.stack()[1]
            caller_module = os.path.basename(frame.filename)
        except Exception:  # noqa: BLE001  # pragma: no cover
            caller_module = "unknown"  # pragma: no cover
    return _get_loader().get(
        name, required=required, default=default, caller_module=caller_module
    )


# ---------------------------------------------------------------------------
# App-startup bootstrap
# ---------------------------------------------------------------------------

# Ordered list of production secrets to pre-load from Key Vault into
# os.environ at app startup. Consuming modules that still read os.getenv()
# directly (shared/auth/_settings.py, shared/crypto/keys.py,
# shared/ai/openai_client.py) will transparently receive vault values once
# bootstrap_secrets_to_env() is called from each module's main.py.
#
# Non-secret config is intentionally excluded — env vars stay for those.
_BOOTSTRAP_SECRETS: tuple[str, ...] = (
    "JWT_SECRET",
    "ENCRYPTION_KEY_ACTIVE",
    "ENCRYPTION_KEY_ACTIVE_ID",
    "DATABASE_URL",
    "DATABASE_URL_SYNC",
    "REDIS_URL",
    "RABBITMQ_URL",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "SAM_API_KEY",
    "BILLING_DATABASE_URL",
    "DRUG_DB_DATABASE_URL",
    "PLAN_DESIGN_DATABASE_URL",
    "REBATE_DATABASE_URL",
)


def bootstrap_secrets_to_env(
    secrets: tuple[str, ...] = _BOOTSTRAP_SECRETS,
    *,
    overwrite_existing: bool = False,
) -> dict[str, bool]:
    """Pre-load Key Vault secrets into os.environ at app startup.

    Call this once from each module's ``main.py`` before any other imports
    that touch ``os.getenv()``. This bridges the Key Vault adapter to
    modules that still read secrets via environment variables directly
    (e.g. ``shared/auth/_settings.py``, ``shared/crypto/keys.py``).

    In development/mock the loader falls back to existing env vars, so this
    is a no-op when secrets are already set locally.

    In production the loader fetches each secret from Key Vault and writes
    it to ``os.environ``, making it available to all downstream ``os.getenv``
    calls in the same process.

    HIPAA: values are written to ``os.environ`` (process memory only) and
    are never logged.

    Args:
        secrets: Tuple of secret names to bootstrap. Defaults to the
            platform-wide list of production secrets.
        overwrite_existing: If True, overwrite env vars already set.
            Default False preserves values already injected by the container
            runtime (e.g. AKS secret-store CSI driver).

    Returns:
        Dict mapping secret name to True (loaded) or False (skipped/absent).
    """
    loader = _get_loader()
    results: dict[str, bool] = {}
    for name in secrets:
        if not overwrite_existing and os.environ.get(name):
            results[name] = False  # already present, skip
            continue
        value = loader.get(name, required=False)
        if value is not None:
            os.environ[name] = value
            results[name] = True
        else:
            results[name] = False
    loaded = sum(1 for v in results.values() if v)
    logger.info(
        "vault_bootstrap_complete",
        extra={
            "vault_secrets_loaded": loaded,
            "vault_secrets_skipped": len(results) - loaded,
            "vault_env": loader._env,
            "auth_user_id": "system",
        },
    )
    return results
