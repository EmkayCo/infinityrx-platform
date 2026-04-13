# InfinityRx Enterprise Platform

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
Main branch protected. Module branches: module/{name}. Feature branches: module/{name}/{feature}.
Worktrees for parallel agents. Integration Coordinator merges at gates.

## References
docs/glossary.md | docs/negative-constraints.md | docs/api-contracts/ | docs/prd/

## Continuous Learning
Before starting any task, read `docs/lessons-learned.md` for recent discoveries.
When you hit a non-obvious bug (>5 min to debug), add a LESSON entry per `docs/team/continuous-learning.md`.
Critical/high severity lessons MUST update the relevant `.claude/rules/` file in the same commit.
Never silently fix a bug — always document what you learned.

## Auto-Gate
All tests pass 100% AND coverage meets thresholds (100% financial/PHI/security, 95% all other active code) AND no dead code/stub files → proceed automatically.
Core active modules below 95%, OR financial/PHI paths below 100%, OR dead code found → STOP, fix before proceeding.
Any test failure → STOP, fix before proceeding.
