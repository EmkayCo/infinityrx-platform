# Teammate 4 "docs-cleanup" — Session Notes

**Date:** 2026-04-14
**Branch:** main (worktree agent-a3a755f5)

## Work Completed

### GROUP 1 — CLAUDE.md status table fix (CR-13)
- Verified actual module state by counting .py files (26–90 per built module)
- 8 modules marked "Not yet implemented" were actually fully built
- Rewrote status table with Module | Phase | Status | Notes columns
- Added "Session Remediation (2026-04-14)" section
- Also added LESSON-007 to CRITICAL LESSONS section (was missing)
- Commit: f00d3fc

### GROUP 2 — Cleanup (L-01, L-02, M-12, M-14, M-21)
- coverage.json → .gitignore
- tier3-situational/ is empty and untracked by git (rmdir requires bash permission — noted)
- ruff --fix --select F401: 412 unused imports fixed (1 remaining — unfixable import alias)
- Pinned Docker: postgres:17.5, redis:7.4.3, rabbitmq:4.0-management, python:3.13.13-slim
- Consolidated pyproject.toml [dev] sections; added aiosqlite>=0.20; numpy >=2.0
- Deleted 12 one-line stub README files from unimplemented Phase 3/4 modules
- Commit: b2e195b

### GROUP 3 — Module READMEs (M-10)
- Created README.md for: billing, payment-processing, reclaimrx, reporting
- Each includes: purpose, dependencies, test commands, API endpoints, events produced/consumed
- Noted known audit gaps inline (CR-01, CR-07, CR-11, H-02, M-17)
- Commit: 5747c3b

### GROUP 4 — Event catalog (H-04)
- Renamed 24 snake_case files to dot-notation via git mv
- Created 55 new event contract files covering all published event types found in codebase
- Total catalog: 98 contracts
- Commit: c52cffe

### GROUP 5 — HIPAA SOPs (H-06)
- Created docs/compliance/ with 5 SOPs
- Each ≥ 100 lines, cites HIPAA sections, has Review Date: 2026-04-14
- Commit: 699e29a

### GROUP 6 — ADRs
- ADR-004: Async session strategy (LESSON-001/007/008 integration)
- ADR-005: Dual-mode event bus (RabbitMQ / InMemory / Azure migration path)
- ADR-006: AES-256-GCM encryption provider pattern with Key Vault plan
- Commit: 9f05594

### GROUP 7 — ERD (M-11)
- erd.mermaid: full entity relationship diagram (core/billing/member/medical_claims)
- erd.md: narrative descriptions, cross-module data flow, audit CR-02 callout
- Commit: eb9b537

### GROUP 8 — CHANGELOG (M-17-ish)
- docs/CHANGELOG.md in keep-a-changelog format
- 5 releases grouped from git log
- Commit: e9cfa23

### GROUP 9 — Teammate notes integration
- Processed teammate1-notes.md and teammate3-notes.md
- Created LESSON-009 (AuditMiddleware injectable args)
- Created LESSON-010 (NPI vs PHI encryption decision)
- Created LESSON-011 (global reference tables vs tenant-owned data)
- No teammate2-notes.md found in _scratch/
- Commit: bfd712c

### GROUP 10 — .env.example env vars
- Added BILLING_DATABASE_URL, DRUG_DB_DATABASE_URL, PRESCRIBER_DB_URL
- Commented with audit H-05 reference
- Commit: ca5eb4e

## Discoveries / Decisions

1. **tier3-situational/ deletion blocked**: rmdir requires bash permission via
   the new shell permission model. Directory is empty and untracked by git so
   there's no cleanup risk; it just can't be deleted without bash access.

2. **1 ruff fix unfixable**: `src.api.compliance.get_session` import in
   edi-compliance test at line 92 is used indirectly via `app.dependency_overrides`
   pattern — ruff F401 can't auto-fix because it's inside a try/except block.

3. **55 new event contracts (vs 29 cited in audit)**: The audit cited 29
   undocumented events. Walking all publishers found 55 additional events
   beyond the 42 that already had (snake_case) contracts.

4. **member.enrolled.md already existed (dot-notation)**: One of the pharmacy/
   prescriber/member contracts was already created in dot-notation before this
   session (visible in git status). No conflict — those were staged alongside
   the renamed files.

5. **prescriber-directory: no TenantScopedMixin on Prescriber is CORRECT**:
   Confirmed with teammate1-notes.md — NPI is a global reference table.
   Documented as LESSON-011.
