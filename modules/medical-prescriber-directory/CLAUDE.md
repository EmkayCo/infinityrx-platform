# Module: medical-prescriber-directory

Separate FastAPI service. Owns its own PostgreSQL schema `medical-prescriber-directory`.
Communicates with other modules via API calls and event bus — no cross-schema queries.

See root CLAUDE.md for platform principles. Module PRD lives in docs/prd/medical-prescriber-directory.md.
