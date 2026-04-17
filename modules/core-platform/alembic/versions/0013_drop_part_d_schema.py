"""Drop the empty ``part_d`` schema.

The ``part_d`` schema was created by the init SQL scripts as a reservation
for a future Phase-4 part-d-pde module (Medicare Part D Prescription Drug
Event processing). That module will not be built — InfinityRx does not
process Part D business. The schema has always been empty (zero tables,
views, or routines); drop it so preflight and integration checks no
longer need to assert its existence.

Not CASCADE on purpose: if anything lands in part_d between now and the
migration being applied elsewhere, we want the DROP to fail loudly rather
than silently delete content.

Revision ID: 0013_drop_part_d_schema
Revises: 0012_ofac_sdn_tables
Create Date: 2026-04-17
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0013_drop_part_d_schema"
down_revision: Union[str, None] = "0012_ofac_sdn_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS part_d")


def downgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS part_d")
