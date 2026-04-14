# Changelog

All notable changes to the InfinityRx Enterprise Platform are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

## [0.5.0] — 2026-04-14 — Audit Remediation Session

Four-teammate parallel audit remediation session following the full platform
audit scored at 63/100. Addresses 13 critical findings, 8 high findings,
and 10 medium/low findings from `docs/audit/full-platform-audit-2026-04-14.md`.

### Added

- `docs/compliance/` — 5 HIPAA Security Rule SOPs (H-06): access control,
  workforce training, contingency plan, breach notification, device/media controls
- `docs/adr/ADR-004` — Async-first SQLAlchemy session strategy (LESSON-001/007/008)
- `docs/adr/ADR-005` — Dual-mode event bus (RabbitMQ / InMemoryEventBus / Azure)
- `docs/adr/ADR-006` — AES-256-GCM encryption provider pattern with Key Vault plan
- `docs/architecture/erd.mermaid` + `erd.md` — Entity Relationship Diagram for
  core/billing/member/medical_claims schemas (M-11)
- `docs/CHANGELOG.md` — This file (keep-a-changelog format)
- 55 new event contract docs in `docs/api-contracts/events/` (H-04)
- `modules/billing/README.md`, `modules/payment-processing/README.md`,
  `modules/reclaimrx/README.md`, `modules/reporting/README.md` (M-10)
- `aiosqlite>=0.20` to `[dependency-groups] dev` in `pyproject.toml` (H-15 prereq)

### Changed

- `CLAUDE.md` — Status table corrected: 8 built modules were marked "Not yet
  implemented" (CR-13). Added Session Remediation 2026-04-14 section.
- `docs/api-contracts/events/` — Renamed 24 snake_case filenames to ADR-003
  dot-notation (H-04): `claim_adjudicated.md` → `claim.adjudicated.md`, etc.
- `docker-compose.yml` — Pinned Docker image tags: `postgres:17.5`,
  `redis:7.4.3`, `rabbitmq:4.0-management` (M-21)
- `modules/core-platform/Dockerfile` — Pinned to `python:3.13.13-slim` (M-21)
- `pyproject.toml` — Consolidated duplicate `[dev]` sections into
  `[dependency-groups] dev` (L-06); tightened `numpy` to `>=2.0` (L-05)
- `shared/middleware/` — Moved `rate_limiter.py` and `security_headers.py`
  from 5 duplicate locations to canonical `shared/middleware/` (M-02)
- All billing, reclaimrx, payment-processing, drug-database, prescriber-directory
  routes converted from sync `def` to `async def` (CR-05)

### Fixed

- `modules/core-platform/src/main.py` — Mount `AuditMiddleware` and
  `TenantIsolationMiddleware` in `create_app()` (CR-04, LESSON-006 regression)
- `modules/billing/src/main.py`, `modules/reclaimrx/src/`, et al. — Add
  `create_app()` factory with full middleware stack to all 4 Phase 2 modules (CR-07)
- `modules/edi-compliance/src/main.py` — Remove silent-noop middleware `try/except`;
  import from `shared/middleware` (CR-08)
- `modules/medical-claims/src/models/tables.py` — Encrypt PHI columns
  (`patient_member_id`, diagnosis codes) with `EncryptedString` AES-256-GCM (CR-02)
- `modules/drug-database/src/api/router.py` — Health endpoint now performs
  real DB dependency check (H-13)
- Billing models — Add `version_id_col` optimistic locking and explicit
  `ondelete=` on all ForeignKeys (H-12, M-07)

### Security

- HIPAA §164.312(a)(2)(iv): medical-claims PHI now encrypted at rest (CR-02)
- `AuditMiddleware` now active on core-platform production path (CR-04)
- `TenantIsolationMiddleware` now active on core-platform production path (CR-04)

### Removed

- 412 unused imports fixed via `ruff --fix --select F401` (M-12)
- 12 one-line stub `README.md` files from unimplemented Phase 3/4 modules
- Duplicate `[project.optional-dependencies] dev` section from `pyproject.toml`
- `coverage.json` added to `.gitignore` (L-01)

---

## [0.4.0] — 2026-04-14 — EDI Compliance Sessions 1–4

Full X12 EDI compliance module implementation across 4 build sessions.

### Added

- X12 engine with 4-level validation (syntax, semantic, HIPAA, business rules)
- 835 remittance advice generator and parser
- 837P/I/D claim generators (professional, institutional, dental)
- 270/271 eligibility inquiry/response
- 276/277 claim status request/response
- 278 prior authorization request/response
- 275 clinical attachments
- 834 benefit enrollment
- 999/TA1 functional acknowledgment
- FHIR R4 bridge for FHIR → X12 translation
- NCPDP Batch 1.2 processor
- AS2 + SFTP transport layer
- Clearinghouse adapter abstractions
- Certificate lifecycle management
- SLA monitoring
- Auto-posting (835 → billing reconciliation)
- Denial ML scoring

---

## [0.3.0] — 2026-04-13 — Medical Claims, Member Management, Drug Database

### Added

- `modules/medical-claims/` — Full CMS-1500/UB-04 claim pipeline, accumulator
  integration, NLP auto-coding stub, analytics endpoints
- `modules/member-management/` — 834/CSV ingestion, accumulator persistence,
  benefit phase tracking, 270/271 eligibility, merge workflow
- `modules/drug-database/` — NDC/pricing/interactions, compound ingredients,
  drug refresh jobs
- `docs/prd/prd-medical-claims.md`, `prd-member-management.md`, `prd-drug-database.md`

---

## [0.2.0] — 2026-04-13 — Phase 3 Modules

### Added

- `modules/pharmacy-directory/` — Lookup, credentialing, PSAO, NCPDP parser,
  NPPES integration, event-driven updates
- `modules/prescriber-directory/` — NPPES, state prescribing rules, DEA tracking,
  taxonomy service
- `modules/dataiq/` — Analytics dashboards, anomaly detection, forecast API,
  benchmark tracking
- `modules/ai-nlp/` — RAG pipeline, document extraction, guardrails, NLP
  classification
- `docs/adr/ADR-003-event-naming.md` — dot-notation event type standard
- `docs/adr/ADR-002-shim-pattern.md` — `_shim/` transitional pattern

---

## [0.1.0] — 2026-04-13 — Platform Foundation + Phase 2 Modules

### Added

- `modules/core-platform/` — Auth (JWT + MFA/TOTP/FIDO2), audit hash chain,
  tenant management, sessions, API keys, DLQ, rate limiting, security headers
- `modules/billing/` — AP/AR, payment batches, NACHA, invoice, journal (hash-chained),
  fee engine, program budgets
- `modules/payment-processing/` — Vendor adapters, NACHA generator, ACH returns
  (80+ codes), OFAC screening, positive pay, reconciliation
- `modules/reclaimrx/` — FWA detection rules, XGBoost ML scoring, graph analysis,
  investigation workflow, recovery estimation
- `modules/reporting/` — Report builder, dashboards, Star Ratings PDC, regulatory
  submissions, actuarial models
- `shared/` — EventEnvelope, EventBus ABC, DLQ, idempotency store, TenantScopedMixin,
  EncryptedString, PHIMixin, penny_allocate, hash chain, CircuitBreaker
- `docs/adr/ADR-001-monorepo-layout.md` — Module layout decision
- `docs/glossary.md`, `docs/anti-patterns.md`, `docs/negative-constraints.md`
- Infrastructure: `docker-compose.yml`, `infrastructure/scripts/backup.sh`,
  `infrastructure/scripts/restore.sh`
- Build system: 11 rules files, 17 agent files, CLAUDE.md

### Security

- LESSON-001: SQLite SAVEPOINT test isolation
- LESSON-004: `re.match` trailing newline bypass — use `\A...\Z` or `re.fullmatch`
- LESSON-005: `logger.extra={"module":...}` collides with LogRecord builtins
- LESSON-006: Security primitives mounted (AUDIT FINDING)
- LESSON-007: PG_UUID float bug under SQLite SAVEPOINT sessions
- LESSON-008: async/sync boundary break with StaticPool SAVEPOINT listener

---

[Unreleased]: https://github.com/infinityrx/infinityrx-platform/compare/main...HEAD
[0.5.0]: https://github.com/infinityrx/infinityrx-platform/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/infinityrx/infinityrx-platform/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/infinityrx/infinityrx-platform/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/infinityrx/infinityrx-platform/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/infinityrx/infinityrx-platform/releases/tag/v0.1.0
