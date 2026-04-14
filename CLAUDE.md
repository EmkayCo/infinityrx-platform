# InfinityRx Enterprise Platform

## CRITICAL LESSONS LEARNED
- **LESSON-001:** SQLAlchemy test sessions need SAVEPOINT-based rollback, not TRUNCATE. Use the nested transaction fixture pattern in `.claude/rules/testing.md`.
- **LESSON-004:** `re.match(r"^\d{6}$")` accepts trailing newlines. Use `\A...\Z` anchors or `re.fullmatch()` for ALL security-sensitive regex validation.
- **LESSON-005:** `logger.extra={"module": ...}` collides with `LogRecord.module` built-in attribute. Use service/subsystem-prefixed keys instead.
- **AUDIT FINDING:** Built primitives must be MOUNTED on production apps — hash chain, MFA gate, security headers, rate limiter all existed but were never wired into live request paths. Every middleware/router primitive needs an integration test through `create_app()`.

## Rules Files
All builders MUST read these rules files before starting work:
- `.claude/rules/security.md`
- `.claude/rules/financial-precision.md`
- `.claude/rules/phi-compliance.md`
- `.claude/rules/tenant-isolation.md`
- `.claude/rules/event-bus.md`
- `.claude/rules/hipaa-2026.md`
- `.claude/rules/architecture.md`
- `.claude/rules/performance.md`
- `.claude/rules/code-standards.md`
- `.claude/rules/error-handling.md`
- `.claude/rules/testing.md`

## Agent Files
Builder agents are in `.claude/agents/build-agents/`. Each builder reads their agent file + all rules files + their module's PRD before starting work.
QA sweep agents are in `.claude/agents/tier1-core/` and MUST run at the end of every build session touching their scope.
Domain specialists are in `.claude/agents/tier2-specialists/` and are called on-demand as subagents when their triggers fire.

## Project Status

| Module | Phase | Status |
|---|---|---|
| core-platform | 1 | Implemented (auth, MFA, audit, tenants, sessions, API keys, DLQ, middleware) |
| billing | 2 | In progress (AP/AR, journal hash chain, NACHA, 835, state compliance) |
| payment-processing | 2 | In progress (vendor adapters, ACH returns, OFAC, business-day calendar) |
| reclaimrx | 2 | In progress (FWA detection, ML scoring, graph analysis, recovery estimation) |
| reporting | 2 | In progress (dashboards, Star Ratings PDC, Excel/PDF exports) |
| ai-nlp | 3 | Not yet implemented |
| dataiq | 3 | Not yet implemented |
| drug-database | 3 | Not yet implemented |
| member-management | 3 | Not yet implemented |
| pharmacy-directory | 3 | Not yet implemented |
| prescriber-directory | 3 | Not yet implemented |
| medical-prescriber-directory | 3 | Not yet implemented |
| adjudication-engine | 4 | Not yet implemented |
| edi-compliance | 4 | Not yet implemented |
| medical-claims | 4 | Not yet implemented |
| mtm-clinical | 4 | Not yet implemented |
| part-d-pde | 4 | Not yet implemented |
| plan-design | 4 | Not yet implemented |
| prior-authorization | 4 | Not yet implemented |
| program-config | 4 | Not yet implemented |
| rebate-management | 4 | Not yet implemented |
| rules-engine | 4 | Not yet implemented |
| switch-connectivity | 4 | Not yet implemented |
| testing-simulator | 4 | Not yet implemented |
| ebv-ebi-rtbc | 4 | Not yet implemented |

## System
Multi-module PBM ecosystem. Multi-tenant, API-first. Build local, deploy to Azure.
100M+ claims/year capacity. Tens of billions of dollars. Zero error tolerance.
ZERO reference to any third-party PBM vendor anywhere in code, docs, or comments.

## Principles
1. Decimal with ROUND_HALF_UP for all money. No floats. Ever.
2. Cannot lose data on crash. Transaction boundaries everywhere.
3. No silent failures. Structured error responses.
4. All actions auditable (who/what/when/where/before/after).
5. All outputs reproducible. Deterministic on identical inputs.
6. YAGNI. Minimum code to satisfy the requirement.
7. Each module is a separate FastAPI service with its own API and schema.
8. Modules communicate via API calls and event bus messages. No direct DB access between modules.
9. Full NCPDP D.0 standard. Build for the standard, not current files.
10. Every screen is operable by a non-technical user.
11. TDD is non-negotiable for all core business logic.
12. Configuration over code. If adding a client requires code changes, architecture is wrong.
13. Fully built with best-practice defaults, then configurable per tenant.

## Tech Stack
Backend: Python 3.13 + FastAPI | Frontend: Next.js 16.2 + React 19.2 + TypeScript + Tailwind + shadcn/ui
Database: PostgreSQL 17 + Redis 7.4 | Events: RabbitMQ (local) / Azure Service Bus (prod)
AI: Azure OpenAI (GPT-4.1), scikit-learn, XGBoost | Infra: Docker, Terraform, AKS

## Database Rules
Each module owns its own PostgreSQL schema. Migrations namespaced per module.
Shared schema (auth, audit, tenants) owned by core-platform, locked after Phase 1.
No cross-schema direct queries. Use API calls between modules.

## Git Strategy
Main branch protected. Module branches: `module/{name}`. Feature branches: `module/{name}/{feature}`.
Worktrees for parallel agents. Integration Coordinator merges at gates.

## References
`docs/glossary.md` | `docs/negative-constraints.md` | `docs/api-contracts/` | `docs/prd/` | `docs/anti-patterns.md`

## Continuous Learning
Before starting any task, read `docs/lessons-learned.md` for recent discoveries.
When you hit a non-obvious bug (>5 min to debug), add a LESSON entry per `docs/team/continuous-learning.md`.
Critical/high severity lessons MUST update the relevant `.claude/rules/` file in the same commit.
Never silently fix a bug — always document what you learned.

## Auto-Gate
All tests pass 100% AND coverage meets thresholds (100% on financial, PHI, security, and auth paths; 99% branch coverage on all other active code) AND no dead code/stub files → proceed automatically.
Any active code below 99% branch coverage, OR financial/PHI/security/auth paths below 100%, OR dead code found → STOP, fix before proceeding.
Any test failure → STOP, fix before proceeding.
