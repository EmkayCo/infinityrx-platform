# ADR-001: Monorepo layout with per-module FastAPI services

**Status:** Accepted
**Date:** 2026-04-13
**Deciders:** Platform architecture
**Context:** InfinityRx must ship roughly 24 PBM modules (claims
adjudication, billing, payment processing, reporting, FWA detection,
etc.). Each module has its own domain model, its own team, its own
deployment cadence, and its own regulatory surface area.

## Decision

Use a single Git repository with a top-level `modules/` directory where
each module is a standalone FastAPI service with its own PostgreSQL
schema, Pydantic schemas, Alembic migration history, and test suite.
Shared code lives under `shared/`, cross-cutting documentation under
`docs/`, and infrastructure under `infrastructure/`.

Modules MAY import from `shared/` but MUST NOT import from another
`modules/<name>/` directory. Cross-module communication is via HTTP
(for synchronous read/write) or the event bus (for asynchronous
notifications).

## Alternatives considered

1. **Polyrepo (one git repo per module).** Rejected: cross-module
   refactors — especially `shared/` migrations and event-schema changes
   — become multi-PR choreography across a dozen repos, each with its
   own CI and review queue. The platform team is too small for this to
   work without ceremony overhead eating most of the velocity.
2. **Single monolith (one FastAPI app).** Rejected: the regulatory
   surface of each module is different — FWA detection sees claim PHI,
   reporting sees aggregated star-ratings data, billing sees prefund
   balances. Co-locating them in one process breaks the principle that
   a breach in one domain can't reach another domain's data.
3. **Monorepo with Nx/Bazel.** Rejected: Python's tooling story for
   these is immature, and `uv` + `pyproject.toml` per module satisfies
   the incremental-build requirement without a heavy dependency.

## Consequences

**Positive:**
- One `uv sync` resolves the full dev dependency tree.
- Shared primitives (auth, audit, events) refactor in a single PR.
- Test suite runs across the whole platform; regressions in module A
  that affect module B's consumers are visible immediately.
- `docs/lessons-learned.md` and `.claude/rules/` apply to all modules
  uniformly.

**Negative:**
- `git log` is noisy — filter by path when browsing a single module's
  history.
- A bad commit in `shared/` can break every module at once. Mitigate
  with strict type checks + integration tests in CI before merging to
  main.
- Module boundaries require discipline: nothing in CI enforces "no
  cross-module imports" today. Follow-up task: add a ruff custom rule
  forbidding `from modules.X import …` outside `modules/X/`.

## Cross-references

- `CLAUDE.md` principle #7: "Each module is a separate FastAPI service
  with its own API and schema."
- `docs/team/process-handbook.md` §2 for the directory layout
  convention.
