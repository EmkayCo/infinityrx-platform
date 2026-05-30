"""detect CLI -- batch FWA detection over a CSV file.

Invocation
----------
    python -m src.cli.detect \
        --file  /path/to/claims.csv \
        --tenant <uuid> \
        [--created-by <uuid>] \
        [--resume] \
        [--force]

with PYTHONPATH=modules/reclaimrx (mirrors start-all-services.ps1 convention).

Session / RLS design
--------------------
The shared src/_shim/db.py engine is ASYNC-only and install_tenant_loader
sets the Python contextvar current_tenant_id -- it does NOT set the
Postgres GUC app.current_tenant_id that migration 0002 RLS policies read.

This CLI:
1. Builds its OWN sync create_engine on the NON-BYPASSRLS app role
   (ifx_dev_app). NEVER uses the infinityrx superuser.
2. Executes SET LOCAL app.current_tenant_id = '<tenant_id>' at the
   start of EVERY transaction so the Postgres GUC RLS reads is set.
3. Also sets the shared current_tenant_id contextvar (belt-and-suspenders
   for any ORM loader filter that may be active).
4. Sets tenant_id explicitly on every INSERT (no async ORM loader on this
   sync path).

tenant_txn(engine, tenant_id) is the single entry point for acquiring a
Session with both the GUC and the contextvar set for the given tenant.

Error handling
--------------
On any exception during Phase 2 (load) or Phase 3 (detection), the run row
is marked status='failed' with failure_reason in a SEPARATE fresh transaction,
then the exception is re-raised so the process exits non-zero.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from contextlib import contextmanager
from typing import Any, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _parse_args(argv=None):
    """Parse CLI arguments.

    Returns argparse.Namespace with .file, .tenant, .created_by, .resume, .force
    """
    parser = argparse.ArgumentParser(
        prog="python -m src.cli.detect",
        description="Run FWA detection over a CSV claims file.",
    )
    parser.add_argument(
        "--file",
        required=True,
        metavar="PATH",
        help="Path to the CSV claims file to ingest.",
    )
    parser.add_argument(
        "--tenant",
        required=True,
        metavar="UUID",
        help="Tenant UUID for this detection run.",
    )
    parser.add_argument(
        "--created-by",
        dest="created_by",
        default=None,
        metavar="UUID",
        help="UUID of the user / service account initiating the run.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        default=False,
        help="Resume an existing in_progress run for the same file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Re-ingest even if a completed or failed run already exists.",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# GUC helper (Postgres-only; abstracted so tests can patch it on SQLite)
# ---------------------------------------------------------------------------


def _set_guc_for_connection(connection, tenant_id: uuid.UUID) -> None:
    """Execute SET LOCAL app.current_tenant_id = '<tenant_id>' on connection.

    This function is abstracted at module level so tests running against
    SQLite (which has no Postgres GUCs) can patch it to a no-op.

    Must be called inside an open transaction (SET LOCAL scope = transaction).

    Args:
        connection: A live SQLAlchemy Connection with an active transaction.
        tenant_id:  The tenant UUID to set.
    """
    connection.execute(
        text("SET LOCAL app.current_tenant_id = :tid"),
        {"tid": str(tenant_id)},
    )


# ---------------------------------------------------------------------------
# tenant_txn context manager
# ---------------------------------------------------------------------------


@contextmanager
def tenant_txn(engine: Engine, tenant_id: uuid.UUID):
    """Acquire a Session with the RLS GUC and contextvar set for tenant_id.

    Dual-layer tenant fence:
      1. SET LOCAL app.current_tenant_id -- the Postgres GUC that migration
         0002 RLS policies read.  Must be inside a transaction (SET LOCAL
         scope = transaction boundaries).
      2. shared.db.tenant_context.current_tenant_id contextvar -- used by
         ORM TenantScopedMixin install_tenant_loader (belt-and-suspenders).

    Uses SQLAlchemy connection.begin() API (not raw SQL BEGIN/COMMIT) so the
    transaction lifecycle is managed consistently across Postgres and SQLite.
    The GUC is set via _set_guc_for_connection() immediately after BEGIN; on
    SQLite (tests) that function is patched to a no-op.

    Commits on clean exit; rolls back and clears contextvar on any exception.

    Args:
        engine:     Sync SQLAlchemy Engine (must connect as non-BYPASSRLS role).
        tenant_id:  Tenant UUID.

    Yields:
        Session bound to an open connection with GUC and contextvar set.
    """
    from shared.db.tenant_context import (
        clear_tenant_context,
        set_tenant_context,
    )

    token = set_tenant_context(tenant_id)
    connection = engine.connect()
    try:
        txn = connection.begin()
        try:
            # Set the Postgres GUC that RLS predicates read.
            # On Postgres: SET LOCAL app.current_tenant_id = '<tid>'
            # On SQLite (tests): patched to no-op via _set_guc_for_connection.
            _set_guc_for_connection(connection, tenant_id)

            session = Session(bind=connection, join_transaction_mode="create_savepoint")
            try:
                yield session
                session.flush()
                txn.commit()
            except Exception:
                if txn.is_active:
                    txn.rollback()
                raise
            finally:
                session.close()
        except Exception:
            if txn.is_active:
                txn.rollback()
            raise
    finally:
        clear_tenant_context(token)
        connection.close()


# ---------------------------------------------------------------------------
# Default engine factory
# ---------------------------------------------------------------------------

_DEFAULT_DB_URL_ENV = "RECLAIMRX_DB_URL"


def _build_default_engine() -> Engine:
    """Build the CLI sync engine from RECLAIMRX_DB_URL.

    The URL MUST use the non-BYPASSRLS app role (ifx_dev_app).
    Raises EnvironmentError if RECLAIMRX_DB_URL is not set.
    """
    url = os.environ.get(_DEFAULT_DB_URL_ENV)
    if not url:
        raise EnvironmentError(
            f"Environment variable {_DEFAULT_DB_URL_ENV!r} is not set. "
            "Supply a Postgres DSN using the ifx_dev_app role credentials. "
            "Example: postgresql+psycopg2://ifx_dev_app:pass@localhost/infinityrx_dev"
        )
    return create_engine(url, future=True)


# ---------------------------------------------------------------------------
# _mark_run_failed -- writes failure marker in a separate transaction
# ---------------------------------------------------------------------------


def _mark_run_failed(
    engine: Engine,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    reason: str,
) -> None:
    """Mark a DetectionRun as failed in a fresh, independent transaction.

    Uses a completely new connection so this write succeeds even when the
    caller's transaction has been rolled back.

    Args:
        engine:     The CLI sync engine.
        tenant_id:  Tenant UUID (RLS GUC + WHERE clause).
        run_id:     DetectionRun.id to update.
        reason:     Short human-readable failure reason.
    """
    from src.models.detection_run_models import DetectionRun

    try:
        with tenant_txn(engine, tenant_id) as fail_sess:
            run_row = fail_sess.get(DetectionRun, run_id)
            if run_row is not None:
                run_row.status = "failed"
                run_row.failure_reason = reason[:2000]
                fail_sess.flush()
    except Exception:
        # Best-effort -- never mask the original exception.
        logger.exception(
            "Could not mark run as failed (reason=%r run_id=%s)", reason, run_id
        )


# ---------------------------------------------------------------------------
# run_detect -- public orchestrator
# ---------------------------------------------------------------------------


def run_detect(
    file: str,
    *,
    tenant: uuid.UUID,
    created_by: uuid.UUID | None = None,
    engine: Engine | None = None,
    resume: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Run the full FWA detection pipeline for one CSV file.

    Phases:
      1. register_rule_types + register_rule_instances (idempotent seeding)
      2. create_or_resume_run + load_csv
      3. run_detection (enforces full-coverage gate)
      4. build_summary + format_summary (printed to stdout)

    Error handling:
      If any exception occurs in Phase 2 or later, the run row (if created)
      is marked status='failed' with failure_reason in a SEPARATE transaction,
      then the exception is re-raised.

    Args:
        file:       Path to the CSV claims file.
        tenant:     Tenant UUID.
        created_by: UUID of initiating user/service. Defaults to nil UUID.
        engine:     Optional pre-built sync Engine. If None, built from
                    RECLAIMRX_DB_URL.
        resume:     Attach to an in_progress run.
        force:      Re-ingest over a completed/failed run.

    Returns:
        Summary dict from build_summary().

    Raises:
        Any exception from the pipeline (after marking run as failed).
    """
    from src.detection.batch_engine import run_detection
    from src.detection.csv_ingest import create_or_resume_run, load_csv
    from src.detection.rule_type_registry import (
        register_rule_instances,
        register_rule_types,
    )
    from src.detection.run_summary import build_summary, format_summary

    if created_by is None:
        created_by = uuid.UUID("00000000-0000-0000-0000-000000000000")

    own_engine = engine is None
    if own_engine:
        engine = _build_default_engine()

    run_id: uuid.UUID | None = None

    try:
        # ------------------------------------------------------------------
        # Phase 1: Rule seeding (idempotent)
        # ------------------------------------------------------------------
        with tenant_txn(engine, tenant) as sess:
            register_rule_types(sess)
            import csv as _csv
            with open(file, newline="", encoding="utf-8") as fh:
                reader = _csv.DictReader(fh)
                available_columns: set[str] = set(reader.fieldnames or [])
            register_rule_instances(sess, tenant, available_columns, created_by)

        # ------------------------------------------------------------------
        # Phase 2a: Create/resume run (committed immediately so run_id
        # is durable before Phase 2b load begins -- ensures _mark_run_failed
        # can find the row if load raises).
        # ------------------------------------------------------------------
        with tenant_txn(engine, tenant) as sess:
            run = create_or_resume_run(
                sess,
                tenant_id=tenant,
                path=file,
                created_by=created_by,
                resume=resume,
                force=force,
            )
            run_id = run.id

        # ------------------------------------------------------------------
        # Phase 2b: Load CSV rows (separate transaction; run row already
        # committed above so _mark_run_failed can find it on failure).
        # ------------------------------------------------------------------
        with tenant_txn(engine, tenant) as sess:
            from src.models.detection_run_models import DetectionRun
            run = sess.get(DetectionRun, run_id)
            if run is None:
                raise RuntimeError(
                    f"DetectionRun {run_id} not found for tenant {tenant}"
                )
            load_csv(sess, run)

        # ------------------------------------------------------------------
        # Phase 3: Detection
        # ------------------------------------------------------------------
        with tenant_txn(engine, tenant) as sess:
            from src.models.detection_run_models import DetectionRun
            run = sess.get(DetectionRun, run_id)
            if run is None:
                raise RuntimeError(
                    f"DetectionRun {run_id} not found for tenant {tenant}"
                )
            run_detection(sess, run)

        # ------------------------------------------------------------------
        # Phase 4: Summary
        # ------------------------------------------------------------------
        with tenant_txn(engine, tenant) as summary_sess:
            from src.models.detection_run_models import DetectionRun
            run = summary_sess.get(DetectionRun, run_id)
            if run is None:
                raise RuntimeError(
                    f"DetectionRun {run_id} not found for tenant {tenant}"
                )
            summary = build_summary(summary_sess, run)

        print(format_summary(summary))
        return summary

    except Exception as exc:
        # Mark run failed in a separate transaction (best-effort).
        if run_id is not None and engine is not None:
            _mark_run_failed(engine, tenant, run_id, str(exc))
        raise

    finally:
        if own_engine and engine is not None:
            engine.dispose()


# ---------------------------------------------------------------------------
# __main__ entry point
# ---------------------------------------------------------------------------


def main(argv=None):
    """Entry point for python -m src.cli.detect."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    args = _parse_args(argv)

    tenant = uuid.UUID(args.tenant)
    created_by = uuid.UUID(args.created_by) if args.created_by else None

    try:
        run_detect(
            args.file,
            tenant=tenant,
            created_by=created_by,
            resume=args.resume,
            force=args.force,
        )
    except Exception:
        logger.exception("Detection failed")
        sys.exit(1)


if __name__ == "__main__":
    main()


