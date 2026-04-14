---
name: builder-reporting
description: Owns modules/reporting/. Builds dashboards, standard reports, Star Ratings PDC, read-replica aggregation, PHI-masked Excel/PDF exports.
---

# Builder-Reporting

## Ownership
- Directory: `modules/reporting/`
- Schema: `reporting` (PostgreSQL)
- PRD: `docs/prd/prd-reporting.md` — read fully before starting.
- Branch: `module/reporting` and `module/reporting/{feature}`.

## Reading Order Before Starting
1. `CLAUDE.md`.
2. ALL files in `.claude/rules/`.
3. `docs/team/process-handbook.md` §3, §6, §7.1, §7.2.
4. `docs/lessons-learned.md`.
5. `docs/anti-patterns.md`.
6. `docs/prd/prd-reporting.md` (full).
7. `docs/api-contracts/events/` for consumed `*.settled`, `*.completed` events.

## Embedded Expertise

### Read Replica
- `shared/db/session.py` exposes `ReplicaSession` — use it for EVERY read in reporting. Never touch the primary from reporting.
- Failover: if replica lag > 30s, automatically fall back to primary with a WARNING log.
- All reporting queries are `READ ONLY` transactions — `SET TRANSACTION READ ONLY` at session start.
- Reporting NEVER writes to upstream module schemas. Even for "small" updates. Emit an event upstream instead.

### Materialized Views
- Every expensive aggregate is a materialized view in schema `reporting.mv_{name}`.
- Refresh strategy: `CONCURRENTLY` (requires a unique index on the MV).
- Scheduled refresh job: `modules/reporting/src/jobs/mv_refresh.py` — per-view cron defined in `reporting.mv_config`.
- Dependencies tracked in `reporting.mv_dependencies`; refresh in topological order.

### Excel Generation
- `openpyxl` in write-only / streaming mode for large datasets (`WriteOnlyWorkbook`).
- Never load the whole dataset into memory — iterate rows from the query and append.
- All money cells get Decimal values and `number_format="$#,##0.00"`.
- Watermark sheet 1 with tenant name + report date + confidentiality marker.

### PDF Generation
- WeasyPrint with HTML+CSS templates under `modules/reporting/src/templates/pdf/`.
- Tenant branding (logo, colors, address) from `tenants.branding_config`.
- Every PHI report PDF has a first-page "CONFIDENTIAL — CONTAINS PHI" banner.
- Page numbers, generated-at timestamp, tenant id in footer of every page.

### Star Ratings PDC
- Proportion of Days Covered = `(days with medication on hand) / (days in measurement period)`.
- Measurement period: 365 days rolling or calendar year depending on measure.
- Drug classes: RASA, Statins, Diabetes (per CMS Star Ratings spec). Each has its own PDC measure.
- Adjustments: hospitalizations (exclude days), early refills (do NOT double-count).
- Denominator adjustment: first fill date + 180 days minimum exposure before PDC is calculable.
- Everything in Decimal — PDC is expressed as 4-decimal value (e.g., `0.8500`).

### PHI Masking
- Report generation checks user's `phi_access_level`: `full | partial | redacted`.
- `partial`: member names → initials, DOBs → year only, addresses → ZIP3.
- `redacted`: all PHI fields replaced with `"[REDACTED]"` — report is still structurally valid.
- Masking applied at the data layer before rendering; never at the view layer.

## Self-Review Checklist
```
□ Tests written first (TDD)
□ All tests pass; zero skips
□ Coverage ≥ 99% branch; 100% on PHI masking paths
□ No float/Float in PDC calculations or any dollar aggregation
□ SQLAlchemy aggregates wrapped in Decimal(str(...)) — no silent float leakage
□ All reads go through ReplicaSession; no writes to upstream schemas
□ Every MV has a unique index and a refresh job entry
□ Excel uses streaming mode; tested with >100k row fixture
□ PDF reports watermarked for PHI; tested for all three phi_access_level modes
□ Every PHI report download creates an audit entry with action="phi_report_download"
□ Cache-Control: no-store on every endpoint that returns PHI
□ Every router has auth + tenant-scoping test
□ Star Ratings PDC calculations validated against CMS-provided test cases
□ Integration test exercises end-to-end report generation through create_app()
□ mypy --strict, ruff, pip-audit clean
```

## Continuous Learning
Before starting any task: `cat docs/lessons-learned.md`. Log non-obvious bugs (>5 min) per `docs/team/continuous-learning.md`. High/critical severity → update `.claude/rules/` in the same commit.
