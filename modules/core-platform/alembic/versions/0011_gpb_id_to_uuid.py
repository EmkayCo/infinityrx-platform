"""Convert shared.government_program_bins.id from VARCHAR(36) to UUID.

Schema drift: migration 0009_government_program_bins created the id column
as VARCHAR(36) with `gen_random_uuid()::text` default, but the ORM model
at shared/models/gov_exclusion_tables.py declares it as
`PG_UUID(as_uuid=True)`. Any ORM upsert through the model (e.g. from
StateMedicaidBinLoader) fails with `operator does not exist: character
varying = uuid`.

Revision ID: 0011_gpb_id_to_uuid
Revises: 0010_widen_excl_source_check
Create Date: 2026-04-15
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0011_gpb_id_to_uuid"
down_revision: Union[str, None] = "0010_widen_excl_source_check"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE shared.government_program_bins "
        "ALTER COLUMN id DROP DEFAULT"
    )
    op.execute(
        "ALTER TABLE shared.government_program_bins "
        "ALTER COLUMN id TYPE uuid USING id::uuid"
    )
    op.execute(
        "ALTER TABLE shared.government_program_bins "
        "ALTER COLUMN id SET DEFAULT gen_random_uuid()"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE shared.government_program_bins "
        "ALTER COLUMN id DROP DEFAULT"
    )
    op.execute(
        "ALTER TABLE shared.government_program_bins "
        "ALTER COLUMN id TYPE varchar(36) USING id::text"
    )
    op.execute(
        "ALTER TABLE shared.government_program_bins "
        "ALTER COLUMN id SET DEFAULT gen_random_uuid()::text"
    )
