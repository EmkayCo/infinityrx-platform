# Security / Data Integrity / Regulatory — Audit Findings

**Audit Date:** 2026-04-14
**Auditor:** Tier-1 Security/Data/Regulatory Agent
**Scope:** Categories 7, 8, 15

---

## Category 7: Security — Score: 64/100

### Critical Findings (LESSON-006 Wiring Verification)

#### PASS — SecurityHeadersMiddleware mounted
`modules/core-platform/src/main.py` line 167: `app.add_middleware(SecurityHeadersMiddleware)` — confirmed present in `create_app()`. Integration test `test_main_middleware.py` verifies this.

#### PASS — RateLimitMiddleware mounted on core-platform
`modules/core-platform/src/main.py` line 166: `app.add_middleware(RateLimitMiddleware, config=RateLimitConfig())` — confirmed.

#### PASS — RateLimitMiddleware mounted on medical-claims, member-management, drug-database, prescriber-directory, edi-compliance, pharmacy-directory
All reviewed `main.py` / `app.py` factories mount `RateLimitMiddleware`.

#### PASS — DLQ router mounted on core-platform, medical-claims
Both `create_app()` factories include `app.include_router(build_dlq_router(...))`.

#### PASS — Audit hash chain wired
`modules/core-platform/src/audit/service.py` lines 58–76: `AuditService.log()` calls `compute_entry_hash()` and stores both `previous_hash` and `entry_hash` on every row. LESSON-006 finding is resolved.

#### PASS — MFA enforcement wired and tested
`modules/core-platform/src/auth/service.py` lines 193–219: login gate checks `tenant.mfa_required`, raises `MfaChallengeRequiredError` for enrolled users and `MfaEnrollmentRequiredError` for unenrolled — no JWT is issued. `test_mfa_login_gate.py` contains tests verifying that login with `mfa_required=True` and no enrollment returns 403, and with enrollment returns 202 challenge (not a JWT).

#### PASS — API keys stored as SHA-256 hash
`modules/core-platform/src/auth/api_keys/service.py` line 63: keys are `hashlib.sha256(...).hexdigest()`. Lookup uses `hmac.compare_digest()` for constant-time comparison.

#### PASS — Passwords use bcrypt (constant-time)
`shared/auth/passwords.py`: direct `bcrypt` library, `checkpw` is constant-time. No passlib dependency.

#### PASS — TOTP uses `\A...\Z` anchors (LESSON-004 resolved)
`shared/auth/mfa/totp.py` uses `\A\d{6}\Z` anchors.

### HIGH — Missing JWT auth on medical-claims API endpoints
**Severity: HIGH**  
**File:** `modules/medical-claims/src/api/routes/claims.py`  
`list_claims`, `get_claim`, `create_claim`, all other claim routes — no `Depends(get_current_user)` or bearer token validation. The only check is `_get_tenant_id(request)` which validates the `x-tenant-id` header as a UUID but performs zero authentication. Any caller who knows a tenant UUID can read/write PHI claims.  
The same pattern is found across all medical-claims route files (`unified_spend.py`, `claims_appeal.py`, `asp.py`, `crosswalk.py`).  
**Prescriber-directory:** `modules/prescriber-directory/src/api/dependencies.py` — `get_tenant_id()` validates the header UUID but no bearer/JWT auth dependency is defined or applied to any route. Unauthenticated requests can read prescriber data.  
**EDI-compliance:** `_require_tenant()` in `generate.py` / `compliance.py` validates UUID but no JWT check — unauthenticated callers can generate or parse X12 EDI files.  
**Remediation required before production:** All PHI-touching endpoints must add `Depends(get_current_user)`.

### HIGH — prescriber-directory session factory missing `install_tenant_loader`
**Severity: HIGH**  
**File:** `modules/prescriber-directory/src/db/session.py`  
`_get_session_factory()` calls `sessionmaker(...)` with no `install_tenant_loader(...)`. The prescriber table also has **no `tenant_id` column** and does not inherit `TenantScopedMixin` — the module treats prescribers as a global reference table. If prescriber data ever becomes tenant-scoped (e.g., network assignments, credentialing status per plan), there is no isolation fence and no loader to add. Additionally the global NPI lookup (no tenant filter) means any tenant can query any prescriber — currently a design choice but must be documented and accepted explicitly.

### MEDIUM — No CORS configuration on any module
**Severity: MEDIUM**  
`grep -rn "CORSMiddleware"` across all modules returns **zero results**. No FastAPI app mounts `CORSMiddleware`. In a browser-accessible API this means the browser's same-origin policy is the only CORS fence, and server-to-server calls are unrestricted. For a PHI-handling platform this requires explicit allow-list configuration.

### MEDIUM — EDI-compliance and medical-claims have no auth even for internal-facing paths
Cross-reference with HIGH above — these modules accept tenant-header-only "auth". A compromised internal service or misconfigured network can access all EDI transactions and medical claims without credentials.

### MEDIUM — `quantize()` calls missing `ROUND_HALF_UP` in analytics routes
**Severity: MEDIUM**  
**Files:**  
- `modules/medical-claims/src/api/routes/analytics.py` lines 76, 117, 156, 191 — `quantize(Decimal("0.01"))` with no `rounding=` argument defaults to `ROUND_HALF_EVEN` (banker's rounding), violating the financial-precision rule. No `ROUND_HALF_UP` import present in these inline Decimal calls.  
- `modules/medical-claims/src/services/denial_service.py` line 152 — same issue on denial rate percentage.

### LOW — FHIR bridge serializes Decimal as float
**Severity: LOW (non-financial display field, but rule violation)**  
**File:** `modules/edi-compliance/src/services/fhir_bridge.py` line 122  
`"value": float(b.monetary_amount)` — converts Decimal benefit amount to IEEE 754 float in the FHIR JSON payload. This violates the financial-precision rule that Decimal amounts must be serialized as `str()` in event/API payloads.

### PASS — No hardcoded secrets found
Grep for `SECRET_KEY\s*=` and `DB_PASSWORD\s*=` in production code returned zero results. All secrets load from environment variables.

### PASS — PHI not logged
PHI scrub grep found no logger calls exposing `member_name`, `ssn`, or `date_of_birth` raw values in service code. `member_service.py` defines `_PHI_FIELDS` and masking logic.

### PASS — Input validation via Pydantic
Spot-checked 5 routers: `claims.py`, `analytics.py`, `generate.py`, `compliance.py`, `role_router.py` — all request body parameters use Pydantic models. Raw `request.json()` not found.

### PASS — RBAC enforced on core-platform
`require_role(...)` and `require_permission(...)` dependencies applied across exclusions, health, files, bank-holidays, audit, and auth APIs.

### Evidence Summary
| Check | Result |
|---|---|
| SecurityHeadersMiddleware mounted | PASS |
| RateLimitMiddleware mounted | PASS |
| DLQ router mounted | PASS |
| Audit hash chain wired | PASS |
| MFA enforcement + tests | PASS |
| API key SHA-256 + constant-time | PASS |
| Password bcrypt | PASS |
| CORS configured | FAIL — missing everywhere |
| JWT auth on medical-claims routes | FAIL — tenant UUID only |
| JWT auth on prescriber-directory routes | FAIL — tenant UUID only |
| JWT auth on edi-compliance routes | FAIL — tenant UUID only |
| install_tenant_loader on prescriber-directory | FAIL |
| quantize with ROUND_HALF_UP in analytics | FAIL |
| Float in FHIR bridge | FAIL |
| No hardcoded secrets | PASS |
| PHI not in logs | PASS |

---

## Category 8: Data Integrity — Score: 77/100

### PASS — No float/Float in model money columns
All reviewed money column files explicitly comment "never Float" and use `Numeric(n, scale)`. Grep across `modules/*/src/models/*.py` returned zero matches for `: float`, `Float(`, or `sa.REAL` on money fields. Billing model `tables.py` confirmed: all amounts use `Numeric(12,2)` or `Numeric(15,2)`.

### PASS — Decimal/ROUND_HALF_UP usage widespread
150+ uses of `ROUND_HALF_UP` / `quantize` found across modules and shared utilities. `shared/utils/money.py` `penny_allocate()` used for splits.

### FAIL — `quantize()` calls missing `rounding=ROUND_HALF_UP` in medical-claims analytics (duplicated from Cat 7)
5 locations in `analytics.py` and `denial_service.py` call `.quantize(Decimal("0.01"))` without `rounding=ROUND_HALF_UP`. Default is `ROUND_HALF_EVEN`. Financial rule violation.

### FAIL — func.sum() aggregates in analytics not always wrapped in Decimal(str(...))
**File:** `modules/medical-claims/src/api/routes/analytics.py`  
Line 142 `total_paid` and line 182 `func.sum(ClaimRecord.paid_amount).desc()` — the label results returned from SQLAlchemy are passed through `Decimal(str(row.total_paid or "0"))` in the serialization (lines 156, 191), which is correct. Line 76 similarly wraps. This check **passes** on closer inspection — all aggregate results are wrapped in `Decimal(str(...))` before serialization.

### FAIL — No `ondelete=` specified on any ForeignKey in billing or medical-claims models
**Severity: MEDIUM**  
`modules/billing/src/models/tables.py`: 10+ ForeignKey columns (e.g., `ForeignKey("billing.claim_records.id")`, `ForeignKey("billing.payment_batches.id")`) with no `ondelete=` clause. PostgreSQL defaults to RESTRICT on FK delete. While RESTRICT is safer than CASCADE, the lack of explicit ondelete means the intent is undocumented and future maintainers may add CASCADE inadvertently. Best practice: explicit `ondelete="RESTRICT"` or `ondelete="SET NULL"` per business requirement.

### PASS — Unique constraints present
`medical-claims`: `UniqueConstraint("tenant_id", "claim_number", "claim_line_number")` and additional NDC/quarter constraints.  
`billing`: `UniqueConstraint("tenant_id", "auth_number")` on claims.

### PASS — DateTime(timezone=True) used on datetime columns
Billing `tables.py` line 73: `DateTime(timezone=True)`. No naked `TIMESTAMP` or `DateTime()` found in scanned model files.

### PASS — UUID primary keys used (except one known outlier)
`drug-database/src/models/tables.py` line 154: `id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)` — one integer PK in the reference/lookup table (`DrugPriceHistory` or similar). This is a reference table (not a tenant-owned transactional table), but should be documented.

### PASS — Backup strategy exists
`infrastructure/scripts/backup.sh`, `restore.sh`, `verify_backup.py`, and `backup-restore.md` are present.

### MEDIUM — drug-database has one integer PK
`modules/drug-database/src/models/tables.py` line 154: integer autoincrement PK. Violates UUID-for-PKs rule. Not a tenant-owned table but architecture rule is absolute.

### Evidence Summary
| Check | Result |
|---|---|
| No float in money columns | PASS |
| Decimal/ROUND_HALF_UP widespread | PASS |
| ROUND_HALF_UP on all quantize calls | FAIL — 5 missing |
| func.sum wrapped in Decimal(str()) | PASS |
| FKs with explicit ondelete | FAIL — none specified |
| Unique constraints present | PASS |
| TIMESTAMPTZ used | PASS |
| UUID primary keys | MOSTLY PASS (1 integer PK in drug-database) |
| Backup scripts exist | PASS |

---

## Category 15: Regulatory & Compliance — Score: 52/100

### HIPAA Security Rule Safeguards Checklist

| Control | Status | Evidence |
|---|---|---|
| Access controls (§164.312(a)) | PARTIAL — core-platform has auth+RBAC; medical-claims/prescriber/edi have no JWT auth | See Cat 7 HIGH findings |
| Audit controls tamper-evident (§164.312(b)) | PASS | AuditService hash chain verified |
| Integrity controls (§164.312(c)) | PARTIAL | Hash chain covers audit; no integrity check on claim records |
| Transmission security TLS 1.3 (§164.312(e)) | NOT VERIFIED | No TLS config found in codebase; assumed Azure infra layer |
| PHI encryption at rest AES-256 (§164.312(a)(2)(iv)) | PASS for member-management | EncryptedString / AES-256-GCM confirmed in member-management and pharmacy-directory |
| PHI encryption on all modules | PARTIAL | medical-claims `ClaimRecord` has PHI fields (`patient_member_id`, `rendering_provider_npi`) but no EncryptedString on those columns |
| MFA enforced (2026 rule) | PASS on core-platform | Tested; SMS disallowed; TOTP/FIDO2 enforced |
| Session timeout 15 min | PASS | Tenant model has `session_timeout_minutes` default; session service enforces inactivity |
| Concurrent session limit 5 | PASS | SessionService `MAX_ACTIVE_SESSIONS = 5` |
| Daily integrity verification job | NOT FOUND | No scheduled job for `verify_audit_chain()` found in codebase |
| Weekly restore test | NOT FOUND | `verify_backup.py` exists but no scheduled CI job found |
| PHI access audit logging | PASS on core-platform, reporting | `@phi_access` decorator and `phi_access_log` table exist |
| Minimum necessary (PHI masking) | PASS on member-management | `MemberService._mask_phi()` masking logic present |

### FAIL — No HIPAA Security Rule SOP documentation
**Severity: HIGH**  
`ls docs/sops/` returns only `backup-restore.md` — **one file**. There are no written SOPs for: access control reviews, workforce training, contingency plans, device and media controls, or breach notification procedures. The PRDs describe the requirements but there are no operational SOPs. HIPAA Security Rule requires documented, implemented, and regularly reviewed policies.

### FAIL — medical-claims PHI columns not encrypted at rest
**Severity: HIGH**  
`modules/medical-claims/src/models/tables.py`: `patient_member_id`, `rendering_provider_npi`, `patient_last_name` (if present), and `diagnosis_codes` are stored as plaintext `String` columns. No `EncryptedString` on any PHI column in this module. Under HIPAA §164.312(a)(2)(iv), ePHI at rest must be encrypted. A compromised database backup would expose this data in plaintext.

### FAIL — Daily audit chain integrity job not implemented
**Severity: HIGH**  
HIPAA 2026 and the platform rules require a daily scheduled job that verifies the audit log hash chain. No such job was found in `modules/core-platform/src/jobs/` or anywhere else. The hash chain is written correctly but never verified automatically.

### FAIL — BAA tracking not implemented
**Severity: HIGH**  
The EDI PRD (`docs/prd/prd-edi-compliance.md` §3.20) defines a BAA tracking table requirement. No implementation exists in `modules/edi-compliance/src/`. HIPAA requires BAAs with every business associate handling PHI.

### 2026 CAA Checklist

| Requirement | Status |
|---|---|
| 100% rebate pass-through tracking | NOT IMPLEMENTED — `modules/billing/src` has no rebate logic; rebate-management module is listed as Phase 4 "Not yet implemented" |
| Spread pricing prohibition reporting | NOT FOUND — no spread pricing detection in billing |
| PBM transparency reporting | NOT FOUND — no CAA-specific reporting module |

### CMS-0057-F (Prior Authorization FHIR API) Status

| Requirement | Status |
|---|---|
| FHIR R4 PA API endpoint | PARTIAL — `modules/edi-compliance/src/services/fhir_bridge.py` has X12↔FHIR translation for 278/271; `modules/edi-compliance/src/x12/generators/gen_278.py` and `parsers/parse_278.py` exist |
| HL7 Da Vinci PAS implementation guide | NOT VERIFIED — FHIR bridge maps CoverageEligibilityResponse but no PAS-specific profile conformance found |
| Prior Auth API exposed as FHIR endpoint | NOT FOUND — no dedicated FHIR REST endpoint; X12 278 wrapped in a generate/parse API |
| Real-time PA decision API | NOT FOUND |

### NCPDP / X12 Compliance

| Standard | Status |
|---|---|
| NCPDP D.0 | PARTIAL — EDI module has NCPDP batch transport but full D.0 adjudication not in edi-compliance |
| X12 835 | PASS — full generator/parser in edi-compliance |
| X12 837P/I | PASS — generators/parsers present |
| X12 270/271 | PASS — generators/parsers present |
| X12 276/277 | PASS — present |
| X12 278 | PASS — present |
| X12 999/TA1 | PASS — present |
| AS2 transport | PRESENT — `modules/edi-compliance/src/transport/as2.py` |

### SOC 2 Readiness

| Control | Status |
|---|---|
| Access control documentation | PARTIAL — code implemented, no written SOP |
| Change management | PARTIAL — git workflow documented in CLAUDE.md, no formal change management SOP |
| Monitoring/alerting | PARTIAL — slow query logging, DLQ depth monitoring described in PRD, not fully wired |
| Audit trail completeness | PASS — hash chain on audit log; PHI access decorator |

### Data Retention

| Item | Status |
|---|---|
| Retention periods defined in PRD | PASS — PDRs specify 7 years for claims (HIPAA), transactions |
| Tenant `data_retention_days` column | PASS — core baseline migration adds `data_retention_days` with default 2555 (7 years) |
| Automated purge job | PARTIAL — reporting module has `purge_expired_report_files`; no general claims purge job |
| `processed_events` table cleanup | NOT FOUND — event bus rule requires DELETE WHERE `processed_at < NOW() - INTERVAL '7 days'`; no such job found |

### Breach Notification

| Item | Status |
|---|---|
| PRD breach notification documented | PASS — `prd-core-platform.md` §P1/P2/P3 triage, 60-day notification, HHS annual report |
| Implemented breach detection/workflow | NOT FOUND — no breach notification service in codebase |
| Tabletop exercise schedule | NOT FOUND |

### Regulatory Score Breakdown
- HIPAA access control (auth): -15 (3 modules unauthenticated)
- HIPAA PHI encryption at rest: -10 (medical-claims plaintext PHI)
- HIPAA SOP docs: -10 (no SOPs beyond backup-restore)
- Daily audit chain verification job: -5
- BAA tracking not implemented: -5
- CAA rebate pass-through: -3 (Phase 4, acceptable if not yet required)

---

## Cross-Category Issue Index

| ID | Category | Severity | Finding | File(s) |
|---|---|---|---|---|
| SEC-001 | 7 | HIGH | No JWT auth on medical-claims, prescriber-directory, edi-compliance endpoints | `modules/medical-claims/src/api/routes/*.py`, `modules/prescriber-directory/src/api/dependencies.py`, `modules/edi-compliance/src/api/*.py` |
| SEC-002 | 7 | HIGH | prescriber-directory missing `install_tenant_loader` and has no `tenant_id` on model | `modules/prescriber-directory/src/db/session.py`, `modules/prescriber-directory/src/models/tables.py` |
| SEC-003 | 7 | MEDIUM | No CORS configuration on any module | All `main.py` / `app.py` files |
| SEC-004 | 7,8 | MEDIUM | `quantize()` without `rounding=ROUND_HALF_UP` in 5 locations | `modules/medical-claims/src/api/routes/analytics.py` (×4), `modules/medical-claims/src/services/denial_service.py` |
| SEC-005 | 7 | LOW | FHIR bridge serializes Decimal benefit amount as `float()` | `modules/edi-compliance/src/services/fhir_bridge.py:122` |
| DAT-001 | 8 | MEDIUM | No explicit `ondelete=` on ForeignKey columns in billing and medical-claims | `modules/billing/src/models/tables.py`, `modules/medical-claims/src/models/tables.py` |
| DAT-002 | 8 | LOW | Integer PK in drug-database reference table | `modules/drug-database/src/models/tables.py:154` |
| REG-001 | 15 | HIGH | medical-claims PHI columns (patient_member_id, diagnoses) stored as plaintext | `modules/medical-claims/src/models/tables.py` |
| REG-002 | 15 | HIGH | No HIPAA SOP documentation (access control, workforce, contingency, breach) | `docs/sops/` — only `backup-restore.md` |
| REG-003 | 15 | HIGH | Daily audit chain verification job not implemented | `modules/core-platform/src/jobs/` |
| REG-004 | 15 | HIGH | BAA tracking table not implemented | `modules/edi-compliance/src/` |
| REG-005 | 15 | MEDIUM | `processed_events` table cleanup job missing | `shared/events/` |
| REG-006 | 15 | MEDIUM | CMS-0057-F: no dedicated FHIR PA REST endpoint | `modules/edi-compliance/src/` |
| REG-007 | 15 | MEDIUM | CAA rebate pass-through not implemented | `modules/billing/src/` (Phase 4) |
