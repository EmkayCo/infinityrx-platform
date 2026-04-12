# Module: mtm-clinical

Separate FastAPI service. Owns its own PostgreSQL schema `mtm-clinical`.
Communicates with other modules via API calls and event bus — no cross-schema queries.

See root CLAUDE.md for platform principles. Module PRD lives in docs/prd/mtm-clinical.md.
