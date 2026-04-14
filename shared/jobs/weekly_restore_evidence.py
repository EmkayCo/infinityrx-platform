"""H-09: weekly restore-evidence runner.

Calls ``infrastructure/scripts/restore.sh`` against a throwaway database,
records the result (success/fail, restore duration, source backup file)
to a JSON evidence file under
``infrastructure/scripts/tests/restore_evidence/restore-{date}.json``,
and exits non-zero on failure so a scheduler can alert.

This is the artefact the HIPAA 2026 §164.308(a)(7)(ii)(D) "weekly verified
restore test" requirement asks for. The script is intentionally simple so
it can be run from cron, GitHub Actions, AKS CronJob, or by hand:

    python -m shared.jobs.weekly_restore_evidence \\
        --backup /var/backups/infinityrx-2026-04-14.sql.gz \\
        --target-db infinityrx_restore_verify

The runner does NOT generate fresh backups — it consumes whatever the
production backup pipeline has already produced.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("shared.jobs.weekly_restore_evidence")

REPO_ROOT = Path(__file__).resolve().parents[2]
RESTORE_SCRIPT = REPO_ROOT / "infrastructure" / "scripts" / "restore.sh"
EVIDENCE_DIR = REPO_ROOT / "infrastructure" / "scripts" / "tests" / "restore_evidence"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _evidence_path(run_date: date) -> Path:
    return EVIDENCE_DIR / f"restore-{run_date.isoformat()}.json"


def _write_evidence(payload: dict[str, Any], run_date: date) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = _evidence_path(run_date)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def run_restore(
    backup_file: Path,
    target_db: str,
    *,
    restore_script: Path | None = None,
    runner: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """Invoke restore.sh and return a structured evidence dict.

    ``runner`` and ``now`` are injected so unit tests can substitute fakes
    without spawning a real subprocess or depending on wall-clock time.
    They default to ``subprocess.run`` and ``_utcnow``, looked up at call
    time so monkeypatching the module attributes works.
    """
    runner = runner or subprocess.run
    now = now or _utcnow
    script = restore_script or RESTORE_SCRIPT
    started = now()
    t0 = time.monotonic()
    try:
        completed = runner(
            [str(script), str(backup_file), target_db],
            check=False,
            capture_output=True,
            text=True,
        )
        duration_ms = int((time.monotonic() - t0) * 1000)
        success = completed.returncode == 0
        return {
            "backup_file": str(backup_file),
            "target_db": target_db,
            "started_at": started.isoformat(),
            "duration_ms": duration_ms,
            "exit_code": completed.returncode,
            "success": success,
            "stdout_tail": (completed.stdout or "").splitlines()[-20:],
            "stderr_tail": (completed.stderr or "").splitlines()[-20:],
        }
    except FileNotFoundError as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        return {
            "backup_file": str(backup_file),
            "target_db": target_db,
            "started_at": started.isoformat(),
            "duration_ms": duration_ms,
            "exit_code": -1,
            "success": False,
            "error": f"restore script not found: {exc}",
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Weekly restore evidence runner (H-09)")
    parser.add_argument("--backup", required=True, type=Path, help="Path to a gzipped pg_dump")
    parser.add_argument(
        "--target-db",
        default=os.getenv("RESTORE_TARGET_DB", "infinityrx_restore_verify"),
        help="Throwaway DB name to restore into",
    )
    parser.add_argument(
        "--evidence-date",
        default=date.today().isoformat(),
        help="Override the evidence filename date (YYYY-MM-DD)",
    )
    args = parser.parse_args(argv)

    evidence = run_restore(args.backup, args.target_db)
    run_date = date.fromisoformat(args.evidence_date)
    written = _write_evidence(evidence, run_date)
    logger.info(
        "weekly_restore_evidence_written",
        extra={"svc_path": str(written), "svc_success": evidence["success"]},
    )
    return 0 if evidence["success"] else 1


if __name__ == "__main__":  # pragma: no cover — CLI entry point
    sys.exit(main())
