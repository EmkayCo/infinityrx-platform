"""B9.B C9 — Tier A batch 04 (10 lookup tables: MEDNAMES routes/status + OBC + ATTRIBUTE).

Follows the canonical batch_01 pattern. Tables:

  RMILGND1_REF_FED_LGND_DESC  — Federal legend indicator descriptor
  RMIMLTD1_REF_MULTI_SRC_DESC — Multi-source code descriptor
  RMINAMD1_NAME_SRC_DESC      — Name source code descriptor
  RMINMD1_MED_NAME_TYPE_DESC  — Med name type code descriptor
  RMIRMID1_ROUTED_MED         — Routed medication (5 columns)
  RMIRTD1_ROUTE               — Route of administration descriptor
  RMISCD1_STATUS_DESC         — Medication status code descriptor
  ROBCD0_OBC_DESC             — OBC descriptor (OBC_DESC nullable)
  RPEIAD0_ATTRIBUTE_DESC      — Attribute descriptor (ATTRIBUTE_GROUP_CODE nullable)
  RPEIAT0_ATTRIBUTE_TYPE_DESC — Attribute type descriptor (LENGTH/PRECISION nullable)

Coercer rules: NUMERIC(n) → int; VARCHAR(n) → str. No Date or Decimal columns
in this batch. See batch_01 docstring for the authoritative pattern notes.
"""
from __future__ import annotations

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    TableSpec,
    Tier,
)


SPECS: list[TableSpec] = [
    # Federal legend indicator descriptor
    TableSpec(
        table_name="RMILGND1_REF_FED_LGND_DESC",
        columns=("MED_REF_FED_LEGEND_IND", "MED_REF_FED_LEGEND_IND_DESC"),
        coercers={
            "MED_REF_FED_LEGEND_IND": str,
            "MED_REF_FED_LEGEND_IND_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMILGND1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Multi-source code descriptor
    TableSpec(
        table_name="RMIMLTD1_REF_MULTI_SRC_DESC",
        columns=("MED_REF_MULTI_SOURCE_CD", "MED_REF_MULTI_SOURCE_CD_DESC"),
        coercers={
            "MED_REF_MULTI_SOURCE_CD": str,
            "MED_REF_MULTI_SOURCE_CD_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIMLTD1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Name source code descriptor
    TableSpec(
        table_name="RMINAMD1_NAME_SRC_DESC",
        columns=("MED_NAME_SOURCE_CD", "MED_NAME_SOURCE_CD_DESC"),
        coercers={
            "MED_NAME_SOURCE_CD": str,
            "MED_NAME_SOURCE_CD_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMINAMD1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Med name type code descriptor
    TableSpec(
        table_name="RMINMD1_MED_NAME_TYPE_DESC",
        columns=("MED_NAME_TYPE_CD", "MED_NAME_TYPE_CD_DESC"),
        coercers={
            "MED_NAME_TYPE_CD": str,
            "MED_NAME_TYPE_CD_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMINMD1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Routed medication (5 columns; natural key = ROUTED_MED_ID, first col)
    TableSpec(
        table_name="RMIRMID1_ROUTED_MED",
        columns=(
            "ROUTED_MED_ID",
            "MED_NAME_ID",
            "MED_ROUTE_ID",
            "MED_ROUTED_MED_ID_DESC",
            "MED_STATUS_CD",
        ),
        coercers={
            "ROUTED_MED_ID": int,
            "MED_NAME_ID": int,
            "MED_ROUTE_ID": int,
            "MED_ROUTED_MED_ID_DESC": str,
            "MED_STATUS_CD": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIRMID1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Route of administration descriptor
    TableSpec(
        table_name="RMIRTD1_ROUTE",
        columns=("MED_ROUTE_ID", "MED_ROUTE_ABBR", "MED_ROUTE_DESC"),
        coercers={
            "MED_ROUTE_ID": int,
            "MED_ROUTE_ABBR": str,
            "MED_ROUTE_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIRTD1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Medication status code descriptor
    TableSpec(
        table_name="RMISCD1_STATUS_DESC",
        columns=("MED_STATUS_CD", "MED_STATUS_CD_DESC"),
        coercers={
            "MED_STATUS_CD": str,
            "MED_STATUS_CD_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMISCD1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # OBC descriptor (OBC_DESC is nullable per DDL)
    TableSpec(
        table_name="ROBCD0_OBC_DESC",
        columns=("OBC", "OBC_SN", "OBC_DESC"),
        coercers={
            "OBC": str,
            "OBC_SN": int,
            "OBC_DESC": str,
        },
        nullable=frozenset({"OBC_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="ROBCD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Attribute descriptor (ATTRIBUTE_GROUP_CODE nullable per DDL)
    TableSpec(
        table_name="RPEIAD0_ATTRIBUTE_DESC",
        columns=(
            "ATTRIBUTE_CODE",
            "ATTRIBUTE_DESC",
            "ATTRIBUTE_TYPE_CODE",
            "ATTRIBUTE_GROUP_CODE",
        ),
        coercers={
            "ATTRIBUTE_CODE": int,
            "ATTRIBUTE_DESC": str,
            "ATTRIBUTE_TYPE_CODE": int,
            "ATTRIBUTE_GROUP_CODE": int,
        },
        nullable=frozenset({"ATTRIBUTE_GROUP_CODE"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIAD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Attribute type descriptor (LENGTH and PRECISION nullable per DDL)
    TableSpec(
        table_name="RPEIAT0_ATTRIBUTE_TYPE_DESC",
        columns=(
            "ATTRIBUTE_TYPE_CODE",
            "ATTRIBUTE_TYPE_DESC",
            "ATTRIBUTE_TYPE_LENGTH",
            "ATTRIBUTE_TYPE_PRECISION",
        ),
        coercers={
            "ATTRIBUTE_TYPE_CODE": int,
            "ATTRIBUTE_TYPE_DESC": str,
            "ATTRIBUTE_TYPE_LENGTH": int,
            "ATTRIBUTE_TYPE_PRECISION": int,
        },
        nullable=frozenset({"ATTRIBUTE_TYPE_LENGTH", "ATTRIBUTE_TYPE_PRECISION"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIAT0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
]


__all__ = ["SPECS"]
