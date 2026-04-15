"""Load JUST RxNorm concepts from cached RXNCONSO.RRF (avoids full re-parse).

Used when concepts batch failed during a full RxNorm load and we want to
backfill without re-parsing 15M records across 4 files.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (_REPO_ROOT, _REPO_ROOT / "modules" / "drug-database"):
    sp = str(_p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(message)s")
logger = logging.getLogger("load_rxnorm_concepts")

_RRF_PATH = Path("/tmp/ifx_ingest/rxnorm/extracted/rrf/RXNCONSO.RRF")
_BATCH = 5000

_FIELDS = ["rxcui", "lat", "ts", "lui", "stt", "sui", "ispref", "rxaui", "saui",
           "scui", "sdui", "sab", "tty", "code", "str", "srl", "suppress", "cvf"]


def _parse_line(line: str) -> dict | None:
    parts = line.rstrip("\n").split("|")
    # RXNCONSO has 18 fields. Each line ends with a trailing pipe so split
    # yields 19 parts (last is empty). Don't rstrip pipes — that drops
    # legitimate trailing empty fields and gives 17 parts.
    if len(parts) < 18:
        return None
    record = dict(zip(_FIELDS, parts[:18]))
    for k in record:
        record[k] = record[k] or None
    return record


def main() -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.orm import Session
    from src.models.rxnorm_tables import RxNormConcept  # type: ignore[import]

    db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    engine = create_engine(db_url, echo=False)

    if not _RRF_PATH.exists():
        logger.error("RXNCONSO.RRF not found at %s", _RRF_PATH)
        return 1

    inserted = errored = total = 0
    now = datetime.now(UTC)

    with Session(engine) as session, _RRF_PATH.open(encoding="utf-8", errors="replace") as fh:
        batch: list[dict] = []
        for line in fh:
            rec = _parse_line(line)
            if rec is None:
                continue
            rec["created_at"] = now
            rec["updated_at"] = now
            batch.append(rec)
            total += 1

            if len(batch) >= _BATCH:
                try:
                    stmt = pg_insert(RxNormConcept).values(batch)
                    stmt = stmt.on_conflict_do_update(
                        constraint="uq_rxnorm_concepts_rxcui_rxaui",
                        set_={c.name: getattr(stmt.excluded, c.name)
                              for c in RxNormConcept.__table__.columns
                              if c.name not in ("rxcui", "rxaui", "created_at")},
                    )
                    result = session.execute(stmt)
                    session.commit()
                    inserted += result.rowcount or 0
                except Exception as exc:
                    session.rollback()
                    errored += len(batch)
                    logger.warning("batch error: %s", str(exc)[:200])
                if total % 50_000 == 0:
                    logger.info("Progress: %d parsed, %d inserted, %d errored", total, inserted, errored)
                batch = []

        if batch:
            try:
                stmt = pg_insert(RxNormConcept).values(batch)
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_rxnorm_concepts_rxcui_rxaui",
                    set_={c.name: getattr(stmt.excluded, c.name)
                          for c in RxNormConcept.__table__.columns
                          if c.name not in ("rxcui", "rxaui", "created_at")},
                )
                result = session.execute(stmt)
                session.commit()
                inserted += result.rowcount or 0
            except Exception as exc:
                session.rollback()
                errored += len(batch)
                logger.warning("final batch error: %s", str(exc)[:200])

    logger.info("DONE total=%d inserted=%d errored=%d", total, inserted, errored)
    return 0


if __name__ == "__main__":
    sys.exit(main())
