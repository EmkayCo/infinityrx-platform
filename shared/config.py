"""Platform configuration loader.

Loads settings from environment variables, seeded by the .env file matching
the active environment. Exposes a cached singleton `get_settings()` that
returns a validated `Settings` instance. All downstream modules MUST read
configuration through this module — never `os.environ` directly — so that
validation is centralised and tests can override settings deterministically.

Environment selection (see CLAUDE.md → Environment Architecture):

  INFINITYRX_ENV=development → loads .env.dev   (or .env.local if present)
  INFINITYRX_ENV=mock        → loads .env.mock
  INFINITYRX_ENV=production  → loads .env.prod
  INFINITYRX_ENV unset       → loads .env.local (legacy / dev fallback)

The JWT_SECRET minimum-length constraint is a security boundary: tokens
signed with a short secret are trivially brute-forceable. Validation happens
at construction time so a misconfigured deployment fails fast, before any
requests are served.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_LOCAL = _REPO_ROOT / ".env.local"


def _resolve_env_file() -> Path | None:
    """Pick the .env file to load based on INFINITYRX_ENV.

    Falls back to .env.local for backward compatibility with the legacy
    single-environment setup and existing test fixtures.
    """
    name = os.environ.get("INFINITYRX_ENV", "").strip().lower()
    candidates: list[Path] = []
    if name == "development" or name == "dev":
        candidates.append(_REPO_ROOT / ".env.dev")
    elif name == "mock":
        candidates.append(_REPO_ROOT / ".env.mock")
    elif name == "production" or name == "prod":
        candidates.append(_REPO_ROOT / ".env.prod")
    candidates.append(_ENV_LOCAL)
    for c in candidates:
        if c.exists():
            return c
    return None


_ENV_FILE = _resolve_env_file()


class Settings(BaseSettings):
    """Validated runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE else None,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Deployment environment (CR-10/M-16) ─────────────────────────────────
    # Controls /docs visibility, CORS strictness, and future Key Vault routing.
    # Default is "development" so local dev works without configuration.
    # Production deployments MUST set ENVIRONMENT=production.
    # "mock" is the demo environment — scrambled data, isolated DB/Redis/queue,
    # OPENAPI_DOCS enabled, never serves real PHI. See .env.mock + .claude/rules.
    ENVIRONMENT: Literal["development", "staging", "production", "mock"] = "development"

    DATABASE_URL: str
    DATABASE_URL_SYNC: str
    # Reference data connection (read-only ifx_ref_reader role). May point
    # at the same physical database as DATABASE_URL — reference tables live
    # in a dedicated `reference` schema in every operational database.
    # Falls back to DATABASE_URL if not explicitly set.
    REFERENCE_DB_URL: str = ""
    REDIS_URL: str
    RABBITMQ_URL: str

    JWT_SECRET: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 60

    STORAGE_PROVIDER: str = "local"
    STORAGE_LOCAL_PATH: str = "./var/files"

    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 25

    OIG_EXCLUSION_URL: str = ""
    SAM_API_KEY: str = ""

    MAX_UPLOAD_BYTES: int = 100 * 1024 * 1024

    # ── DLQ monitoring (event-bus rule: alert when depth > 0 for > 15 min) ──
    # DLQ_ALERT_THRESHOLD=0 means "alert on any queued entry" — matches the
    # event-bus rule wording exactly.  Override via env var to raise the floor
    # and avoid alert fatigue during normal replay windows (W41.8 T1-B).
    DLQ_ALERT_THRESHOLD: int = 0
    DLQ_ALERT_WINDOW_MINUTES: int = 15
    # Maximum retry attempts before a message is dead-lettered.  Mirrors the
    # default in RetryingHandler; centralising here makes it configurable
    # per deployment without code changes (closes G5).
    DLQ_MAX_RETRIES: int = 3

    # ── CORS (M-06/M-16) ────────────────────────────────────────────────────
    # Explicit allow-list; empty list = no CORS headers (for APIs behind a
    # gateway) or set to ["*"] only in development. Never wildcard in prod.
    CORS_ALLOW_ORIGINS: list[str] = []

    # ── Azure Key Vault (H-05) ───────────────────────────────────────────────
    # When set, the Key Vault stub can resolve secrets from AKV at startup.
    # Leave empty in development — local .env.local or env vars are used.
    AZURE_KEYVAULT_URL: str = ""

    # ── B9 FDB MTL guard (charter v3.2 + ADVERSARIAL A8) ────────────────────
    # MTL = Medical Test Lexicon. 19 FDB tables that clinical-screening users
    # consume. B9 ships the schema (tables + alembic migrations) but does NOT
    # ingest data into them by default — InfinityRx is not subscribed to the
    # clinical-screening tier.
    #
    # When False (default):
    #   * loader registry filters out specs with loader_group="fdb_mtl"
    #   * FDW manifest excludes MTL tables (charter v3.2: MTL EXCLUDED
    #     from default FDW to prevent silent false-negative joins)
    #   * DB-level guard REVOKEs INSERT/UPDATE/DELETE on every mtl_* table
    #     from the app roles (defense-in-depth — see
    #     infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl)
    #
    # When True (future MTL-activation wave):
    #   * loader includes Tier D specs
    #   * FDW manifest expands to 283 entries
    #   * GRANT migration runs to restore writes
    #
    # B9.G ships the Tier D schema with the default-False flag. Flipping
    # to True is a future wave with its own gate.
    FDB_LOAD_MTL: bool = False

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def _validate_alg(cls, value: str) -> str:
        allowed = {"HS256", "HS384", "HS512", "RS256"}
        if value not in allowed:
            raise ValueError(f"JWT_ALGORITHM must be one of {sorted(allowed)}")
        return value

    @field_validator("CORS_ALLOW_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> list[str]:
        """Accept both JSON array and comma-separated string from env vars."""
        if isinstance(value, str):
            # Support CORS_ALLOW_ORIGINS="https://app.example.com,https://admin.example.com"
            return [o.strip() for o in value.split(",") if o.strip()]
        return list(value) if value else []


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    return Settings()  # type: ignore[call-arg]


def reset_settings_cache() -> None:
    """Clear the settings cache. Tests use this to reload env vars."""
    get_settings.cache_clear()


def get_operational_db_url() -> str:
    """Return the URL of the current environment's operational database.

    Operational data = claims, members, payments, audit, tenant config —
    everything that is environment-isolated. Read/write via the per-env
    app role (ifx_dev_app, ifx_mock_app, ifx_prod_app).
    """
    return get_settings().DATABASE_URL


def get_reference_db_url() -> str:
    """Return the URL of the reference-data database (read-only).

    Reference data = drug NDC, NPPES prescribers, NCPDP pharmacies, CMS
    rates, etc. Logically the same in every environment, physically
    replicated in a `reference` schema inside each operational database.
    Falls back to the operational URL if REFERENCE_DB_URL is unset.
    """
    settings = get_settings()
    return settings.REFERENCE_DB_URL or settings.DATABASE_URL


def get_environment() -> str:
    """Return the active environment name from INFINITYRX_ENV.

    Distinct from Settings.ENVIRONMENT (which is the value loaded from the
    .env file) — this is the shell-level marker set by switch_env.sh.
    Useful for code paths that need to behave differently per environment
    (e.g., disabling destructive migrations against prod).
    """
    return os.environ.get("INFINITYRX_ENV", "development")
