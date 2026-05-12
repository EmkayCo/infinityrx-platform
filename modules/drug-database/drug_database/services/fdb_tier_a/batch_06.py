"""B9.B C11 — Tier A batch 06 (10 lookup tables: NDC attribute, price attr, product/package, route).

Follows the canonical batch_04 pattern. Tables:

  RNDCTD0_NDC_ATTRIBUTE_TYP_DSC  — NDC attribute type code descriptor (2 cols)
  RNDCVD0_NDC_ATTRIBUTE_VALU_DSC — NDC attribute value descriptor (3 cols)
  RPRDPAT0_PRICE_ATTR_TYPE_DESC  — Price attribute type descriptor (4 cols, 2 nullable)
  RPRDPAV0_PRICE_ATTR_VALUE_DESC — Price attribute value descriptor (3 cols, 1 nullable)
  RPRDPCD0_EXT_PRODUCT_CD_DESC   — Extended product code descriptor (5 cols, 1 nullable)
  RPRDPKD0_PACKAGE_DESC          — Package type descriptor (4 cols)
  RPRDSD0_PRODUCT_STATUS_DESC    — Product status descriptor (3 cols, 1 nullable)
  RPRDUOM0_PRICE_QTY_UOM         — Price quantity unit of measure (2 cols)
  RROUTED3_ROUTE_DESC            — Route descriptor (5 cols, 4 nullable)
  RRTGN0_ROUTED_GEN_MSTR         — Routed generic master (5 cols)

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
    # NDC attribute type code descriptor (2 cols, none nullable)
    TableSpec(
        table_name="RNDCTD0_NDC_ATTRIBUTE_TYP_DSC",
        columns=("NDC_ATTRIBUTE_TYPE_CD", "NDC_ATTRIBUTE_TYPE_DSC"),
        coercers={
            "NDC_ATTRIBUTE_TYPE_CD": int,
            "NDC_ATTRIBUTE_TYPE_DSC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RNDCTD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('NDC_ATTRIBUTE_TYPE_CD',),
    ),
    # NDC attribute value descriptor (3 cols, none nullable)
    TableSpec(
        table_name="RNDCVD0_NDC_ATTRIBUTE_VALU_DSC",
        columns=(
            "NDC_ATTRIBUTE_TYPE_CD",
            "NDC_ATTRIBUTE_VALUE",
            "NDC_ATTRIBUTE_VALUE_DSC",
        ),
        coercers={
            "NDC_ATTRIBUTE_TYPE_CD": int,
            "NDC_ATTRIBUTE_VALUE": str,
            "NDC_ATTRIBUTE_VALUE_DSC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RNDCVD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('NDC_ATTRIBUTE_TYPE_CD',),
    ),
    # Price attribute type descriptor (4 cols; LENGTH and PRECISION nullable per DDL)
    TableSpec(
        table_name="RPRDPAT0_PRICE_ATTR_TYPE_DESC",
        columns=(
            "PRICE_ATTRIBUTE_TYPE_CD",
            "PRICE_ATTRIBUTE_TYPE_DESC",
            "PRICE_ATTRIBUTE_TYPE_LENGTH",
            "PRICE_ATTRIBUTE_TYPE_PRECISION",
        ),
        coercers={
            "PRICE_ATTRIBUTE_TYPE_CD": str,
            "PRICE_ATTRIBUTE_TYPE_DESC": str,
            "PRICE_ATTRIBUTE_TYPE_LENGTH": int,
            "PRICE_ATTRIBUTE_TYPE_PRECISION": int,
        },
        nullable=frozenset({"PRICE_ATTRIBUTE_TYPE_LENGTH", "PRICE_ATTRIBUTE_TYPE_PRECISION"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPRDPAT0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('PRICE_ATTRIBUTE_TYPE_CD',),
    ),
    # Price attribute value descriptor (3 cols; VALUE_DESC nullable per DDL)
    TableSpec(
        table_name="RPRDPAV0_PRICE_ATTR_VALUE_DESC",
        columns=(
            "PRICE_ATTRIBUTE_CD",
            "PRICE_ATTRIBUTE_VALUE",
            "PRICE_ATTRIBUTE_VALUE_DESC",
        ),
        coercers={
            "PRICE_ATTRIBUTE_CD": str,
            "PRICE_ATTRIBUTE_VALUE": str,
            "PRICE_ATTRIBUTE_VALUE_DESC": str,
        },
        nullable=frozenset({"PRICE_ATTRIBUTE_VALUE_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPRDPAV0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('PRICE_ATTRIBUTE_CD',),
    ),
    # Extended product code descriptor (5 cols; DEFINITION nullable per DDL)
    TableSpec(
        table_name="RPRDPCD0_EXT_PRODUCT_CD_DESC",
        columns=(
            "EXT_PRODUCT_CD_TYPE_ID",
            "EXT_PRODUCT_CD_DESC",
            "EXT_PRODUCT_CD_DATA_TYPE",
            "EXT_PRODUCT_CD_FIELD_LENGTH",
            "EXT_PRODUCT_CD_DEFINITION",
        ),
        coercers={
            "EXT_PRODUCT_CD_TYPE_ID": int,
            "EXT_PRODUCT_CD_DESC": str,
            "EXT_PRODUCT_CD_DATA_TYPE": str,
            "EXT_PRODUCT_CD_FIELD_LENGTH": int,
            "EXT_PRODUCT_CD_DEFINITION": str,
        },
        nullable=frozenset({"EXT_PRODUCT_CD_DEFINITION"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPRDPCD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('EXT_PRODUCT_CD_TYPE_ID',),
    ),
    # Package type descriptor (4 cols, none nullable)
    TableSpec(
        table_name="RPRDPKD0_PACKAGE_DESC",
        columns=(
            "PACKAGE_TYPE_ID",
            "PKG_TYPE_LONG_DESC",
            "PKG_TYPE_SHORT_DESC",
            "ACTIVELY_USED_IND",
        ),
        coercers={
            "PACKAGE_TYPE_ID": int,
            "PKG_TYPE_LONG_DESC": str,
            "PKG_TYPE_SHORT_DESC": str,
            "ACTIVELY_USED_IND": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPRDPKD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('PACKAGE_TYPE_ID',),
    ),
    # Product status descriptor (3 cols; STATUS_DEFINITION nullable per DDL)
    TableSpec(
        table_name="RPRDSD0_PRODUCT_STATUS_DESC",
        columns=(
            "FDB_PRODUCT_STATUS_CD",
            "FDB_PRODUCT_STATUS_DESC",
            "FDB_PRODUCT_STATUS_DEFINITION",
        ),
        coercers={
            "FDB_PRODUCT_STATUS_CD": str,
            "FDB_PRODUCT_STATUS_DESC": str,
            "FDB_PRODUCT_STATUS_DEFINITION": str,
        },
        nullable=frozenset({"FDB_PRODUCT_STATUS_DEFINITION"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPRDSD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('FDB_PRODUCT_STATUS_CD',),
    ),
    # Price quantity unit of measure (2 cols, none nullable)
    TableSpec(
        table_name="RPRDUOM0_PRICE_QTY_UOM",
        columns=("PRICE_UOM_ID", "PRICE_UOM_DESC"),
        coercers={
            "PRICE_UOM_ID": int,
            "PRICE_UOM_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPRDUOM0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('PRICE_UOM_ID',),
    ),
    # Route descriptor (5 cols; RT, GCRT2, GCRT_DESC, SYSTEMIC nullable per DDL)
    TableSpec(
        table_name="RROUTED3_ROUTE_DESC",
        columns=(
            "GCRT",
            "RT",
            "GCRT2",
            "GCRT_DESC",
            "SYSTEMIC",
        ),
        coercers={
            "GCRT": str,
            "RT": str,
            "GCRT2": str,
            "GCRT_DESC": str,
            "SYSTEMIC": str,
        },
        nullable=frozenset({"RT", "GCRT2", "GCRT_DESC", "SYSTEMIC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RROUTED3",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('GCRT',),
    ),
    # Routed generic master (5 cols, none nullable)
    TableSpec(
        table_name="RRTGN0_ROUTED_GEN_MSTR",
        columns=(
            "ROUTED_GEN_ID",
            "ROUTED_GEN_DESC",
            "GCRT",
            "HICL_SEQNO",
            "ROUTED_GEN_STATUS_CD",
        ),
        coercers={
            "ROUTED_GEN_ID": int,
            "ROUTED_GEN_DESC": str,
            "GCRT": str,
            "HICL_SEQNO": int,
            "ROUTED_GEN_STATUS_CD": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RRTGN0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('ROUTED_GEN_ID',),
    ),
]


__all__ = ["SPECS"]
