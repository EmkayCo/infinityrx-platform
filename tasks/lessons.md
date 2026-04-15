# Lessons Log

Operational + collaboration lessons for the InfinityRx platform. Distinct
from `docs/lessons-learned.md` — that file holds module-level engineering
lessons (LESSON-001 through LESSON-011, etc.). This file holds team /
process / infrastructure lessons.

---

## Lesson: Environment Architecture Established
What happened: Partial rollback lost multi-DB scripts during stash/merge collision.
Root cause: No clear environment separation before parallel agent work started. Files created ad-hoc without being committed and protected.
Rule: All infrastructure changes (docker-compose, init scripts, env files, config.py) must be committed IMMEDIATELY after creation — before any other work happens. Environment scripts are foundational — they go in first, get committed, and are never modified by feature branch agents.
Date: 2026-04-15

## Lesson: Branch Discipline
What happened: Phase 1B feature branches merged directly to main, causing 5-way merge conflicts.
Root cause: No integration branch (develop) to absorb merges incrementally.
Rule: Feature branches ALWAYS merge to develop. Never to main. Main only gets updated by merging develop after tests pass. Sequential merges to develop (not batch merges) prevent conflict accumulation.
Date: 2026-04-15

## Lesson: Shared File Ownership
What happened: vitest.config.ts, mock-data/handlers.ts, and node_modules symlinks conflicted across 5 agent worktrees.
Root cause: No ownership rules for shared files during parallel work.
Rule: Shared files (vitest.config.ts, docker-compose.yml, shared/config.py, portal/shared/*) get ONE owner per phase. Other agents document their needs in tasks/shared-file-requests.md. Owner consolidates. Each worktree runs its own npm install — no symlinks to other worktrees.
Date: 2026-04-15
