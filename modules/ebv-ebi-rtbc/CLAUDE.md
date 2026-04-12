# Module: ebv-ebi-rtbc

Separate FastAPI service. Owns its own PostgreSQL schema `ebv-ebi-rtbc`.
Communicates with other modules via API calls and event bus — no cross-schema queries.

See root CLAUDE.md for platform principles. Module PRD lives in docs/prd/ebv-ebi-rtbc.md.
