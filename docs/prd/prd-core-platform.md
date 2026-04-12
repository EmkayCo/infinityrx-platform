# PRD — Module 1: Core Platform

**Module:** Core Platform  
**Priority:** Phase 1 (build first — everything depends on this)  
**Sessions:** 4 concurrent  
**Duration:** 1-2 weeks  

---

## 1. Purpose

The Core Platform is the foundation that every other module plugs into. It provides multi-tenant isolation, authentication, authorization, inter-module communication, audit logging, job scheduling, file management, notifications, and operational tooling. No other module can function without this.

This module has no business logic specific to pharmacy claims, billing, or FWA. It is a generic multi-tenant SaaS platform foundation that could support any enterprise application. The PBM-specific logic lives in the other 24 modules.

---

## 2. Data Model

### 2.1 Tenants

```sql
CREATE SCHEMA core;

CREATE TABLE core.tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,          -- URL-friendly identifier
    display_name VARCHAR(255) NOT NULL,          -- What users see
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'terminated')),
    
    -- White-label branding
    logo_url TEXT,
    primary_color VARCHAR(7) DEFAULT '#0B1D3A',  -- InfinityRx navy default
    secondary_color VARCHAR(7) DEFAULT '#FFFFFF',
    font_family VARCHAR(100) DEFAULT 'Inter',
    custom_domain VARCHAR(255),                   -- e.g., portal.connectiverx.com
    
    -- Contact
    contact_name VARCHAR(255),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(20),
    
    -- Configuration
    timezone VARCHAR(50) DEFAULT 'America/New_York',
    date_format VARCHAR(20) DEFAULT 'MM/DD/YYYY',
    currency VARCHAR(3) DEFAULT 'USD',
    
    -- Data retention
    data_retention_days INTEGER DEFAULT 2555,      -- 7 years default (HIPAA)
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES core.users(id),
    updated_by UUID REFERENCES core.users(id)
);

CREATE INDEX idx_tenants_slug ON core.tenants(slug);
CREATE INDEX idx_tenants_status ON core.tenants(status);
```

### 2.2 Users & Roles

```sql
CREATE TABLE core.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(id),
    email VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    azure_ad_oid VARCHAR(255),                    -- Azure AD B2C object ID
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'locked')),
    last_login_at TIMESTAMPTZ,
    failed_login_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(tenant_id, email)
);

CREATE TABLE core.roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES core.tenants(id),   -- NULL = system-wide role
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_system BOOLEAN DEFAULT FALSE,               -- System roles can't be deleted
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Default system roles (created on platform init, available to all tenants)
-- platform_admin: InfinityRx super admin — all tenants, all modules
-- tenant_admin: Admin for one tenant — all modules within tenant
-- tenant_operator: Run operations (billing cycles, imports) within tenant
-- tenant_viewer: Read-only access within tenant
-- client_admin: External client admin — scoped view, their data only
-- client_viewer: External client viewer — scoped read-only
-- pharmacy_admin: Pharmacy user — their claims/payments only
-- pharmacy_viewer: Pharmacy read-only
-- provider_admin: Medical provider — their claims only
-- member: Patient/member — their own data only

CREATE TABLE core.user_roles (
    user_id UUID NOT NULL REFERENCES core.users(id),
    role_id UUID NOT NULL REFERENCES core.roles(id),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by UUID REFERENCES core.users(id),
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE core.permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module VARCHAR(100) NOT NULL,                  -- e.g., 'billing', 'reclaimrx', 'pharmacy_directory'
    action VARCHAR(100) NOT NULL,                  -- e.g., 'read', 'write', 'delete', 'approve', 'export'
    description TEXT,
    UNIQUE(module, action)
);

CREATE TABLE core.role_permissions (
    role_id UUID NOT NULL REFERENCES core.roles(id),
    permission_id UUID NOT NULL REFERENCES core.permissions(id),
    PRIMARY KEY (role_id, permission_id)
);
```

### 2.3 Audit Log

```sql
CREATE TABLE core.audit_log (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES core.tenants(id),
    user_id UUID REFERENCES core.users(id),
    action VARCHAR(100) NOT NULL,                  -- e.g., 'create', 'update', 'delete', 'approve', 'login', 'phi_access'
    module VARCHAR(100) NOT NULL,                  -- Which module
    entity_type VARCHAR(100),                      -- e.g., 'claim', 'batch', 'member', 'pharmacy'
    entity_id VARCHAR(255),                        -- ID of the affected entity
    before_value JSONB,                            -- State before change (for updates)
    after_value JSONB,                             -- State after change
    ip_address INET,
    user_agent TEXT,
    correlation_id UUID,                           -- Links related actions across modules
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_tenant_created ON core.audit_log(tenant_id, created_at DESC);
CREATE INDEX idx_audit_entity ON core.audit_log(tenant_id, entity_type, entity_id);
CREATE INDEX idx_audit_user ON core.audit_log(tenant_id, user_id, created_at DESC);
CREATE INDEX idx_audit_action ON core.audit_log(tenant_id, action, created_at DESC);

-- Partition by month for performance at scale
-- At 100M claims/year, audit_log grows fast — partitioning keeps queries fast
```

### 2.4 Notifications

```sql
CREATE TABLE core.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(id),
    user_id UUID NOT NULL REFERENCES core.users(id),
    notification_type VARCHAR(100) NOT NULL,        -- e.g., 'batch_released', 'gate_failed', 'exclusion_match'
    severity VARCHAR(20) DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'critical')),
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    link TEXT,                                      -- Deep link to relevant screen
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE core.notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES core.users(id),
    notification_type VARCHAR(100) NOT NULL,
    email_enabled BOOLEAN DEFAULT TRUE,
    in_app_enabled BOOLEAN DEFAULT TRUE,
    sms_enabled BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, notification_type)
);

-- Default notification types (pre-built, configurable per tenant):
-- batch_released, batch_failed, payment_settled, payment_failed,
-- prefund_low, prefund_critical, exclusion_match, anomaly_detected,
-- pa_decision, cycle_reminder, gate_review_complete, gate_review_failed,
-- member_enrolled, member_terminated, audit_initiated, dispute_submitted,
-- report_ready, sftp_delivery_failed, system_health_warning
```

### 2.5 Jobs

```sql
CREATE TABLE core.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES core.tenants(id),    -- NULL = system-wide job
    name VARCHAR(255) NOT NULL,
    job_type VARCHAR(100) NOT NULL,                 -- e.g., 'fdb_refresh', 'ncpdp_refresh', 'exclusion_screen', 'report_generate'
    schedule VARCHAR(100),                          -- Cron expression
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'paused', 'disabled')),
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    config JSONB,                                   -- Job-specific configuration
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE core.job_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES core.jobs(id),
    status VARCHAR(20) NOT NULL CHECK (status IN ('running', 'succeeded', 'failed', 'cancelled')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    result JSONB,                                   -- Outcome details
    error_message TEXT,
    items_processed INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0
);
```

### 2.6 Files

```sql
CREATE TABLE core.files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(id),
    filename VARCHAR(500) NOT NULL,
    original_filename VARCHAR(500) NOT NULL,
    content_type VARCHAR(100),
    size_bytes BIGINT,
    storage_path TEXT NOT NULL,                     -- Local path or Azure Blob URL
    module VARCHAR(100),                            -- Which module owns this file
    entity_type VARCHAR(100),                       -- What it's attached to
    entity_id VARCHAR(255),
    uploaded_by UUID REFERENCES core.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 2.7 Government Exclusion Screening

```sql
CREATE TABLE core.exclusion_list (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(20) NOT NULL CHECK (source IN ('OIG', 'SAM')),
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('individual', 'organization')),
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
    tenant_id UUID NOT NULL REFERENCES core.tenants(id),
    exclusion_list_id BIGINT REFERENCES core.exclusion_list(id),
    matched_entity_type VARCHAR(50) NOT NULL,       -- 'pharmacy', 'prescriber', 'member'
    matched_entity_id VARCHAR(255) NOT NULL,
    match_confidence VARCHAR(20) DEFAULT 'exact' CHECK (match_confidence IN ('exact', 'probable', 'possible')),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'dismissed')),
    reviewed_by UUID REFERENCES core.users(id),
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Default: OIG exclusion list refreshed monthly, SAM.gov refreshed monthly
-- All pharmacies, prescribers screened at onboarding and on each refresh
-- Any match blocks entity participation until reviewed and dismissed
```

---

## 3. API Endpoints

```
/api/v1/

# Tenant Management (platform_admin only)
POST   /tenants                        Create tenant
GET    /tenants                        List tenants
GET    /tenants/{id}                   Get tenant details
PUT    /tenants/{id}                   Update tenant
PUT    /tenants/{id}/branding          Update white-label branding
POST   /tenants/{id}/suspend           Suspend tenant
POST   /tenants/{id}/activate          Reactivate tenant

# Authentication
POST   /auth/login                     Login (returns JWT)
POST   /auth/logout                    Logout (invalidate token)
POST   /auth/refresh                   Refresh JWT
GET    /auth/me                        Current user profile
PUT    /auth/me                        Update profile

# User Management (tenant_admin)
POST   /users                          Create user
GET    /users                          List users (tenant-scoped)
GET    /users/{id}                     Get user
PUT    /users/{id}                     Update user
PUT    /users/{id}/roles               Assign roles
POST   /users/{id}/lock                Lock user
POST   /users/{id}/unlock              Unlock user

# Role Management (tenant_admin)
GET    /roles                          List roles
POST   /roles                          Create custom role
PUT    /roles/{id}                     Update role
PUT    /roles/{id}/permissions         Assign permissions
GET    /permissions                    List all available permissions

# Audit Log (tenant_admin, tenant_operator read-only)
GET    /audit                          Query audit log (filterable by action, module, entity, user, date range)
GET    /audit/export                   Export audit log (CSV/Excel)
GET    /audit/{id}                     Get specific audit entry

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
POST   /files/upload                   Upload file
GET    /files                          List files (tenant-scoped, filterable)
GET    /files/{id}                     Download file
DELETE /files/{id}                     Delete file

# Government Exclusion
GET    /exclusions/matches             List exclusion matches (tenant-scoped)
PUT    /exclusions/matches/{id}        Review match (confirm/dismiss)
POST   /exclusions/screen              Trigger manual screening for an entity
GET    /exclusions/status              Last refresh date, match counts

# System Health (platform_admin)
GET    /health                         Health check (DB, Redis, message queue)
GET    /health/detailed                Detailed status per service
```

**Every endpoint enforces:**
1. JWT authentication (except /auth/login, /health)
2. Tenant isolation (user only sees their tenant's data)
3. Role-based permission check
4. Audit logging (every mutating request logged)
5. Rate limiting (configurable per tenant and per user type)
6. Request correlation ID (propagated to all downstream calls)

---

## 4. Core Services

### 4.1 Tenant Isolation

Every database query includes `tenant_id` in the WHERE clause. This is not optional. The tenant context is extracted from the JWT token and injected into every database session automatically via middleware. There is no code path where a query can execute without tenant scoping (except platform_admin endpoints that explicitly span tenants).

**Implementation:** FastAPI middleware extracts `tenant_id` from JWT claims. A custom SQLAlchemy session factory applies a default filter on all queries. Integration tests verify: User A in Tenant 1 cannot access data from Tenant 2 through any endpoint, any parameter manipulation, any export, any report, any search, or any cached value.

### 4.2 Event Bus

Inter-module communication via events. Modules publish events to named topics. Other modules subscribe to relevant topics.

**Pre-built event types:**
```python
# Claims events
"claim.submitted"        # New claim received
"claim.adjudicated"      # Claim processed with result
"claim.reversed"         # Claim reversed
"claim.reprocessed"      # Claim re-adjudicated

# Billing events
"batch.created"          # New billing batch
"batch.released"         # Batch approved and released
"payment.generated"      # Payment file created
"payment.settled"        # Payment confirmed by bank
"payment.returned"       # ACH return received
"invoice.generated"      # Client invoice created

# Member events
"member.enrolled"        # New member added
"member.terminated"      # Member coverage ended
"member.eligibility_changed"  # Eligibility updated (triggers restacking)

# FWA events
"anomaly.detected"       # ReclaimRx flagged suspicious activity
"recovery.estimated"     # Recovery amount calculated
"audit.initiated"        # Pharmacy audit started

# System events
"exclusion.match_found"  # Government exclusion match
"job.completed"          # Scheduled job finished
"job.failed"             # Scheduled job failed
"sftp.delivery_failed"   # SFTP file delivery failed
```

**Message format:**
```json
{
    "event_type": "claim.adjudicated",
    "tenant_id": "uuid",
    "correlation_id": "uuid",
    "timestamp": "2026-04-12T10:30:00Z",
    "source_module": "adjudication-engine",
    "payload": { ... }
}
```

Local dev: RabbitMQ with topic exchanges. Production: Azure Service Bus with topic subscriptions. The event bus client in `shared/events/` abstracts the provider so modules don't know which broker they're talking to.

### 4.3 Audit Logging

Every mutating API call is logged automatically via middleware. The audit service captures:
- **who**: user_id, tenant_id
- **what**: action (create/update/delete/approve/export/phi_access), module, entity_type, entity_id
- **when**: timestamp
- **where**: IP address, user agent
- **before/after**: JSON snapshots for updates (what changed)
- **correlation_id**: links related actions across modules (e.g., a billing cycle release triggers payment generation triggers 835 generation — all share one correlation_id)

**PHI access logging:** Any endpoint that returns PHI (member name, DOB, address, etc.) logs a `phi_access` audit entry with the specific fields accessed. This is separate from the PHI masking layer (which strips PHI for unauthorized users) — even authorized PHI access is logged.

**Queryable:** Operators can search audit log by any field. Exportable to CSV/Excel. Retention per tenant's configured data_retention_days.

**SOC 2 ready:** The audit log schema and query capabilities satisfy SOC 2 Type II control requirements for access monitoring, change tracking, and incident investigation.

### 4.4 Government Exclusion Screening

**Default implementation:**
- OIG LEIE (List of Excluded Individuals and Entities): downloaded monthly from oig.hhs.gov, parsed, loaded into exclusion_list table
- SAM.gov: entity status API queried monthly for all active pharmacies and prescribers
- Every pharmacy, prescriber, and member is screened at onboarding
- On each monthly refresh, all active entities are re-screened
- Match algorithm: exact NPI match (high confidence), fuzzy name+state match (probable), name-only match (possible)
- Any match generates a notification to tenant admins and blocks the entity from processing until reviewed
- Match review workflow: admin confirms (entity is excluded — block permanently) or dismisses (false positive — document reason)

**Configurable per tenant:**
- Screening frequency (monthly, weekly, daily)
- Which entity types to screen (pharmacy, prescriber, member, or all)
- Match confidence threshold for auto-block vs manual review
- Notification routing (who gets alerted)

---

## 5. Infrastructure

### 5.1 Docker Compose (Local Development)

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
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ifx_dev -d infinityrx"]
      interval: 5s
      timeout: 5s
      retries: 5

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

### 5.2 Schema Initialization

```sql
-- infrastructure/docker/init-schemas.sql
-- Creates one schema per module. Each module owns its schema exclusively.
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS billing;
CREATE SCHEMA IF NOT EXISTS reclaimrx;
CREATE SCHEMA IF NOT EXISTS drug_db;
CREATE SCHEMA IF NOT EXISTS pharmacy_dir;
CREATE SCHEMA IF NOT EXISTS med_prescriber_dir;
CREATE SCHEMA IF NOT EXISTS member_mgmt;
CREATE SCHEMA IF NOT EXISTS plan_design;
CREATE SCHEMA IF NOT EXISTS rules_engine;
CREATE SCHEMA IF NOT EXISTS adjudication;
CREATE SCHEMA IF NOT EXISTS switch_conn;
CREATE SCHEMA IF NOT EXISTS prior_auth;
CREATE SCHEMA IF NOT EXISTS payment_proc;
CREATE SCHEMA IF NOT EXISTS edi_compliance;
CREATE SCHEMA IF NOT EXISTS medical_claims;
CREATE SCHEMA IF NOT EXISTS reporting;
CREATE SCHEMA IF NOT EXISTS program_config;
CREATE SCHEMA IF NOT EXISTS testing_sim;
CREATE SCHEMA IF NOT EXISTS ebv_ebi;
CREATE SCHEMA IF NOT EXISTS ai_nlp;
CREATE SCHEMA IF NOT EXISTS rebate_mgmt;
CREATE SCHEMA IF NOT EXISTS dataiq;
CREATE SCHEMA IF NOT EXISTS part_d;
CREATE SCHEMA IF NOT EXISTS mtm_clinical;
```

### 5.3 Pre-Flight Validator

Script that runs at the start of every agent session:

```python
# shared/utils/preflight.py
# Checks: 
# 1. PostgreSQL reachable and all schemas exist
# 2. Redis reachable
# 3. RabbitMQ reachable
# 4. .env.local exists with required vars
# 5. Git worktree is clean (no uncommitted changes)
# 6. Current module's tasks/todo.md exists and is readable
# 7. Current module's tasks/lessons.md has been read (print last 5 entries)
# All checks pass → print "PRE-FLIGHT: ALL CLEAR" 
# Any check fails → print which check failed and how to fix it, then exit
```

---

## 6. UI Screens

### 6.1 Platform Admin Dashboard
- Tenant list with status indicators (active/suspended)
- System health overview (DB, Redis, queue, each module's service)
- Active job runs
- Recent exclusion matches requiring review
- System-wide metrics (total claims processed, total tenants, active users)

### 6.2 Tenant Admin Dashboard
- Module access overview
- User management (invite, roles, lock/unlock)
- Branding configuration (logo upload, color pickers, font selector, preview)
- Notification configuration
- Audit log viewer with search/filter/export
- Job schedule management

### 6.3 Help Desk Unified View
- Single search bar: enter auth number, member ID, pharmacy NPI, or any identifier
- Results show: claim details, member eligibility, plan rules that applied, pharmacy info, payment status
- Cross-module data pulled via API calls to relevant modules
- Operator can initiate actions: override, adjustment, PA, escalation
- All actions audit-logged

**UX:** Read-only by default. "Take Action" button unlocks action options. Every action requires confirmation. Destructive actions (reversal, adjustment) require typed confirmation.

---

## 7. Test Scenarios

### 7.1 Tenant Isolation (Critical)
- User in Tenant A cannot see Tenant B data through any endpoint
- User in Tenant A cannot access Tenant B data by changing ID parameters
- User in Tenant A cannot see Tenant B data in search results
- User in Tenant A cannot see Tenant B data in exports
- Cached data is tenant-scoped (Redis keys include tenant_id)
- Event bus messages are tenant-scoped (subscribers only receive their tenant's events)

### 7.2 Authentication & Authorization
- Expired JWT returns 401
- Invalid JWT returns 401
- User without permission for an action returns 403
- Locked user cannot login
- Failed login increments counter; after 5 failures, account locks
- Role changes take effect immediately (not cached)
- Platform admin can access all tenants
- Tenant admin cannot access other tenants

### 7.3 Audit Logging
- Every POST/PUT/DELETE request generates an audit entry
- Audit entry contains correct before/after values for updates
- PHI access generates separate phi_access audit entry
- Audit log query respects tenant isolation
- Correlation ID propagates across event-driven workflows

### 7.4 Government Exclusion
- Known excluded NPI is flagged on screening
- Fuzzy name match generates "probable" confidence
- Confirmed exclusion blocks entity from processing
- Dismissed match is documented with reason
- Monthly refresh detects newly excluded entities

---

## 8. Session Decomposition (4 Concurrent Sessions)

### Session 1 — Infrastructure & Database
- Docker Compose file
- Schema initialization SQL
- Database connection framework (SQLAlchemy async, connection pooling)
- Migration runner (Alembic with module-namespaced migrations)
- Tenant isolation middleware
- Pre-flight validator script
- .env.example and configuration loading

### Session 2 — Authentication & Users
- Azure AD B2C integration (or local JWT for dev)
- JWT token generation/validation/refresh
- User CRUD API
- Role and permission system
- Permission checking middleware
- Login/logout/lock flows
- Default system roles creation

### Session 3 — Event Bus & Audit & Notifications
- Event bus client (RabbitMQ local / Azure Service Bus prod)
- Publish/subscribe pattern with topic routing
- Audit logging middleware (auto-capture on mutating requests)
- Audit log query API with filtering
- Audit log export (CSV/Excel)
- Notification service (create, deliver, preferences)
- Email delivery integration (SMTP configurable)

### Session 4 — Jobs, Files, Exclusions, Health
- Job scheduler (cron-based, configurable)
- Job execution framework with status tracking
- File upload/download/storage service
- Government exclusion list ingestion (OIG + SAM.gov)
- Exclusion screening engine (exact + fuzzy matching)
- Exclusion match review workflow
- Health check endpoints (per-service status)
- CI/CD pipeline configuration

---

## 9. Integration Points

### Events Published
- `exclusion.match_found` — when screening finds a match
- `job.completed` / `job.failed` — when any job finishes
- `user.created` / `user.updated` — when user accounts change
- `tenant.created` / `tenant.suspended` — when tenant status changes

### Events Consumed
- All events from all modules — for audit log enrichment
- Module-specific events — for notification routing

### APIs Consumed By Other Modules
- `/auth/validate` — every module validates JWT on every request
- `/audit` — every module writes audit entries
- `/notifications` — every module can trigger notifications
- `/files` — every module can store/retrieve files
- `/exclusions/screen` — modules check entities against exclusion list
- `/jobs` — modules register their scheduled jobs

---

## 10. Default Implementation

The following ship fully functional out of the box:

- **10 default system roles** with pre-assigned permissions for every module
- **19 default notification types** with sensible default routing
- **OIG/SAM.gov screening** with monthly refresh, exact+fuzzy matching, review workflow
- **Audit logging** captures every mutating action automatically — zero configuration needed
- **Health checks** monitor PostgreSQL, Redis, RabbitMQ, and report status
- **Pre-flight validator** verifies environment before any work begins

A new tenant is provisioned with:
- Admin user account
- All default roles available
- All notification types enabled
- Exclusion screening active
- Audit logging active
- Default InfinityRx branding (customizable immediately)

No configuration required to start using the platform. Everything works on defaults. Tenants customize from there.
