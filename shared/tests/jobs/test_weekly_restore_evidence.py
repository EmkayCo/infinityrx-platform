"""H-09: tests for the weekly restore-evidence runner."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from shared.jobs import weekly_restore_evidence as wre


@pytest.fixture()
def evidence_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(wre, "EVIDENCE_DIR", tmp_path / "restore_evidence")
    return tmp_path / "restore_evidence"


def _fake_runner_factory(returncode: int, stdout: str = "", stderr: str = ""):
    def _runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=returncode, stdout=stdout, stderr=stderr
        )

    return _runner


def test_run_restore_success_returns_evidence(tmp_path: Path) -> None:
    backup = tmp_path / "backup.sql.gz"
    backup.write_bytes(b"")
    evidence = wre.run_restore(
        backup,
        "verify_db",
        restore_script=tmp_path / "restore.sh",
        runner=_fake_runner_factory(0, stdout="ok", stderr=""),
        now=lambda: datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
    )
    assert evidence["success"] is True
    assert evidence["exit_code"] == 0
    assert evidence["backup_file"].endswith("backup.sql.gz")
    assert evidence["target_db"] == "verify_db"
    assert evidence["started_at"].startswith("2026-04-14")


def test_run_restore_failure_records_exit_code(tmp_path: Path) -> None:
    evidence = wre.run_restore(
        tmp_path / "missing.sql.gz",
        "verify_db",
        restore_script=tmp_path / "restore.sh",
        runner=_fake_runner_factory(3, stderr="missing backup"),
        now=lambda: datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
    )
    assert evidence["success"] is False
    assert evidence["exit_code"] == 3
    assert "missing backup" in evidence["stderr_tail"][-1]


def test_run_restore_handles_missing_script(tmp_path: Path) -> None:
    def _missing(*_args, **_kwargs):
        raise FileNotFoundError("/nope/restore.sh")

    evidence = wre.run_restore(
        tmp_path / "backup.sql.gz",
        "verify_db",
        restore_script=Path("/nope/restore.sh"),
        runner=_missing,
        now=lambda: datetime(2026, 4, 14, 12, 0, tzinfo=UTC),
    )
    assert evidence["success"] is False
    assert evidence["exit_code"] == -1
    assert "restore script not found" in evidence["error"]


def test_main_writes_evidence_file_on_success(
    evidence_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(wre, "RESTORE_SCRIPT", tmp_path / "restore.sh")
    monkeypatch.setattr(
        wre.subprocess, "run", _fake_runner_factory(0, stdout="restored 1234 rows")
    )
    backup = tmp_path / "backup.sql.gz"
    backup.write_bytes(b"")

    rc = wre.main(
        [
            "--backup",
            str(backup),
            "--target-db",
            "verify_db",
            "--evidence-date",
            "2026-04-14",
        ]
    )
    assert rc == 0
    written = evidence_dir / "restore-2026-04-14.json"
    assert written.exists()
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["success"] is True
    assert payload["target_db"] == "verify_db"


def test_main_returns_nonzero_on_failure(
    evidence_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(wre, "RESTORE_SCRIPT", tmp_path / "restore.sh")
    monkeypatch.setattr(wre.subprocess, "run", _fake_runner_factory(1, stderr="boom"))
    backup = tmp_path / "backup.sql.gz"
    backup.write_bytes(b"")

    rc = wre.main(
        [
            "--backup",
            str(backup),
            "--target-db",
            "verify_db",
            "--evidence-date",
            "2026-04-14",
        ]
    )
    assert rc == 1
    written = evidence_dir / "restore-2026-04-14.json"
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["success"] is False
    assert payload["exit_code"] == 1
