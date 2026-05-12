"""B9.B C8 — Tier A batch 03 (10 RMID/RMIG/RMII lookup tables).

Covers FDB NDDF Plus tables in the RMID*/RMIG*/RMII* namespace:
DEA schedule codes, DESI indicators, dose forms, routed dose form
medID cross-references, GCN sequence assignment codes, generic
therapeutic equivalency / name / pricing / spread codes, and
innovator indicator codes.

Pattern rules (see batch_01 for the authoritative template):

  * tier=Tier.A, loader_group="fdb_tier_a"
  * delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY
  * record_counts_key = first underscore-segment of the table name
  * NUMERIC(n) → int coercer; VARCHAR(n) → str coercer
  * nullable=frozenset({...}) only where the DDL manifest marks
    nullable=true; all 10 tables in this batch are fully NOT NULL
  * Natural key = first column in every spec
"""
from __future__ import annotations

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    TableSpec,
    Tier,
)


SPECS: list[TableSpec] = [
    # DEA schedule code descriptor
    TableSpec(
        table_name="RMIDEAD1_REF_FED_DEA_DESC",
        columns=("MED_REF_DEA_CD", "MED_REF_DEA_CD_DESC"),
        coercers={"MED_REF_DEA_CD": str, "MED_REF_DEA_CD_DESC": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIDEAD1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # DESI indicator descriptor
    TableSpec(
        table_name="RMIDESD1_REF_DESI_IND_DESC",
        columns=("MED_REF_DESI_IND", "MED_REF_DESI_IND_DESC"),
        coercers={"MED_REF_DESI_IND": str, "MED_REF_DESI_IND_DESC": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIDESD1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Dose form (3-column: id + abbreviation + description)
    TableSpec(
        table_name="RMIDFD1_DOSE_FORM",
        columns=("MED_DOSAGE_FORM_ID", "MED_DOSAGE_FORM_ABBR", "MED_DOSAGE_FORM_DESC"),
        coercers={
            "MED_DOSAGE_FORM_ID": int,
            "MED_DOSAGE_FORM_ABBR": str,
            "MED_DOSAGE_FORM_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIDFD1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Routed dose form medID cross-reference (5-column)
    TableSpec(
        table_name="RMIDFID1_ROUTED_DOSE_FORM_MED",
        columns=(
            "ROUTED_DOSAGE_FORM_MED_ID",
            "ROUTED_MED_ID",
            "MED_DOSAGE_FORM_ID",
            "MED_ROUTED_DF_MED_ID_DESC",
            "MED_STATUS_CD",
        ),
        coercers={
            "ROUTED_DOSAGE_FORM_MED_ID": int,
            "ROUTED_MED_ID": int,
            "MED_DOSAGE_FORM_ID": int,
            "MED_ROUTED_DF_MED_ID_DESC": str,
            "MED_STATUS_CD": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIDFID1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # GCN sequence-number assignment code descriptor
    TableSpec(
        table_name="RMIGCND1_GCNSEQNO_ASSGN_DESC",
        columns=("MED_GCNSEQNO_ASSIGN_CD", "MED_GCNSEQNO_ASSIGN_CD_DESC"),
        coercers={"MED_GCNSEQNO_ASSIGN_CD": str, "MED_GCNSEQNO_ASSIGN_CD_DESC": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIGCND1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Generic therapeutic equivalency code descriptor
    TableSpec(
        table_name="RMIGECD1_REF_GEN_THERAP_DESC",
        columns=("MED_REF_GEN_THERA_EQU_CD", "MED_REF_GEN_THERA_EQU_CD_DESC"),
        coercers={
            "MED_REF_GEN_THERA_EQU_CD": str,
            "MED_REF_GEN_THERA_EQU_CD_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIGECD1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Generic drug name code descriptor
    TableSpec(
        table_name="RMIGNCD1_REF_GEN_NAME_DESC",
        columns=("MED_REF_GEN_DRUG_NAME_CD", "MED_REF_GEN_DRUG_NAME_CD_DESC"),
        coercers={
            "MED_REF_GEN_DRUG_NAME_CD": str,
            "MED_REF_GEN_DRUG_NAME_CD_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIGNCD1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Generic competitive price code descriptor
    TableSpec(
        table_name="RMIGPCD1_REF_GEN_PRC_DESC",
        columns=("MED_REF_GEN_COMP_PRICE_CD", "MED_REF_GEN_COMP_PRICE_CD_DESC"),
        coercers={
            "MED_REF_GEN_COMP_PRICE_CD": str,
            "MED_REF_GEN_COMP_PRICE_CD_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIGPCD1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Generic price spread code descriptor
    TableSpec(
        table_name="RMIGSCD1_REF_GEN_PRC_SPRD_DESC",
        columns=("MED_REF_GEN_SPREAD_CD", "MED_REF_GEN_SPREAD_CD_DESC"),
        coercers={
            "MED_REF_GEN_SPREAD_CD": str,
            "MED_REF_GEN_SPREAD_CD_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIGSCD1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Innovator indicator code descriptor
    TableSpec(
        table_name="RMIINND1_REF_INNOV_IND_DESC",
        columns=("MED_REF_INNOV_IND", "MED_REF_INNOV_IND_DESC"),
        coercers={"MED_REF_INNOV_IND": str, "MED_REF_INNOV_IND_DESC": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIINND1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
]


__all__ = ["SPECS"]
