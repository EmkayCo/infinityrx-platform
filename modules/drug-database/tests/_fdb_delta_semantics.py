"""B9.A C8 — DB-backed DELTA_SEMANTICS simulator (SQLite).

C3 (`_fdb_contract.py::assert_delta_semantics_acd_cycle`) is the
*abstract* A/C/D/re-A driver — it takes a `DeltaSimulator` callable
and asserts post-step state per `DeltaSemantics`. The simulator is
the integration surface; this module provides the concrete
SQLite-backed implementation.

Why SQLite (and not Postgres) for the unit test:
  * The semantics under test (`INSERT ON CONFLICT DO UPDATE` vs
    `DO NOTHING`, DELETE-by-natural-key, append-only history) are
    portable across both engines.
  * SQLite 3.24+ supports `ON CONFLICT` with the same syntax used
    in production Postgres.
  * Per `_engine` fixture conventions in
    `modules/drug-database/tests/conftest.py`, SQLite is the unit-
    test target; Postgres is integration.
  * Catches the A4 regression (UPSERT silently swallowed) without
    a live DB. The B9.B-G integration tests wire the same
    simulator shape against the real Postgres `drug_database`
    schema for full end-to-end coverage.

Public surface:

    make_sqlite_simulator(
        engine,
        table_name,
        natural_key_columns,
        all_columns,
        *,
        conflict_action="upsert" | "nothing",
        append_only=False,
    ) -> tuple[DeltaSimulator, Callable[[], None]]

Returns a `(simulator, teardown)` pair. The caller wires `simulator`
into `assert_delta_semantics_acd_cycle` and runs `teardown()` after.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy import (
    Column,
    Engine,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    delete,
    insert,
    select,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


def make_sqlite_simulator(
    engine: Engine,
    *,
    table_name: str,
    natural_key_columns: Sequence[str],
    all_columns: Sequence[str],
    conflict_action: str = "upsert",
    append_only: bool = False,
) -> tuple[Callable[[dict[str, Any], str], tuple[int, dict[str, Any] | None]], Callable[[], None]]:
    """Create an in-DB simulator that drives A/C/D transactions.

    Args:
        engine: SQLAlchemy engine (typically the shared SQLite test engine).
        table_name: SQLite-safe table name; created fresh, dropped on teardown.
        natural_key_columns: column names that form the conflict target.
            For APPEND_ONLY the natural key is irrelevant for INSERT but is
            still used by the DELETE branch.
        all_columns: complete column list (must include natural_key_columns).
        conflict_action: 'upsert' → INSERT...ON CONFLICT DO UPDATE.
                         'nothing' → INSERT...ON CONFLICT DO NOTHING (the
                         exact regression A4 guards against).
        append_only: If True, every 'A' / 'C' / 'D' becomes a new row
            (history table semantics — no conflict resolution, DELETE
            is a no-op for the count assertion). Mutually exclusive
            with conflict_action.

    Returns:
        (simulator, teardown). The simulator is a callable matching
        the `DeltaSimulator` protocol from `_fdb_contract.py`.
    """
    if append_only and conflict_action != "upsert":
        # 'upsert' is the default; flag the contradiction loudly
        raise ValueError(
            "append_only=True is mutually exclusive with conflict_action; "
            "leave conflict_action at default."
        )
    if not append_only and conflict_action not in {"upsert", "nothing"}:
        raise ValueError(
            f"conflict_action must be 'upsert' or 'nothing', got {conflict_action!r}"
        )

    metadata = MetaData()
    columns = [Column(c, String, primary_key=False) for c in all_columns]
    natural_key = tuple(natural_key_columns)
    table_args: list[Any] = list(columns)
    # APPEND_ONLY tables have no conflict target; everything else needs
    # a UNIQUE constraint over natural_key so ON CONFLICT can bind to it.
    if not append_only:
        table_args.append(
            UniqueConstraint(*natural_key, name=f"uq_{table_name}_nk")
        )
    table = Table(table_name, metadata, *table_args)
    metadata.create_all(engine)

    def _count_and_state(row: dict[str, Any]) -> tuple[int, dict[str, Any] | None]:
        with engine.connect() as conn:
            total = conn.execute(select(table)).fetchall()
            # Find the row whose natural key matches the supplied row's.
            target_state: dict[str, Any] | None = None
            for r in total:
                rd = r._mapping  # type: ignore[attr-defined]
                if all(rd[k] == row[k] for k in natural_key if k in rd):
                    target_state = dict(rd)
                    # In APPEND_ONLY there can be multiple — keep the latest.
            return len(total), target_state

    def simulator(row: dict[str, Any], tx: str) -> tuple[int, dict[str, Any] | None]:
        # Coerce all values to str — SQLite typing is loose but the
        # comparison in _count_and_state expects consistent types.
        row_str = {k: (str(v) if v is not None else None) for k, v in row.items()}

        with engine.begin() as conn:
            if tx == "D":
                if append_only:
                    # Append a tombstone marker — same shape, no special col.
                    # Keeps the count growth invariant of APPEND_ONLY.
                    conn.execute(insert(table).values(**row_str))
                else:
                    where_clauses = [
                        table.c[k] == row_str[k] for k in natural_key
                    ]
                    stmt = delete(table)
                    for w in where_clauses:
                        stmt = stmt.where(w)
                    conn.execute(stmt)
            else:
                # A or C — both go through INSERT (with or without conflict
                # resolution). Real production paths typically issue 'A'
                # straight as INSERT and 'C' as UPDATE; the FDB UPD format
                # delivers both as INSERT-shaped rows with a leading code,
                # which is why the contract surface is UPSERT-shaped.
                if append_only:
                    conn.execute(insert(table).values(**row_str))
                else:
                    stmt = sqlite_insert(table).values(**row_str)
                    if conflict_action == "upsert":
                        update_cols = {
                            c: row_str[c]
                            for c in all_columns
                            if c not in natural_key
                        }
                        if update_cols:
                            stmt = stmt.on_conflict_do_update(
                                index_elements=list(natural_key),
                                set_=update_cols,
                            )
                        else:
                            # Natural-key-only table; nothing to update on conflict.
                            stmt = stmt.on_conflict_do_nothing(
                                index_elements=list(natural_key)
                            )
                    else:
                        # 'nothing' → the A4 regression scenario.
                        stmt = stmt.on_conflict_do_nothing(
                            index_elements=list(natural_key)
                        )
                    conn.execute(stmt)

        return _count_and_state(row_str)

    def teardown() -> None:
        metadata.drop_all(engine)

    return simulator, teardown


__all__ = ["make_sqlite_simulator"]
