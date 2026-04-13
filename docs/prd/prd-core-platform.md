# PRD — Module 1: Core Platform (v2 — FINAL)

**Module:** Core Platform  
**Folder:** `modules/core-platform/`  
**Priority:** Phase 1 (build first — everything depends on this)  
**Sessions:** 4 concurrent  
**Duration:** 1-2 weeks  

---

## 1. Purpose

The Core Platform is the foundation that every other module plugs into. It provides multi-tenant isolation, authentication, authorization, inter-module communication, audit logging, job scheduling, file management, notifications, and operational tooling. No other module can function without this.

This module has no business logic specific to pharmacy claims, billing, or FWA. It is a generic multi-tenant SaaS platform foundation that could support any enterprise healthcare application. The PBM-specific logic lives in the other 24 modules.

**HIPAA 2026 compliance is a first-class requirement.** The 2026 HIPAA Security Rule update changes several safeguards from "addressable" to "required": MFA, encryption at rest, 72-hour restoration, and tamper-evident audit logs. This module must satisfy all of them.

---

## 2. Data Model

### 2.1 Tenants

```sql
CREATE SCHEMA core;

CREATE TABLE core.tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'terminated')),
    
    -- White-label branding
    logo_url TEXT,
    primary_color VARCHAR(7) DEFAULT '#0B1D3A',
    secondary_color VARCHAR(7) DEFAULT '#FFFFFF',
    font_family VARCHAR(100) DEFAULT 'Inter',
    custom_domain VARCHAR(255),
    
    -- Contact
    contact_name VARCHAR(255),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(20),
    
    -- Configuration
    timezone VARCHAR(50) DEFAULT 'America/New_York',
    date_format VARCHAR(20) DEFAULT 'MM/DD/YYYY',
    number_format VARCHAR(20) DEFAULT 'en-US',
    currency VARCHAR(3) DEFAULT 'USD',
    
    -- Security
    mfa_required BOOLEAN DEFAULT TRUE,
    mfa_methods JSONB DEFAULT '["totp", "fido2"]',
    session_timeout_minutes INTEGER DEFAULT 15,
    max_concurrent_sessions INTEGER DEFAULT 5,
    ip_allowlist JSONB,                               -- null = no restriction
    
    -- Data retention
    data_retention_days INTEGER DEFAULT 2555,
    
    -- Feature flags
    enabled_features JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);
```

### 2.2 Users & Authentication

```sql
CREATE TABLE core.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(id),
    email VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    azure_ad_oid VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'locked')),
    
    -- MFA
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_method VARCHAR(50),                           -- totp, fido2, authenticator
    mfa_secret_encrypted TEXT,                        -- encrypted TOTP secret
    mfa_backup_codes_encrypted TEXT,                  -- encrypted backup codes
    mfa_enrolled_at TIMESTAMPTZ,
    
    -- Session management
    last_login_at TIMESTAMPTZ,
    last_activity_at TIMESTAMPTZ,
    failed_login_count INTEGER DEFAULT 0,
    locked_at TIMESTAMPTZ,
    locked_reason VARCHAR(255),
    password_changed_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, email)
);

-- Active sessions (for concurrent session management and forced logout)
CREATE TABLE core.sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES core.users(id),
    tenant_id UUID NOT NULL,
    
    token_hash VARCHAR(64) NOT NULL,                  -- SHA-256 of JWT, NOT the token itself
    device_info JSONB,                                -- user agent, IP, device fingerprint
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    revoked_reason VARCHAR(255),
    
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_sessions_user ON core.sessions(user_id, is_active);

-- API keys (for service-to-service and client API access)
CREATE TABLE core.api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(id),
    
    name VARCHAR(255) NOT NULL,
    key_hash VARCHAR(64) NOT NULL,                    -- SHA-256 of key, NOT the key itself
    key_prefix VARCHAR(8) NOT NULL,                   -- first 8 chars for identification
    
    key_type VARCHAR(50) NOT NULL,                    -- service (module-to-module), client (external), webhook
    
    -- Scoping
    permissions JSONB,                                -- which permissions this key has
    allowed_ips JSONB,                                -- IP restriction
    rate_limit_per_minute INTEGER DEFAULT 100,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES core.users(id)
);

CREATE TABLE core.roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES core.tenants(id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE core.user_roles (
    user_id UUID NOT NULL REFERENCES core.users(id),
    role_id UUID NOT NULL REFERENCES core.roles(id),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by UUID REFERENCES core.users(id),
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE core.permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    description TEXT,
    UNIQUE(module, action)
);

CREATE TABLE core.role_permissions (
    role_id UUID NOT NULL REFERENCES core.roles(id),
    permission_id UUID NOT NULL REFERENCES core.permissions(id),
    PRIMARY KEY (role_id, permission_id)
);
```

### 2.3 Audit Log (Tamper-Evident)

```sql
CREATE TABLE core.audit_log (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL,
    user_id UUID,
    
    action VARCHAR(100) NOT NULL,
    module VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100),
    entity_id VARCHAR(255),
    
    before_value JSONB,
    after_value JSONB,
    
    ip_address INET,
    user_agent TEXT,
    correlation_id UUID,
    
    -- Tamper evidence (HIPAA 2026 requirement)
    previous_hash VARCHAR(64),                        -- hash of previous entry (hash chain)
    entry_hash VARCHAR(64) NOT NULL,                  -- SHA-256(tenant_id + action + entity + timestamp + previous_hash)
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Partition by month for query performance at scale
-- CREATE TABLE core.audit_log_2026_04 PARTITION OF core.audit_log
--     FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE INDEX idx_audit_tenant_created ON core.audit_log(tenant_id, created_at DESC);
CREATE INDEX idx_audit_entity ON core.audit_log(tenant_id, entity_type, entity_id);
CREATE INDEX idx_audit_user ON core.audit_log(tenant_id, user_id, created_at DESC);
CREATE INDEX idx_audit_action ON core.audit_log(tenant_id, action, created_at DESC);
CREATE INDEX idx_audit_correlation ON core.audit_log(correlation_id);
```

### 2.4 Notifications

```sql
CREATE TABLE core.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    notification_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'critical')),
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    link TEXT,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE core.notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    notification_type VARCHAR(100) NOT NULL,
    email_enabled BOOLEAN DEFAULT TRUE,
    in_app_enabled BOOLEAN DEFAULT TRUE,
    sms_enabled BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, notification_type)
);
```

### 2.5 Jobs

```sql
CREATE TABLE core.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID,
    name VARCHAR(255) NOT NULL,
    job_type VARCHAR(100) NOT NULL,
    schedule VARCHAR(100),                            -- cron expression
    status VARCHAR(20) DEFAULT 'active',
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    config JSONB,
    
    -- Locking (prevent duplicate execution)
    lock_key VARCHAR(255),                            -- unique key for advisory lock
    lock_timeout_minutes INTEGER DEFAULT 30,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE core.job_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES core.jobs(id),
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    result JSONB,
    error_message TEXT,
    items_processed INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0
);
```

### 2.6 Files

```sql
CREATE TABLE core.files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    filename VARCHAR(500) NOT NULL,
    original_filename VARCHAR(500) NOT NULL,
    content_type VARCHAR(100),
    size_bytes BIGINT,
    storage_path TEXT NOT NULL,
    
    -- Encryption
    is_encrypted BOOLEAN DEFAULT FALSE,
    encryption_key_ref VARCHAR(255),
    
    -- Classification
    contains_phi BOOLEAN DEFAULT FALSE,
    contains_financial BOOLEAN DEFAULT FALSE,
    
    module VARCHAR(100),
    entity_type VARCHAR(100),
    entity_id VARCHAR(255),
    uploaded_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 2.7 Government Exclusion Screening

```sql
CREATE TABLE core.exclusion_list (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(20) NOT NULL CHECK (source IN ('OIG', 'SAM', 'OFAC')),
    entity_type VARCHAR(20) NOT NULL,
    npi VARCHAR(10),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    organization_name VARCHAR(500),
    state VARCHAR(2),
    exclusion_type VARCHAR(100),
    exclusion_date DATE,
    reinstate_date DATE,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE core.exclusion_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    exclusion_list_id BIGINT REFERENCES core.exclusion_list(id),
    matched_entity_type VARCHAR(50) NOT NULL,
    matched_entity_id VARCHAR(255) NOT NULL,
    match_confidence VARCHAR(20) DEFAULT 'exact',
    status VARCHAR(20) DEFAULT 'pending',
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 2.8 Feature Flags

```sql
CREATE TABLE core.feature_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_key VARCHAR(100) NOT NULL UNIQUE,         -- e.g., 'reclaimrx.graph_analysis', 'ai_nlp.enabled'
    name VARCHAR(255) NOT NULL,
    description TEXT,
    default_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE core.tenant_feature_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(id),
    feature_flag_id UUID NOT NULL REFERENCES core.feature_flags(id),
    is_enabled BOOLEAN NOT NULL,
    enabled_by UUID,
    enabled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, feature_flag_id)
);
```

### 2.9 Webhooks

```sql
CREATE TABLE core.webhook_endpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    name VARCHAR(255) NOT NULL,
    url VARCHAR(500) NOT NULL,
    secret VARCHAR(255) NOT NULL,                     -- for HMAC-SHA256 signature
    
    event_types JSONB NOT NULL,                       -- which events to deliver
    
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Health
    last_delivery_at TIMESTAMPTZ,
    last_delivery_status VARCHAR(50),
    consecutive_failures INTEGER DEFAULT 0,
    disabled_at TIMESTAMPTZ,                          -- auto-disabled after too many failures
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE core.webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_endpoint_id UUID NOT NULL REFERENCES core.webhook_endpoints(id),
    tenant_id UUID NOT NULL,
    
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    
    -- Delivery
    status VARCHAR(50) DEFAULT 'pending',             -- pending, delivered, failed, exhausted
    attempt_count INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    
    response_status_code INTEGER,
    response_body TEXT,
    
    next_retry_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 2.10 Bank Holiday Calendar

```sql
CREATE TABLE core.bank_holidays (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    holiday_date DATE NOT NULL,
    name VARCHAR(255) NOT NULL,
    country VARCHAR(2) DEFAULT 'US',
    is_federal BOOLEAN DEFAULT TRUE,
    is_bank_holiday BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(holiday_date, country)
);
```

---

## 3. API Endpoints

```
/api/v1/

# Tenant Management (platform_admin only)
POST   /tenants                        Create tenant (atomic provisioning)
GET    /tenants                        List tenants
GET    /tenants/{id}                   Get tenant details
PUT    /tenants/{id}                   Update tenant
PUT    /tenants/{id}/branding          Update white-label branding
POST   /tenants/{id}/suspend           Suspend tenant
POST   /tenants/{id}/activate          Reactivate tenant
POST   /tenants/{id}/export-data       Export all tenant data (for offboarding)
POST   /tenants/{id}/purge             Purge tenant data (after export, with confirmation)

# Authentication
POST   /auth/login                     Login (returns JWT, triggers MFA if enabled)
POST   /auth/mfa/verify                Verify MFA code/token
POST   /auth/mfa/enroll                Begin MFA enrollment
POST   /auth/logout                    Logout (revoke session)
POST   /auth/refresh                   Refresh JWT
GET    /auth/me                        Current user profile
PUT    /auth/me                        Update profile
GET    /auth/sessions                  List active sessions for current user
DELETE /auth/sessions/{id}             Revoke specific session

# User Management (tenant_admin)
POST   /users                          Create user
GET    /users                          List users (tenant-scoped)
GET    /users/{id}                     Get user
PUT    /users/{id}                     Update user
PUT    /users/{id}/roles               Assign roles
POST   /users/{id}/lock                Lock user
POST   /users/{id}/unlock              Unlock user
POST   /users/{id}/reset-mfa           Reset MFA enrollment

# API Keys (tenant_admin)
POST   /api-keys                       Create API key (returns key once, never again)
GET    /api-keys                       List API keys (prefix only, not full key)
DELETE /api-keys/{id}                  Revoke API key

# Role Management (tenant_admin)
GET    /roles                          List roles
POST   /roles                          Create custom role
PUT    /roles/{id}                     Update role
PUT    /roles/{id}/permissions         Assign permissions
GET    /permissions                    List all available permissions

# Audit Log (tenant_admin, tenant_operator read-only)
GET    /audit                          Query audit log (filterable)
GET    /audit/export                   Export audit log (CSV/Excel)
GET    /audit/{id}                     Get specific audit entry
GET    /audit/verify-integrity         Verify hash chain integrity for date range

# Notifications
GET    /notifications                  List notifications (user-scoped)
PUT    /notifications/{id}/read        Mark as read
PUT    /notifications/read-all         Mark all as read
GET    /notifications/preferences      Get notification preferences
PUT    /notifications/preferences      Update preferences

# Jobs (tenant_admin, platform_admin)
GET    /jobs                           List jobs
POST   /jobs                           Create scheduled job
PUT    /jobs/{id}                      Update job config/schedule
POST   /jobs/{id}/run                  Trigger immediate run
POST   /jobs/{id}/pause                Pause job
GET    /jobs/{id}/runs                 List job runs
GET    /jobs/runs/{run_id}             Get job run details

# Files
POST   /files/upload                   Upload file (auto-encrypted if contains PHI/financial)
GET    /files                          List files (tenant-scoped)
GET    /files/{id}                     Download file (decrypted on-the-fly)
DELETE /files/{id}                     Delete file

# Government Exclusion
GET    /exclusions/matches             List exclusion matches
PUT    /exclusions/matches/{id}        Review match (confirm/dismiss)
POST   /exclusions/screen              Trigger manual screening
GET    /exclusions/status              Last refresh date, match counts

# Feature Flags
GET    /features                       List feature flags with tenant overrides
PUT    /features/{key}                 Toggle feature for tenant

# Webhooks
POST   /webhooks                       Register webhook endpoint
GET    /webhooks                       List webhook endpoints
PUT    /webhooks/{id}                  Update endpoint
DELETE /webhooks/{id}                  Delete endpoint
POST   /webhooks/{id}/test             Send test webhook
GET    /webhooks/{id}/deliveries       Delivery history

# Bank Holidays
GET    /bank-holidays                  List holidays for date range
POST   /bank-holidays                  Add custom holiday
GET    /bank-holidays/is-business-day/{date}  Check if date is a business day
GET    /bank-holidays/next-business-day/{date}  Get next business day after date

# System Health
GET    /health                         Shallow health check (is process running)
GET    /health/detailed                Deep health check (DB, Redis, queue, all deps)
GET    /health/readiness               Kubernetes readiness probe
GET    /health/liveness                Kubernetes liveness probe
```

**Every endpoint enforces:**
1. Authentication (JWT or API key, except /health and /auth/login)
2. MFA verification (for PHI-accessing endpoints, if tenant requires MFA)
3. Tenant isolation (user only sees their tenant's data)
4. Role-based permission check
5. Rate limiting (configurable per tenant, per user type, per endpoint)
6. Input validation (Pydantic models, max lengths, regex patterns)
7. Audit logging (every mutating request logged with hash chain)
8. Security headers (HSTS, X-Content-Type-Options, X-Frame-Options, CSP, Cache-Control)
9. Request correlation ID (generated if not present, propagated to all downstream calls)
10. Request size limit (default: 10MB, configurable per endpoint)

---

## 4. Core Services

### 4.1 Tenant Isolation

Every database query includes `tenant_id` in the WHERE clause. This is enforced at multiple layers:

**Layer 1 — Middleware**: FastAPI middleware extracts `tenant_id` from JWT claims and injects into request context. Every route handler receives tenant context automatically.

**Layer 2 — ORM**: Custom SQLAlchemy session factory applies a default filter on all queries. No query can execute without tenant scoping (except platform_admin endpoints).

**Layer 3 — Database**: PostgreSQL Row-Level Security (RLS) policies as defense-in-depth. Even if the ORM filter is bypassed (CVE scenario), RLS prevents cross-tenant access.

**Layer 4 — Cache**: Redis keys prefixed with `tenant:{tenant_id}:`. Cache reads and writes always include tenant prefix. TTL-based expiry.

**Layer 5 — Events**: Event bus messages include `tenant_id`. Subscribers filter by tenant. A tenant's subscriber only receives that tenant's events.

**Verification**: Automated integration test suite creates two tenants, populates data in both, then queries EVERY endpoint as Tenant A and verifies zero results from Tenant B. This test runs on every build. Any failure blocks deployment.

### 4.2 Authentication & MFA (HIPAA 2026 Compliant)

**MFA is mandatory.** The 2026 HIPAA Security Rule requires MFA for all ePHI access. SMS-based OTP is insufficient. Supported methods:

1. **TOTP (Authenticator app)** — Google Authenticator, Microsoft Authenticator, Authy. Default method. 6-digit rotating code.
2. **FIDO2 / WebAuthn** — Hardware security keys (YubiKey) or platform authenticators (Touch ID, Windows Hello). Phishing-resistant. Recommended for high-security tenants.
3. **Backup codes** — 10 single-use codes generated at enrollment. For recovery when primary method unavailable.

**MFA flow:**
1. User submits email + password → system validates → returns MFA challenge (not a JWT yet)
2. User submits MFA code/assertion → system validates → returns JWT
3. JWT includes `mfa_verified: true` claim
4. Endpoints accessing PHI check for `mfa_verified` — reject if false

**MFA enrollment:**
- New users must enroll in MFA on first login (forced enrollment flow)
- Tenant admin can reset a user's MFA (for lost device)
- Backup codes downloadable once at enrollment

**Session management:**
- Active sessions tracked in `core.sessions`
- Configurable session timeout per tenant (default: 15 minutes inactivity)
- Maximum concurrent sessions per user (default: 5, configurable per tenant)
- Force-logout: admin can revoke any user's sessions
- Token refresh extends session only if user was active within timeout window
- Automatic session cleanup job removes expired sessions hourly

**Account lockout:**
- After configurable failed login attempts (default: 5), account locks
- Lockout duration: configurable (default: 30 minutes, or until admin unlock)
- Lock events logged in audit trail

**API key authentication:**
- For service-to-service (module-to-module) communication
- For external client API access
- Key displayed once at creation, stored as SHA-256 hash
- Scoped by permissions (subset of the creating user's permissions)
- IP allowlisting per key
- Rate limiting per key
- Expiration date (optional)

### 4.3 Event Bus (Reliable Messaging)

Inter-module communication via events. Local: RabbitMQ. Production: Azure Service Bus. The client abstracts the provider.

**Reliability guarantees:**

1. **At-least-once delivery**: every message is delivered at least once. Consumers must be idempotent (processing the same message twice produces the same result).
2. **Ordering per entity**: messages for the same entity (e.g., same payment_batch_id) are delivered in order. Different entities can be processed in parallel.
3. **Dead letter queue**: messages that fail processing after configurable retries (default: 3) go to the DLQ. DLQ is monitored. Alerts fire when DLQ depth > 0. Messages can be replayed from DLQ after the issue is fixed.
4. **Event schema versioning**: every message includes a `schema_version` field. New fields are optional (forward-compatible). Old fields are never removed. Consumers ignore unknown fields.
5. **Event replay**: event store retains all published events for configurable period (default: 30 days). Any consumer can request replay of events by type and time range. Used for: recovering from consumer downtime, reprocessing after bug fix, populating a new module with historical events.
6. **Backpressure handling**: if a consumer falls behind, the queue grows but doesn't drop messages. Alert when queue depth exceeds configurable threshold. Consumer can be scaled horizontally to catch up.

**Message format:**
```json
{
    "event_id": "uuid",
    "event_type": "claim.adjudicated",
    "schema_version": "1.0",
    "tenant_id": "uuid",
    "correlation_id": "uuid",
    "timestamp": "2026-04-12T10:30:00Z",
    "source_module": "adjudication-engine",
    "idempotency_key": "uuid",
    "payload": { ... }
}
```

### 4.4 Audit Logging (Tamper-Evident)

Every mutating API call logged automatically via middleware. HIPAA 2026 requires immutable, tamper-evident audit logs.

**Tamper evidence via hash chain:**
- Each audit entry includes `entry_hash` = SHA-256 of (tenant_id + action + entity_type + entity_id + timestamp + previous_hash)
- `previous_hash` = `entry_hash` of the immediately preceding entry for the same tenant
- Any modification or deletion of an entry breaks the hash chain
- Integrity verification endpoint: `/audit/verify-integrity?start_date=X&end_date=Y` — walks the chain and reports any breaks
- Verification runs automatically as a daily job. Any break triggers a CRITICAL alert.

**What is logged:**
- Every POST, PUT, DELETE request (automatic via middleware)
- PHI access (any GET that returns PHI fields — separate `phi_access` action)
- Login attempts (success and failure)
- MFA events (enrollment, verification, failure)
- Session events (creation, refresh, timeout, revocation)
- Permission changes (role assignment, permission grant)
- API key events (creation, usage, revocation)
- Configuration changes (tenant settings, feature flags)
- File operations (upload, download, delete)

**Retention:** Audit logs retained per tenant's data_retention_days (default: 7 years). Archived to cold storage after retention period. Never deleted unless legally required.

### 4.5 Government Exclusion Screening

**Default implementation:**
- **OIG LEIE**: downloaded monthly from oig.hhs.gov
- **SAM.gov**: queried monthly for all active entities
- **OFAC SDN**: downloaded daily from treasury.gov (for payment compliance)
- Match algorithm: exact NPI (high confidence), fuzzy name+state (probable), name-only (possible)
- Any match → notification + entity blocked until reviewed
- Configurable screening frequency, entity types, and match thresholds per tenant

### 4.6 Webhook Delivery System

All modules can trigger webhooks. The webhook system lives in Core Platform.

1. When any module emits an event, the webhook service checks for matching webhook endpoints
2. For each matching endpoint: construct payload, sign with HMAC-SHA256 using the endpoint's secret
3. Deliver via POST to the endpoint URL
4. If delivery fails (timeout, non-2xx response): retry with exponential backoff (1 min, 5 min, 30 min)
5. After 3 failures: mark delivery as exhausted. If endpoint has 10+ consecutive failures, auto-disable and alert tenant admin.
6. All deliveries logged for troubleshooting
7. Test endpoint: send a synthetic test event to verify the endpoint is working

### 4.7 Feature Flags

Per-tenant feature toggles without redeployment:

1. Feature flags defined globally (e.g., `reclaimrx.graph_analysis`, `ai_nlp.enabled`, `billing.auto_approve`)
2. Each flag has a default state (enabled or disabled)
3. Tenants can override the default for their instance
4. Feature check: `is_feature_enabled(tenant_id, feature_key)` — checked at request time, not cached longer than 60 seconds
5. Feature flag changes logged in audit trail
6. Used for: beta features, module enablement per tenant, gradual rollout

---

## 5. Security (HIPAA 2026 Compliant)

### 5.1 Encryption

**At rest (REQUIRED — HIPAA 2026):**
- PostgreSQL: TDE (Transparent Data Encryption) at the database level
- PHI columns (member name, DOB, SSN, address): additional application-level AES-256 encryption via pgcrypto or application-layer encryption before storage
- Encryption keys managed by Azure Key Vault (production) or local key file (development)
- Key rotation: supported without downtime. Old keys retained for decryption of existing data. New data encrypted with new key.
- Files: all files containing PHI or financial data encrypted at rest (AES-256)
- Redis: encrypted at rest (Azure Cache for Redis provides this; local dev uses unencrypted Redis with access controls)

**In transit:**
- TLS 1.3 for all API communication
- TLS 1.2 minimum for legacy integrations (configurable)
- SFTP with SSH encryption for file transfers
- No unencrypted communication paths

### 5.2 Input Validation

Centralized validation framework:

- **All request bodies**: validated via Pydantic models (FastAPI native)
- **String fields**: maximum length enforced (configurable per field, default: 255)
- **Numeric fields**: range validation (min/max)
- **Pattern fields**: regex validation for known formats:
  - NPI: exactly 10 digits, passes Luhn check
  - NDC: 11 digits (5-4-2 or 10-digit with inferred format)
  - Phone: E.164 format
  - Email: RFC 5322 compliant
  - Date: ISO 8601
- **SQL injection**: parameterized queries only (SQLAlchemy handles this). No raw SQL with user input. Static analysis check in CI/CD.
- **XSS**: output encoding for any user-provided text rendered in UI
- **File upload**: content type validation, max file size (configurable, default: 50MB), virus scanning (ClamAV or Azure Defender)

### 5.3 Security Headers

All API responses include:
```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Content-Security-Policy: default-src 'self'
Cache-Control: no-store                     (for PHI-containing responses)
X-Request-ID: {correlation_id}
```

### 5.4 Rate Limiting

Token bucket algorithm at the API gateway:
- Per tenant: configurable (default: 1000 requests/minute)
- Per user: configurable (default: 100 requests/minute)
- Per API key: configurable per key
- Per endpoint: expensive endpoints (report generation, bulk operations) have lower limits
- Rate limit headers in responses: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- 429 Too Many Requests response when limit exceeded

### 5.5 Dependency Scanning

- Python: `safety check` on every build (scans for known CVEs in dependencies)
- Node.js: `npm audit` on every build
- Docker: container image scanning (Trivy or Azure Defender)
- Critical vulnerabilities: block deployment
- High vulnerabilities: warn, require acknowledgment within 7 days
- Automated weekly scan of deployed dependencies

### 5.6 Emergency Access Procedure (Break-Glass)

HIPAA Security Rule §164.312(a)(2)(ii) REQUIRES documented and tested emergency access procedures for when normal authentication is unavailable.

**Scenarios covered:**
- Azure AD / identity provider is down
- MFA provider is unavailable (authenticator app server outage)
- Database is degraded (read-only mode)
- Primary system is under active cyber attack
- Natural disaster affecting primary infrastructure

**Break-glass implementation:**
1. **Emergency admin account**: pre-provisioned local account (not Azure AD dependent) with platform_admin role. Credentials stored in a sealed envelope in a physical safe AND in Azure Key Vault with restricted access.
2. **Emergency access activation**: requires two-person authorization (dual control). Both individuals must authenticate via separate mechanism (e.g., Key Vault access + physical seal break).
3. **Emergency audit trail**: all actions taken via emergency access are logged to a SEPARATE audit store (in case primary audit is compromised). Special `emergency_access` flag on all audit entries.
4. **Automatic expiry**: emergency session expires after configurable period (default: 4 hours). Cannot be extended — must re-authenticate via emergency process.
5. **Post-emergency review**: after emergency access ends, MANDATORY review of all actions taken. Documentation of: why emergency access was needed, what was done, what needs follow-up.
6. **Testing**: emergency access procedure tested quarterly. Test results documented. Any failure triggers remediation within 30 days.

### 5.7 Incident Response & Breach Notification

HIPAA Breach Notification Rule (45 CFR §§164.400-414) and 2026 update requiring 72-hour notification for certain security incidents.

**Incident response plan (documented, tested):**

1. **Detection**: automated alerting on: failed login spikes (>10x normal), unusual data access patterns (after-hours bulk PHI access), audit chain integrity failure, security scan findings, external threat intelligence.
2. **Triage**: designated incident response team. On-call rotation. Classification: P1 (active breach, data exfiltration), P2 (suspected breach, anomalous behavior), P3 (security event, no confirmed exposure).
3. **Containment**: P1 = immediate isolation (suspend affected accounts, revoke sessions, block IP ranges). P2 = enhanced monitoring and investigation. P3 = log and review.
4. **Investigation**: forensic analysis capabilities: audit log analysis (who accessed what, when), session replay from audit trail, data access scope determination (how many records, which tenants, which members).
5. **Notification timeline**:
   - 72 hours: notify HHS for security incidents meeting 2026 threshold
   - 60 days: notify affected individuals for breaches of unsecured PHI (500+ records)
   - Annual: report smaller breaches (<500 records) to HHS by end of calendar year
   - Immediately: notify affected tenants (our clients) per BAA requirements
6. **Notification templates**: pre-written, legally reviewed templates for: individual notification letters, HHS notification forms, media notification (required for 500+ individuals in one state), tenant notification.
7. **Recovery**: restore from verified backup. Remediate vulnerability. Document lessons learned.
8. **Testing**: tabletop exercise annually. Full breach simulation biennially.

**Data model addition:**
```sql
CREATE TABLE core.security_incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    severity VARCHAR(10) NOT NULL,                     -- P1, P2, P3
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    
    detected_at TIMESTAMPTZ NOT NULL,
    detected_by VARCHAR(255),                          -- system, user, external
    
    classification VARCHAR(100),                       -- active_breach, suspected_breach, security_event
    
    -- Scope
    affected_tenants JSONB,
    affected_records_count INTEGER,
    phi_involved BOOLEAN DEFAULT FALSE,
    
    -- Timeline
    contained_at TIMESTAMPTZ,
    investigated_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    
    -- Notifications
    hhs_notified_at TIMESTAMPTZ,
    hhs_notification_reference VARCHAR(255),
    individuals_notified_at TIMESTAMPTZ,
    tenants_notified_at TIMESTAMPTZ,
    
    -- Resolution
    root_cause TEXT,
    remediation_actions TEXT,
    lessons_learned TEXT,
    
    status VARCHAR(50) DEFAULT 'open',
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 5.8 Password Policy

Even with mandatory MFA, the password itself needs minimum security:

- Minimum length: 12 characters (configurable per tenant, minimum 12)
- Complexity: at least one uppercase, one lowercase, one number, one special character
- Password history: cannot reuse last 12 passwords
- No common passwords: check against NIST SP 800-63B list of compromised passwords (Have I Been Pwned API or local list)
- No forced rotation (NIST 800-63B recommends against mandatory rotation when MFA is in place)
- Account lockout after configurable failed attempts (default: 5)
- Password stored as bcrypt hash with work factor ≥12

### 5.9 SSO / SAML / OIDC Support

Enterprise tenants require SSO integration with their identity provider:

- **SAML 2.0**: tenant provides SAML metadata (entity ID, SSO URL, certificate). Platform acts as Service Provider.
- **OpenID Connect**: tenant provides issuer URL, client ID, client secret. Platform acts as Relying Party.
- **Configurable per tenant**: some tenants use SSO, others use local auth. Both can coexist.
- **Just-in-time provisioning**: on first SSO login, auto-create user account in the tenant with a default role (configurable)
- **Attribute mapping**: map IdP attributes (name, email, groups) to platform user fields and roles
- **Logout**: support both SP-initiated and IdP-initiated single logout

### 5.10 CORS Configuration

For browser-based portal access and client API integration:

- CORS origins configurable per tenant (e.g., `https://portal.clientname.com`)
- Default: same-origin only (no external access)
- Allowed methods: GET, POST, PUT, DELETE, OPTIONS
- Allowed headers: Authorization, Content-Type, X-Request-ID
- Credentials: allowed for authenticated endpoints
- Max age: 3600 seconds (1 hour preflight cache)

---

## 5B. Standardized Error Response Format

All modules MUST return errors in this format. No exceptions.

```json
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Human-readable error description",
        "details": [
            {
                "field": "pharmacy_npi",
                "message": "NPI must be exactly 10 digits",
                "code": "INVALID_FORMAT"
            }
        ],
        "correlation_id": "uuid",
        "timestamp": "2026-04-12T10:30:00Z"
    }
}
```

**Error code categories:**
- `VALIDATION_ERROR` (400) — input failed validation
- `AUTHENTICATION_ERROR` (401) — not authenticated
- `MFA_REQUIRED` (401) — authenticated but MFA not verified
- `AUTHORIZATION_ERROR` (403) — authenticated but not permitted
- `NOT_FOUND` (404) — resource doesn't exist (or not in this tenant)
- `CONFLICT` (409) — duplicate resource, concurrent modification
- `RATE_LIMITED` (429) — rate limit exceeded
- `INTERNAL_ERROR` (500) — unexpected server error (details never leak internals)
- `SERVICE_UNAVAILABLE` (503) — dependency down, circuit breaker open
- `DATA_LOCKED` (423) — resource is locked (e.g., approved batch, closed period)

Every error response logged with correlation_id for troubleshooting.

---

## 5C. API Versioning Strategy

- URL-based versioning: `/api/v1/`, `/api/v2/`
- Current version: v1. All Phase 2-5 modules build on v1.
- Version bump rules:
  - Adding a new optional field to a response: NOT a breaking change (stays v1)
  - Adding a new endpoint: NOT a breaking change (stays v1)
  - Removing a field from a response: BREAKING (requires v2)
  - Changing a field type or semantics: BREAKING (requires v2)
  - Removing an endpoint: BREAKING (requires v2)
- When v2 is introduced: v1 continues to work for a deprecation period (minimum 12 months). v1 endpoints return `Deprecation` header with sunset date.
- OpenAPI spec auto-generated from FastAPI route definitions. Hosted at `/api/v1/docs` (Swagger UI) and `/api/v1/openapi.json`.

---

## 5D. Monitoring & Alerting Framework

**Metrics collected (per module):**
- Request rate (per endpoint, per tenant)
- Error rate (4xx, 5xx per endpoint)
- Response time (P50, P95, P99 per endpoint)
- Database query time (P50, P95, P99)
- Connection pool utilization (%)
- Event bus queue depth (per topic)
- DLQ depth
- Active sessions per tenant
- Job run duration and success rate

**Alerts (pre-configured):**
| Alert | Condition | Severity |
|-------|-----------|----------|
| Error rate spike | 5xx rate >5% for 5 minutes | CRITICAL |
| Slow responses | P95 >5 seconds for 10 minutes | WARNING |
| DB connection pool exhaustion | Pool >80% utilized | WARNING |
| DB connection pool full | Pool 100% utilized | CRITICAL |
| Event bus DLQ not empty | DLQ depth >0 for 15 minutes | WARNING |
| Event bus queue backing up | Queue depth >1000 for 10 minutes | WARNING |
| Audit chain integrity failure | Hash chain break detected | CRITICAL |
| Failed login spike | >10x normal rate | CRITICAL |
| PHI bulk access | >100 PHI records accessed in 1 minute | WARNING |
| Disk space low | <20% remaining | WARNING |
| Read replica lag | >30 seconds | WARNING |
| Scheduled job failed | Any job failure | WARNING |
| Backup verification failed | Weekly restore test failed | CRITICAL |
| Certificate expiring | TLS cert expires in <30 days | WARNING |

### 5E. Configuration Validation

When tenant settings are changed, validate consistency before saving:
- Session timeout must be ≥5 minutes and ≤480 minutes
- MFA methods must include at least one valid method
- IP allowlist entries must be valid CIDR notation
- Timezone must be a valid IANA timezone
- Date format must be a recognized pattern
- Data retention must be ≥2555 days (7 years, HIPAA minimum)
- Rate limits must be positive integers
- Feature flag keys must exist in the feature_flags table
- If SSO is configured: metadata must validate (certificate not expired, endpoints reachable)

---

## 6. Infrastructure

### 6.1 Docker Compose (Local Development)

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:17-alpine
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: infinityrx
      POSTGRES_USER: ifx_dev
      POSTGRES_PASSWORD: dev_password_change_me
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./infrastructure/docker/init-schemas.sql:/docker-entrypoint-initdb.d/01-schemas.sql
    command: >
      postgres
        -c log_min_duration_statement=1000
        -c shared_preload_libraries=pg_stat_statements
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ifx_dev -d infinityrx"]
      interval: 5s
      timeout: 5s
      retries: 5

  postgres-replica:
    image: postgres:17-alpine
    ports: ["5433:5432"]
    environment:
      POSTGRES_DB: infinityrx
      POSTGRES_USER: ifx_dev
      POSTGRES_PASSWORD: dev_password_change_me
    depends_on:
      - postgres
    # Note: full streaming replication config in infrastructure/docker/replica-setup.sh

  redis:
    image: redis:7.4-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s

  rabbitmq:
    image: rabbitmq:4-management-alpine
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: ifx_dev
      RABBITMQ_DEFAULT_PASS: dev_password_change_me
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "check_running"]
      interval: 10s

volumes:
  pgdata:
```

### 6.2 Database Configuration

- **Connection pooling**: 20 connections per module (configurable). Max 100 total. Pool exhaustion alert at 80%.
- **Slow query logging**: queries >1 second logged. Queries >5 seconds generate alert. `log_min_duration_statement = 1000` in PostgreSQL config.
- **Statement statistics**: `pg_stat_statements` extension for query performance analysis.
- **Read replica**: streaming replication for Reporting module. All report queries route to replica. Replica lag monitored — alert if >5 seconds.
- **Backup**: automated daily backup (pg_dump for dev, Azure Backup for production). Weekly restore test to verify backup integrity. HIPAA 2026 requires 72-hour restoration proof.
- **Migration rollback**: every Alembic migration has a tested `downgrade()`. Irreversible migrations (data transforms) flagged and require manual approval before applying.

---

## 7. Operational Patterns

### 7.1 Structured Logging

All application logs in JSON format:
```json
{
    "timestamp": "2026-04-12T10:30:00.123Z",
    "level": "INFO",
    "module": "billing",
    "correlation_id": "uuid",
    "tenant_id": "uuid",
    "user_id": "uuid",
    "request_id": "uuid",
    "message": "Payment batch generated",
    "data": { "batch_id": "uuid", "payment_count": 47 }
}
```
- PHI never appears in application logs (separate PHI access audit entries)
- Correlation ID propagated across all module calls for distributed tracing
- Log aggregation: Azure Monitor / Application Insights (production), stdout (local dev)

### 7.2 Health Checks

- **Shallow** (`/health`): process is running, returns 200. Used by load balancer. <10ms response.
- **Deep** (`/health/detailed`): tests PostgreSQL connection, Redis connection, RabbitMQ connection, disk space, memory usage. Returns component-level status. Used by monitoring. <5 second response.
- **Readiness** (`/health/readiness`): is the service ready to accept traffic? Checks: database migration current, event bus connected, essential config loaded.
- **Liveness** (`/health/liveness`): is the process alive and not deadlocked? Simple check, always fast.

### 7.3 Graceful Shutdown

When a service receives SIGTERM (deployment, scaling):
1. Stop accepting new requests
2. Finish processing all in-flight requests (up to 30-second deadline)
3. Flush any pending audit log entries
4. Close database connections
5. Acknowledge any pending event bus messages
6. Exit

Implemented via FastAPI lifespan events. Without this, a deployment during billing batch generation could produce a corrupt batch.

### 7.4 Circuit Breaker

For external service calls (Echo API, Azure AD, FDB, NCPDP):
- Track consecutive failures per external service
- After configurable threshold (default: 5 consecutive failures): circuit OPEN — stop calling, return cached data or error immediately
- After cooldown period (default: 60 seconds): circuit HALF-OPEN — allow one test call
- If test succeeds: circuit CLOSED — resume normal operation
- If test fails: circuit OPEN again with increased cooldown
- Circuit state visible in health check and monitoring dashboard

### 7.5 Timezone Handling

- All timestamps stored in UTC in the database
- All API responses return timestamps in UTC (ISO 8601 with Z suffix)
- Display layer converts to tenant's configured timezone
- Date-based business logic (billing cycles, report periods, claim aging) uses tenant's timezone for boundary calculations
- "End of day" = 23:59:59 in tenant's timezone, converted to UTC for queries
- Bank holiday calendar uses business days in US Eastern time (NACHA standard)

---

## 8. Tenant Lifecycle

### 8.1 Provisioning (Atomic)

Single API call creates a fully functional tenant:
1. Create tenant record with configuration
2. Create all module schemas in database (run per-module schema init)
3. Create admin user account
4. Assign default roles and permissions
5. Enable default notification types
6. Activate exclusion screening
7. Activate audit logging
8. Apply default feature flags
9. Send welcome email to admin
10. Log provisioning in audit trail

If ANY step fails, the entire provisioning rolls back. No partially provisioned tenants.

### 8.2 Data Export (Offboarding)

When a tenant leaves:
1. Generate complete data package: all claims, all billing records, all invoices, all member data, all pharmacy data, all investigation records, all reports, all audit logs
2. Package in standard format (JSON + CSV + PDF for documents)
3. Encrypt the package with the tenant's provided key
4. Deliver via secure download link (expires in 72 hours)
5. After confirmed receipt: begin purge countdown (configurable, default: 90 days)

### 8.3 Data Purge

After export and retention period:
1. Delete all tenant data from all module schemas
2. Delete all files
3. Delete all audit log entries (unless retention law requires keeping)
4. Remove tenant from exclusion screening
5. Deactivate all API keys and webhook endpoints
6. Mark tenant as `terminated`
7. Purge verification: automated check that no tenant data remains in any table
8. Purge logged as a system audit entry (not tenant-scoped)

---

## 9. UI Screens

### 9.1 Platform Admin Dashboard
- Tenant list with status indicators
- System health overview (all services, all dependencies)
- Active job runs
- Recent exclusion matches requiring review
- System-wide metrics (claims, tenants, users)
- DLQ depth monitoring
- Audit integrity status

### 9.2 Tenant Admin Dashboard
- Module access overview with feature flag status
- User management (invite, roles, MFA status, lock/unlock)
- Branding configuration
- Notification configuration
- Webhook management
- Audit log viewer with integrity verification
- Job schedule management
- Feature flag toggles

### 9.3 Help Desk Unified View
- Single search bar: auth number, member ID, pharmacy NPI, or any identifier
- Cross-module results: claim details, eligibility, plan rules, pharmacy info, payment status, FWA flags
- Operator actions: override, adjustment, PA, escalation (all require confirmation, all audit-logged)
- Read-only by default. "Take Action" explicitly unlocks.

---

## 10. Test Scenarios (100% Coverage Required)

### 10.1 Tenant Isolation (Critical — 100%)
- User in Tenant A cannot see Tenant B data through ANY endpoint (automated test against every endpoint)
- Parameter manipulation (changing tenant_id in URL) returns 403
- Cached data tenant-scoped (Redis keys include tenant_id)
- Event bus messages tenant-scoped
- RLS policies prevent cross-tenant access even if middleware bypassed
- API key scoped to creating tenant only

### 10.2 Authentication & MFA (Critical — 100%)
- Login without MFA → MFA challenge (not JWT)
- Correct MFA → JWT with mfa_verified=true
- Wrong MFA code → rejection, attempt counter incremented
- Account locks after 5 failed MFA attempts
- Session timeout after inactivity period → token rejected
- Concurrent session limit enforced → oldest session revoked
- API key auth works for service endpoints
- API key with revoked status → rejected
- Expired API key → rejected
- Emergency access: two-person authorization required, special audit trail created, session auto-expires
- SSO login via SAML: successful assertion creates user session with correct tenant and roles
- SSO login via OIDC: successful auth code exchange creates user session
- JIT provisioning: first SSO login auto-creates user with default role
- Password rejected if in compromised password list
- Password rejected if doesn't meet complexity requirements
- Password rejected if matches one of last 12 passwords

### 10.3 Audit Logging (Critical — 100%)
- Every mutating request generates audit entry
- Hash chain integrity maintained across entries
- Tampering with an entry breaks the chain and is detected by verification
- PHI access logged separately
- Correlation ID propagates across event-driven workflows
- Audit integrity verification job catches breaks

### 10.4 Event Bus Reliability (Critical — 100%)
- Message delivered at least once
- Duplicate message processed idempotently (same result)
- Failed message goes to DLQ after retries
- DLQ message can be replayed
- Messages for same entity processed in order
- Consumer downtime → messages queue and deliver when consumer returns
- Schema version forward compatibility (new fields don't break old consumers)

### 10.5 Security (Critical — 100%)
- SQL injection attempts blocked on every input field
- XSS attempts sanitized
- Security headers present on every response
- PHI-containing responses include Cache-Control: no-store
- Rate limiting enforced per tenant and per user
- File upload rejects non-allowed content types
- Encryption: PHI fields unreadable in raw database query

### 10.6 Government Exclusion
- Known excluded NPI flagged on screening
- Fuzzy name match generates "probable" confidence
- OFAC SDN match blocks payment processing
- Confirmed exclusion blocks entity from all processing
- Monthly refresh detects newly excluded entities

### 10.7 Edge Cases
- Tenant provisioning fails at step 5 of 10 → all previous steps rolled back
- Two users login simultaneously to same account → both get valid sessions up to concurrent limit
- Health check when database is down → shallow returns 200, deep returns 503 with detail
- Webhook endpoint returns 500 three times → auto-disabled, admin notified
- Feature flag changed mid-request → next request uses new value
- Circuit breaker opens on external service → cached/error response, no cascade failure
- Emergency access used without two-person authorization → blocked
- SSO IdP is down → fallback to local auth (if tenant has local auth enabled) or clear error
- CORS request from non-allowed origin → blocked with proper error
- Configuration validation rejects session_timeout of 0 minutes
- Incident created as P1 → breach notification deadline automatically calculated and tracked
- Standardized error format returned for every error case (4xx, 5xx) across all endpoints
- Rate limit exceeded → 429 response with retry-after header, not 500

---

## 11. Performance Requirements

- Authentication (login + MFA): <500ms total
- API response (non-PHI): <200ms P95
- API response (PHI-containing, decryption overhead): <500ms P95
- Audit log write: <50ms (non-blocking, async)
- Health check (shallow): <10ms
- Health check (deep): <5 seconds
- Event publish: <100ms
- Event delivery to consumer: <1 second (P95)
- Webhook delivery: <5 seconds per attempt
- Feature flag check: <10ms (cached)
- Tenant provisioning: <30 seconds (all steps)

---

## 12. Data Retention

- Audit logs: tenant's configured retention (default: 7 years), then archive to cold storage. Never delete without legal authorization.
- Sessions: 30 days after expiry, then purge
- Job runs: 90 days, then archive
- Files: per tenant policy + file classification (PHI files follow tenant retention, non-PHI configurable)
- Webhook deliveries: 90 days, then purge
- Feature flag history: indefinite (configuration data)
- Bank holidays: indefinite (reference data)
- Exclusion list: current + last 2 refreshes retained

---

## 13. Default Implementation

Ships fully functional:

- **10 default system roles** with pre-assigned permissions
- **MFA mandatory** with TOTP and FIDO2 support (HIPAA 2026 compliant)
- **Password policy** enforcing NIST 800-63B standards (12+ chars, compromised password check)
- **Session management** with configurable timeout and concurrent session limits
- **Emergency access (break-glass)** procedure documented, implemented, and testable
- **API key management** for service-to-service and client API auth
- **SSO support** for SAML 2.0 and OpenID Connect (configurable per tenant)
- **19 default notification types** with sensible routing
- **OIG/SAM.gov/OFAC screening** with configurable refresh
- **Tamper-evident audit log** with hash chain and integrity verification
- **Event bus** with DLQ, ordering, replay, and schema versioning
- **Webhook delivery system** with retry and auto-disable
- **Feature flags** per tenant without redeployment
- **Tenant lifecycle**: atomic provisioning, data export, and purge
- **Bank holiday calendar** pre-loaded with US federal holidays
- **Incident response plan** with breach notification templates and timeline tracking
- **Security**: AES-256 encryption at rest, TLS 1.3 in transit, input validation, security headers, rate limiting, CORS, dependency scanning
- **Standardized error responses** across all modules
- **API versioning** with documented upgrade strategy and OpenAPI spec
- **Observability**: structured JSON logging, correlation IDs, shallow+deep health checks, slow query logging
- **Monitoring**: 15+ pre-configured alerts covering performance, security, and compliance
- **Resilience**: circuit breakers, graceful shutdown, connection pool management
- **Read replica** for reporting queries
- **Database backup** with verified restore (72-hour restoration proof)
- **Configuration validation** preventing invalid tenant settings

No configuration required to start. Everything works on defaults. Tenants customize from there.

---

## 14. Session Decomposition (4 Concurrent Sessions)

### Session 1 — Infrastructure & Database
- Docker Compose (PostgreSQL 17 + replica, Redis 7.4, RabbitMQ 4)
- Schema initialization SQL (all 25 module schemas)
- Database connection framework (SQLAlchemy async, connection pooling, slow query logging)
- Migration runner (Alembic with namespaced migrations and tested rollbacks)
- Tenant isolation (middleware + RLS + cache scoping)
- Read replica configuration
- Bank holiday calendar table and API
- Pre-flight validator
- .env.example and configuration loading

### Session 2 — Authentication, Security & Users
- MFA system (TOTP + FIDO2 + backup codes)
- Password policy (NIST 800-63B, compromised password check)
- JWT generation/validation/refresh with MFA claims
- Session management (tracking, timeout, concurrent limits, revocation)
- Emergency access (break-glass) procedure and emergency admin account
- User CRUD API
- Role and permission system with 10 default roles
- API key management (creation, hashing, scoping, rate limiting)
- SSO integration (SAML 2.0 + OIDC with JIT provisioning)
- Input validation framework (Pydantic patterns for NPI, NDC, etc.)
- Security headers middleware
- CORS middleware (configurable per tenant)
- Rate limiting middleware
- Account lockout logic
- Encryption utilities (AES-256 encrypt/decrypt for PHI fields)
- Standardized error response middleware
- Configuration validation service

### Session 3 — Event Bus, Audit & Notifications
- Event bus client (RabbitMQ local / Azure Service Bus prod)
- At-least-once delivery with idempotency
- Message ordering per entity
- Dead letter queue with monitoring and replay
- Event schema versioning
- Tamper-evident audit log (hash chain)
- Audit integrity verification (daily job + API endpoint)
- Audit log query/filter/export API
- Notification service with 19 default types
- Email delivery integration
- Webhook delivery system (registration, signing, delivery, retry, auto-disable)

### Session 4 — Jobs, Files, Exclusions, Health, Features, Incident Response
- Job scheduler with locking (prevent duplicate runs)
- Job timeout handling
- File upload/storage with auto-encryption for PHI/financial files
- Government exclusion ingestion (OIG + SAM + OFAC)
- Exclusion screening engine (exact + fuzzy)
- Feature flag system (global flags, tenant overrides, API)
- Health checks (shallow, deep, readiness, liveness)
- Circuit breaker pattern for external services
- Graceful shutdown handler
- Structured logging configuration
- Monitoring and alerting framework (15+ pre-configured alerts)
- Incident response workflow (security_incidents table, notification templates, timeline tracking)
- Dependency vulnerability scanning in CI/CD
- Tenant provisioning (atomic, with rollback)
- Tenant data export and purge workflows
- Database backup verification job
- Bank holiday calendar
- OpenAPI spec generation and hosting
