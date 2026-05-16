"""B9.C Tier B auto-aggregator."""
from __future__ import annotations
import importlib
import pkgutil
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from drug_database.services.fdb_adapter import TableSpec

_BATCH_PREFIX = "batch_"

def _discover_batch_modules() -> list[str]:
    pkg = importlib.import_module(__name__)
    return sorted(i.name for i in pkgutil.iter_modules(pkg.__path__) if i.name.startswith(_BATCH_PREFIX))

def _load_specs() -> list["TableSpec"]:
    out: list["TableSpec"] = []
    for name in _discover_batch_modules():
        mod = importlib.import_module(f"{__name__}.{name}")
        specs = getattr(mod, "SPECS", None)
        if specs is None:
            raise ImportError(f"{__name__}.{name} missing SPECS export.")
        out.extend(specs)
    return out

TIER_B_SPECS: list["TableSpec"] = _load_specs()
TIER_B_TABLE_NAMES: frozenset[str] = frozenset(s.table_name for s in TIER_B_SPECS)

def discovered_batches() -> list[str]:
    return _discover_batch_modules()

__all__ = ["TIER_B_SPECS", "TIER_B_TABLE_NAMES", "discovered_batches"]
