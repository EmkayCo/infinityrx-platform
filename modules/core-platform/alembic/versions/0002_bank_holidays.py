"""bank_holidays: add core.bank_holidays table

Revision ID: 0002_bank_holidays
Revises: 0001_core_baseline
Create Date: 2026-04-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_bank_holidays"
down_revision: Union[str, None] = "0001_core_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bank_holidays",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False, server_default="US"),
        sa.Column("is_federal", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_bank_holiday", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bank_holidays")),
        sa.UniqueConstraint(
            "holiday_date",
            "country",
            name="uq_bank_holiday_date_country",
        ),
        schema="core",
    )
    op.create_index(
        "ix_bank_holidays_country_date",
        "bank_holidays",
        ["country", "holiday_date"],
        unique=False,
        schema="core",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bank_holidays_country_date",
        table_name="bank_holidays",
        schema="core",
    )
    op.drop_table("bank_holidays", schema="core")
