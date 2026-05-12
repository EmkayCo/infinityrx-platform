"""B9.B Tier A — Per-batch TableSpec aggregator.

Auto-discovers every `batch_*.py` module in this package and unions
their `SPECS` exports into a single `TIER_A_SPECS` list. Multi-agent
parallelism: each agent owns one `batch_N.py` file; the aggregator
picks up all batches without anyone editing a shared registry list.

Per-batch module contract:

    # drug_database/services/fdb_tier_a/batch_NN.py
    from drug_database.services.fdb_adapter import (
        DeltaSemantics, TableSpec, Tier,
    )

    SPECS: list[TableSpec] = [
        TableSpec(
            table_name="RFOO_TEST",
            columns=("col_a", "col_b"),
            coercers={"col_a": int, "col_b": str},
            tier=Tier.A,
            loader_group="fdb_tier_a",
            record_counts_key="RFOO_TEST",
            delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        ),
        ...
    ]

The aggregator imports each batch on first access, caches the unioned
result, and exposes:

    TIER_A_SPECS         — list[TableSpec]    (the canonical Tier A registry)
    TIER_A_TABLE_NAMES   — frozenset[str]     (helper for coverage tests)
    discovered_batches() — list[str]          (which batch modules loaded)
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drug_database.services.fdb_adapter import TableSpec


_BATCH_PREFIX = "batch_"


def _discover_batch_modules() -> list[str]:
    """Return sorted names of every batch_*.py module in this package."""
    pkg = importlib.import_module(__name__)
    names = sorted(
        info.name for info in pkgutil.iter_modules(pkg.__path__)
        if info.name.startswith(_BATCH_PREFIX)
    )
    return names


def _load_specs() -> list["TableSpec"]:
    """Import every batch module and concatenate its SPECS list.

    Order is lexicographic by module name (batch_01, batch_02, ...).
    Each batch module MUST expose a top-level `SPECS: list[TableSpec]`.
    Missing SPECS → loud ImportError so the operator notices.
    """
    out: list["TableSpec"] = []
    for name in _discover_batch_modules():
        mod = importlib.import_module(f"{__name__}.{name}")
        specs = getattr(mod, "SPECS", None)
        if specs is None:
            raise ImportError(
                f"{__name__}.{name} missing required `SPECS: list[TableSpec]` "
                f"export. Every batch module must declare it (see package "
                f"docstring for the contract)."
            )
        out.extend(specs)
    return out


# Eager load at package import — the registry is a known cost paid once.
TIER_A_SPECS: list["TableSpec"] = _load_specs()
TIER_A_TABLE_NAMES: frozenset[str] = frozenset(s.table_name for s in TIER_A_SPECS)


def discovered_batches() -> list[str]:
    """Return the list of batch module names that were loaded.

    Useful for status-line reporting and for the F4 coverage test.
    """
    return _discover_batch_modules()


__all__ = [
    "TIER_A_SPECS",
    "TIER_A_TABLE_NAMES",
    "discovered_batches",
]
