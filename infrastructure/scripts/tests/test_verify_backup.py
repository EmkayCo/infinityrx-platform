"""Smoke tests for infrastructure/scripts/verify_backup.py.

Live-DB verification is a CI-environment concern (requires postgres +
restore.sh); these tests validate only the comparison logic and
command-line argument handling that we can exercise without a broker.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPT = Path(__file__).resolve().parent.parent / "verify_backup.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_backup", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_rejects_missing_args() -> None:
    vb = _load_module()
    assert vb.main(["verify_backup.py"]) == 2
    assert vb.main(["verify_backup.py", "a", "b"]) == 2


def test_verify_fails_on_missing_file(tmp_path) -> None:
    vb = _load_module()
    rc = vb.verify(str(tmp_path / "nonexistent.sql.gz"))
    assert rc == 2


def test_verify_returns_3_when_restore_fails(tmp_path) -> None:
    vb = _load_module()
    fake_backup = tmp_path / "dump.sql.gz"
    fake_backup.write_bytes(b"not a real dump")

    with (
        patch.object(vb, "_analyze"),
        patch.object(vb, "_row_counts", return_value={("core", "tenants"): 3}),
        patch.object(vb, "_exact_row_counts", return_value={("core", "tenants"): 3}),
        patch("subprocess.run") as fake_run,
    ):
        fake_run.return_value = MagicMock(returncode=2)
        assert vb.verify(str(fake_backup)) == 3


def test_verify_detects_row_count_mismatch(tmp_path, capsys) -> None:
    vb = _load_module()
    fake_backup = tmp_path / "dump.sql.gz"
    fake_backup.write_bytes(b"x")

    source = {("core", "tenants"): 3, ("core", "users"): 10}
    target = {("core", "tenants"): 3, ("core", "users"): 9}  # drift!

    with (
        patch.object(vb, "_analyze"),
        patch.object(vb, "_row_counts", return_value=source),
        patch.object(vb, "_exact_row_counts", side_effect=[source, target]),
        patch("subprocess.run", return_value=MagicMock(returncode=0)),
        patch.object(vb, "_connect") as fake_conn,
    ):
        conn = MagicMock()
        fake_conn.return_value = conn
        rc = vb.verify(str(fake_backup))
    assert rc == 1
    err = capsys.readouterr().err
    assert "row count mismatch" in err
    assert "core.users" in err


def test_verify_detects_missing_table(tmp_path, capsys) -> None:
    vb = _load_module()
    fake_backup = tmp_path / "dump.sql.gz"
    fake_backup.write_bytes(b"x")

    source = {("core", "tenants"): 3, ("core", "users"): 10}
    target = {("core", "tenants"): 3}  # users table missing

    with (
        patch.object(vb, "_analyze"),
        patch.object(vb, "_row_counts", return_value=source),
        patch.object(vb, "_exact_row_counts", side_effect=[source, target]),
        patch("subprocess.run", return_value=MagicMock(returncode=0)),
        patch.object(vb, "_connect") as fake_conn,
    ):
        conn = MagicMock()
        fake_conn.return_value = conn
        rc = vb.verify(str(fake_backup))
    assert rc == 1
    assert "missing table core.users" in capsys.readouterr().err


def test_verify_detects_unexpected_table(tmp_path, capsys) -> None:
    vb = _load_module()
    fake_backup = tmp_path / "dump.sql.gz"
    fake_backup.write_bytes(b"x")

    source = {("core", "tenants"): 3}
    target = {("core", "tenants"): 3, ("junk", "leftover"): 0}

    with (
        patch.object(vb, "_analyze"),
        patch.object(vb, "_row_counts", return_value=source),
        patch.object(vb, "_exact_row_counts", side_effect=[source, target]),
        patch("subprocess.run", return_value=MagicMock(returncode=0)),
        patch.object(vb, "_connect") as fake_conn,
    ):
        conn = MagicMock()
        fake_conn.return_value = conn
        rc = vb.verify(str(fake_backup))
    assert rc == 1
    assert "unexpected table in target: junk.leftover" in capsys.readouterr().err


def test_verify_passes_when_counts_match(tmp_path) -> None:
    vb = _load_module()
    fake_backup = tmp_path / "dump.sql.gz"
    fake_backup.write_bytes(b"x")

    counts = {("core", "tenants"): 3, ("core", "users"): 10}

    with (
        patch.object(vb, "_analyze"),
        patch.object(vb, "_row_counts", return_value=counts),
        patch.object(vb, "_exact_row_counts", side_effect=[counts, counts]),
        patch("subprocess.run", return_value=MagicMock(returncode=0)),
        patch.object(vb, "_connect") as fake_conn,
    ):
        conn = MagicMock()
        fake_conn.return_value = conn
        rc = vb.verify(str(fake_backup))
    assert rc == 0
