# Module: part-d-pde

Separate FastAPI service. Owns its own PostgreSQL schema `part-d-pde`.
Communicates with other modules via API calls and event bus — no cross-schema queries.

See root CLAUDE.md for platform principles. Module PRD lives in docs/prd/part-d-pde.md.
