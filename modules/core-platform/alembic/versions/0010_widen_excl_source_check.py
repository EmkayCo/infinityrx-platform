"""Widen core.exclusion_list.source CHECK constraint to include OFAC/STATE/DEA.

Originally the 0008_compliance_reference_tables migration scoped the
`source` column to only `OIG` and `SAM`, because those were the two
federal lists the unified crosswalk was designed for. LOADER-10 adds an
aggregator that unifies into `core.exclusion_list` — we also want it to
support OFAC SDN, state exclusion lists, and DEA deregistrations as they
come online.

This migration drops the old constraint and re-creates it with the
widened value set:

    CHECK (source IN ('OIG', 'SAM', 'OFAC', 'STATE', 'DEA'))

Revision ID: 0010_widen_exclusion_source_check
Revises: 0009_government_program_bins
Create Date: 2026-04-15
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0010_widen_excl_source_check"
down_revision: Union[str, None] = "0009_government_program_bins"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "core"
_TABLE = "exclusion_list"
# The full constraint name in postgres is
# `ck_exclusion_list_exclusion_list_source_valid` — the naming convention
# prepends `ck_<tablename>_` to whatever conceptual name we pass. So we
# drop by raw SQL (which takes the full name) and re-create via
# op.create_check_constraint (which re-applies the prefix).
_CONCEPTUAL_NAME = "exclusion_list_source_valid"
_FULL_NAME = "ck_exclusion_list_exclusion_list_source_valid"


def upgrade() -> None:
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} DROP CONSTRAINT {_FULL_NAME}")
    op.create_check_constraint(
        _CONCEPTUAL_NAME,
        _TABLE,
        "source IN ('OIG', 'SAM', 'OFAC', 'STATE', 'DEA')",
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} DROP CONSTRAINT {_FULL_NAME}")
    op.create_check_constraint(
        _CONCEPTUAL_NAME,
        _TABLE,
        "source IN ('OIG', 'SAM')",
        schema=_SCHEMA,
    )
