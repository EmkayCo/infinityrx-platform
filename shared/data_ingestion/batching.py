"""Batched upsert and scoped-replace primitives for reference-data loaders.

This module solves the repeating bug pattern that plagued every hand-written
loader in the codebase:

- **BUG-01 / 02 / 03 / 05** — single-transaction rollback. A late failure
  wiped every earlier batch. Fixed here by per-batch commit inside the loop.
- **BUG-01a / 02a / 05a** — duplicate natural keys within a single batch
  triggered ``UniqueViolation`` because ``ON CONFLICT ... DO UPDATE`` does not
  tolerate multiple rows with the same ``unique_key`` in the same VALUES list
  (Postgres spec: "the target row cannot be affected more than once").
  Fixed here by in-batch dedup on ``unique_key`` BEFORE the upsert.
- **BUG-03a** — opaque error accounting. We had 478K errored rows for weeks
  with no idea which code path owned them. Fixed here by an
  :class:`ErrorAggregator` that tracks the top-N distinct error messages with
  counts and logs them at the end of every run.

The two primitives are:

- :class:`BatchedUpserter` — streaming batched UPSERT by a single ``unique_key``
  (possibly composite). Handles new + update detection; can optionally emit
  "history row on change" inserts. Used by FDA NDC drugs, NADAC pricing, ASP
  pricing, NCPDP main pharmacy table, SAM exclusions, OIG LEIE, etc.

- :class:`ScopedReplacer` — streaming batched "delete-then-insert" for child
  tables whose rows are fully replaced per parent key (e.g., all patent rows
  for an Orange Book product, all medicaid rows for a given NCPDP provider).
  In-batch dedup still applies so cardinality violations on composite unique
  constraints are prevented.

All primitives use synchronous SQLAlchemy sessions — global reference-data
ingestion is cross-tenant and runs in a separate transactional scope from the
tenant-scoped async API sessions (LESSON-011).
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from shared.data_ingestion.base import IngestionResult

logger = logging.getLogger(__name__)

_DEFAULT_BATCH_SIZE = 1_000
_DEFAULT_PROGRESS_BATCHES = 100
_MAX_ERROR_SAMPLES = 5

# Columns we never overwrite on conflict. created_at must survive the upsert.
_DEFAULT_IMMUTABLE_ON_UPDATE: tuple[str, ...] = ("id", "created_at")


# ---------------------------------------------------------------------------
# Error aggregation
# ---------------------------------------------------------------------------


@dataclass
class ErrorAggregator:
    """Tracks error counts by message so we know which path owns the errors.

    Every error increments the counter for its normalised message. At the end
    of the run we log the top-N messages with counts. This is the diagnostic
    that would have found BUG-03a in 30 seconds instead of 3 sessions.
    """

    counts: Counter[str] = field(default_factory=Counter)
    samples: list[dict[str, Any]] = field(default_factory=list)
    total_errors: int = 0

    def record(self, error_kind: str, message: str, raw_row: Any = None) -> None:
        """Record one error. ``error_kind`` buckets distinct failure reasons."""
        self.total_errors += 1
        key = f"{error_kind}: {message[:200]}"
        self.counts[key] += 1
        if len(self.samples) < _MAX_ERROR_SAMPLES:
            self.samples.append(
                {
                    "kind": error_kind,
                    "message": message[:500],
                    "raw_row": str(raw_row)[:500] if raw_row is not None else None,
                }
            )

    def log_summary(self, *, source_name: str, top_n: int = 5) -> None:
        """Log the top-N distinct error messages with counts."""
        if not self.counts:
            return
        top = self.counts.most_common(top_n)
        for msg, count in top:
            logger.warning(
                "Loader error bucket",
                extra={
                    "ingest_source": source_name,
                    "ingest_error_kind": msg,
                    "ingest_error_count": count,
                },
            )


# ---------------------------------------------------------------------------
# Upsert configuration
# ---------------------------------------------------------------------------


@dataclass
class HistoryConfig:
    """Declarative history-row behaviour for :class:`BatchedUpserter`.

    When a primary row is inserted (new) or updated (changed per the
    ``change_detector`` callback), we emit a corresponding row to the
    ``table`` with ``ON CONFLICT DO NOTHING`` on ``unique_key``.

    The ``change_detector`` callback is called with ``(previous_current_row,
    new_row) -> bool``. If ``None``, we always emit a history row for both
    new and existing rows.
    """

    table: Table
    unique_key: list[str]
    build_history_row: Callable[[dict[str, Any]], dict[str, Any]]
    change_detector: Callable[[dict[str, Any], dict[str, Any]], bool] | None = None


@dataclass
class BatchedUpserter:
    """Streaming batched upsert by ``unique_key`` with per-batch commit.

    The caller provides:

    * ``table`` — SQLAlchemy ``Table`` object for the target (e.g.,
      ``Drug.__table__``).
    * ``unique_key`` — list of column names that form the ON CONFLICT target
      index (typically one, occasionally composite like ``(ndc_11,
      effective_date, as_of_date)``).
    * ``validate`` — optional per-row callback that transforms a raw dict into
      the final row dict, or raises ``ValueError`` to reject the row. The
      raise path is what drives the error-bucket diagnostics.
    * ``dedup_selector`` — optional callable returning the dedup key tuple
      when it differs from ``unique_key`` (e.g., keep latest by date).
    * ``prefer_row`` — when two rows dedup to the same key, this callable
      ``(existing_row, new_row) -> dict`` picks the winner. Defaults to
      last-seen (``new_row``).
    * ``history`` — optional ``HistoryConfig`` to emit history rows on insert
      and change.
    * ``immutable_on_update`` — tuple of column names to EXCLUDE from the
      ``SET`` clause of ``ON CONFLICT DO UPDATE`` (defaults to ``id`` +
      ``created_at``).
    * ``batch_size`` — commit after this many rows (default 1000).
    """

    db: Session
    source_name: str
    table: Table
    unique_key: list[str]
    validate: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    dedup_selector: Callable[[dict[str, Any]], tuple[Any, ...]] | None = None
    prefer_row: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None
    history: HistoryConfig | None = None
    immutable_on_update: tuple[str, ...] = _DEFAULT_IMMUTABLE_ON_UPDATE
    batch_size: int = _DEFAULT_BATCH_SIZE
    progress_every_batches: int = _DEFAULT_PROGRESS_BATCHES

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def load(self, records: Iterable[dict[str, Any]]) -> IngestionResult:
        """Iterate ``records``, batch, upsert, commit per batch."""
        errors = ErrorAggregator()
        processed = 0
        inserted = 0
        updated = 0
        batch_count = 0
        dedup_dropped = 0

        batch: list[dict[str, Any]] = []
        for raw in records:
            processed += 1
            try:
                row = self.validate(raw) if self.validate else raw
            except ValueError as exc:
                errors.record("validation", str(exc), raw_row=raw)
                continue

            batch.append(row)
            if len(batch) >= self.batch_size:
                batch_count += 1
                batch, ins, upd, dd = self._flush_batch(batch, errors, batch_count)
                inserted += ins
                updated += upd
                dedup_dropped += dd
                batch = []
                if batch_count % self.progress_every_batches == 0:
                    logger.info(
                        "Loader progress",
                        extra={
                            "ingest_source": self.source_name,
                            "ingest_batches_complete": batch_count,
                            "ingest_records_processed": processed,
                            "ingest_records_inserted": inserted,
                            "ingest_records_updated": updated,
                            "ingest_records_errored": errors.total_errors,
                        },
                    )

        if batch:
            batch_count += 1
            _, ins, upd, dd = self._flush_batch(batch, errors, batch_count)
            inserted += ins
            updated += upd
            dedup_dropped += dd

        errors.log_summary(source_name=self.source_name)

        logger.info(
            "Loader batched upsert complete",
            extra={
                "ingest_source": self.source_name,
                "ingest_batches": batch_count,
                "ingest_records_processed": processed,
                "ingest_records_inserted": inserted,
                "ingest_records_updated": updated,
                "ingest_records_errored": errors.total_errors,
                "ingest_records_deduped": dedup_dropped,
            },
        )

        return IngestionResult(
            source=self.source_name,
            status="completed",
            records_processed=processed,
            records_inserted=inserted,
            records_updated=updated,
            records_skipped=dedup_dropped,
            records_errored=errors.total_errors,
        )

    # ------------------------------------------------------------------
    # Internal: batch flush
    # ------------------------------------------------------------------

    def _flush_batch(
        self,
        batch: list[dict[str, Any]],
        errors: ErrorAggregator,
        batch_number: int,
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        """Dedup → upsert → commit a single batch. Returns (new_batch, ins, upd, deduped)."""
        original_len = len(batch)
        deduped_batch = self._dedup_batch(batch)
        dedup_dropped = original_len - len(deduped_batch)

        # Detect new vs existing by pre-fetching current rows for the keys in batch
        existing: dict[tuple[Any, ...], dict[str, Any]] = {}
        if self.history is not None:
            existing = self._prefetch_existing(deduped_batch)

        now = datetime.now(UTC)
        enriched = [self._enrich_timestamps(r, now) for r in deduped_batch]

        inserted = 0
        updated = 0

        try:
            self._execute_upsert(enriched)

            # History rows — only after upsert succeeds so we don't emit history for failed inserts
            if self.history is not None:
                for row in deduped_batch:
                    key = tuple(row[c] for c in self.unique_key)
                    prev = existing.get(key)
                    if prev is None:
                        inserted += 1
                        self._insert_history_row(row)
                    else:
                        changed = (
                            self.history.change_detector(prev, row)
                            if self.history.change_detector is not None
                            else True
                        )
                        if changed:
                            updated += 1
                            self._insert_history_row(row)
                        # else: identical — no history row, no update counted
            else:
                # Without history tracking we conservatively count every deduped row
                # as "processed" and skip insert/update breakdown.
                inserted += len(deduped_batch)

            self.db.commit()

        except Exception as exc:  # noqa: BLE001 — broad to survive any DB error per batch
            self.db.rollback()
            msg = str(exc)
            # Bucket by the first 200 chars of the error so ON-CONFLICT / FK / truncation
            # errors each get their own bucket.
            errors.record(
                "batch_upsert",
                msg,
                raw_row={"batch_number": batch_number, "size": len(deduped_batch), "sample": deduped_batch[0] if deduped_batch else None},
            )
            errors.total_errors += len(deduped_batch) - 1  # -1 because record() already incremented once
            logger.exception(
                "Batch upsert failed — rolled back",
                extra={
                    "ingest_source": self.source_name,
                    "ingest_batch_number": batch_number,
                    "ingest_batch_size": len(deduped_batch),
                    "ingest_error": msg[:500],
                    "ingest_sample_row": str(deduped_batch[0] if deduped_batch else {})[:500],
                },
            )

        return [], inserted, updated, dedup_dropped

    def _dedup_batch(self, batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove duplicate rows by ``dedup_selector`` (defaults to ``unique_key``).

        When duplicates are found, ``prefer_row`` picks the winner (default:
        last-seen).
        """
        selector = self.dedup_selector or (lambda r: tuple(r[c] for c in self.unique_key))
        prefer = self.prefer_row or (lambda _existing, new: new)

        kept: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in batch:
            try:
                key = selector(row)
            except KeyError as exc:
                # Missing unique_key column in row — let DB enforce and bubble up.
                logger.warning(
                    "Dedup selector missing key — row passed through",
                    extra={"ingest_source": self.source_name, "ingest_missing_column": str(exc)},
                )
                kept[id(row)] = row  # type: ignore[index]
                continue
            if key in kept:
                kept[key] = prefer(kept[key], row)
            else:
                kept[key] = row
        return list(kept.values())

    def _prefetch_existing(
        self, batch: list[dict[str, Any]]
    ) -> dict[tuple[Any, ...], dict[str, Any]]:
        """Fetch current rows for the unique keys in this batch (history path only)."""
        if not batch:
            return {}
        from sqlalchemy import and_, or_, select

        # Build WHERE clause of ORed tuple matches for composite keys.
        if len(self.unique_key) == 1:
            col = self.table.c[self.unique_key[0]]
            values = [r[self.unique_key[0]] for r in batch]
            stmt = select(self.table).where(col.in_(values))
        else:
            predicates = [
                and_(*[self.table.c[col] == row[col] for col in self.unique_key])
                for row in batch
            ]
            stmt = select(self.table).where(or_(*predicates))

        result: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in self.db.execute(stmt).mappings():
            key = tuple(row[c] for c in self.unique_key)
            result[key] = dict(row)
        return result

    def _enrich_timestamps(self, row: dict[str, Any], now: datetime) -> dict[str, Any]:
        """Add ``created_at``/``updated_at`` if the table has them and they're missing."""
        enriched = dict(row)
        col_names = {c.name for c in self.table.columns}
        if "created_at" in col_names and "created_at" not in enriched:
            enriched["created_at"] = now
        if "updated_at" in col_names:
            enriched["updated_at"] = now
        return enriched

    def _execute_upsert(self, rows: list[dict[str, Any]]) -> None:
        """Execute one ``INSERT ... ON CONFLICT DO UPDATE`` for the batch."""
        if not rows:
            return
        stmt = pg_insert(self.table).values(rows)
        update_cols = {
            c.name: stmt.excluded[c.name]
            for c in self.table.columns
            if c.name not in self.unique_key and c.name not in self.immutable_on_update
        }
        if update_cols:
            stmt = stmt.on_conflict_do_update(
                index_elements=self.unique_key,
                set_=update_cols,
            )
        else:
            # Every column is in the unique key or immutable — nothing to update.
            stmt = stmt.on_conflict_do_nothing(index_elements=self.unique_key)
        self.db.execute(stmt)

    def _insert_history_row(self, source_row: dict[str, Any]) -> None:
        """Emit a history row — ON CONFLICT DO NOTHING on the history unique key."""
        assert self.history is not None
        hist_row = self.history.build_history_row(source_row)
        col_names = {c.name for c in self.history.table.columns}
        if "created_at" in col_names and "created_at" not in hist_row:
            hist_row["created_at"] = datetime.now(UTC)
        stmt = pg_insert(self.history.table).values([hist_row])
        stmt = stmt.on_conflict_do_nothing(index_elements=self.history.unique_key)
        self.db.execute(stmt)


# ---------------------------------------------------------------------------
# Scoped replacer — delete-then-insert for child tables per parent key
# ---------------------------------------------------------------------------


@dataclass
class ScopedReplacer:
    """Delete-then-insert child rows scoped to a parent key.

    Pattern used by NCPDP child tables (replace all medicaid / fwa-actions /
    coordinates rows for a given ``ncpdp_provider_id``), Orange Book patents
    (replace all patents for a given application), etc.

    Caller provides:

    * ``table`` — child table to write into.
    * ``scope_key`` — column(s) identifying the parent scope. Rows with a
      given scope_key value are deleted before this batch's new rows are
      inserted.
    * ``unique_key`` — composite unique constraint on the child table. Used
      for in-batch dedup so we don't violate the constraint with duplicate
      rows for the same parent from the same input file.

    Records are grouped by ``scope_key`` before flush so DELETEs are bundled
    per-parent.
    """

    db: Session
    source_name: str
    table: Table
    scope_key: list[str]
    unique_key: list[str]
    validate: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    batch_size: int = _DEFAULT_BATCH_SIZE
    progress_every_batches: int = _DEFAULT_PROGRESS_BATCHES

    def load(self, records: Iterable[dict[str, Any]]) -> IngestionResult:
        errors = ErrorAggregator()
        processed = 0
        inserted = 0
        dedup_dropped = 0
        batch_count = 0

        # Group rows by scope key so each flush can batch-delete the scopes it's replacing.
        scope_buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        pending_rows = 0

        for raw in records:
            processed += 1
            try:
                row = self.validate(raw) if self.validate else raw
            except ValueError as exc:
                errors.record("validation", str(exc), raw_row=raw)
                continue

            scope = tuple(row[c] for c in self.scope_key)
            scope_buckets.setdefault(scope, []).append(row)
            pending_rows += 1

            if pending_rows >= self.batch_size:
                batch_count += 1
                ins, dd = self._flush_scopes(scope_buckets, errors, batch_count)
                inserted += ins
                dedup_dropped += dd
                scope_buckets = {}
                pending_rows = 0
                if batch_count % self.progress_every_batches == 0:
                    logger.info(
                        "ScopedReplacer progress",
                        extra={
                            "ingest_source": self.source_name,
                            "ingest_table": self.table.name,
                            "ingest_batches_complete": batch_count,
                            "ingest_records_processed": processed,
                            "ingest_records_inserted": inserted,
                            "ingest_records_errored": errors.total_errors,
                        },
                    )

        if scope_buckets:
            batch_count += 1
            ins, dd = self._flush_scopes(scope_buckets, errors, batch_count)
            inserted += ins
            dedup_dropped += dd

        errors.log_summary(source_name=self.source_name)

        logger.info(
            "ScopedReplacer complete",
            extra={
                "ingest_source": self.source_name,
                "ingest_table": self.table.name,
                "ingest_records_processed": processed,
                "ingest_records_inserted": inserted,
                "ingest_records_errored": errors.total_errors,
                "ingest_records_deduped": dedup_dropped,
            },
        )

        return IngestionResult(
            source=self.source_name,
            status="completed",
            records_processed=processed,
            records_inserted=inserted,
            records_skipped=dedup_dropped,
            records_errored=errors.total_errors,
        )

    def _flush_scopes(
        self,
        scope_buckets: dict[tuple[Any, ...], list[dict[str, Any]]],
        errors: ErrorAggregator,
        batch_number: int,
    ) -> tuple[int, int]:
        """Delete + insert all pending scopes in a single transaction."""
        from sqlalchemy import and_, or_

        try:
            # Delete all rows whose scope key is in this batch
            scope_values = list(scope_buckets.keys())
            if scope_values:
                if len(self.scope_key) == 1:
                    col = self.table.c[self.scope_key[0]]
                    values = [k[0] for k in scope_values]
                    self.db.execute(self.table.delete().where(col.in_(values)))
                else:
                    predicates = [
                        and_(*[self.table.c[col] == val for col, val in zip(self.scope_key, key, strict=True)])
                        for key in scope_values
                    ]
                    self.db.execute(self.table.delete().where(or_(*predicates)))

            # Dedup each scope's rows by unique_key before insert
            to_insert: list[dict[str, Any]] = []
            dedup_dropped = 0
            for rows in scope_buckets.values():
                seen: dict[tuple[Any, ...], dict[str, Any]] = {}
                for row in rows:
                    key = tuple(row[c] for c in self.unique_key)
                    if key not in seen:
                        seen[key] = row
                dedup_dropped += len(rows) - len(seen)
                to_insert.extend(seen.values())

            if to_insert:
                now = datetime.now(UTC)
                col_names = {c.name for c in self.table.columns}
                add_created = "created_at" in col_names
                add_updated = "updated_at" in col_names
                enriched = [
                    {
                        **r,
                        **({"created_at": now} if add_created and "created_at" not in r else {}),
                        **({"updated_at": now} if add_updated else {}),
                    }
                    for r in to_insert
                ]
                self.db.execute(self.table.insert(), enriched)

            self.db.commit()
            return len(to_insert), dedup_dropped

        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            msg = str(exc)
            total_rows = sum(len(v) for v in scope_buckets.values())
            errors.record("scoped_replace", msg, raw_row={"batch_number": batch_number, "scopes": len(scope_buckets), "rows": total_rows})
            errors.total_errors += max(total_rows - 1, 0)
            logger.exception(
                "ScopedReplacer batch failed — rolled back",
                extra={
                    "ingest_source": self.source_name,
                    "ingest_table": self.table.name,
                    "ingest_batch_number": batch_number,
                    "ingest_scopes": len(scope_buckets),
                    "ingest_rows": total_rows,
                    "ingest_error": msg[:500],
                },
            )
            return 0, 0


# ---------------------------------------------------------------------------
# Standalone one-shot primitives — for multi-table services that buffer per
# table and need to flush batches as they fill. The orchestration lives in the
# caller; these helpers handle dedup + upsert + commit + error bucketing for a
# single batch of rows.
# ---------------------------------------------------------------------------


def flush_upsert_batch(
    db: Session,
    *,
    source_name: str,
    table: Table,
    unique_key: list[str],
    rows: list[dict[str, Any]],
    errors: ErrorAggregator,
    immutable_on_update: tuple[str, ...] = _DEFAULT_IMMUTABLE_ON_UPDATE,
    prefer_row: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
) -> tuple[int, int]:
    """One-shot dedup + ON CONFLICT upsert + per-batch commit.

    Returns ``(upserted_count, deduped_count)``. Errors are recorded on the
    shared :class:`ErrorAggregator`. Use when a caller is buffering rows by
    table and needs to flush a filled batch without going through the
    iterator-consuming ``BatchedUpserter.load()`` entry point.
    """
    if not rows:
        return 0, 0

    # In-batch dedup
    prefer = prefer_row or (lambda _existing, new: new)
    kept: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        try:
            key = tuple(row[c] for c in unique_key)
        except KeyError:
            # Row missing a unique-key column — keep under its own identity
            kept[(id(row),)] = row
            continue
        if key in kept:
            kept[key] = prefer(kept[key], row)
        else:
            kept[key] = row

    deduped = list(kept.values())
    dedup_dropped = len(rows) - len(deduped)

    # Timestamp enrichment
    now = datetime.now(UTC)
    col_names = {c.name for c in table.columns}
    enriched: list[dict[str, Any]] = []
    for r in deduped:
        new_r = dict(r)
        if "created_at" in col_names and "created_at" not in new_r:
            new_r["created_at"] = now
        if "updated_at" in col_names:
            new_r["updated_at"] = now
        enriched.append(new_r)

    # Execute
    try:
        stmt = pg_insert(table).values(enriched)
        update_cols = {
            c.name: stmt.excluded[c.name]
            for c in table.columns
            if c.name not in unique_key and c.name not in immutable_on_update
        }
        if update_cols:
            stmt = stmt.on_conflict_do_update(
                index_elements=unique_key,
                set_=update_cols,
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=unique_key)
        db.execute(stmt)
        db.commit()
        return len(enriched), dedup_dropped

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        msg = str(exc)
        errors.record(
            f"upsert:{table.name}",
            msg,
            raw_row={"batch_size": len(enriched), "sample": enriched[0] if enriched else None},
        )
        errors.total_errors += max(len(enriched) - 1, 0)
        logger.exception(
            "Upsert batch failed — rolled back",
            extra={
                "ingest_source": source_name,
                "ingest_table": table.name,
                "ingest_batch_size": len(enriched),
                "ingest_error": msg[:500],
            },
        )
        return 0, dedup_dropped


def flush_scoped_replace_batch(
    db: Session,
    *,
    source_name: str,
    table: Table,
    scope_key: list[str],
    unique_key: list[str],
    rows: list[dict[str, Any]],
    errors: ErrorAggregator,
) -> tuple[int, int]:
    """One-shot delete-then-insert by ``scope_key`` with in-batch dedup on ``unique_key``.

    Returns ``(inserted_count, deduped_count)``. Groups the input rows by
    ``scope_key``, deletes the existing rows whose scope_key matches, then
    inserts the deduped new rows.
    """
    if not rows:
        return 0, 0

    from sqlalchemy import and_, or_

    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        try:
            scope = tuple(row[c] for c in scope_key)
        except KeyError as exc:
            errors.record("scoped_replace", f"Missing scope_key column {exc}", raw_row=row)
            continue
        buckets.setdefault(scope, []).append(row)

    try:
        # Delete
        scopes = list(buckets.keys())
        if scopes:
            if len(scope_key) == 1:
                col = table.c[scope_key[0]]
                db.execute(table.delete().where(col.in_([s[0] for s in scopes])))
            else:
                preds = [
                    and_(*[table.c[col] == val for col, val in zip(scope_key, s, strict=True)])
                    for s in scopes
                ]
                db.execute(table.delete().where(or_(*preds)))

        # Dedup + insert
        to_insert: list[dict[str, Any]] = []
        dedup_dropped = 0
        for bucket_rows in buckets.values():
            seen: dict[tuple[Any, ...], dict[str, Any]] = {}
            for row in bucket_rows:
                try:
                    key = tuple(row[c] for c in unique_key)
                except KeyError:
                    continue
                if key not in seen:
                    seen[key] = row
            dedup_dropped += len(bucket_rows) - len(seen)
            to_insert.extend(seen.values())

        if to_insert:
            now = datetime.now(UTC)
            col_names = {c.name for c in table.columns}
            enriched = [
                {
                    **r,
                    **({"created_at": now} if "created_at" in col_names and "created_at" not in r else {}),
                    **({"updated_at": now} if "updated_at" in col_names else {}),
                }
                for r in to_insert
            ]
            db.execute(table.insert(), enriched)

        db.commit()
        return len(to_insert), dedup_dropped

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        msg = str(exc)
        errors.record(f"scoped_replace:{table.name}", msg, raw_row={"scopes": len(buckets), "rows": len(rows)})
        errors.total_errors += max(len(rows) - 1, 0)
        logger.exception(
            "Scoped replace batch failed — rolled back",
            extra={
                "ingest_source": source_name,
                "ingest_table": table.name,
                "ingest_scopes": len(buckets),
                "ingest_rows": len(rows),
                "ingest_error": msg[:500],
            },
        )
        return 0, 0


# ---------------------------------------------------------------------------
# COPY-staging primitives (Wave 11.5)
#
# Postgres `COPY ... FROM STDIN` bypasses the SQL parser for the data path
# and is ~3-10x faster than multi-VALUES INSERT on wide / large batches.
# These primitives follow the standard upsert-via-COPY pattern:
#
#   1. CREATE TEMP TABLE stg_<target> (LIKE target) ON COMMIT DROP
#   2. COPY stg FROM STDIN (text format, \N null)
#   3. INSERT INTO target SELECT ... FROM stg ON CONFLICT DO UPDATE
#      (or scoped-replace: DELETE using stg, then INSERT)
#   4. db.commit()  — ON COMMIT DROP removes the temp table
#
# SQLite (and any non-postgres dialect) falls back to the VALUES-based path
# so unit-test fixtures stay green without a Postgres harness.
# ---------------------------------------------------------------------------


def _pg_copy_text_encode(value: Any) -> str:
    """Encode a single value for Postgres COPY text format.

    Text format rules:
      - NULL is the literal string ``\\N``
      - Field separator is TAB
      - Row separator is LF
      - In values we escape ``\\``, TAB, CR, LF with ``\\\\``, ``\\t``, ``\\r``, ``\\n``

    Python's standard string conversions are already compatible with
    Postgres text format for int/bool/Decimal/date/datetime — we just
    escape the control characters and backslash.
    """
    if value is None:
        return r"\N"
    if value is True:
        return "t"
    if value is False:
        return "f"
    s = str(value)
    if not s:
        return ""
    # Order matters: backslash first so we don't double-escape our own escapes.
    return (
        s.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _encode_rows_as_copy_text(
    rows: list[dict[str, Any]], columns: list[str]
) -> str:
    """Serialize ``rows`` into a Postgres COPY text buffer.

    Rows are projected onto ``columns`` in the given order; missing keys
    are encoded as NULL. Returns the full buffer as a string (caller wraps
    it in ``io.StringIO`` for ``cursor.copy_expert``).
    """
    lines: list[str] = []
    for row in rows:
        lines.append("\t".join(_pg_copy_text_encode(row.get(c)) for c in columns))
    return "\n".join(lines) + ("\n" if lines else "")


def _is_postgres(db: Session) -> bool:
    """True if the session is bound to a PostgreSQL dialect."""
    bind = db.get_bind() if hasattr(db, "get_bind") else db.bind
    return bind is not None and bind.dialect.name == "postgresql"


def _raw_cursor(db: Session) -> Any:
    """Return the underlying DBAPI cursor for the session's current connection.

    Use only after ``db.connection()`` has bound the session to a connection
    (any prior statement does so, or call it yourself). Caller is responsible
    for closing the cursor.
    """
    return db.connection().connection.cursor()


def _staging_table_name(target: Table) -> str:
    """Derive a stable TEMP table name from a target table name.

    TEMP tables are session-scoped but we use ``ON COMMIT DROP`` so each
    successful flush removes its own staging table. Name is unqualified
    (no schema) because TEMP tables live in the session's pg_temp schema.
    """
    # Strip any schema qualifier — temp tables are always pg_temp.
    raw = target.name
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in raw)
    return f"stg_{safe}"[:63]  # Postgres NAMEDATALEN is 64


def flush_upsert_batch_copy(
    db: Session,
    *,
    source_name: str,
    table: Table,
    unique_key: list[str],
    rows: list[dict[str, Any]],
    errors: ErrorAggregator,
    immutable_on_update: tuple[str, ...] = _DEFAULT_IMMUTABLE_ON_UPDATE,
    prefer_row: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
) -> tuple[int, int]:
    """COPY-staging variant of :func:`flush_upsert_batch`.

    Drop-in replacement: same signature, same return semantics. On
    non-PostgreSQL dialects this transparently delegates to the existing
    VALUES-based primitive so SQLite-backed unit tests still pass.

    On PostgreSQL:

      1. In-batch dedup on ``unique_key`` (same as VALUES path).
      2. Timestamp enrichment (``created_at``/``updated_at`` if table has them).
      3. ``CREATE TEMP TABLE stg_<target> (LIKE target) ON COMMIT DROP``.
      4. ``COPY stg FROM STDIN`` with text format.
      5. ``INSERT INTO target (cols) SELECT cols FROM stg
            ON CONFLICT (unique_key) DO UPDATE SET ...``
      6. ``db.commit()``.
    """
    if not _is_postgres(db):
        return flush_upsert_batch(
            db,
            source_name=source_name,
            table=table,
            unique_key=unique_key,
            rows=rows,
            errors=errors,
            immutable_on_update=immutable_on_update,
            prefer_row=prefer_row,
        )

    if not rows:
        return 0, 0

    # In-batch dedup — identical semantics to flush_upsert_batch.
    prefer = prefer_row or (lambda _existing, new: new)
    kept: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        try:
            key = tuple(row[c] for c in unique_key)
        except KeyError:
            kept[(id(row),)] = row
            continue
        if key in kept:
            kept[key] = prefer(kept[key], row)
        else:
            kept[key] = row

    deduped = list(kept.values())
    dedup_dropped = len(rows) - len(deduped)

    # Timestamp enrichment.
    now = datetime.now(UTC)
    col_names = [c.name for c in table.columns]
    col_set = set(col_names)
    enriched: list[dict[str, Any]] = []
    for r in deduped:
        new_r = dict(r)
        if "created_at" in col_set and "created_at" not in new_r:
            new_r["created_at"] = now
        if "updated_at" in col_set:
            new_r["updated_at"] = now
        enriched.append(new_r)

    target_name = _qualified_sql_name(table)
    stg_name = _staging_table_name(table)
    col_list_sql = ", ".join(f'"{c}"' for c in col_names)
    update_cols = [
        c for c in col_names
        if c not in unique_key and c not in immutable_on_update
    ]

    try:
        cursor = _raw_cursor(db)
        try:
            cursor.execute(
                f'CREATE TEMP TABLE IF NOT EXISTS "{stg_name}" '
                f"(LIKE {target_name} INCLUDING DEFAULTS) ON COMMIT DROP"
            )
            cursor.execute(f'TRUNCATE "{stg_name}"')

            # COPY text-format payload
            import io
            buf = io.StringIO(_encode_rows_as_copy_text(enriched, col_names))
            cursor.copy_expert(
                f'COPY "{stg_name}" ({col_list_sql}) FROM STDIN',
                buf,
            )

            # INSERT ... SELECT ... ON CONFLICT
            if update_cols:
                set_clause = ", ".join(
                    f'"{c}" = EXCLUDED."{c}"' for c in update_cols
                )
                conflict_cols_sql = ", ".join(f'"{c}"' for c in unique_key)
                cursor.execute(
                    f"INSERT INTO {target_name} ({col_list_sql}) "
                    f'SELECT {col_list_sql} FROM "{stg_name}" '
                    f"ON CONFLICT ({conflict_cols_sql}) DO UPDATE SET {set_clause}"
                )
            else:
                # Every column is in the unique key or immutable — nothing to update.
                conflict_cols_sql = ", ".join(f'"{c}"' for c in unique_key)
                cursor.execute(
                    f"INSERT INTO {target_name} ({col_list_sql}) "
                    f'SELECT {col_list_sql} FROM "{stg_name}" '
                    f"ON CONFLICT ({conflict_cols_sql}) DO NOTHING"
                )
        finally:
            cursor.close()

        db.commit()
        return len(enriched), dedup_dropped

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        msg = str(exc)
        errors.record(
            f"upsert_copy:{table.name}",
            msg,
            raw_row={
                "batch_size": len(enriched),
                "sample": enriched[0] if enriched else None,
            },
        )
        errors.total_errors += max(len(enriched) - 1, 0)
        logger.exception(
            "COPY upsert batch failed — rolled back",
            extra={
                "ingest_source": source_name,
                "ingest_table": table.name,
                "ingest_batch_size": len(enriched),
                "ingest_error": msg[:500],
            },
        )
        return 0, dedup_dropped


def flush_scoped_replace_batch_copy(
    db: Session,
    *,
    source_name: str,
    table: Table,
    scope_key: list[str],
    unique_key: list[str],
    rows: list[dict[str, Any]],
    errors: ErrorAggregator,
) -> tuple[int, int]:
    """COPY-staging variant of :func:`flush_scoped_replace_batch`.

    Drop-in replacement. On non-PostgreSQL dialects delegates to the VALUES
    path. On PostgreSQL:

      1. Group + in-batch dedup per ``scope_key`` on ``unique_key``.
      2. ``CREATE TEMP TABLE stg (LIKE target) ON COMMIT DROP`` + COPY.
      3. ``DELETE FROM target USING (SELECT DISTINCT scope_key FROM stg) s
            WHERE target.scope_key = s.scope_key``  — bulk-deletes every
            parent scope the new batch replaces, in a single statement.
      4. ``INSERT INTO target SELECT ... FROM stg``.
      5. ``db.commit()``.
    """
    if not _is_postgres(db):
        return flush_scoped_replace_batch(
            db,
            source_name=source_name,
            table=table,
            scope_key=scope_key,
            unique_key=unique_key,
            rows=rows,
            errors=errors,
        )

    if not rows:
        return 0, 0

    # Group rows by scope_key for dedup.
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        try:
            scope = tuple(row[c] for c in scope_key)
        except KeyError as exc:
            errors.record(
                "scoped_replace_copy",
                f"Missing scope_key column {exc}",
                raw_row=row,
            )
            continue
        buckets.setdefault(scope, []).append(row)

    if not buckets:
        return 0, 0

    # Dedup within each scope on unique_key; concatenate for insert.
    to_insert: list[dict[str, Any]] = []
    dedup_dropped = 0
    for bucket_rows in buckets.values():
        seen: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in bucket_rows:
            try:
                key = tuple(row[c] for c in unique_key)
            except KeyError:
                continue
            if key not in seen:
                seen[key] = row
        dedup_dropped += len(bucket_rows) - len(seen)
        to_insert.extend(seen.values())

    if not to_insert:
        # Nothing to insert — but we still need to delete the parent scopes
        # the caller mentioned so orphaned rows get cleaned. Fall through.
        pass

    # Timestamp enrichment.
    now = datetime.now(UTC)
    col_names = [c.name for c in table.columns]
    col_set = set(col_names)
    enriched: list[dict[str, Any]] = []
    for r in to_insert:
        new_r = dict(r)
        if "created_at" in col_set and "created_at" not in new_r:
            new_r["created_at"] = now
        if "updated_at" in col_set:
            new_r["updated_at"] = now
        enriched.append(new_r)

    target_name = _qualified_sql_name(table)
    stg_name = _staging_table_name(table)
    col_list_sql = ", ".join(f'"{c}"' for c in col_names)

    try:
        cursor = _raw_cursor(db)
        try:
            cursor.execute(
                f'CREATE TEMP TABLE IF NOT EXISTS "{stg_name}" '
                f"(LIKE {target_name} INCLUDING DEFAULTS) ON COMMIT DROP"
            )
            cursor.execute(f'TRUNCATE "{stg_name}"')

            if enriched:
                import io
                buf = io.StringIO(_encode_rows_as_copy_text(enriched, col_names))
                cursor.copy_expert(
                    f'COPY "{stg_name}" ({col_list_sql}) FROM STDIN',
                    buf,
                )

            # Bulk-delete every parent scope this batch replaces.
            # Use DISTINCT on the scope columns of the staging table so we
            # issue exactly one DELETE for the whole batch.
            scope_col_sql = ", ".join(f'"{c}"' for c in scope_key)
            join_pred = " AND ".join(
                f'{target_name}."{c}" = s."{c}"' for c in scope_key
            )
            if enriched:
                # Pull distinct scopes from staging.
                cursor.execute(
                    f"DELETE FROM {target_name} USING "
                    f'(SELECT DISTINCT {scope_col_sql} FROM "{stg_name}") s '
                    f"WHERE {join_pred}"
                )
            else:
                # Staging is empty but caller asked to clear some scopes.
                # We fall back to a values-list delete of the keys the caller
                # mentioned. For the NPPES use case this path is unreachable
                # (a scope only shows up if it had at least one row), but we
                # handle it for parity with the VALUES primitive.
                from sqlalchemy import and_, or_
                scope_values = list(buckets.keys())
                if len(scope_key) == 1:
                    col = table.c[scope_key[0]]
                    db.execute(
                        table.delete().where(col.in_([s[0] for s in scope_values]))
                    )
                else:
                    preds = [
                        and_(*[
                            table.c[c] == v
                            for c, v in zip(scope_key, s, strict=True)
                        ])
                        for s in scope_values
                    ]
                    db.execute(table.delete().where(or_(*preds)))

            # Insert the new rows from staging.
            if enriched:
                cursor.execute(
                    f"INSERT INTO {target_name} ({col_list_sql}) "
                    f'SELECT {col_list_sql} FROM "{stg_name}"'
                )
        finally:
            cursor.close()

        db.commit()
        return len(enriched), dedup_dropped

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        msg = str(exc)
        errors.record(
            f"scoped_replace_copy:{table.name}",
            msg,
            raw_row={"scopes": len(buckets), "rows": len(rows)},
        )
        errors.total_errors += max(len(rows) - 1, 0)
        logger.exception(
            "COPY scoped-replace batch failed — rolled back",
            extra={
                "ingest_source": source_name,
                "ingest_table": table.name,
                "ingest_scopes": len(buckets),
                "ingest_rows": len(rows),
                "ingest_error": msg[:500],
            },
        )
        return 0, 0


def _qualified_sql_name(table: Table) -> str:
    """Return a fully-qualified, quoted table name for raw SQL."""
    if table.schema:
        return f'"{table.schema}"."{table.name}"'
    return f'"{table.name}"'


def merge_results(results: Iterable[IngestionResult], *, source: str) -> IngestionResult:
    """Collapse multiple per-table IngestionResults into a single summary row.

    Use when one logical loader writes to multiple tables (e.g., Orange Book
    writes products + patents + exclusivity). The aggregate result's counters
    are sums; status is ``completed`` if every sub-result completed, else
    ``failed``.
    """
    acc = IngestionResult(source=source, status="completed")
    for r in results:
        if r.status != "completed":
            acc.status = r.status
        acc.records_processed += r.records_processed
        acc.records_inserted += r.records_inserted
        acc.records_updated += r.records_updated
        acc.records_skipped += r.records_skipped
        acc.records_errored += r.records_errored
        if r.error_message:
            acc.error_message = r.error_message
    return acc


__all__ = [
    "BatchedUpserter",
    "ErrorAggregator",
    "HistoryConfig",
    "ScopedReplacer",
    "flush_scoped_replace_batch",
    "flush_scoped_replace_batch_copy",
    "flush_upsert_batch",
    "flush_upsert_batch_copy",
    "merge_results",
]


# Satisfy static type-check for the Iterator import usage
_ = Iterator  # noqa: F841
