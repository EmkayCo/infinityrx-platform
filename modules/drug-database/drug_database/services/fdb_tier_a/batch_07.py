"""B9.B C12 — Tier A batch 07 (10 lookup tables: RTD/Strength/TC/TM families).

Follows the canonical batch_04 pattern. Tables:

  RRTGNSD0_RTD_GEN_STATUS_DSC   — Routed generic status code descriptor (2 cols)
  RSTR1_STRNGTH_DESC             — Strength descriptor (5 cols; STRNUM/VOLNUM/STRUN50/VOLUN50 nullable)
  RSTRSCD0_STRENGTH_STATUS_DESC  — Strength status code descriptor (2 cols; STRENGTH_STATUS_DESC nullable)
  RSTRTD0_STRENGTH_TYP_DESC      — Strength type code descriptor (2 cols; STRENGTH_TYP_DESC nullable)
  RSTRUOM0_STRENGTH_UOM          — Strength unit of measure (4 cols; UOM_DESC/UOM_ABBR/UOM_PREFERRED_DESC nullable)
  RTCD0_STD_THERAP_CLASS_DESC    — Standard therapeutic class descriptor (2 cols; TC_DESC nullable)
  RTMDT0_TM_NAME_TYPE            — TM name type (2 cols)
  RTMGRPD1_TM_GROUP_DESC         — TM group descriptor (2 cols; TM_GROUP_DESC nullable)
  RTMNGT0_TM_GNN_TYPE            — TM GNN type (2 cols)
  RTMSRCD1_TM_SOURCE_DESC        — TM source descriptor (2 cols; TM_SOURCE_DESC nullable)

Coercer rules: NUMERIC(n) → int; VARCHAR(n) → str. No DATE or Decimal columns
in this batch. See batch_01 docstring for the authoritative pattern notes.
"""
from __future__ import annotations

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    TableSpec,
    Tier,
)


SPECS: list[TableSpec] = [
    # Routed generic status code descriptor
    TableSpec(
        table_name="RRTGNSD0_RTD_GEN_STATUS_DSC",
        columns=("ROUTED_GEN_STATUS_CD", "ROUTED_GEN_STATUS_CD_DESC"),
        coercers={
            "ROUTED_GEN_STATUS_CD": str,
            "ROUTED_GEN_STATUS_CD_DESC": str,
        },
        nullable=frozenset(),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RRTGNSD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Strength descriptor (5 cols; STRNUM/VOLNUM/STRUN50/VOLUN50 nullable per DDL)
    TableSpec(
        table_name="RSTR1_STRNGTH_DESC",
        columns=("STR60", "STRNUM", "VOLNUM", "STRUN50", "VOLUN50"),
        coercers={
            "STR60": str,
            "STRNUM": int,
            "VOLNUM": int,
            "STRUN50": str,
            "VOLUN50": str,
        },
        nullable=frozenset({"STRNUM", "VOLNUM", "STRUN50", "VOLUN50"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RSTR1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Strength status code descriptor (STRENGTH_STATUS_DESC nullable per DDL)
    TableSpec(
        table_name="RSTRSCD0_STRENGTH_STATUS_DESC",
        columns=("STRENGTH_STATUS_CODE", "STRENGTH_STATUS_DESC"),
        coercers={
            "STRENGTH_STATUS_CODE": int,
            "STRENGTH_STATUS_DESC": str,
        },
        nullable=frozenset({"STRENGTH_STATUS_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RSTRSCD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Strength type code descriptor (STRENGTH_TYP_DESC nullable per DDL)
    TableSpec(
        table_name="RSTRTD0_STRENGTH_TYP_DESC",
        columns=("STRENGTH_TYP_CODE", "STRENGTH_TYP_DESC"),
        coercers={
            "STRENGTH_TYP_CODE": int,
            "STRENGTH_TYP_DESC": str,
        },
        nullable=frozenset({"STRENGTH_TYP_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RSTRTD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Strength unit of measure (UOM_DESC/UOM_ABBR/UOM_PREFERRED_DESC nullable per DDL)
    TableSpec(
        table_name="RSTRUOM0_STRENGTH_UOM",
        columns=("UOM_ID", "UOM_DESC", "UOM_ABBR", "UOM_PREFERRED_DESC"),
        coercers={
            "UOM_ID": int,
            "UOM_DESC": str,
            "UOM_ABBR": str,
            "UOM_PREFERRED_DESC": str,
        },
        nullable=frozenset({"UOM_DESC", "UOM_ABBR", "UOM_PREFERRED_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RSTRUOM0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Standard therapeutic class descriptor (TC_DESC nullable per DDL)
    TableSpec(
        table_name="RTCD0_STD_THERAP_CLASS_DESC",
        columns=("TC", "TC_DESC"),
        coercers={
            "TC": int,
            "TC_DESC": str,
        },
        nullable=frozenset({"TC_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RTCD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # TM name type (no nullable columns per DDL)
    TableSpec(
        table_name="RTMDT0_TM_NAME_TYPE",
        columns=("TM_NAME_TYPE_ID", "TM_NAME_TYPE_DESC"),
        coercers={
            "TM_NAME_TYPE_ID": int,
            "TM_NAME_TYPE_DESC": str,
        },
        nullable=frozenset(),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RTMDT0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # TM group descriptor (TM_GROUP_DESC nullable per DDL)
    TableSpec(
        table_name="RTMGRPD1_TM_GROUP_DESC",
        columns=("TM_GROUP_ID", "TM_GROUP_DESC"),
        coercers={
            "TM_GROUP_ID": int,
            "TM_GROUP_DESC": str,
        },
        nullable=frozenset({"TM_GROUP_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RTMGRPD1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # TM GNN type (no nullable columns per DDL)
    TableSpec(
        table_name="RTMNGT0_TM_GNN_TYPE",
        columns=("TM_GNN_TYPE_ID", "TM_GNN_TYPE_DESC"),
        coercers={
            "TM_GNN_TYPE_ID": int,
            "TM_GNN_TYPE_DESC": str,
        },
        nullable=frozenset(),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RTMNGT0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # TM source descriptor (TM_SOURCE_DESC nullable per DDL)
    TableSpec(
        table_name="RTMSRCD1_TM_SOURCE_DESC",
        columns=("TM_SOURCE_ID", "TM_SOURCE_DESC"),
        coercers={
            "TM_SOURCE_ID": int,
            "TM_SOURCE_DESC": str,
        },
        nullable=frozenset({"TM_SOURCE_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RTMSRCD1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
]


__all__ = ["SPECS"]
