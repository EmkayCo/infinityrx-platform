# Testing Rules (Mandatory — All Modules)

## Coverage Requirements
- 100% test coverage on ALL financial logic (calculations, Decimal operations, fee splits, payment amounts, ledger entries)
- 100% test coverage on ALL PHI paths (masking, access logging, tenant isolation, encryption)
- 100% test coverage on ALL security paths (auth, authorization, input validation)
- 95% test coverage on all other active code
- Coverage measured ONLY on modules with actual implementation
- Exclude unimplemented modules from coverage config (pyproject.toml)
- Reported coverage must reflect reality — no inflated numbers from empty files

## Test Execution Rules
- Every test must pass — zero failures, zero skips, zero expected failures
- Tests run BEFORE marking any task complete
- If any test fails, fix it before moving to the next task
- Integration tests run after all teammates merge
- No task is done until tests prove it works with real/sample data

## Dead Code / Stub File Scanner
At every gate review, verify:
- No empty placeholder files for modules not in the current phase
- No pass-only or NotImplementedError-only files
- No commented-out code blocks
- No TODO/FIXME without a linked task in tasks/todo.md
- If a module isn't being built this phase, its files should not exist (only the folder structure)

Delete any empty stub/placeholder files that exist now.
