# Module: rules-engine

Separate FastAPI service. Owns its own PostgreSQL schema `rules-engine`.
Communicates with other modules via API calls and event bus — no cross-schema queries.

See root CLAUDE.md for platform principles. Module PRD lives in docs/prd/rules-engine.md.
