"""B9.B C7 — Tier A batch 02 (10 lookup tables).

Covers NDDF BASICS 3.0 and NDDF MEDNAMES 3.0 reference tables:

  - Application types (RAPLT0)
  - Dose form descriptions (RDOSED2)
  - HIC organ-system / Rx-class / therapeutic-class descriptors
    (RHIC1D2, RHIC2D3, RHIC3D3)
  - Labeler descriptors (RLBLRID3)
  - MEDID specification, search-term, search-term-type, DESI-2-indicator
    descriptors (RMEDSPD0, RMEDST0, RMEDSTD0, RMIDE2D1)

Pattern follows batch_01 exactly. Every spec:
  * tier=Tier.A
  * loader_group="fdb_tier_a"
  * delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY
  * record_counts_key = first underscore-segment of table_name
  * NUMERIC(n) → int coercer; VARCHAR(n) → str coercer
  * nullable reflects manifest nullable=true columns exactly
"""
from __future__ import annotations

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    TableSpec,
    Tier,
)


SPECS: list[TableSpec] = [
    # FDA application type (NDDF BASICS 3.0)
    TableSpec(
        table_name="RAPLT0_APPL_TYPE",
        columns=("APPL_TYPE_ID", "APPL_TYPE_ABBREV", "APPL_TYPE_DESC"),
        coercers={
            "APPL_TYPE_ID": int,
            "APPL_TYPE_ABBREV": str,
            "APPL_TYPE_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RAPLT0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('APPL_TYPE_ID',),
    ),
    # Dose form description (NDDF BASICS 3.0)
    TableSpec(
        table_name="RDOSED2_DOSE_DESC",
        columns=("GCDF", "DOSE", "GCDF_DESC"),
        coercers={"GCDF": str, "DOSE": str, "GCDF_DESC": str},
        nullable=frozenset({"DOSE", "GCDF_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RDOSED2",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('GCDF',),
    ),
    # HIC organ-system descriptor (NDDF BASICS 3.0)
    TableSpec(
        table_name="RHIC1D2_HIC_ORGAN_SYS_DESC",
        columns=("HIC1_SEQN", "HIC1", "HIC1_DESC"),
        coercers={"HIC1_SEQN": int, "HIC1": str, "HIC1_DESC": str},
        nullable=frozenset({"HIC1_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RHIC1D2",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('HIC1_SEQN',),
    ),
    # HIC Rx-class descriptor (NDDF BASICS 3.0)
    TableSpec(
        table_name="RHIC2D3_HIC_RX_CLASS_DESC",
        columns=("HIC2_SEQN", "HIC2", "HIC2_DESC", "HIC2_ROOT"),
        coercers={
            "HIC2_SEQN": int,
            "HIC2": str,
            "HIC2_DESC": str,
            "HIC2_ROOT": int,
        },
        nullable=frozenset({"HIC2_DESC", "HIC2_ROOT"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RHIC2D3",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('HIC2_SEQN',),
    ),
    # HIC therapeutic-class descriptor (NDDF BASICS 3.0)
    TableSpec(
        table_name="RHIC3D3_HIC_THERAP_CLASS_DESC",
        columns=("HIC3_SEQN", "HIC3", "HIC3_DESC", "HIC3_GRPN", "HIC3_ROOT"),
        coercers={
            "HIC3_SEQN": int,
            "HIC3": str,
            "HIC3_DESC": str,
            "HIC3_GRPN": int,
            "HIC3_ROOT": int,
        },
        nullable=frozenset({"HIC3_DESC", "HIC3_GRPN", "HIC3_ROOT"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RHIC3D3",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('HIC3_SEQN',),
    ),
    # Labeler descriptor (NDDF BASICS 3.0)
    TableSpec(
        table_name="RLBLRID3_LBLR_DESC",
        columns=("LBLRID", "MFG", "LBLRIND"),
        coercers={"LBLRID": str, "MFG": str, "LBLRIND": str},
        nullable=frozenset({"MFG", "LBLRIND"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RLBLRID3",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('LBLRID',),
    ),
    # MEDID specification code descriptor (NDDF MEDNAMES 3.0)
    TableSpec(
        table_name="RMEDSPD0_SPECIFICATION_DESC",
        columns=("MEDID_SPECIFICATION_CODE", "MEDID_SPECIFICATION_CODE_DESC"),
        coercers={
            "MEDID_SPECIFICATION_CODE": int,
            "MEDID_SPECIFICATION_CODE_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMEDSPD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('MEDID_SPECIFICATION_CODE',),
    ),
    # MEDID search term (NDDF MEDNAMES 3.0)
    TableSpec(
        table_name="RMEDST0_MEDID_SEARCH_TERM",
        columns=(
            "MEDID",
            "SEARCH_TERM_TYPE_CD",
            "SEARCH_TERM_TEXT",
            "MED_MEDID_DESC",
            "MEDICAL_SUPPLY_IND",
        ),
        coercers={
            "MEDID": int,
            "SEARCH_TERM_TYPE_CD": int,
            "SEARCH_TERM_TEXT": str,
            "MED_MEDID_DESC": str,
            "MEDICAL_SUPPLY_IND": int,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMEDST0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('MEDID',),
    ),
    # Search term type code descriptor (NDDF MEDNAMES 3.0)
    TableSpec(
        table_name="RMEDSTD0_SEARCH_TERM_TYPE_DESC",
        columns=("SEARCH_TERM_TYPE_CD", "SEARCH_TERM_TYPE_CD_DESC"),
        coercers={
            "SEARCH_TERM_TYPE_CD": int,
            "SEARCH_TERM_TYPE_CD_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMEDSTD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('SEARCH_TERM_TYPE_CD',),
    ),
    # DESI-2 indicator descriptor (NDDF MEDNAMES 3.0)
    TableSpec(
        table_name="RMIDE2D1_REF_DESI2_IND_DESC",
        columns=("MED_REF_DESI2_IND", "MED_REF_DESI2_IND_DESC"),
        coercers={"MED_REF_DESI2_IND": str, "MED_REF_DESI2_IND_DESC": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIDE2D1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('MED_REF_DESI2_IND',),
    ),
]


__all__ = ["SPECS"]
