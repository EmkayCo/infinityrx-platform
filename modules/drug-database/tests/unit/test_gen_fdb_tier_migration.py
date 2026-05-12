"""B9.A C2 — Unit tests for the FDB tier migration generator.

The generator runs ONCE per tier during B9.B-G execution. Its output
becomes a real `alembic/versions/<revision>.py` file. These tests
verify the generator produces valid Python with the right structure
before any tier actually runs through it.
"""
from __future__ import annotations

import ast
from decimal import Decimal

import pytest
import sys
from pathlib import Path

# Add the scripts/ directory to path so we can import the generator.
_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from gen_fdb_tier_migration import (  # noqa: E402
    _sql_type_for_coercer,
    generate_tier_migration,
)

from drug_database.services.fdb_adapter import (  # noqa: E402
    DeltaSemantics,
    TableSpec,
    Tier,
)


# ---------------------------------------------------------------------------
# _sql_type_for_coercer — coercer → SQL type mapping
# ---------------------------------------------------------------------------


def test_sql_type_for_int() -> None:
    assert _sql_type_for_coercer(int) == "sa.Integer()"


def test_sql_type_for_str() -> None:
    assert _sql_type_for_coercer(str) == "sa.Text()"


def test_sql_type_for_decimal() -> None:
    """Decimal → Numeric(16,5) matches RNP3 ANSI DDL exactly (financial-precision.md)."""
    assert _sql_type_for_coercer(Decimal) == "sa.Numeric(16, 5)"


def test_sql_type_for_float_is_rejected() -> None:
    """float is forbidden for FDB columns (financial-precision rule)."""
    with pytest.raises(ValueError, match="float coercer is forbidden"):
        _sql_type_for_coercer(float)


def test_sql_type_for_unknown_coercer_raises() -> None:
    """Unknown coercers must error loudly; no silent default (ADVERSARIAL N4)."""
    def my_custom_coercer(s: str) -> object:
        return s

    with pytest.raises(ValueError, match="Unknown coercer"):
        _sql_type_for_coercer(my_custom_coercer)


# ---------------------------------------------------------------------------
# generate_tier_migration — full output
# ---------------------------------------------------------------------------


def _make_simple_tier_a_spec(name: str = "RMIID1_MED") -> TableSpec:
    """A minimal valid Tier A TableSpec for tests."""
    return TableSpec(
        table_name=name,
        columns=("med_name_id", "med_name"),
        coercers={"med_name_id": int, "med_name": str},
        tier=Tier.A,
        record_counts_key=name.split("_")[0],
        loader_group="fdb_tier_a",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    )


def test_generated_migration_is_valid_python() -> None:
    """ast.parse on the generator output succeeds — output is a real .py file."""
    specs = [_make_simple_tier_a_spec("RMIID1_MED"), _make_simple_tier_a_spec("RTGEN1_GEN")]
    src = generate_tier_migration(
        specs=specs,
        tier=Tier.A,
        revision_id="0009_fdb_tier_a",
        down_revision="0008_fdb_pricing",
    )
    ast.parse(src)  # raises SyntaxError on invalid Python


def test_generated_migration_has_revision_metadata() -> None:
    """Output declares the right revision + down_revision."""
    specs = [_make_simple_tier_a_spec()]
    src = generate_tier_migration(
        specs=specs,
        tier=Tier.A,
        revision_id="0009_fdb_tier_a",
        down_revision="0008_fdb_pricing",
    )
    assert 'revision: str = "0009_fdb_tier_a"' in src
    assert 'down_revision: Union[str, None] = "0008_fdb_pricing"' in src


def test_generated_migration_includes_all_specs_in_upgrade_and_downgrade() -> None:
    """Each spec produces a CREATE TABLE in upgrade() and a DROP in downgrade()."""
    specs = [
        _make_simple_tier_a_spec("RMIID1_MED"),
        _make_simple_tier_a_spec("RTGEN1_GEN"),
        _make_simple_tier_a_spec("RDFID1_DOSE"),
    ]
    src = generate_tier_migration(
        specs=specs,
        tier=Tier.A,
        revision_id="0009_fdb_tier_a",
        down_revision="0008_fdb_pricing",
    )
    # Tables present in lower-case form in op.create_table() + op.drop_table()
    assert 'op.create_table(\n        "rmiid1_med"' in src
    assert 'op.create_table(\n        "rtgen1_gen"' in src
    assert 'op.create_table(\n        "rdfid1_dose"' in src
    assert 'op.drop_table("rmiid1_med", schema=_SCHEMA)' in src
    assert 'op.drop_table("rtgen1_gen", schema=_SCHEMA)' in src
    assert 'op.drop_table("rdfid1_dose", schema=_SCHEMA)' in src


def test_generated_migration_uses_env_driven_role_pattern() -> None:
    """B7.3 lesson: GRANT statements use IFX_APP_ROLE env, NOT hardcoded ifx_prod_app."""
    src = generate_tier_migration(
        specs=[_make_simple_tier_a_spec()],
        tier=Tier.A,
        revision_id="0009_fdb_tier_a",
        down_revision="0008_fdb_pricing",
    )
    assert 'os.environ.get("IFX_APP_ROLE", "ifx_dev_app")' in src
    assert '_APP_ROLES = ("ifx_dev_app", "ifx_mock_app", _APP_ROLE)' in src
    # And critically — NO hardcoded ifx_prod_app as the default fallback
    # (the comment may explain prod set IFX_APP_ROLE=ifx_prod_app — that's fine)
    assert 'os.environ.get("IFX_APP_ROLE", "ifx_prod_app")' not in src


def test_empty_specs_list_raises() -> None:
    """Generator refuses to emit a migration with no tables."""
    with pytest.raises(ValueError, match="empty specs"):
        generate_tier_migration(
            specs=[],
            tier=Tier.A,
            revision_id="0009_fdb_tier_a",
            down_revision="0008_fdb_pricing",
        )


def test_spec_with_wrong_tier_raises() -> None:
    """Generator refuses to mix tiers in one migration (SPEC-locked granularity)."""
    tier_b_spec = TableSpec(
        table_name="RNDC9_BAR",
        columns=("a",),
        coercers={"a": str},
        tier=Tier.B,
    )
    with pytest.raises(ValueError, match="tier B but generator was invoked for tier A"):
        generate_tier_migration(
            specs=[_make_simple_tier_a_spec(), tier_b_spec],
            tier=Tier.A,
            revision_id="0009_fdb_tier_a",
            down_revision="0008_fdb_pricing",
        )


def test_generated_migration_includes_dryrun_reminder() -> None:
    """ADVERSARIAL R1 A2: docstring instructs operator to dry-run alembic up+down+up."""
    src = generate_tier_migration(
        specs=[_make_simple_tier_a_spec()],
        tier=Tier.A,
        revision_id="0009_fdb_tier_a",
        down_revision="0008_fdb_pricing",
    )
    assert "alembic upgrade head" in src
    assert "alembic downgrade -1" in src
    assert "dryrun_evidence.md" in src
