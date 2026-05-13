# InfinityRx — Windows Dev Setup Runbook

**Audience:** developers running InfinityRx locally on Windows (Git Bash + PowerShell).
**Origin:** captured during the B10.1 floor-up environment audit (2026-05-12) after a
Mac → Windows migration produced "can't launch app + all these errors." Every step
below was verified end-to-end on Windows 11 Pro (build 26200) with Git Bash 2.54
and PowerShell 5.1. Mac/Linux equivalents are noted inline.

---

## 0. Prerequisites

Install these BEFORE cloning. Versions are minimums — newer is fine.

| Tool | Minimum | Verify |
|---|---|---|
| **Node.js** | 18.18 (Next.js 16 requires this) | `node --version` |
| **npm** | 11+ | `npm --version` |
| **uv** (Python package manager) | 0.11+ | `uv --version` — install via `pip install --user uv` or `winget install Astral.UV` |
| **Python** | 3.13 (managed BY uv, not system) | `py -V:Astral/CPython3.13.13 --version` |
| **Git for Windows** | 2.54+ | `git --version` |
| **Docker Desktop** | latest | `docker --version` |
| **PostgreSQL 17 client** (optional, for psql) | 17 | `psql --version` |

**System Python is NOT used.** `uv sync` (Step 2) provisions Python 3.13 via Astral
into `.venv/Scripts/python.exe`. Don't try to use `python` on PATH — that's typically
3.11 or 3.14 on this Windows machine and the project requires `>=3.13,<3.14`.

## 1. Clone + initial config

```bash
git clone <your-fork-or-remote> infinityrx-platform
cd infinityrx-platform
```

**Critical Windows git config** (one-time, repo-local):

```bash
# Prevents phantom "M" entries for shell scripts that flip 100755 -> 100644
# because Windows filesystems don't track Unix execute bits. Without this,
# every infrastructure/scripts/*.sh shows as modified on every git status.
git config core.fileMode false

# Prevents msys-style automatic path conversion when passing `/foo/bar`
# strings to native Windows tools — important for many CLI args.
# (Set per-command via MSYS_NO_PATHCONV=1 when needed; setting globally
# breaks some Git Bash workflows. Leave at default unless you understand.)
```

## 2. Python environment + dependencies

```bash
# From repo root:
uv sync
```

This:
- Creates `.venv/` if absent (Python 3.13.13 via Astral)
- Installs the ~103 packages in `uv.lock`
- **Does NOT install pip into the venv** — uv replaces pip. Don't run
  `.venv/Scripts/python.exe -m pip ...`; use `uv run python ...` or
  `uv pip install ...` instead.

**Verify:**

```bash
uv pip list | wc -l       # Should be ~104 (one per dep + the project itself)
uv run python --version   # Should be Python 3.13.13
```

## 3. Start Docker services

PostgreSQL + Redis + RabbitMQ are dockerized. From repo root:

```bash
# Start Docker Desktop FIRST (GUI app — must be running before this works).
# PowerShell helper to launch it programmatically + wait for ready:
#   & "C:\Program Files\Docker\Docker\Docker Desktop.exe"; while (!(docker info 2>$null)) { Start-Sleep 1 }

docker compose up -d
```

First run pulls images (~115MB for postgres:17.5 + ~30MB for redis + ~80MB
for rabbitmq:4.0-management). Subsequent runs start in ~5-10 seconds.

**Verify:**

```bash
docker compose ps
# All 3 should be "Up X seconds (healthy)"

# Sanity checks:
docker exec infinityrx-postgres pg_isready -U infinityrx   # Should print: accepting connections
docker exec infinityrx-redis redis-cli ping                # Should print: PONG
# RabbitMQ management UI at http://localhost:15672 (infinityrx / infinityrx_dev)
```

## 4. Run database migrations

```bash
bash infrastructure/scripts/run_migrations.sh dev
```

This migrates all 6 backend modules (core-platform, drug-database,
pharmacy-directory, prescriber-directory, billing, payment-processing)
against `infinityrx_dev`. Takes ~20-40 seconds first time.

**Note** for fresh clones on Mac/Linux: the script auto-detects venv layout
(`.venv/bin/` on POSIX, `.venv/Scripts/` on Windows) — no manual config needed.

**Benign warning** you'll see during migration:

```
WARNING:  database "infinityrx_dev" has a collation version mismatch
DETAIL:  The database was created using collation version 2.36, ...
```

This means the postgres container is newer than when it was first created on
your previous machine. Run `ALTER DATABASE infinityrx_dev REFRESH COLLATION
VERSION` once if you want to silence it. Not blocking.

## 5. Launch backend modules

Backend modules use **a non-trivial PYTHONPATH formula** because each module's
`src/` package uses both relative AND absolute imports. There is no top-level
launcher script today — each module launches independently. This is documented
limitation; future work to add a unified launcher.

**Formula:** three paths on PYTHONPATH — repo root (for `shared.*`), module
root (for `src.*`), and module's `src/` (for absolute sibling imports like
`from infrastructure.tenant_middleware import ...`).

### Generic launch template

```bash
cd modules/<MODULE_NAME>

# Env (use values from .env.dev or your local override)
export INFINITYRX_ENV=development
export DATABASE_URL='postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev'
export DATABASE_URL_SYNC='postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev'
export REDIS_URL='redis://localhost:6379/1'
export RABBITMQ_URL='amqp://infinityrx:infinityrx_bootstrap@localhost:5672/'
export ENCRYPTION_KEY_ACTIVE='ifx-dev-encryption-key-32chars!!'

# PYTHONPATH (Windows uses ; as separator; Mac/Linux uses :)
REPO="$(git rev-parse --show-toplevel)"          # absolute path to repo root
export PYTHONPATH="$REPO;$REPO/modules/<MODULE_NAME>;$REPO/modules/<MODULE_NAME>/src"

# Launch via uv (project flag points at root pyproject.toml)
uv run --project ../.. uvicorn src.main:app --host 127.0.0.1 --port <PORT>
```

### Verified ports

| Module | Port | Health endpoint |
|---|---|---|
| `core-platform` | 8001 | `GET /health` → `{"status":"ok","version":"0.1.0",...}` |
| `adjudication-engine` | 8000 | `GET /health` → `{"status":"healthy","module":"adjudication-engine"}` |
| `billing` | 8002 | (verify per module) |
| `payment-processing` | 8003 | (verify per module) |
| `drug-database` | 8004 | (verify per module) |
| `ai-nlp` | 8005 | (verify per module) |
| `dataiq` | 8006 | (verify per module) |
| `reclaimrx` | 8007 | (verify per module) |
| `reporting` | 8008 | (verify per module) |
| `medical-claims` | 8009 | (verify per module) |
| `member-management` | 8010 | (verify per module) |
| `pharmacy-directory` | 8011 | (verify per module) |
| `prescriber-directory` | 8012 | (verify per module) |
| `edi-compliance` | 8013 | (verify per module) |

Port assignments are conventional, not enforced. Update this table when changes are made.

### Quick smoke (adj-engine on :8000)

```bash
curl -s http://127.0.0.1:8000/health
# {"status":"healthy","module":"adjudication-engine"}

curl -s http://127.0.0.1:8000/openapi.json | python -c "import json,sys; print(len(json.load(sys.stdin).get('paths',{})), 'paths mounted')"
# 8 paths mounted
```

## 6. Launch portal

```bash
cd portal/operator
npm install           # First time only
npm run build         # Production build (~44s)
npm run start         # Boots in ~7s on :3000
```

**Mock mode vs real-backend mode.** The portal defaults to `NEXT_PUBLIC_USE_MOCK_DATA=true`
in `.env.local`. This routes every API call through a mock layer (`portal/shared/lib/mock-data/`)
so the portal works without ANY backend running. To use the real backend instead:

1. Set `NEXT_PUBLIC_USE_MOCK_DATA=false` in `.env.local`.
2. Ensure ALL relevant backend modules are running (currently 14 modules per Step 5).
3. Restart `npm run start`.

For day-to-day frontend dev, mock mode is faster. For integration testing, real-backend.

**B10 test-mode auth bypass.** For automated capture/QA against `next start`
(production mode), the `b10-test` NextAuth Credentials provider accepts a token
from `.env.local`. See `B10/auth-env.md` and `portal/shared/lib/auth-b10-test-bypass.ts`.

## 7. Common Windows pitfalls

### Output buffering on `npm run X` when piped

**Symptom:** `npm run start` appears to hang silently when piped through `head`/`tee`/`grep`.

**Cause:** Git Bash + cmd.exe + npm wrap each child stdout in a buffered pipe. The
buffer doesn't flush until ~4-64KB of output accumulate. `next start` produces only
~3KB before reaching "Ready," so the buffer never fills and observer sees silence.

**Workaround:** Run `npm run start` plainly in a terminal you watch. Don't pipe it.
If you need a log file, use `> file.log` redirection (no upstream interpretation).

### pCloud `[conflicted]` shadow files

**Symptom:** Files with names like `script [conflicted].sh` appearing throughout the
tree. May contain real lost work from another machine.

**Cause:** pCloud (or any sync provider with conflict resolution) creates parallel
copies when it can't decide which version is authoritative. Common after migration.

**Workaround:** Run `find . -name "*[conflicted*" -not -path "./node_modules/*"
-not -path "./.git/*"` periodically. Diff each [conflicted] against canonical;
merge or delete as appropriate. The audit on 2026-05-12 found 26 such files; see
commit `d9e4859` for the recovery pattern.

### `.git/refs/heads/<branch> [conflicted]`

**Symptom:** `git log --all` fails with `fatal: bad object refs/heads/...
[conflicted]`. Other git operations may also misbehave.

**Workaround:** Delete the file: `Remove-Item -LiteralPath ".git/refs/heads/<branch>
[conflicted]" -Force` (PowerShell, use `-LiteralPath` because of brackets in name).
Verify with `git for-each-ref refs/heads`.

### Phantom `M` entries on shell scripts

**Symptom:** `git status` reports `infrastructure/scripts/*.sh` as modified even
though you haven't touched them.

**Cause:** Windows filesystem doesn't track Unix execute bits. With `core.fileMode=true`
(git default), git compares stored mode (100755) to filesystem mode (100644) and
reports a phantom change.

**Workaround:** `git config core.fileMode false` (Step 1, repeated here for emphasis).

### Stale `.pyc` files with Mac paths embedded

**Symptom:** Python errors show `/Users/Dev/infinityrx-platform/...` paths in
tracebacks even though the project is at `C:\Users\MK\...`.

**Cause:** `.pyc` bytecode files cache the original source path. When files are
migrated between machines, the .pyc files retain the old paths until regenerated.

**Workaround:** `find . -type d -name __pycache__ -not -path "*/node_modules/*"
-not -path "*/.venv/*" -prune -exec rm -rf {} +` to clear all bytecode caches.

## 8. Verified launch sequence (smoke test)

For a fresh checkout, this exact sequence should work end-to-end on Windows:

```bash
# 1-2: setup
git config core.fileMode false
uv sync

# 3: services
docker compose up -d
sleep 10
docker exec infinityrx-postgres pg_isready -U infinityrx

# 4: migrations
bash infrastructure/scripts/run_migrations.sh dev

# 5: one backend module (smoke)
( cd modules/adjudication-engine && \
  INFINITYRX_ENV=development \
  DATABASE_URL='postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev' \
  DATABASE_URL_SYNC='postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev' \
  REDIS_URL='redis://localhost:6379/1' \
  RABBITMQ_URL='amqp://infinityrx:infinityrx_bootstrap@localhost:5672/' \
  ENCRYPTION_KEY_ACTIVE='ifx-dev-encryption-key-32chars!!' \
  PYTHONPATH="$(git rev-parse --show-toplevel);$(pwd);$(pwd)/src" \
  uv run --project ../.. uvicorn src.main:app --host 127.0.0.1 --port 8000 )
# In another terminal:
curl -s http://127.0.0.1:8000/health
# {"status":"healthy","module":"adjudication-engine"}

# 6: portal
cd portal/operator
npm run build
npm run start
# Open http://localhost:3000
```

If every command above succeeds, your Windows dev environment is healthy.

## 9. Known issues / future work

- **No top-level launcher script.** Each backend module is launched individually with
  the PYTHONPATH formula above. A `scripts/launch-all.{sh,ps1}` would be useful.
- **Mixed relative/absolute imports inside `modules/<X>/src/`.** Causes the 3-path
  PYTHONPATH formula. B8 fixed this for `drug-database` (renamed `src/` →
  `drug_database/`); applying the same pattern to other modules would simplify
  launches significantly.
- **`bash infrastructure/scripts/qa.sh` is bash-only.** No PowerShell port yet;
  Windows devs use Git Bash. The 4 wrapped steps (tsc, eslint, vitest, build) all
  work standalone.
- **`tests/test_sam_cross_ref.py`** imports a removed symbol from
  `shared/data_ingestion/sources/sam_exclusions.py`. Pre-existing test rot; skip
  with `-k "not test_sam_cross_ref"` or fix the test.

## 10. Cross-references

- `pyproject.toml` — Python deps + pytest config (note `[tool.uv]` and pytest's
  `testpaths` discipline).
- `docker-compose.yml` — postgres + redis + rabbitmq service definitions.
- `infrastructure/scripts/run_migrations.sh` — alembic migration orchestration.
- `infrastructure/scripts/switch_env.sh` — environment switching helper.
- `conftest.py` (repo root) — pytest sys.path wiring (modules/core-platform/src
  + repo root).
- `CLAUDE.md` — project rules + module status.
- `B10/w5-triage-findings.md` — visual QA findings from the W5 capture.
- `Werkbench/projects/infinityrx-platform/waves/B10/STATE.md` — wave state ledger
  (Werkbench overlay; gitignored from project repo).
