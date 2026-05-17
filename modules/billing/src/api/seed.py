"""Billing fixture seed endpoint — dev/staging only.

POST /api/v1/billing/seed
  Reads committed JSON fixtures from packages/modules/paysync/fixtures/seeds/
  and inserts them into the billing DB (idempotent — skips rows that already
  exist by primary key).

DELETE /api/v1/billing/seed
  Truncates all billing fixture data for the given tenant_id in dependency
  order (children first). Used by Playwright afterAll cleanup.

Production guard: both endpoints return 403 when INFINITYRX_ENV=production.
The guard fires before any DB operation so production DBs are never touched.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.dependencies import DBSession

logger = logging.getLogger("billing.seed")

router = APIRouter(prefix="/api/v1/billing", tags=["seed"])

# Path to the committed fixture seed files.  Resolved relative to this file so
# it works regardless of cwd.  The seeds live at:
#   <repo-root>/packages/modules/paysync/fixtures/seeds/
_REPO_ROOT = Path(__file__).resolve().parents[6]
_SEEDS_DIR = _REPO_ROOT / "packages" / "modules" / "paysync" / "fixtures" / "seeds"

# Insertion order: parents before children (FK constraint order).
_INSERT_ORDER = [
    "uploads",
    "cycles",
    "batches",
    "invoices",
    "payment_runs",
    "file_artifacts",
    "journal_entries",
    "reconciliations",
    "carryovers",
    "bank_settlements",
]

# Truncation order: children before parents (reverse of insert order).
_TRUNCATE_ORDER = list(reversed(_INSERT_ORDER))

# Map seed filename stem -> billing ORM table name.
_TABLE_MAP: dict[str, str] = {
    "uploads": "billing_uploads",
    "cycles": "billing_payment_cycles",
    "batches": "billing_payment_batches",
    "invoices": "billing_invoices",
    "payment_runs": "billing_payment_runs",
    "file_artifacts": "billing_file_artifacts",
    "journal_entries": "billing_journal_entries",
    "reconciliations": "billing_reconciliations",
    "carryovers": "billing_carryovers",
    "bank_settlements": "billing_bank_settlements",
}


def _is_production() -> bool:
    return os.getenv("INFINITYRX_ENV", "development").lower() == "production"


def _block_in_production() -> None:
    """Route-level dependency: fail fast with 403 before DBSession resolves.

    Ensures production environments reject the request before the seed
    handler touches the database.
    """
    if _is_production():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seed endpoint is not available in production environments.",
        )


def _get_session() -> Session:
    """Return a live DB session using the module's session factory."""
    from src.db.session import get_db_session  # noqa: PLC0415
    return get_db_session().__enter__()


class SeedRequest(BaseModel):
    tenant_id: str = "t0000000-0000-0000-0000-000000000001"


def _load_seed_file(stem: str) -> list[dict[str, Any]]:
    path = _SEEDS_DIR / f"{stem}.json"
    if not path.exists():
        logger.warning("billing.seed: fixture file not found — %s", path)
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _upsert_rows(
    session: Session,
    table_name: str,
    rows: list[dict[str, Any]],
    tenant_id: str,
) -> int:
    """Insert rows that don't already exist by primary key.

    Uses SQLite-compatible INSERT OR IGNORE / PostgreSQL INSERT ... ON CONFLICT
    DO NOTHING via a raw SQL branch so tests (SQLite) and production (Postgres)
    both work.
    """
    if not rows:
        return 0

    dialect = session.bind.dialect.name if session.bind else "sqlite"
    inserted = 0

    for row in rows:
        # Normalise tenant_id to match the request (seed files use demo IDs).
        row = dict(row)
        row["tenant_id"] = tenant_id  # B4 fix: normalize tenant for cross-tenant safety

        # Build INSERT statement appropriate for the dialect.
        cols = list(row.keys())
        placeholders = ", ".join(f":{c}" for c in cols)
        col_list = ", ".join(cols)

        if dialect == "postgresql":
            sql = text(
                f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"
                " ON CONFLICT DO NOTHING"
            )
        else:
            sql = text(
                f"INSERT OR IGNORE INTO {table_name} ({col_list}) VALUES ({placeholders})"
            )

        try:
            result = session.execute(sql, row)
            inserted += result.rowcount or 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("billing.seed: skipping row in %s — %s", table_name, exc)
            session.rollback()

    return inserted


@router.post("/seed", status_code=status.HTTP_200_OK, dependencies=[Depends(_block_in_production)])
async def seed_billing_fixtures(
    body: SeedRequest, request: Request, session: DBSession
) -> JSONResponse:
    """Seed paysync fixture data into the billing DB.

    Blocked in production. Idempotent -- safe to call multiple times.
    Uses the DBSession dependency so test fixtures can override the engine.
    """
    if _is_production():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seed endpoint is not available in production environments.",
        )

    inserted_totals: dict[str, int] = {}

    try:
        for stem in _INSERT_ORDER:
            table = _TABLE_MAP.get(stem)
            if table is None:
                continue
            rows = _load_seed_file(stem)
            count = _upsert_rows(session, table, rows, body.tenant_id)
            inserted_totals[stem] = count
        session.commit()
    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        logger.exception("billing.seed: seed failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Seed failed: {exc}",
        ) from exc

    total = sum(inserted_totals.values())
    logger.info("billing.seed: seeded %d rows", total)
    return JSONResponse(
        content={"seeded": True, "inserted": total, "by_table": inserted_totals}
    )


@router.delete("/seed", status_code=status.HTTP_200_OK, dependencies=[Depends(_block_in_production)])
async def cleanup_billing_fixtures(
    body: SeedRequest, request: Request, session: DBSession
) -> JSONResponse:
    """Truncate paysync fixture data from the billing DB.

    Blocked in production. Used by Playwright afterAll hooks.
    Truncates in FK-safe dependency order (children first).
    Uses the DBSession dependency so test fixtures can override the engine.
    """
    if _is_production():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seed endpoint is not available in production environments.",
        )

    deleted_totals: dict[str, int] = {}

    try:
        for stem in _TRUNCATE_ORDER:
            table = _TABLE_MAP.get(stem)
            if table is None:
                continue
            try:
                result = session.execute(
                    text(f"DELETE FROM {table} WHERE tenant_id = :tid"),
                    {"tid": body.tenant_id},
                )
                deleted_totals[stem] = result.rowcount or 0
            except Exception as exc:  # noqa: BLE001
                logger.warning("billing.seed cleanup: error on %s -- %s", table, exc)
                session.rollback()
        session.commit()
    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        logger.exception("billing.seed: cleanup failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cleanup failed: {exc}",
        ) from exc

    total = sum(deleted_totals.values())
    logger.info("billing.seed: cleaned up %d rows", total)
    return JSONResponse(
        content={"cleaned": True, "deleted": total, "by_table": deleted_totals}
    )
