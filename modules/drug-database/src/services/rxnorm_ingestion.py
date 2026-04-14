"""RxNorm bulk upsert service.

Handles streaming batch upserts for all four RxNorm core tables plus the
two derived crosswalk tables. All upserts use PostgreSQL INSERT ON CONFLICT
DO UPDATE. Crosswalks are built from stored data via SQL INSERT...SELECT.

No floats. No tenant scope. Global reference data per LESSON-011.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from shared.data_ingestion.base import IngestionResult

logger = logging.getLogger(__name__)

_BATCH_SIZE = 1000


class RxNormIngestionService:
    """Bulk-upsert service for all RxNorm tables.

    Accepts parsed record dicts tagged with ``_file`` key indicating
    which RRF file they originated from. Routes each record to the
    correct table and upserts in batches of 1000.
    """

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    async def load_records(
        self,
        records: Iterator[dict[str, Any]],
        source_name: str = "rxnorm",
    ) -> IngestionResult:
        """Load all RxNorm records and build crosswalk tables.

        Consumes the iterator, routes by ``_file`` key to the correct
        table, upserts in batches, then builds the two crosswalk tables.
        """
        from src.models.rxnorm_tables import (  # type: ignore[import]
            RxNormAttribute,
            RxNormConcept,
            RxNormRelationship,
            RxNormSemanticType,
        )

        buffers: dict[str, list[dict[str, Any]]] = {
            "RXNCONSO": [],
            "RXNREL": [],
            "RXNSAT": [],
            "RXNSTY": [],
        }

        counters = {"inserted": 0, "updated": 0, "errored": 0, "processed": 0}

        table_map = {
            "RXNCONSO": (RxNormConcept, self._upsert_concepts),
            "RXNREL": (RxNormRelationship, self._upsert_relationships),
            "RXNSAT": (RxNormAttribute, self._upsert_attributes),
            "RXNSTY": (RxNormSemanticType, self._upsert_semantic_types),
        }

        for record in records:
            file_key = record.pop("_file", None)
            if file_key not in buffers:
                counters["errored"] += 1
                continue

            buffers[file_key].append(record)
            counters["processed"] += 1

            if len(buffers[file_key]) >= _BATCH_SIZE:
                ins, upd, err = table_map[file_key][1](buffers[file_key])
                counters["inserted"] += ins
                counters["updated"] += upd
                counters["errored"] += err
                buffers[file_key] = []

        # Flush remaining
        for file_key, batch in buffers.items():
            if batch:
                ins, upd, err = table_map[file_key][1](batch)
                counters["inserted"] += ins
                counters["updated"] += upd
                counters["errored"] += err

        self._db.flush()

        # Build derived crosswalk tables
        ndc_ins, ndc_err = self._build_ndc_crosswalk()
        atc_ins, atc_err = self._build_atc_crosswalk()
        counters["inserted"] += ndc_ins + atc_ins
        counters["errored"] += ndc_err + atc_err

        self._db.flush()

        logger.info(
            "RxNorm load complete",
            extra={
                "ingest_source": source_name,
                "ingest_records_inserted": counters["inserted"],
                "ingest_records_errored": counters["errored"],
            },
        )

        return IngestionResult(
            source=source_name,
            status="completed",
            records_processed=counters["processed"],
            records_inserted=counters["inserted"],
            records_updated=counters["updated"],
            records_errored=counters["errored"],
        )

    def _upsert_concepts(self, batch: list[dict[str, Any]]) -> tuple[int, int, int]:
        from src.models.rxnorm_tables import RxNormConcept  # type: ignore[import]

        inserted = updated = errored = 0
        try:
            stmt = pg_insert(RxNormConcept).values(batch)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_rxnorm_concepts_rxcui_rxaui",
                set_={
                    "lat": stmt.excluded.lat,
                    "ts": stmt.excluded.ts,
                    "lui": stmt.excluded.lui,
                    "stt": stmt.excluded.stt,
                    "sui": stmt.excluded.sui,
                    "ispref": stmt.excluded.ispref,
                    "saui": stmt.excluded.saui,
                    "scui": stmt.excluded.scui,
                    "sdui": stmt.excluded.sdui,
                    "sab": stmt.excluded.sab,
                    "tty": stmt.excluded.tty,
                    "code": stmt.excluded.code,
                    "str": stmt.excluded.str,
                    "srl": stmt.excluded.srl,
                    "suppress": stmt.excluded.suppress,
                    "cvf": stmt.excluded.cvf,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            result = self._db.execute(stmt)
            inserted = result.rowcount
        except Exception:
            logger.exception(
                "RxNorm concepts upsert error",
                extra={"ingest_source": "rxnorm", "ingest_batch_size": len(batch)},
            )
            errored = len(batch)
        return inserted, updated, errored

    def _upsert_relationships(self, batch: list[dict[str, Any]]) -> tuple[int, int, int]:
        from src.models.rxnorm_tables import RxNormRelationship  # type: ignore[import]

        inserted = updated = errored = 0
        try:
            stmt = pg_insert(RxNormRelationship).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["rui"],
                set_={
                    "rxcui1": stmt.excluded.rxcui1,
                    "rxaui1": stmt.excluded.rxaui1,
                    "stype1": stmt.excluded.stype1,
                    "rel": stmt.excluded.rel,
                    "rxcui2": stmt.excluded.rxcui2,
                    "rxaui2": stmt.excluded.rxaui2,
                    "stype2": stmt.excluded.stype2,
                    "rela": stmt.excluded.rela,
                    "srui": stmt.excluded.srui,
                    "sab": stmt.excluded.sab,
                    "sl": stmt.excluded.sl,
                    "rg": stmt.excluded.rg,
                    "dir": stmt.excluded.dir,
                    "suppress": stmt.excluded.suppress,
                    "cvf": stmt.excluded.cvf,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            result = self._db.execute(stmt)
            inserted = result.rowcount
        except Exception:
            logger.exception(
                "RxNorm relationships upsert error",
                extra={"ingest_source": "rxnorm", "ingest_batch_size": len(batch)},
            )
            errored = len(batch)
        return inserted, updated, errored

    def _upsert_attributes(self, batch: list[dict[str, Any]]) -> tuple[int, int, int]:
        from src.models.rxnorm_tables import RxNormAttribute  # type: ignore[import]

        inserted = updated = errored = 0
        try:
            stmt = pg_insert(RxNormAttribute).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["atui"],
                set_={
                    "rxcui": stmt.excluded.rxcui,
                    "lui": stmt.excluded.lui,
                    "sui": stmt.excluded.sui,
                    "rxaui": stmt.excluded.rxaui,
                    "stype": stmt.excluded.stype,
                    "code": stmt.excluded.code,
                    "satui": stmt.excluded.satui,
                    "atn": stmt.excluded.atn,
                    "sab": stmt.excluded.sab,
                    "atv": stmt.excluded.atv,
                    "suppress": stmt.excluded.suppress,
                    "cvf": stmt.excluded.cvf,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            result = self._db.execute(stmt)
            inserted = result.rowcount
        except Exception:
            logger.exception(
                "RxNorm attributes upsert error",
                extra={"ingest_source": "rxnorm", "ingest_batch_size": len(batch)},
            )
            errored = len(batch)
        return inserted, updated, errored

    def _upsert_semantic_types(self, batch: list[dict[str, Any]]) -> tuple[int, int, int]:
        from src.models.rxnorm_tables import RxNormSemanticType  # type: ignore[import]

        inserted = updated = errored = 0
        try:
            stmt = pg_insert(RxNormSemanticType).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["atui"],
                set_={
                    "rxcui": stmt.excluded.rxcui,
                    "tui": stmt.excluded.tui,
                    "stn": stmt.excluded.stn,
                    "sty": stmt.excluded.sty,
                    "cvf": stmt.excluded.cvf,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            result = self._db.execute(stmt)
            inserted = result.rowcount
        except Exception:
            logger.exception(
                "RxNorm semantic types upsert error",
                extra={"ingest_source": "rxnorm", "ingest_batch_size": len(batch)},
            )
            errored = len(batch)
        return inserted, updated, errored

    def _build_ndc_crosswalk(self) -> tuple[int, int]:
        """Build rxnorm_ndc_crosswalk from rxnorm_attributes + rxnorm_concepts.

        Selects RXNSAT rows where ATN='NDC', joins to preferred atom in RXNCONSO
        (where ISPREF='Y' and LAT='ENG') for drug name and TTY.
        Uses INSERT...ON CONFLICT DO UPDATE.
        """
        try:
            sql = text("""
                INSERT INTO drug_database.rxnorm_ndc_crosswalk (ndc_11, rxcui, drug_name, tty, created_at, updated_at)
                SELECT
                    SUBSTRING(ra.atv FROM 1 FOR 11) AS ndc_11,
                    ra.rxcui,
                    rc.str AS drug_name,
                    rc.tty,
                    NOW(),
                    NOW()
                FROM drug_database.rxnorm_attributes ra
                LEFT JOIN drug_database.rxnorm_concepts rc
                    ON rc.rxcui = ra.rxcui
                    AND rc.ispref = 'Y'
                    AND rc.lat = 'ENG'
                WHERE ra.atn = 'NDC'
                  AND ra.atv IS NOT NULL
                  AND LENGTH(ra.atv) >= 11
                ON CONFLICT (ndc_11) DO UPDATE
                    SET rxcui = EXCLUDED.rxcui,
                        drug_name = EXCLUDED.drug_name,
                        tty = EXCLUDED.tty,
                        updated_at = NOW()
            """)
            result = self._db.execute(sql)
            return result.rowcount, 0
        except Exception:
            logger.exception(
                "RxNorm NDC crosswalk build error",
                extra={"ingest_source": "rxnorm"},
            )
            return 0, 1

    def _build_atc_crosswalk(self) -> tuple[int, int]:
        """Build rxnorm_atc_crosswalk from rxnorm_attributes and rxnorm_concepts.

        Combines:
        - RXNSAT rows where ATN='ATC' (atv contains ATC code)
        - RXNCONSO rows where SAB='ATC' (code contains ATC code, str contains name)
        Uses INSERT...ON CONFLICT DO UPDATE.
        """
        try:
            sql = text("""
                INSERT INTO drug_database.rxnorm_atc_crosswalk (rxcui, atc_code, atc_level, atc_name, created_at, updated_at)
                SELECT
                    rxcui,
                    atc_code,
                    CASE
                        WHEN LENGTH(atc_code) = 1 THEN '1'
                        WHEN LENGTH(atc_code) = 3 THEN '2'
                        WHEN LENGTH(atc_code) = 4 THEN '3'
                        WHEN LENGTH(atc_code) = 5 THEN '4'
                        ELSE '5'
                    END AS atc_level,
                    atc_name,
                    NOW(),
                    NOW()
                FROM (
                    SELECT ra.rxcui, ra.atv AS atc_code, rc.str AS atc_name
                    FROM drug_database.rxnorm_attributes ra
                    LEFT JOIN drug_database.rxnorm_concepts rc
                        ON rc.rxcui = ra.rxcui AND rc.sab = 'ATC' AND rc.ispref = 'Y'
                    WHERE ra.atn = 'ATC' AND ra.atv IS NOT NULL

                    UNION

                    SELECT rc.rxcui, rc.code AS atc_code, rc.str AS atc_name
                    FROM drug_database.rxnorm_concepts rc
                    WHERE rc.sab = 'ATC' AND rc.code IS NOT NULL
                ) combined
                ON CONFLICT ON CONSTRAINT uq_rxnorm_atc_crosswalk DO UPDATE
                    SET atc_level = EXCLUDED.atc_level,
                        atc_name = EXCLUDED.atc_name,
                        updated_at = NOW()
            """)
            result = self._db.execute(sql)
            return result.rowcount, 0
        except Exception:
            logger.exception(
                "RxNorm ATC crosswalk build error",
                extra={"ingest_source": "rxnorm"},
            )
            return 0, 1

    def upsert_ndc_crosswalk_row(
        self,
        ndc_11: str,
        rxcui: str | None,
        drug_name: str | None,
        tty: str | None,
    ) -> None:
        """Direct upsert of a single NDC crosswalk row (used in tests)."""
        from src.models.rxnorm_tables import RxNormNDCCrosswalk  # type: ignore[import]

        stmt = pg_insert(RxNormNDCCrosswalk).values(
            ndc_11=ndc_11,
            rxcui=rxcui,
            drug_name=drug_name,
            tty=tty,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["ndc_11"],
            set_={
                "rxcui": stmt.excluded.rxcui,
                "drug_name": stmt.excluded.drug_name,
                "tty": stmt.excluded.tty,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        self._db.execute(stmt)

    def upsert_atc_crosswalk_row(
        self,
        rxcui: str,
        atc_code: str,
        atc_level: str | None = None,
        atc_name: str | None = None,
    ) -> None:
        """Direct upsert of a single ATC crosswalk row (used in tests)."""
        from src.models.rxnorm_tables import RxNormATCCrosswalk  # type: ignore[import]

        stmt = pg_insert(RxNormATCCrosswalk).values(
            rxcui=rxcui,
            atc_code=atc_code,
            atc_level=atc_level,
            atc_name=atc_name,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_rxnorm_atc_crosswalk",
            set_={
                "atc_level": stmt.excluded.atc_level,
                "atc_name": stmt.excluded.atc_name,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        self._db.execute(stmt)


__all__ = ["RxNormIngestionService"]
