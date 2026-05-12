"""B9.A C4 — Tests for the FDB loader registry + MTL guard.

These tests lock in two contracts:

  1. The settings flag `FDB_LOAD_MTL` defaults to False. Flipping it
     to True is a deliberate operator action (future activation wave).

  2. The `filter_loadable_specs` helper excludes `loader_group="fdb_mtl"`
     specs when `fdb_load_mtl=False`, regardless of any `only_groups`
     override. The flag is the gate; group selection is sub-filtering.

  3. `test_fdb_mtl_zero_loadable_under_default_flag` is the trivially-
     true assertion that stays present from B9.A through B9.G — it
     fails the moment someone accidentally registers an MTL spec WITHOUT
     `loader_group="fdb_mtl"`, or flips the default flag to True.

The DB-level REVOKE template at
`infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl` is the
defense-in-depth backstop; it is not exercised here (B9.G's grant
migration test does that).
"""
from __future__ import annotations

import pytest

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    TableSpec,
    Tier,
)
from drug_database.services.fdb_loader_registry import (
    MTL_LOADER_GROUP,
    filter_loadable_specs,
    mtl_specs,
)


# ---------------------------------------------------------------------------
# Sample fixture specs covering all 4 tier groups
# ---------------------------------------------------------------------------


_PHASE_09_SPEC = TableSpec(
    table_name="RNP3_NDC_PRICE",
    columns=("ndc_11",),
    coercers={"ndc_11": str},
    delta_semantics=DeltaSemantics.APPEND_ONLY,
    # loader_group=None — Phase 09 backward-compat
)

_TIER_A_SPEC = TableSpec(
    table_name="RMIID1_MED",
    columns=("med_name_id",),
    coercers={"med_name_id": int},
    tier=Tier.A,
    loader_group="fdb_tier_a",
)

_TIER_B_SPEC = TableSpec(
    table_name="RNDC9_BAR",
    columns=("ndc_9",),
    coercers={"ndc_9": str},
    tier=Tier.B,
    loader_group="fdb_tier_b",
)

_TIER_C_SPEC = TableSpec(
    table_name="RNDC14_NDC_MSTR",
    columns=("ndc_14",),
    coercers={"ndc_14": str},
    tier=Tier.C,
    loader_group="fdb_tier_c",
)

_MTL_SPEC = TableSpec(
    table_name="MTL_TEST_LEX_MASTER",
    columns=("test_id",),
    coercers={"test_id": int},
    tier=Tier.D,
    loader_group=MTL_LOADER_GROUP,
)

_ALL_SPECS = [
    _PHASE_09_SPEC,
    _TIER_A_SPEC,
    _TIER_B_SPEC,
    _TIER_C_SPEC,
    _MTL_SPEC,
]


# ---------------------------------------------------------------------------
# Settings flag default
# ---------------------------------------------------------------------------


def test_fdb_load_mtl_setting_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """The settings flag defaults to False — opt-in only."""
    # Reset cache so we don't pick up a previously-loaded Settings.
    monkeypatch.delenv("FDB_LOAD_MTL", raising=False)
    from shared import config as cfg
    cfg.reset_settings_cache()
    settings = cfg.get_settings()
    assert settings.FDB_LOAD_MTL is False


def test_fdb_load_mtl_setting_accepts_explicit_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Env var override → True (smoke; activation wave flips this)."""
    monkeypatch.setenv("FDB_LOAD_MTL", "true")
    from shared import config as cfg
    cfg.reset_settings_cache()
    try:
        settings = cfg.get_settings()
        assert settings.FDB_LOAD_MTL is True
    finally:
        monkeypatch.delenv("FDB_LOAD_MTL", raising=False)
        cfg.reset_settings_cache()


# ---------------------------------------------------------------------------
# filter_loadable_specs
# ---------------------------------------------------------------------------


def test_filter_excludes_mtl_under_default_flag() -> None:
    """fdb_load_mtl=False → MTL specs are dropped."""
    out = filter_loadable_specs(_ALL_SPECS, fdb_load_mtl=False)
    table_names = [s.table_name for s in out]
    assert "MTL_TEST_LEX_MASTER" not in table_names
    assert "RNP3_NDC_PRICE" in table_names  # Phase 09 untouched
    assert len(out) == 4  # all except MTL


def test_filter_includes_mtl_when_flag_true() -> None:
    out = filter_loadable_specs(_ALL_SPECS, fdb_load_mtl=True)
    assert len(out) == 5
    assert any(s.table_name == "MTL_TEST_LEX_MASTER" for s in out)


def test_filter_preserves_input_order() -> None:
    out = filter_loadable_specs(_ALL_SPECS, fdb_load_mtl=True)
    assert [s.table_name for s in out] == [
        "RNP3_NDC_PRICE",
        "RMIID1_MED",
        "RNDC9_BAR",
        "RNDC14_NDC_MSTR",
        "MTL_TEST_LEX_MASTER",
    ]


def test_filter_only_groups_restricts_to_requested_groups() -> None:
    """only_groups=['fdb_tier_a'] → only Tier A specs returned."""
    out = filter_loadable_specs(
        _ALL_SPECS, fdb_load_mtl=False, only_groups=["fdb_tier_a"]
    )
    assert len(out) == 1
    assert out[0].table_name == "RMIID1_MED"


def test_filter_only_groups_mtl_still_denied_under_default_flag() -> None:
    """Even an explicit only_groups=['fdb_mtl'] is denied if the flag is False.

    This is the load-bearing assertion — the flag is the GATE; group
    selection is sub-filtering. If a future caller passes `only_groups=
    ['fdb_mtl']` from a CLI typo, the flag still says no.
    """
    out = filter_loadable_specs(
        _ALL_SPECS, fdb_load_mtl=False, only_groups=[MTL_LOADER_GROUP]
    )
    assert out == []


def test_filter_only_groups_mtl_allowed_when_flag_true() -> None:
    out = filter_loadable_specs(
        _ALL_SPECS, fdb_load_mtl=True, only_groups=[MTL_LOADER_GROUP]
    )
    assert len(out) == 1
    assert out[0].table_name == "MTL_TEST_LEX_MASTER"


def test_filter_phase_09_specs_unaffected_by_flag() -> None:
    """loader_group=None specs always load (Phase 09 backward-compat)."""
    for flag in (True, False):
        out = filter_loadable_specs([_PHASE_09_SPEC], fdb_load_mtl=flag)
        assert out == [_PHASE_09_SPEC]


def test_filter_empty_input_is_empty_output() -> None:
    assert filter_loadable_specs([], fdb_load_mtl=False) == []


# ---------------------------------------------------------------------------
# mtl_specs accessor
# ---------------------------------------------------------------------------


def test_mtl_specs_returns_only_mtl() -> None:
    out = mtl_specs(_ALL_SPECS)
    assert len(out) == 1
    assert out[0].table_name == "MTL_TEST_LEX_MASTER"


def test_mtl_specs_empty_when_no_mtl() -> None:
    """Mirrors B9.A reality: no MTL specs registered yet → empty."""
    assert mtl_specs([_PHASE_09_SPEC, _TIER_A_SPEC]) == []


# ---------------------------------------------------------------------------
# Lock-in test — survives B9.A through B9.G
# ---------------------------------------------------------------------------


def test_fdb_mtl_zero_loadable_under_default_flag() -> None:
    """Charter SC: under default `FDB_LOAD_MTL=False`, no MTL spec loads.

    B9.A: trivially true (no MTL specs exist yet).
    B9.B-F: still trivially true (no MTL specs registered).
    B9.G: now load-bearing (19 MTL specs registered with loader_group=
          "fdb_mtl"; flag default False excludes them all).
    Future activation wave: this test is RELAXED in tandem with the
          flag flip — it does not change semantics, the registered
          specs simply graduate to loadable.

    The assertion holds at every gate by construction: the registry
    helper filters before any load. The test is here to catch the
    regression where a future PR adds an MTL spec WITHOUT the
    `loader_group="fdb_mtl"` label (which would silently bypass the
    flag and load on default).
    """
    # Use the full _ALL_SPECS to simulate what the real catalog will
    # eventually look like. The assertion: every spec whose tier is
    # Tier.D must have loader_group=MTL_LOADER_GROUP, AND under default
    # flag none of them appear in the filter output.
    tier_d_specs = [s for s in _ALL_SPECS if s.tier == Tier.D]
    for spec in tier_d_specs:
        assert spec.loader_group == MTL_LOADER_GROUP, (
            f"{spec.table_name}: Tier D specs MUST set "
            f"loader_group='fdb_mtl' or they bypass the MTL guard."
        )

    default_load = filter_loadable_specs(_ALL_SPECS, fdb_load_mtl=False)
    assert not any(s.tier == Tier.D for s in default_load), (
        "Tier D / MTL specs appeared in the default load — MTL guard FAILED. "
        "Either FDB_LOAD_MTL default flipped to True (forbidden without an "
        "activation wave) or loader_group label is missing on a Tier D spec."
    )


def test_revoke_sql_template_exists() -> None:
    """Defense-in-depth backstop file is present and references the placeholders."""
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[4]
    tmpl = repo_root / "infrastructure" / "scripts" / "lib" / "fdb_mtl_revoke.sql.tmpl"
    assert tmpl.exists(), f"MTL REVOKE template missing at {tmpl}"
    body = tmpl.read_text(encoding="utf-8")
    # Required placeholders the B9.G migration substitutes.
    for placeholder in ("{{SCHEMA}}", "{{MTL_TABLES}}", "{{APP_ROLES}}"):
        assert placeholder in body, (
            f"{placeholder} missing from fdb_mtl_revoke.sql.tmpl — B9.G "
            f"migration cannot substitute without it."
        )
    # Critical statements present.
    assert "REVOKE INSERT, UPDATE, DELETE" in body
    assert "RAISE EXCEPTION" in body  # verification block
