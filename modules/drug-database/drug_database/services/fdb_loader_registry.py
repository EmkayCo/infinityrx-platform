"""B9.A C4 — FDB loader registry with MTL guard.

The registry filters a list of `TableSpec`s by `loader_group` and
applies the `FDB_LOAD_MTL` settings flag (charter v3.2 + ADVERSARIAL
A8 mitigation):

  loader_group="fdb_mtl"  +  FDB_LOAD_MTL=False (default) → EXCLUDED
  loader_group="fdb_mtl"  +  FDB_LOAD_MTL=True            → INCLUDED
  loader_group=<anything> +  any flag value               → INCLUDED

MTL = Medical Test Lexicon. InfinityRx ships the 19 Tier D schemas
(B9.G) but does NOT subscribe to the clinical-screening tier — the
tables are empty by design until a future activation wave flips
`FDB_LOAD_MTL=True` and lands the corresponding GRANT migration
(`infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl` is the
defense-in-depth backstop for the app-layer filter).

Why a registry helper exists:
  * App-layer enforcement is the FAST PATH — never even ask the DB
    to insert MTL rows under the default flag.
  * DB-layer REVOKE is the SLOW PATH — even if app code regresses
    and tries to write MTL, the DB rejects with permission error.
  * Both layers must agree. Disagreement is a bug, not a feature.

Phase 09 backward-compat: loader_group is None for the 3 pre-B9
TableSpecs (RNP3, RPRDPTD0, RNPTYPD0). Filter never excludes those.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

from drug_database.services.fdb_adapter import TableSpec


MTL_LOADER_GROUP = "fdb_mtl"


def filter_loadable_specs(
    specs: Iterable[TableSpec],
    *,
    fdb_load_mtl: bool,
    only_groups: Sequence[str] | None = None,
) -> list[TableSpec]:
    """Return the subset of `specs` that should run in this load.

    Args:
        specs: full TableSpec catalog (or subset).
        fdb_load_mtl: settings.FDB_LOAD_MTL — False excludes MTL.
        only_groups: if given, restrict the output to specs whose
            loader_group is in this list. None means "all groups
            (subject to MTL guard)".

    Returns:
        Filtered list, preserving input order. Phase 09 specs (with
        loader_group=None) are always included unless `only_groups`
        is set, in which case they are included only when None is
        explicitly listed.
    """
    out: list[TableSpec] = []
    for spec in specs:
        # MTL guard FIRST — even an explicit `only_groups=["fdb_mtl"]`
        # is denied when the flag is False. If the operator really
        # wants MTL, they must set FDB_LOAD_MTL=True. Anything else
        # makes the flag a lie.
        if spec.loader_group == MTL_LOADER_GROUP and not fdb_load_mtl:
            continue
        if only_groups is not None:
            if spec.loader_group not in only_groups:
                continue
        out.append(spec)
    return out


def mtl_specs(specs: Iterable[TableSpec]) -> list[TableSpec]:
    """Return only the MTL-grouped specs from `specs`.

    Used by the lock-in test that asserts MTL is excluded under
    default flag, and by the future MTL-activation wave's grant
    migration to enumerate exactly which tables need GRANT restoration.
    """
    return [s for s in specs if s.loader_group == MTL_LOADER_GROUP]


__all__ = ["filter_loadable_specs", "mtl_specs", "MTL_LOADER_GROUP"]
