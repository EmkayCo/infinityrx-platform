"""B9.B C16 — Tier A batch 11 (11 link/relation tables with DATE columns).

This batch covers biologics ingredient links, proprietary name lookup,
med-concept relation tables, external product code mappings, cross-reference
family tables, and the ScriptQQ master/link set.

DATE columns appear in 5 of the 11 specs:
  - RMEDMGL0_MED_GENERIC_MED_LINK  col 4  MED_CONCEPT_OBSDATEC   nullable
  - RMEDMHL0_MED_HICLSEQNO_LINK    col 5  MED_CONCEPT_OBSDATEC   nullable
  - RPRDPC0_EXT_PRODUCT_CD         col 3  EXT_PRODUCT_CD_START_DT NOT NULL
                                   col 5  EXT_PRODUCT_CD_END_DT   nullable
  - RXRNCQQ0_QQ_MSTR               col 5  OBSOLETE_DATE           nullable

All DATE columns use `_parse_fdb_date` (YYYYMMDD → datetime.date).
Nullable columns (manifest nullable=true) are declared in `nullable=frozenset`.

Natural key widths are mixed in this batch (1, 2, 3, or 4 columns).
The NATURAL_KEY_COUNT dict drives the test's hybrid ACD parametrization:
  NK >= 2 → composite-NK pattern (batch_08 template)
  NK == 1 → single-NK + extra_cols pattern (batch_04 template)

Delta semantics: UPSERT_BY_NATURAL_KEY throughout.
"""
from __future__ import annotations

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    TableSpec,
    Tier,
    _parse_fdb_date,
)


SPECS: list[TableSpec] = [
    # Biologics BLA ingredient → HIC sequence link (5 cols, NK=4).
    # All columns NOT NULL; BLA_APPL_NBR is VARCHAR, rest NUMERIC.
    TableSpec(
        table_name="RBLAHIC0_INGREDIENTS",
        columns=(
            "BLA_APPL_NBR",
            "APPL_TYPE_ID",
            "BIOLOGICS_SN",
            "MULTI_INGREDIENT_SN",
            "HIC_SEQN",
        ),
        coercers={
            "BLA_APPL_NBR": str,
            "APPL_TYPE_ID": int,
            "BIOLOGICS_SN": int,
            "MULTI_INGREDIENT_SN": int,
            "HIC_SEQN": int,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RBLAHIC0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Biologics BLA proprietary name lookup (4 cols, NK=1 PROPRIETARY_NAME_ID).
    # All columns NOT NULL.
    TableSpec(
        table_name="RBLAPN0_PROPRIETARY_NAME",
        columns=(
            "PROPRIETARY_NAME_ID",
            "BLA_APPL_NBR",
            "APPL_TYPE_ID",
            "PROPRIETARY_NAME",
        ),
        coercers={
            "PROPRIETARY_NAME_ID": int,
            "BLA_APPL_NBR": str,
            "APPL_TYPE_ID": int,
            "PROPRIETARY_NAME": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RBLAPN0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Med concept → generic med concept link (4 cols, NK=3).
    # MED_CONCEPT_OBSDATEC is DATE, nullable.
    TableSpec(
        table_name="RMEDMGL0_MED_GENERIC_MED_LINK",
        columns=(
            "MED_CONCEPT_ID",
            "MED_CONCEPT_ID_TYP",
            "GENERIC_MED_CONCEPT_ID",
            "MED_CONCEPT_OBSDATEC",
        ),
        coercers={
            "MED_CONCEPT_ID": int,
            "MED_CONCEPT_ID_TYP": int,
            "GENERIC_MED_CONCEPT_ID": int,
            "MED_CONCEPT_OBSDATEC": _parse_fdb_date,
        },
        nullable=frozenset({"MED_CONCEPT_OBSDATEC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMEDMGL0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Med concept → HICL sequence number link (5 cols, NK=3).
    # MED_CONCEPT_HICL_SRC_CD is NUMERIC NOT NULL (col 4).
    # MED_CONCEPT_OBSDATEC is DATE, nullable (col 5).
    TableSpec(
        table_name="RMEDMHL0_MED_HICLSEQNO_LINK",
        columns=(
            "MED_CONCEPT_ID",
            "MED_CONCEPT_ID_TYP",
            "HICL_SEQNO",
            "MED_CONCEPT_HICL_SRC_CD",
            "MED_CONCEPT_OBSDATEC",
        ),
        coercers={
            "MED_CONCEPT_ID": int,
            "MED_CONCEPT_ID_TYP": int,
            "HICL_SEQNO": int,
            "MED_CONCEPT_HICL_SRC_CD": int,
            "MED_CONCEPT_OBSDATEC": _parse_fdb_date,
        },
        nullable=frozenset({"MED_CONCEPT_OBSDATEC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMEDMHL0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # External product code mapping (5 cols, NK=4).
    # EXT_PRODUCT_CD_START_DT is DATE NOT NULL (part of NK).
    # EXT_PRODUCT_CD_END_DT is DATE, nullable.
    TableSpec(
        table_name="RPRDPC0_EXT_PRODUCT_CD",
        columns=(
            "FDB_PRODUCT_ID",
            "EXT_PRODUCT_CD_TYPE_ID",
            "EXT_PRODUCT_CD_START_DT",
            "EXT_PRODUCT_CD",
            "EXT_PRODUCT_CD_END_DT",
        ),
        coercers={
            "FDB_PRODUCT_ID": int,
            "EXT_PRODUCT_CD_TYPE_ID": int,
            "EXT_PRODUCT_CD_START_DT": _parse_fdb_date,
            "EXT_PRODUCT_CD": str,
            "EXT_PRODUCT_CD_END_DT": _parse_fdb_date,
        },
        nullable=frozenset({"EXT_PRODUCT_CD_END_DT"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPRDPC0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # DAM AGCSP → HIC sequence cross-reference (3 cols, NK=2).
    # All columns NOT NULL.
    TableSpec(
        table_name="RXRFAHX0_AGCSP_HICSEQN",
        columns=(
            "DAM_AGCSP",
            "HIC_SEQN",
            "HIC",
        ),
        coercers={
            "DAM_AGCSP": int,
            "HIC_SEQN": int,
            "HIC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RXRFAHX0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # DACN → DAM AGCSP cross-reference (2 cols, NK=2).
    # Both columns NOT NULL.
    TableSpec(
        table_name="RXRFDDX0_DACN_AGCSP",
        columns=(
            "DACN",
            "DAM_AGCSP",
        ),
        coercers={
            "DACN": str,
            "DAM_AGCSP": int,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RXRFDDX0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # GCDF → ScriptQQ cross-reference (2 cols, NK=2).
    # Both columns NOT NULL.
    TableSpec(
        table_name="RXRGDFQ0_GCDF_SCRIPT_QQ",
        columns=(
            "GCDF",
            "SCRIPT_QQ_ID",
        ),
        coercers={
            "GCDF": str,
            "SCRIPT_QQ_ID": int,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RXRGDFQ0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Med dosage form → ScriptQQ cross-reference (2 cols, NK=2).
    # Both columns NOT NULL.
    TableSpec(
        table_name="RXRMDFQ0_MEDDOSFM_SCRIPT_QQ",
        columns=(
            "MED_DOSAGE_FORM_ID",
            "SCRIPT_QQ_ID",
        ),
        coercers={
            "MED_DOSAGE_FORM_ID": int,
            "SCRIPT_QQ_ID": int,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RXRMDFQ0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # ScriptQQ master (5 cols, NK=1 SCRIPT_QQ_ID).
    # Cols 2-5 nullable; OBSOLETE_DATE is DATE nullable.
    TableSpec(
        table_name="RXRNCQQ0_QQ_MSTR",
        columns=(
            "SCRIPT_QQ_ID",
            "SCRIPT_QQ_CD",
            "SCRIPT_QQ_DESC",
            "XRF_SOURCE_ID",
            "OBSOLETE_DATE",
        ),
        coercers={
            "SCRIPT_QQ_ID": int,
            "SCRIPT_QQ_CD": str,
            "SCRIPT_QQ_DESC": str,
            "XRF_SOURCE_ID": int,
            "OBSOLETE_DATE": _parse_fdb_date,
        },
        nullable=frozenset({"SCRIPT_QQ_CD", "SCRIPT_QQ_DESC", "XRF_SOURCE_ID", "OBSOLETE_DATE"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RXRNCQQ0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # POE med dosage form → ScriptQQ cross-reference (2 cols, NK=2).
    # Both columns NOT NULL.
    TableSpec(
        table_name="RXRPDFQ0_POEMDOSFM_SCRIPT_QQ",
        columns=(
            "POEUNITCDE",
            "SCRIPT_QQ_ID",
        ),
        coercers={
            "POEUNITCDE": int,
            "SCRIPT_QQ_ID": int,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RXRPDFQ0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
]


# Number of natural-key columns per spec — drives the test's hybrid
# ACD cycle parametrization:
#   NK >= 2 → composite-NK pattern (batch_08 template)
#   NK == 1 → single-NK + extra_cols pattern (batch_04 template)
NATURAL_KEY_COUNT: dict[str, int] = {
    "RBLAHIC0_INGREDIENTS": 4,
    "RBLAPN0_PROPRIETARY_NAME": 1,
    "RMEDMGL0_MED_GENERIC_MED_LINK": 3,
    "RMEDMHL0_MED_HICLSEQNO_LINK": 3,
    "RPRDPC0_EXT_PRODUCT_CD": 4,
    "RXRFAHX0_AGCSP_HICSEQN": 2,
    "RXRFDDX0_DACN_AGCSP": 2,
    "RXRGDFQ0_GCDF_SCRIPT_QQ": 2,
    "RXRMDFQ0_MEDDOSFM_SCRIPT_QQ": 2,
    "RXRNCQQ0_QQ_MSTR": 1,
    "RXRPDFQ0_POEMDOSFM_SCRIPT_QQ": 2,
}


__all__ = ["SPECS", "NATURAL_KEY_COUNT"]
