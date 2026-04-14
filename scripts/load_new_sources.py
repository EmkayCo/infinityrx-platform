"""Run any of the 6 new ingesters against the live DB.

Usage:
    python scripts/load_new_sources.py <source>

where <source> is one of:
    rxnorm, fda_rems, fda_purple_book, fda_drug_shortages,
    medicare_opt_out, medicare_part_d, oig_leie

Sets the DB URL, wires module-specific sys.path inserts, instantiates
the ingester, runs it via .run(run_type="manual_trigger"), and prints
a summary line.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _setup_sys_path(source: str) -> None:
    paths = [_REPO_ROOT]
    if source.startswith("rxnorm") or source.startswith("fda_"):
        paths.append(_REPO_ROOT / "modules" / "drug-database")
    if source.startswith("medicare_") or source.startswith("oig_") or source.startswith("dea_") or source.startswith("sam_"):
        paths.append(_REPO_ROOT / "modules" / "prescriber-directory")
    if source.startswith("oig_") or source.startswith("sam_"):
        paths.append(_REPO_ROOT / "modules" / "pharmacy-directory")
    for p in paths:
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)


def _ingester_for(source: str, db_session):
    if source == "rxnorm":
        from shared.data_ingestion.sources.rxnorm import RxNormIngester
        return RxNormIngester(db_session=db_session)
    if source == "fda_rems":
        from shared.data_ingestion.sources.fda_rems import FdaRemsIngester
        return FdaRemsIngester(db_session=db_session)
    if source == "fda_drug_shortages":
        from shared.data_ingestion.sources.fda_drug_shortages import FdaDrugShortagesIngester
        return FdaDrugShortagesIngester(db_session=db_session)
    if source == "fda_purple_book":
        from shared.data_ingestion.sources.fda_purple_book import FdaPurpleBookIngester
        return FdaPurpleBookIngester(db_session=db_session)
    if source == "medicare_opt_out":
        from shared.data_ingestion.sources.cms_opt_out import CmsOptOutIngester
        return CmsOptOutIngester(db_session=db_session)
    if source == "medicare_part_d":
        from shared.data_ingestion.sources.cms_part_d_prescriber import CmsPartDPrescriberIngester
        return CmsPartDPrescriberIngester(db_session=db_session)
    if source == "oig_leie":
        from shared.data_ingestion.sources.oig_leie import OigLeieIngester
        return OigLeieIngester(db_session=db_session)
    raise ValueError(f"Unknown source: {source}")


async def main(source: str) -> int:
    _setup_sys_path(source)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL_SYNC required", file=sys.stderr)
        return 1
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    engine = create_engine(db_url, echo=False)
    with Session(engine) as session:
        ingester = _ingester_for(source, session)
        result = await ingester.run(run_type="manual_trigger")

    print("=" * 60)
    print(f"{source.upper()}: status={result.status}")
    print(f"  records_in_source:  {result.records_in_source:,}")
    print(f"  records_inserted:   {result.records_inserted:,}")
    print(f"  records_updated:    {result.records_updated:,}")
    print(f"  records_errored:    {result.records_errored:,}")
    print(f"  duration:           {result.duration_seconds:.1f}s")
    if result.error_message:
        print(f"  error: {result.error_message}")
    print("=" * 60)
    return 0 if result.status in {"completed", "skipped_unchanged"} else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.source)))
