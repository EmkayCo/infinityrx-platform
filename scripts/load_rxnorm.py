"""Load RxNorm into drug_database.

Downloads RxNorm from NLM (full release with UMLS_API_KEY, or the no-auth
prescribable subset as fallback), extracts the ZIP, streams the four RRF
files through the shared batching primitives, and populates:

  drug_database.rxnorm_concepts        (RXNCONSO.RRF)
  drug_database.rxnorm_relationships   (RXNREL.RRF)
  drug_database.rxnorm_attributes      (RXNSAT.RRF)
  drug_database.rxnorm_semantic_types  (RXNSTY.RRF)
  drug_database.rxnorm_ndc_crosswalk   (derived via SQL from attributes)
  drug_database.rxnorm_atc_crosswalk   (derived via SQL)

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_rxnorm.py [--dry-run] [--sample N]

Options:
    --dry-run     Download + parse without DB load; report per-file record counts.
    --sample N    Only process the first N records yielded by the parser.
                  Useful for dev/CI runs of the full release (~15M records).

Environment:
    DATABASE_URL_SYNC — set by switch_env.sh
    UMLS_API_KEY      — optional; full release requires this. Falls back to
                        the no-auth prescribable subset when unset.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DRUG_DB_ROOT = _REPO_ROOT / "modules" / "drug-database"
for _p in (str(_REPO_ROOT), str(_DRUG_DB_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
)
logger = logging.getLogger("load_rxnorm")


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        logger.error(
            "DATABASE_URL_SYNC not set. "
            "Run: source infrastructure/scripts/switch_env.sh dev"
        )
        sys.exit(1)
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _dry_run(sample: int | None) -> None:
    """Download + parse without DB; report per-file record counts."""
    from collections import Counter
    from unittest.mock import MagicMock

    from shared.data_ingestion.sources.rxnorm import RxNormIngester

    ingester = RxNormIngester(db_session=MagicMock())

    logger.info("Downloading RxNorm ZIP...")
    extract_dir = await ingester.download()

    parse_iter = ingester.parse(extract_dir)
    if sample is not None and sample > 0:
        parse_iter = itertools.islice(parse_iter, sample)

    counts: Counter[str] = Counter()
    for record in parse_iter:
        counts[record.get("_file", "UNKNOWN")] += 1

    print(f"\n{'=' * 60}")
    print("RxNorm DRY-RUN record counts")
    print(f"{'=' * 60}")
    for file_key, count in sorted(counts.items()):
        print(f"  {file_key:20s}  {count:>12,}")
    print(f"{'=' * 60}")


async def _run(sample: int | None) -> None:
    """Full pipeline: download → parse → load via shared primitives."""
    import itertools as _it

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from shared.data_ingestion.sources.rxnorm import RxNormIngester

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    with Session(engine) as session:
        ingester = RxNormIngester(db_session=session)

        if sample is not None and sample > 0:
            original_parse = ingester.parse

            def _capped_parse(file_path):
                return _it.islice(original_parse(file_path), sample)

            ingester.parse = _capped_parse  # type: ignore[method-assign]
            logger.info("--sample %d: parser will yield at most %d records", sample, sample)

        logger.info("Starting RxNorm pipeline...")
        result = await ingester.run(run_type="manual_trigger")

    if result.status == "failed":
        logger.error("Ingest failed: %s", getattr(result, "error_message", "unknown"))
        sys.exit(2)

    print(f"\n{'=' * 60}")
    print("RxNorm Load Result")
    print(f"{'=' * 60}")
    print(f"  Status:             {result.status}")
    print(f"  Records in source:  {result.records_in_source:,}")
    print(f"  Records processed:  {result.records_processed:,}")
    print(f"  Records inserted:   {result.records_inserted:,}")
    print(f"  Records updated:    {result.records_updated:,}")
    print(f"  Records skipped:    {result.records_skipped:,}")
    print(f"  Records errored:    {result.records_errored:,}")
    print(f"  Duration:           {result.duration_seconds:.1f}s")
    if result.error_message:
        print(f"  Error:              {result.error_message}")
    print(f"{'=' * 60}")

    with engine.connect() as conn:
        for table in (
            "rxnorm_concepts",
            "rxnorm_relationships",
            "rxnorm_attributes",
            "rxnorm_semantic_types",
            "rxnorm_ndc_crosswalk",
            "rxnorm_atc_crosswalk",
        ):
            cnt = conn.execute(
                text(f"SELECT count(*) FROM drug_database.{table}")
            ).scalar()
            print(f"  drug_database.{table}: {cnt:,} rows")

    if result.records_errored > 0:
        logger.error("Non-zero error count: %d — check logs", result.records_errored)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load RxNorm")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download + parse without DB load (prints record counts only)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Only process the first N records (full release is ~15M; "
        "prescribable subset is ~1-2M)",
    )
    args = parser.parse_args()
    asyncio.run(_dry_run(args.sample) if args.dry_run else _run(args.sample))


if __name__ == "__main__":
    main()
