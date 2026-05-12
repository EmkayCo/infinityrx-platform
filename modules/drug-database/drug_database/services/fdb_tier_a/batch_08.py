"""B9.B C13 — Tier A batch 08 (composite-NK template: 5 TALL MAN tables).

This batch establishes the COMPOSITE NATURAL KEY pattern that
subsequent link/relation batches (09, 10) replicate. The TALL MAN
PLUS tables all share the shape:

    (entity_id, TM_SOURCE_ID, TM_IND, <desc>)
                ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
                3-column natural key

The first column varies (MEDID / ROUTED_MED_ID / ROUTED_DOSAGE_FORM_MED_ID
/ MED_NAME_ID / HICL_SEQNO + TM_GNN_TYPE_ID for RTMNGN0). Source ID +
TM indicator are the variant axes — same source can have multiple
indicator-tagged entries per entity, hence the 3-column NK.

Delta semantics: still UPSERT_BY_NATURAL_KEY. A change to the desc
column for the same (entity, source, ind) tuple overwrites the row;
this matches the FDB weekly delta contract for TALL MAN data.
"""
from __future__ import annotations

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    TableSpec,
    Tier,
)


SPECS: list[TableSpec] = [
    # Tall Man: routed dose-form med id alternates
    TableSpec(
        table_name="RTMDFID1_TM_ROUTED_DF_MED",
        columns=(
            "ROUTED_DOSAGE_FORM_MED_ID",
            "TM_SOURCE_ID",
            "TM_IND",
            "TM_ALT_ROUTED_DF_MED_ID_DESC",
        ),
        coercers={
            "ROUTED_DOSAGE_FORM_MED_ID": int,
            "TM_SOURCE_ID": int,
            "TM_IND": str,
            "TM_ALT_ROUTED_DF_MED_ID_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RTMDFID1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('ROUTED_DOSAGE_FORM_MED_ID', 'TM_SOURCE_ID', 'TM_IND'),
    ),
    # Tall Man: MEDID alternates
    TableSpec(
        table_name="RTMMID1_TM_MED",
        columns=("MEDID", "TM_SOURCE_ID", "TM_IND", "TM_ALT_MEDID_DESC"),
        coercers={
            "MEDID": int,
            "TM_SOURCE_ID": int,
            "TM_IND": str,
            "TM_ALT_MEDID_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RTMMID1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('MEDID', 'TM_SOURCE_ID', 'TM_IND'),
    ),
    # Tall Man: GNN alternates — 4-column NK (the largest composite in batch_08)
    TableSpec(
        table_name="RTMNGN0_TM_GNN",
        columns=(
            "HICL_SEQNO",
            "TM_GNN_TYPE_ID",
            "TM_SOURCE_ID",
            "TM_IND",
            "TM_ALT_GNN_DESC",
        ),
        coercers={
            "HICL_SEQNO": int,
            "TM_GNN_TYPE_ID": int,
            "TM_SOURCE_ID": int,
            "TM_IND": str,
            "TM_ALT_GNN_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RTMNGN0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('HICL_SEQNO', 'TM_GNN_TYPE_ID', 'TM_SOURCE_ID', 'TM_IND'),
    ),
    # Tall Man: med-name id alternates
    TableSpec(
        table_name="RTMNMID1_TM_MED_NAME",
        columns=(
            "MED_NAME_ID",
            "TM_SOURCE_ID",
            "TM_IND",
            "TM_ALT_MED_NAME_DESC",
        ),
        coercers={
            "MED_NAME_ID": int,
            "TM_SOURCE_ID": int,
            "TM_IND": str,
            "TM_ALT_MED_NAME_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RTMNMID1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('MED_NAME_ID', 'TM_SOURCE_ID', 'TM_IND'),
    ),
    # Tall Man: routed-med id alternates
    TableSpec(
        table_name="RTMRMID1_TM_ROUTED_MED",
        columns=(
            "ROUTED_MED_ID",
            "TM_SOURCE_ID",
            "TM_IND",
            "TM_ALT_ROUTED_MED_ID_DESC",
        ),
        coercers={
            "ROUTED_MED_ID": int,
            "TM_SOURCE_ID": int,
            "TM_IND": str,
            "TM_ALT_ROUTED_MED_ID_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RTMRMID1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('ROUTED_MED_ID', 'TM_SOURCE_ID', 'TM_IND'),
    ),
]


# Number of natural-key columns per spec — drives the test's
# composite-NK ACD cycle parametrization. The composite-NK pattern
# is: all columns except the LAST are the natural key; the LAST is
# the desc that the C step toggles.
NATURAL_KEY_COUNT: dict[str, int] = {
    "RTMDFID1_TM_ROUTED_DF_MED": 3,
    "RTMMID1_TM_MED": 3,
    "RTMNGN0_TM_GNN": 4,
    "RTMNMID1_TM_MED_NAME": 3,
    "RTMRMID1_TM_ROUTED_MED": 3,
}


__all__ = ["SPECS", "NATURAL_KEY_COUNT"]
