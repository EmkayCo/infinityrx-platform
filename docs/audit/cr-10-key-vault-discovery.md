# CR-10 Azure Key Vault Discovery

**Date:** 2026-05-15
**Branch:** wave/B10-w5-cr-10-key-vault
**Auditor:** Integration Coordinator (P0b wave)

---

## 1. Current Secret Loading Mechanism

All secrets are currently loaded via **raw environment variables** through two
paths:

| Path | Mechanism | Files |
|---|---|---|
| `shared/config.py` `Settings` class | `pydantic_settings.BaseSettings` reads from OS env + `.env.*` file | `shared/config.py` |
| `shared/auth/_settings.py` | `os.getenv()` with default fallbacks | `shared/auth/_settings.py` |
| `shared/crypto/keys.py` `EnvKeyProvider` | `os.environ.get()` directly | `shared/crypto/keys.py` |
| `shared/ai/openai_client.py` `OpenAIConfig` | `pydantic_settings.BaseSettings` with `env_prefix="AZURE_OPENAI_"` | `shared/ai/openai_client.py` |
| `modules/core-platform/src/_shim/config.py` | `os.getenv()` dataclass | `modules/core-platform/src/_shim/config.py` |

`AZURE_KEYVAULT_URL` exists in `shared/config.py` as a field but is **never
consumed** — it is a stub placeholder with no loading logic behind it.

No `azure-identity` or `azure-keyvault-secrets` SDK usage exists anywhere in
the codebase today (confirmed by grep).

---

## 2. Secret Inventory

| Secret Name | Sensitivity | Used By | Notes |
|---|---|---|---|
| `JWT_SECRET` | HIGH — signs all auth tokens | core-platform auth, all modules via `shared.auth._settings` | min 32 chars enforced |
| `ENCRYPTION_KEY_ACTIVE` | CRITICAL — AES-256 PHI encryption master key | `shared/crypto/keys.py` EnvKeyProvider, every PHI model | base64-encoded 32 bytes |
| `ENCRYPTION_KEY_ACTIVE_ID` | LOW | `shared/crypto/keys.py` | defaults to "v1" |
| `ENCRYPTION_KEY_{id}` | CRITICAL — rotation keys | `shared/crypto/keys.py` | zero or more old keys |
| `AZURE_OPENAI_ENDPOINT` | MEDIUM — Azure service URL | `shared/ai/openai_client.py` | not a secret per se, but scoped resource |
| `AZURE_OPENAI_API_KEY` | HIGH — Azure OpenAI billing key | `shared/ai/openai_client.py` | accessed via `AZURE_OPENAI_` prefix |
| `SAM_API_KEY` | MEDIUM — SAM.gov exclusion API | `modules/core-platform/src/_shim/config.py`, `shared/config.py` | empty string allowed in dev |
| `DATABASE_URL` | HIGH — full DB connection string with creds | `shared/config.py`, all modules | contains username + password |
| `DATABASE_URL_SYNC` | HIGH | alembic env files for billing, payment-processing, prescriber-directory, drug-database | sync variant |
| `REDIS_URL` | MEDIUM — may contain auth token | `shared/config.py`, health checks, dataiq | |
| `RABBITMQ_URL` | MEDIUM — contains username:password | `shared/config.py` | amqp://user:pass@host/ |
| `BILLING_DATABASE_URL` | HIGH | `modules/billing/src/db/session.py` | module-specific DB |
| `DRUG_DB_DATABASE_URL` | HIGH | `modules/drug-database/src/db/session.py` | module-specific DB |
| `PLAN_DESIGN_DATABASE_URL` | HIGH | `modules/plan-design/src/db/session.py` | module-specific DB |
| `REBATE_DATABASE_URL` | HIGH | `modules/rebate-management/src/db/session.py` | module-specific DB |

**Non-secret config (NOT migrated — stays as env vars):**
`ENVIRONMENT`, `INFINITYRX_ENV`, `JWT_ALGORITHM`, `JWT_EXPIRES_MINUTES`,
`STORAGE_PROVIDER`, `STORAGE_LOCAL_PATH`, `SMTP_HOST`, `SMTP_PORT`,
`OIG_EXCLUSION_URL`, `MAX_UPLOAD_BYTES`, `DLQ_*`, `CORS_ALLOW_ORIGINS`,
`SLOW_QUERY_THRESHOLD_MS`, `LOG_LEVEL`, `LOG_MODE`, `FDB_LOAD_MTL`,
`ENCRYPTION_PROVIDER`.

---

## 3. Target Key Vault Adapter Design

### Architecture

```
shared/config/
    __init__.py          # re-exports get_secret, MissingSecretError
    key_vault.py         # KeyVaultSecretLoader + module-level get_secret()
```

### Behavior per environment

| INFINITYRX_ENV | Vault behavior |
|---|---|
| `development` / `dev` | env-var fallback only; Azure SDK never imported |
| `mock` | env-var fallback only; matches `.env.mock` pattern |
| `production` / `prod` | REQUIRES Key Vault; `MissingSecretError` on absent secret |

### Key design decisions

1. **DefaultAzureCredential** — correct for AKS workload identity: managed
   identity is tried before CLI/environment, matching AKS pod-identity chain.
2. **Lazy load** — vault client created on first `get_secret()` call, not at
   import. Avoids breaking dev bootstraps that have no Azure access.
3. **Process-memory TTL cache** — 5-minute default, configurable via
   `KEY_VAULT_CACHE_TTL_SECONDS`. Secret rotation is picked up within one TTL
   window.
4. **Audit logging** — every secret access emits a `secret.accessed` structured
   log entry with secret name (never value). No audit DB write is attempted
   from this layer — that would create a circular dep on DB being up at config
   load time. The log entry is machine-parseable by the audit ingestion pipeline.
5. **`get_secret()` module-level function** — thin wrapper around the singleton
   loader. Drop-in replacement for `os.getenv()` at call sites.
6. **`required=True` default in production** — raises `MissingSecretError`
   with the secret name (not value) in the message.

---

## 4. Migration Risk Table

| Module / Path | Secrets to Migrate | Risk | Notes |
|---|---|---|---|
| `shared/config.py` | `JWT_SECRET`, `REDIS_URL`, `RABBITMQ_URL`, `DATABASE_URL`, `DATABASE_URL_SYNC`, `SAM_API_KEY`, `AZURE_KEYVAULT_URL` | LOW | Pydantic `BaseSettings` stays; `AZURE_KEYVAULT_URL` now consumed by adapter |
| `shared/auth/_settings.py` | `JWT_SECRET` | LOW | Already reads from `shared.config` when available; no change needed |
| `shared/crypto/keys.py` `EnvKeyProvider` | `ENCRYPTION_KEY_ACTIVE`, rotation keys | MEDIUM | Stays env-var-based in dev; in prod Key Vault provides `ENCRYPTION_KEY_ACTIVE` value via adapter |
| `shared/ai/openai_client.py` `OpenAIConfig` | `AZURE_OPENAI_API_KEY` | LOW | `BaseSettings` with `env_prefix` — adapter feeds the env var, no code change needed |
| `modules/core-platform/src/_shim/config.py` | `SAM_API_KEY` | LOW | Shim; replaced by `shared.config.get_settings().SAM_API_KEY` long-term |
| `modules/billing/src/db/session.py` | `BILLING_DATABASE_URL` | LOW | Module-scoped DB session; adapter feeds env var |
| `modules/drug-database/src/db/session.py` | `DRUG_DB_DATABASE_URL` | LOW | Same pattern |
| `modules/plan-design/src/db/session.py` | `PLAN_DESIGN_DATABASE_URL` | LOW | Same pattern |
| `modules/rebate-management/src/db/session.py` | `REBATE_DATABASE_URL` | LOW | Same pattern |
| All module `alembic/env.py` files | `DATABASE_URL_SYNC` | LOW | Reads `os.environ` directly; adapter populates env at startup |
| CI pipelines | All secrets above | MEDIUM | CI must set `INFINITYRX_ENV=development` to use env-var fallback |

**Overall risk: LOW.** The adapter is purely additive — it wraps secret
resolution without changing how consuming code reads values. In `development`
mode it is a pass-through to env vars.
