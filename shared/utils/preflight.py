"""Pre-flight environment validator.

Intended to be invoked at the start of every agent session::

    python -m shared.utils.preflight

It verifies the developer's local environment is in a state where work can
proceed: all infrastructure reachable, all schemas present, required files
in place, and the git worktree clean. The script exits ``0`` when every
check passes and prints ``PRE-FLIGHT: ALL CLEAR``; otherwise it prints which
check failed together with a remediation hint and exits ``1``.

Design: every check is a small pure function returning a
:class:`CheckResult` so tests can exercise individual failures without
spinning up real services. The top-level ``main()`` wires them together.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import aio_pika
import asyncpg
import redis.asyncio as redis_async

from shared.config import get_settings

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_LOCAL = _REPO_ROOT / ".env.local"
_TODO = _REPO_ROOT / "modules" / "core-platform" / "tasks" / "todo.md"
_LESSONS = _REPO_ROOT / "modules" / "core-platform" / "tasks" / "lessons.md"

REQUIRED_SCHEMAS: tuple[str, ...] = (
    "core",
    "billing",
    "reclaimrx",
    "drug_db",
    "pharmacy_dir",
    "med_prescriber_dir",
    "member_mgmt",
    "plan_design",
    "rules_engine",
    "adjudication",
    "switch_conn",
    "prior_auth",
    "payment_proc",
    "edi_compliance",
    "medical_claims",
    "reporting",
    "program_config",
    "testing_sim",
    "ebv_ebi",
    "ai_nlp",
    "rebate_mgmt",
    "dataiq",
    "mtm_clinical",
)

REQUIRED_ENV_KEYS: tuple[str, ...] = (
    "DATABASE_URL",
    "REDIS_URL",
    "RABBITMQ_URL",
    "JWT_SECRET",
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    remediation: str = ""


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


async def check_postgres() -> CheckResult:
    settings = get_settings()
    url = settings.DATABASE_URL.replace("+asyncpg", "")
    try:
        conn = await asyncpg.connect(url)
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            "postgres",
            False,
            f"cannot connect: {exc}",
            "Start the postgres container: docker compose up -d postgres",
        )
    try:
        rows = await conn.fetch(
            "SELECT nspname FROM pg_namespace WHERE nspname = ANY($1::text[])",
            list(REQUIRED_SCHEMAS),
        )
    finally:
        await conn.close()
    found = {r["nspname"] for r in rows}
    missing = [s for s in REQUIRED_SCHEMAS if s not in found]
    if missing:
        return CheckResult(
            "postgres",
            False,
            f"missing schemas: {', '.join(missing)}",
            "Apply infrastructure/docker/init-schemas.sql against the running db",
        )
    return CheckResult("postgres", True, f"reachable, {len(REQUIRED_SCHEMAS)} schemas present")


async def check_redis() -> CheckResult:
    settings = get_settings()
    client = redis_async.from_url(settings.REDIS_URL)
    try:
        pong = await client.ping()
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            "redis",
            False,
            f"cannot ping: {exc}",
            "Start redis: docker compose up -d redis",
        )
    finally:
        await client.aclose()
    if not pong:
        return CheckResult("redis", False, "ping returned falsy", "Restart redis container")
    return CheckResult("redis", True, "PONG")


async def check_rabbitmq() -> CheckResult:
    settings = get_settings()
    try:
        conn = await aio_pika.connect_robust(settings.RABBITMQ_URL, timeout=5)
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            "rabbitmq",
            False,
            f"cannot connect: {exc}",
            "Start rabbitmq: docker compose up -d rabbitmq",
        )
    await conn.close()
    return CheckResult("rabbitmq", True, "connected")


def check_env_file(env_path: Path = _ENV_LOCAL) -> CheckResult:
    if not env_path.exists():
        return CheckResult(
            "env_file",
            False,
            f"{env_path} not found",
            "Copy .env.example to .env.local and fill in secrets",
        )
    content = env_path.read_text(encoding="utf-8")
    missing = [k for k in REQUIRED_ENV_KEYS if f"{k}=" not in content]
    if missing:
        return CheckResult(
            "env_file",
            False,
            f"missing keys: {', '.join(missing)}",
            "Add the missing keys to .env.local",
        )
    return CheckResult("env_file", True, f"{env_path.name} present with required keys")


def check_git_clean(cwd: Path = _REPO_ROOT) -> CheckResult:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return CheckResult(
            "git_clean",
            False,
            f"git status failed: {exc}",
            "Ensure this directory is a git worktree",
        )
    if out.stdout.strip():
        return CheckResult(
            "git_clean",
            False,
            "uncommitted changes present",
            "Commit or stash your changes before starting work",
        )
    return CheckResult("git_clean", True, "worktree clean")


def check_todo(todo_path: Path = _TODO) -> CheckResult:
    if not todo_path.exists():
        return CheckResult(
            "todo",
            False,
            f"{todo_path} missing",
            "Create modules/core-platform/tasks/todo.md",
        )
    return CheckResult("todo", True, f"{todo_path.name} readable")


def check_lessons(lessons_path: Path = _LESSONS) -> CheckResult:
    if not lessons_path.exists():
        return CheckResult(
            "lessons",
            False,
            f"{lessons_path} missing",
            "Create modules/core-platform/tasks/lessons.md",
        )
    lines = [
        ln.rstrip() for ln in lessons_path.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    tail = "\n    ".join(lines[-5:]) if lines else "(empty)"
    return CheckResult(
        "lessons", True, f"{lessons_path.name} readable; last entries:\n    {tail}"
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def run_all_checks(
    postgres: Callable[[], "asyncio.Future[CheckResult]"] | None = None,
    redis: Callable[[], "asyncio.Future[CheckResult]"] | None = None,
    rabbitmq: Callable[[], "asyncio.Future[CheckResult]"] | None = None,
) -> list[CheckResult]:
    """Run every check and return the results in display order.

    The three infrastructure checks accept optional injectable overrides so
    tests can simulate failures without touching the real services.
    """
    pg_fn = postgres or check_postgres
    rd_fn = redis or check_redis
    mq_fn = rabbitmq or check_rabbitmq

    results: list[CheckResult] = []
    results.append(await pg_fn())
    results.append(await rd_fn())
    results.append(await mq_fn())
    results.append(check_env_file())
    results.append(check_git_clean())
    results.append(check_todo())
    results.append(check_lessons())
    return results


def format_report(results: list[CheckResult]) -> tuple[str, bool]:
    lines = []
    all_ok = True
    for r in results:
        marker = "OK  " if r.ok else "FAIL"
        lines.append(f"[{marker}] {r.name}: {r.detail}")
        if not r.ok:
            all_ok = False
            if r.remediation:
                lines.append(f"       remediation: {r.remediation}")
    if all_ok:
        lines.append("")
        lines.append("PRE-FLIGHT: ALL CLEAR")
    else:
        lines.append("")
        lines.append("PRE-FLIGHT: FAILED — address the items above and rerun")
    return "\n".join(lines), all_ok


async def _amain() -> int:
    results = await run_all_checks()
    report, ok = format_report(results)
    print(report)
    return 0 if ok else 1


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    sys.exit(main())
