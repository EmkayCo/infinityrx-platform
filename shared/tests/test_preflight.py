"""Tests for the pre-flight validator.

The infra checks talk to injected fakes so the test suite never flakes on
a developer's network. One happy-path test does hit the real local Postgres
to prove the actual ``check_postgres`` function works end-to-end against
the configured database.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.utils import preflight
from shared.utils.preflight import (
    CheckResult,
    check_env_file,
    check_git_clean,
    check_lessons,
    check_postgres,
    check_todo,
    format_report,
    run_all_checks,
)


async def _ok(name: str = "x") -> CheckResult:
    return CheckResult(name, True, "ok")


async def _fail(name: str = "x") -> CheckResult:
    return CheckResult(name, False, "down", "start it")


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------


def test_format_report_all_clear() -> None:
    report, ok = format_report(
        [CheckResult("a", True, "ok"), CheckResult("b", True, "ok")]
    )
    assert ok is True
    assert "PRE-FLIGHT: ALL CLEAR" in report


def test_format_report_failure_without_remediation() -> None:
    report, ok = format_report([CheckResult("a", False, "down", "")])
    assert ok is False
    assert "remediation" not in report


def test_format_report_failure_includes_remediation() -> None:
    report, ok = format_report(
        [CheckResult("a", False, "down", "restart a"), CheckResult("b", True, "ok")]
    )
    assert ok is False
    assert "PRE-FLIGHT: FAILED" in report
    assert "restart a" in report


# ---------------------------------------------------------------------------
# check_env_file
# ---------------------------------------------------------------------------


def test_check_env_file_missing(tmp_path: Path) -> None:
    r = check_env_file(tmp_path / "nope.env")
    assert r.ok is False
    assert "not found" in r.detail


def test_check_env_file_missing_keys(tmp_path: Path) -> None:
    p = tmp_path / ".env.local"
    p.write_text("DATABASE_URL=x\n", encoding="utf-8")
    r = check_env_file(p)
    assert r.ok is False
    assert "missing keys" in r.detail


def test_check_env_file_ok(tmp_path: Path) -> None:
    p = tmp_path / ".env.local"
    p.write_text(
        "DATABASE_URL=x\nREDIS_URL=y\nRABBITMQ_URL=z\nJWT_SECRET=" + "x" * 32 + "\n",
        encoding="utf-8",
    )
    r = check_env_file(p)
    assert r.ok is True


# ---------------------------------------------------------------------------
# check_git_clean
# ---------------------------------------------------------------------------


def test_check_git_clean_non_git_dir(tmp_path: Path) -> None:
    r = check_git_clean(tmp_path)
    assert r.ok is False


def test_check_git_clean_worktree(monkeypatch, tmp_path: Path) -> None:
    import subprocess as sp

    class _Fake:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    monkeypatch.setattr(
        sp, "run", lambda *a, **k: _Fake("")  # noqa: ARG005
    )
    r = check_git_clean(tmp_path)
    assert r.ok is True


def test_check_git_clean_dirty(monkeypatch, tmp_path: Path) -> None:
    import subprocess as sp

    class _Fake:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    monkeypatch.setattr(
        sp, "run", lambda *a, **k: _Fake(" M foo\n")  # noqa: ARG005
    )
    r = check_git_clean(tmp_path)
    assert r.ok is False
    assert "uncommitted" in r.detail


# ---------------------------------------------------------------------------
# check_todo / check_lessons
# ---------------------------------------------------------------------------


def test_check_todo_missing(tmp_path: Path) -> None:
    r = check_todo(tmp_path / "todo.md")
    assert r.ok is False


def test_check_todo_ok(tmp_path: Path) -> None:
    p = tmp_path / "todo.md"
    p.write_text("hi\n")
    assert check_todo(p).ok is True


def test_check_lessons_missing(tmp_path: Path) -> None:
    assert check_lessons(tmp_path / "lessons.md").ok is False


def test_check_lessons_tail(tmp_path: Path) -> None:
    p = tmp_path / "lessons.md"
    p.write_text("\n".join(f"line {i}" for i in range(10)), encoding="utf-8")
    r = check_lessons(p)
    assert r.ok is True
    assert "line 9" in r.detail


def test_check_lessons_empty(tmp_path: Path) -> None:
    p = tmp_path / "lessons.md"
    p.write_text("", encoding="utf-8")
    r = check_lessons(p)
    assert r.ok is True
    assert "empty" in r.detail


# ---------------------------------------------------------------------------
# check_postgres (real DB)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_check_postgres_real() -> None:
    """Exercise the real check against the developer's running Postgres."""
    r = await check_postgres()
    assert r.ok is True, r.detail


async def test_check_postgres_connect_failure(monkeypatch) -> None:
    async def _boom(url):  # noqa: ARG001
        raise ConnectionRefusedError("nope")

    monkeypatch.setattr(preflight.asyncpg, "connect", _boom)
    r = await preflight.check_postgres()
    assert r.ok is False
    assert "cannot connect" in r.detail


async def test_check_postgres_missing_schemas(monkeypatch) -> None:
    class _FakeConn:
        async def fetch(self, *args, **kwargs):  # noqa: ARG002
            return [{"nspname": "core"}]  # only one of 25

        async def close(self):
            return None

    async def _connect(url):  # noqa: ARG001
        return _FakeConn()

    monkeypatch.setattr(preflight.asyncpg, "connect", _connect)
    r = await preflight.check_postgres()
    assert r.ok is False
    assert "missing schemas" in r.detail


async def test_check_redis_ok(monkeypatch) -> None:
    class _FakeRedis:
        async def ping(self):
            return True

        async def aclose(self):
            return None

    monkeypatch.setattr(preflight.redis_async, "from_url", lambda _u: _FakeRedis())
    r = await preflight.check_redis()
    assert r.ok is True


async def test_check_redis_connect_failure(monkeypatch) -> None:
    class _FakeRedis:
        async def ping(self):
            raise ConnectionError("down")

        async def aclose(self):
            return None

    monkeypatch.setattr(preflight.redis_async, "from_url", lambda _u: _FakeRedis())
    r = await preflight.check_redis()
    assert r.ok is False
    assert "cannot ping" in r.detail


async def test_check_redis_ping_falsy(monkeypatch) -> None:
    class _FakeRedis:
        async def ping(self):
            return False

        async def aclose(self):
            return None

    monkeypatch.setattr(preflight.redis_async, "from_url", lambda _u: _FakeRedis())
    r = await preflight.check_redis()
    assert r.ok is False
    assert "falsy" in r.detail


async def test_check_rabbitmq_ok(monkeypatch) -> None:
    class _FakeConn:
        async def close(self):
            return None

    async def _connect(url, timeout):  # noqa: ARG001
        return _FakeConn()

    monkeypatch.setattr(preflight.aio_pika, "connect_robust", _connect)
    r = await preflight.check_rabbitmq()
    assert r.ok is True


async def test_check_rabbitmq_failure(monkeypatch) -> None:
    async def _connect(url, timeout):  # noqa: ARG001
        raise ConnectionError("down")

    monkeypatch.setattr(preflight.aio_pika, "connect_robust", _connect)
    r = await preflight.check_rabbitmq()
    assert r.ok is False
    assert "cannot connect" in r.detail


# ---------------------------------------------------------------------------
# run_all_checks + main
# ---------------------------------------------------------------------------


async def test_run_all_checks_injects_fakes_and_returns_results() -> None:
    results = await run_all_checks(
        postgres=lambda: _ok("postgres"),
        redis=lambda: _ok("redis"),
        rabbitmq=lambda: _ok("rabbitmq"),
    )
    assert len(results) == 7
    assert [r.name for r in results[:3]] == ["postgres", "redis", "rabbitmq"]


async def test_run_all_checks_reports_failures() -> None:
    results = await run_all_checks(
        postgres=lambda: _fail("postgres"),
        redis=lambda: _ok("redis"),
        rabbitmq=lambda: _fail("rabbitmq"),
    )
    failing = [r for r in results if not r.ok]
    assert {r.name for r in failing} >= {"postgres", "rabbitmq"}


async def test_amain_exits_zero_when_all_pass(monkeypatch) -> None:
    async def _fake_run_all() -> list[CheckResult]:
        return [CheckResult(n, True, "ok") for n in ("a", "b", "c")]

    monkeypatch.setattr(preflight, "run_all_checks", _fake_run_all)
    assert await preflight._amain() == 0


async def test_amain_exits_one_on_failure(monkeypatch) -> None:
    async def _fake_run_all() -> list[CheckResult]:
        return [CheckResult("a", False, "bad", "fix")]

    monkeypatch.setattr(preflight, "run_all_checks", _fake_run_all)
    assert await preflight._amain() == 1


def test_main_entrypoint_returns_int(monkeypatch) -> None:
    async def _fake_amain() -> int:
        return 0

    # Patch the async main via asyncio.run — call main() and assert int.
    monkeypatch.setattr(preflight, "_amain", _fake_amain)
    assert preflight.main() == 0
