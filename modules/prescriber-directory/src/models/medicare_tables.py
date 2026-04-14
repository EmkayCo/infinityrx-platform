"""Medicare reference tables for the prescriber-directory module.

Schema: prescriber_dir

Two tables:
  - MedicarePartDUtilization  — annual per-(NPI, year) prescribing utilization
  - MedicareOptOut            — providers who have opted out of Medicare

LESSON-010: NPI is a public identifier — plaintext OK, do NOT encrypt.
LESSON-011: Global reference data — no TenantScopedMixin, no tenant_id.
financial-precision.md: All money columns are Numeric, NEVER Float.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .tables import PrescriberBase

SCHEMA = "prescriber_dir"


class MedicarePartDUtilization(PrescriberBase):
    """Annual Medicare Part D prescribing utilization per (NPI, year).

    Source: CMS Medicare Part D Prescribers by Provider (Socrata API).
    PK: (npi, year) — one row per prescriber per data year.

    All money columns use Numeric(18, 2) — NEVER Float (financial-precision.md).
    Rate fields use Numeric(7, 4) — percentages as decimal fraction.
    Risk score uses Numeric(6, 4).

    LESSON-010: NPI plaintext.
    LESSON-011: Global reference — no TenantScopedMixin.
    """

    __tablename__ = "medicare_part_d_utilization"
    __table_args__ = (
        sa.PrimaryKeyConstraint("npi", "year", name="pk_part_d_npi_year"),
        sa.Index("idx_part_d_year", "year"),
        sa.Index("idx_part_d_prscrbr_type", "prscrbr_type"),
        sa.Index("idx_part_d_state", "prscrbr_state_abrvtn"),
        {"schema": SCHEMA},
    )

    # Identity
    npi: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    year: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    prscrbr_last_org_name: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    prscrbr_first_name: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    prscrbr_city: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    prscrbr_state_abrvtn: Mapped[str | None] = mapped_column(sa.String(2), nullable=True)
    prscrbr_state_fips: Mapped[str | None] = mapped_column(sa.String(5), nullable=True)
    prscrbr_zip5: Mapped[str | None] = mapped_column(sa.String(5), nullable=True)
    prscrbr_ruca: Mapped[str | None] = mapped_column(sa.String(10), nullable=True)
    prscrbr_cntry: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    prscrbr_type: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    prscrbr_type_src: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)

    # Utilization totals
    tot_clms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    tot_30day_fills: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    tot_day_suply: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    tot_drug_cst: Mapped[Any] = mapped_column(sa.Numeric(18, 2), nullable=True)
    tot_benes: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)

    # Brand / Generic split
    brnd_clms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    brnd_drug_cst: Mapped[Any] = mapped_column(sa.Numeric(18, 2), nullable=True)
    gnrc_clms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    gnrc_drug_cst: Mapped[Any] = mapped_column(sa.Numeric(18, 2), nullable=True)
    othr_clms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    othr_drug_cst: Mapped[Any] = mapped_column(sa.Numeric(18, 2), nullable=True)

    # Plan split
    mapd_clms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    mapd_drug_cst: Mapped[Any] = mapped_column(sa.Numeric(18, 2), nullable=True)
    pdp_clms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    pdp_drug_cst: Mapped[Any] = mapped_column(sa.Numeric(18, 2), nullable=True)
    lis_clms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    lis_drug_cst: Mapped[Any] = mapped_column(sa.Numeric(18, 2), nullable=True)

    # Drug classes
    opioid_clms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    opioid_drug_cst: Mapped[Any] = mapped_column(sa.Numeric(18, 2), nullable=True)
    opioid_prscrbr_rate: Mapped[Any] = mapped_column(sa.Numeric(7, 4), nullable=True)
    opioid_la_clms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    opioid_la_drug_cst: Mapped[Any] = mapped_column(sa.Numeric(18, 2), nullable=True)
    antbtc_clms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    antbtc_drug_cst: Mapped[Any] = mapped_column(sa.Numeric(18, 2), nullable=True)
    antpsycht_ge65_clms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    antpsycht_ge65_drug_cst: Mapped[Any] = mapped_column(sa.Numeric(18, 2), nullable=True)

    # Beneficiary demographics
    bene_avg_age: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    bene_avg_risk_scre: Mapped[Any] = mapped_column(sa.Numeric(6, 4), nullable=True)
    bene_race_wht_cnt: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    bene_race_black_cnt: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    bene_race_api_cnt: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    bene_race_hspnc_cnt: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    bene_race_natind_cnt: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    bene_race_othr_cnt: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    bene_dual_cnt: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    bene_ndual_cnt: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)

    # 65+ subset
    ge65_tot_clms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    ge65_tot_drug_cst: Mapped[Any] = mapped_column(sa.Numeric(18, 2), nullable=True)
    ge65_brnd_clms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    ge65_brnd_drug_cst: Mapped[Any] = mapped_column(sa.Numeric(18, 2), nullable=True)
    ge65_gnrc_clms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    ge65_gnrc_drug_cst: Mapped[Any] = mapped_column(sa.Numeric(18, 2), nullable=True)
    ge65_othr_clms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    ge65_othr_drug_cst: Mapped[Any] = mapped_column(sa.Numeric(18, 2), nullable=True)

    # Raw payload fallback (all source fields)
    raw_payload: Mapped[Any] = mapped_column(JSONB, nullable=True)

    updated_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )


class MedicareOptOut(PrescriberBase):
    """Providers who have opted out of Medicare.

    Source: CMS Opt-Out Affidavits (Socrata API / CSV).
    PK: npi — one row per opted-out provider.

    LESSON-010: NPI plaintext.
    LESSON-011: Global reference — no TenantScopedMixin.
    """

    __tablename__ = "medicare_opt_out"
    __table_args__ = (
        sa.Index("idx_opt_out_end_date", "opt_out_end_date"),
        sa.Index("idx_opt_out_state", "state"),
        {"schema": SCHEMA},
    )

    npi: Mapped[str] = mapped_column(sa.String(10), primary_key=True)
    first_name: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    middle_name: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    specialty: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    opt_out_effective_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    opt_out_end_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    order_referring: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    address: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(sa.String(2), nullable=True)
    zip: Mapped[str | None] = mapped_column(sa.String(10), nullable=True)
    phone: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    raw_payload: Mapped[Any] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )


__all__ = ["MedicareOptOut", "MedicarePartDUtilization", "SCHEMA"]
