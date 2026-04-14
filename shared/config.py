"""Platform configuration loader.

Loads settings from environment variables (optionally seeded by .env.local).
Exposes a cached singleton `get_settings()` that returns a validated
`Settings` instance. All downstream modules MUST read configuration through
this module — never `os.environ` directly — so that validation is centralised
and tests can override settings deterministically.

The JWT_SECRET minimum-length constraint is a security boundary: tokens
signed with a short secret are trivially brute-forceable. Validation happens
at construction time so a misconfigured deployment fails fast, before any
requests are served.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_LOCAL = _REPO_ROOT / ".env.local"


class Settings(BaseSettings):
    """Validated runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_LOCAL) if _ENV_LOCAL.exists() else None,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Deployment environment (CR-10/M-16) ─────────────────────────────────
    # Controls /docs visibility, CORS strictness, and future Key Vault routing.
    # Default is "development" so local dev works without configuration.
    # Production deployments MUST set ENVIRONMENT=production.
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    DATABASE_URL: str
    DATABASE_URL_SYNC: str
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

    # ── CORS (M-06/M-16) ────────────────────────────────────────────────────
    # Explicit allow-list; empty list = no CORS headers (for APIs behind a
    # gateway) or set to ["*"] only in development. Never wildcard in prod.
    CORS_ALLOW_ORIGINS: list[str] = []

    # ── Azure Key Vault (H-05) ───────────────────────────────────────────────
    # When set, the Key Vault stub can resolve secrets from AKV at startup.
    # Leave empty in development — local .env.local or env vars are used.
    AZURE_KEYVAULT_URL: str = ""

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
