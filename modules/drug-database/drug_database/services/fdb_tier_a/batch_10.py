"""B9.B C15 — Tier A batch 10 (11 link/relation tables — composite+single NK).

This batch covers two structural families:

  COMPOSITE-NK (9 tables)
  -----------------------
  Each table is a pure cross-reference or attribute link. Natural key
  spans all or all-but-one columns. Where a non-key column exists it is
  a flag or conversion factor rather than a free-text description —
  still toggled in the C step of the ACD cycle per the UPSERT contract.

  Pure-link sub-family (5 tables, NK == total column count):
    RETCSCH0_ETC_SEARCH         — (ETC_SEARCH_ETC_ID, ETC_PRODUCT_RELATED_ETC_ID)
    RETCXRF0_ETC_HIC3_ETC       — (ETC_ID, HIC3_SEQN)
    RPEIAL0_DF_ATTRIBUTE_LINK   — (DOSAGE_FORM_ID, DOSAGE_FORM_ATTRIBUTE_ID)
    RPEIRER0_RELATED_RT         — (CONTINUOUS_RT_ID, INTERMITTENT_RT_ID)
    RPEIRH0_RT_HIERARCHY        — (PARENT_RT_ID, CLINICAL_RT_ID)

  Link-with-indicator sub-family (3 tables, NK=2, 3rd col is a flag):
    RPEIGL0_GEN_DF_MSTR_LINK    — (DOSAGE_FORM_ID, GCDF) + PREFERRED_DOSAGE_FORM_IND
    RPEIML0_MED_DF_MSTR_LINK    — (DOSAGE_FORM_ID, MED_DOSAGE_FORM_ID) + PREFERRED_DOSAGE_FORM_IND
    RPEIOL0_OVW_DF_MSTR_LINK    — (DOSAGE_FORM_ID, OVW_DOSAGE_FORM_ID) + PREFERRED_DOSAGE_FORM_IND

  UOM conversion (1 table, NK=2, 3rd col is NUMERIC(16,6)):
    RPEIUC0_UOM_CONVERSION      — (FROM_UOM_MSTR_ID, TO_UOM_MSTR_ID) + UOM_CONVERSION_FACTOR

  SINGLE-NK (2 tables)
  --------------------
  Standard id+desc shape already established in batch_04.
    RUNITSD0_UNITS_DESC         — DOSING_MODULE_UNIT_ABBREV (VARCHAR NK) + 2 nullable descs
    RXRNSRC0_SOURCE_DESC        — XRF_SOURCE_ID (NUMERIC NK) + 1 nullable desc

Delta semantics: all 11 tables are UPSERT_BY_NATURAL_KEY. Weekly FDB
drops update in-place by natural key; deletion is explicit A/C/D. The
link-with-indicator tables update the indicator flag on conflict; pure-
link tables have nothing to update on conflict (no-op, correct per the
simulator's `on_conflict_do_nothing` fallback for all-NK tables).

NATURAL_KEY_COUNT convention (from batch_08):
  value = number of leading columns that form the natural key.
  For pure-link tables (all cols are NK): value == len(spec.columns).
  Test helper uses this to split columns into NK portion + extra portion.
"""
from __future__ import annotations

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    decimal_16_6,
    TableSpec,
    Tier,
)


SPECS: list[TableSpec] = [
    # ------------------------------------------------------------------
    # ETC search cross-reference — pure link, 2-col composite NK
    # ------------------------------------------------------------------
    TableSpec(
        table_name="RETCSCH0_ETC_SEARCH",
        columns=(
            "ETC_SEARCH_ETC_ID",
            "ETC_PRODUCT_RELATED_ETC_ID",
        ),
        coercers={
            "ETC_SEARCH_ETC_ID": int,
            "ETC_PRODUCT_RELATED_ETC_ID": int,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RETCSCH0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('ETC_SEARCH_ETC_ID', 'ETC_PRODUCT_RELATED_ETC_ID'),
    ),
    # ------------------------------------------------------------------
    # ETC ↔ HIC3 cross-reference — pure link, 2-col composite NK
    # ------------------------------------------------------------------
    TableSpec(
        table_name="RETCXRF0_ETC_HIC3_ETC",
        columns=(
            "ETC_ID",
            "HIC3_SEQN",
        ),
        coercers={
            "ETC_ID": int,
            "HIC3_SEQN": int,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RETCXRF0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('ETC_ID', 'HIC3_SEQN'),
    ),
    # ------------------------------------------------------------------
    # Dosage-form ↔ attribute link — pure link, 2-col composite NK
    # ------------------------------------------------------------------
    TableSpec(
        table_name="RPEIAL0_DF_ATTRIBUTE_LINK",
        columns=(
            "DOSAGE_FORM_ID",
            "DOSAGE_FORM_ATTRIBUTE_ID",
        ),
        coercers={
            "DOSAGE_FORM_ID": int,
            "DOSAGE_FORM_ATTRIBUTE_ID": int,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIAL0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('DOSAGE_FORM_ID', 'DOSAGE_FORM_ATTRIBUTE_ID'),
    ),
    # ------------------------------------------------------------------
    # Generic dosage-form master link — NK=2, indicator flag as 3rd col
    # ------------------------------------------------------------------
    TableSpec(
        table_name="RPEIGL0_GEN_DF_MSTR_LINK",
        columns=(
            "DOSAGE_FORM_ID",
            "GCDF",
            "PREFERRED_DOSAGE_FORM_IND",
        ),
        coercers={
            "DOSAGE_FORM_ID": int,
            "GCDF": str,
            "PREFERRED_DOSAGE_FORM_IND": int,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIGL0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('DOSAGE_FORM_ID', 'GCDF'),
    ),
    # ------------------------------------------------------------------
    # Med dosage-form master link — NK=2, indicator flag as 3rd col
    # ------------------------------------------------------------------
    TableSpec(
        table_name="RPEIML0_MED_DF_MSTR_LINK",
        columns=(
            "DOSAGE_FORM_ID",
            "MED_DOSAGE_FORM_ID",
            "PREFERRED_DOSAGE_FORM_IND",
        ),
        coercers={
            "DOSAGE_FORM_ID": int,
            "MED_DOSAGE_FORM_ID": int,
            "PREFERRED_DOSAGE_FORM_IND": int,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIML0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('DOSAGE_FORM_ID', 'MED_DOSAGE_FORM_ID'),
    ),
    # ------------------------------------------------------------------
    # OVW dosage-form master link — NK=2, indicator flag as 3rd col
    # ------------------------------------------------------------------
    TableSpec(
        table_name="RPEIOL0_OVW_DF_MSTR_LINK",
        columns=(
            "DOSAGE_FORM_ID",
            "OVW_DOSAGE_FORM_ID",
            "PREFERRED_DOSAGE_FORM_IND",
        ),
        coercers={
            "DOSAGE_FORM_ID": int,
            "OVW_DOSAGE_FORM_ID": int,
            "PREFERRED_DOSAGE_FORM_IND": int,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIOL0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('DOSAGE_FORM_ID', 'OVW_DOSAGE_FORM_ID'),
    ),
    # ------------------------------------------------------------------
    # Related route-of-administration — pure link, 2-col composite NK
    # ------------------------------------------------------------------
    TableSpec(
        table_name="RPEIRER0_RELATED_RT",
        columns=(
            "CONTINUOUS_RT_ID",
            "INTERMITTENT_RT_ID",
        ),
        coercers={
            "CONTINUOUS_RT_ID": int,
            "INTERMITTENT_RT_ID": int,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIRER0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('CONTINUOUS_RT_ID', 'INTERMITTENT_RT_ID'),
    ),
    # ------------------------------------------------------------------
    # Route-of-administration hierarchy — pure link, 2-col composite NK
    # ------------------------------------------------------------------
    TableSpec(
        table_name="RPEIRH0_RT_HIERARCHY",
        columns=(
            "PARENT_RT_ID",
            "CLINICAL_RT_ID",
        ),
        coercers={
            "PARENT_RT_ID": int,
            "CLINICAL_RT_ID": int,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIRH0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('PARENT_RT_ID', 'CLINICAL_RT_ID'),
    ),
    # ------------------------------------------------------------------
    # Unit-of-measure conversion — NK=2, conversion factor as 3rd col
    # ------------------------------------------------------------------
    TableSpec(
        table_name="RPEIUC0_UOM_CONVERSION",
        columns=(
            "FROM_UOM_MSTR_ID",
            "TO_UOM_MSTR_ID",
            "UOM_CONVERSION_FACTOR",
        ),
        coercers={
            "FROM_UOM_MSTR_ID": int,
            "TO_UOM_MSTR_ID": int,
            "UOM_CONVERSION_FACTOR": decimal_16_6,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIUC0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('FROM_UOM_MSTR_ID', 'TO_UOM_MSTR_ID'),
    ),
    # ------------------------------------------------------------------
    # Dosing-module units description — single NK (VARCHAR), 2 nullable descs
    # ------------------------------------------------------------------
    TableSpec(
        table_name="RUNITSD0_UNITS_DESC",
        columns=(
            "DOSING_MODULE_UNIT_ABBREV",
            "UNIT_DESC_ABBREV",
            "UNIT_DESC_EXPANDED",
        ),
        coercers={
            "DOSING_MODULE_UNIT_ABBREV": str,
            "UNIT_DESC_ABBREV": str,
            "UNIT_DESC_EXPANDED": str,
        },
        nullable=frozenset({"UNIT_DESC_ABBREV", "UNIT_DESC_EXPANDED"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RUNITSD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('DOSING_MODULE_UNIT_ABBREV',),
    ),
    # ------------------------------------------------------------------
    # XRF source description — single NK (NUMERIC), 1 nullable desc
    # ------------------------------------------------------------------
    TableSpec(
        table_name="RXRNSRC0_SOURCE_DESC",
        columns=(
            "XRF_SOURCE_ID",
            "XRF_SOURCE_DESC",
        ),
        coercers={
            "XRF_SOURCE_ID": int,
            "XRF_SOURCE_DESC": str,
        },
        nullable=frozenset({"XRF_SOURCE_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RXRNSRC0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('XRF_SOURCE_ID',),
    ),
]


# Number of natural-key columns per spec — drives the test's ACD cycle
# parametrization. Convention from batch_08:
#
#   nk_count == len(spec.columns)  → pure-link table, all cols are NK,
#                                     no non-key column exists; the C step
#                                     passes vacuously (nothing to toggle).
#   nk_count < len(spec.columns)   → composite-NK with trailing extra cols;
#                                     last col (or cols[nk_count:]) is toggled.
#   nk_count == 1                  → single-NK; batch_04 extra_cols pattern.
NATURAL_KEY_COUNT: dict[str, int] = {
    "RETCSCH0_ETC_SEARCH": 2,         # pure link — all 2 cols are NK
    "RETCXRF0_ETC_HIC3_ETC": 2,       # pure link — all 2 cols are NK
    "RPEIAL0_DF_ATTRIBUTE_LINK": 2,   # pure link — all 2 cols are NK
    "RPEIGL0_GEN_DF_MSTR_LINK": 2,    # NK=2, indicator flag is 3rd col
    "RPEIML0_MED_DF_MSTR_LINK": 2,    # NK=2, indicator flag is 3rd col
    "RPEIOL0_OVW_DF_MSTR_LINK": 2,    # NK=2, indicator flag is 3rd col
    "RPEIRER0_RELATED_RT": 2,         # pure link — all 2 cols are NK
    "RPEIRH0_RT_HIERARCHY": 2,        # pure link — all 2 cols are NK
    "RPEIUC0_UOM_CONVERSION": 2,      # NK=2, conversion factor is 3rd col
    "RUNITSD0_UNITS_DESC": 1,         # single-NK — batch_04 pattern
    "RXRNSRC0_SOURCE_DESC": 1,        # single-NK — batch_04 pattern
}


__all__ = ["SPECS", "NATURAL_KEY_COUNT"]
