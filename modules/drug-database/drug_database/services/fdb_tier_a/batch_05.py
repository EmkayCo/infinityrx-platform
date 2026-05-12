"""B9.B C10 — Tier A batch 05 (10 lookup tables, 1 DATE coercer).

Follows the canonical pattern established in batch_01. One deviation
from the batch_01 pattern: RPEIDM0_DOSAGE_FORM_MSTR has a DATE column
(DOSAGE_FORM_RETIRE_DT) which requires the `_parse_fdb_date` coercer
from fdb_adapter rather than the plain `str` coercer used by all other
Tier A VARCHAR columns.

Tables in this batch:

  RPEIAV0_ATTRIBUTE_VALUE_DESC    — attribute value descriptor (3 cols)
  RPEIDFA0_DOSAGE_FORM_ATTRIBUTE  — dosage form attribute (2 cols)
  RPEIDM0_DOSAGE_FORM_MSTR        — dosage form master (5 cols, 1 DATE)
  RPEIDT0_DOSAGE_FORM_TYPE        — dosage form type (2 cols)
  RPEIPP0_PATIENT_PARAM_REQ_DESC  — patient parameter requirement (2 cols)
  RPEIRL0_RT_LABELED_DESC         — route/labeled descriptor (2 cols)
  RPEIST0_STR_CONC_TYPE           — strength/concentration type (2 cols)
  RPEIUT0_UOM_TYPE_DESC           — unit-of-measure type (2 cols)
  RPRDCC0_CURRENCY_CD_DESC        — currency code descriptor (2 cols)
  RPRDPAD0_PRICE_ATTR_DESC        — price attribute descriptor (4 cols)
"""
from __future__ import annotations

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    TableSpec,
    Tier,
    _parse_fdb_date,
)


SPECS: list[TableSpec] = [
    # Attribute value descriptor (3-column: code + value + description)
    TableSpec(
        table_name="RPEIAV0_ATTRIBUTE_VALUE_DESC",
        columns=("ATTRIBUTE_CODE", "ATTRIBUTE_VALUE", "ATTRIBUTE_VALUE_DESC"),
        coercers={
            "ATTRIBUTE_CODE": int,
            "ATTRIBUTE_VALUE": str,
            "ATTRIBUTE_VALUE_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIAV0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Dosage form attribute descriptor
    TableSpec(
        table_name="RPEIDFA0_DOSAGE_FORM_ATTRIBUTE",
        columns=("DOSAGE_FORM_ATTRIBUTE_ID", "DOSAGE_FORM_ATTRIBUTE_DESC"),
        coercers={
            "DOSAGE_FORM_ATTRIBUTE_ID": int,
            "DOSAGE_FORM_ATTRIBUTE_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIDFA0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Dosage form master — 5-column table with a DATE retirement column.
    # DOSAGE_FORM_RETIRE_DT is DATE: uses _parse_fdb_date (YYYYMMDD→date).
    # Nullable: DOSAGE_FORM_DESC_SHORT, DOSAGE_FORM_RETIRE_DT, UOM_MSTR_ID.
    TableSpec(
        table_name="RPEIDM0_DOSAGE_FORM_MSTR",
        columns=(
            "DOSAGE_FORM_ID",
            "DOSAGE_FORM_DESC_SHORT",
            "DOSAGE_FORM_DESC_LONG",
            "DOSAGE_FORM_RETIRE_DT",
            "UOM_MSTR_ID",
        ),
        coercers={
            "DOSAGE_FORM_ID": int,
            "DOSAGE_FORM_DESC_SHORT": str,
            "DOSAGE_FORM_DESC_LONG": str,
            "DOSAGE_FORM_RETIRE_DT": _parse_fdb_date,
            "UOM_MSTR_ID": int,
        },
        nullable=frozenset({"DOSAGE_FORM_DESC_SHORT", "DOSAGE_FORM_RETIRE_DT", "UOM_MSTR_ID"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIDM0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Dosage form type descriptor
    TableSpec(
        table_name="RPEIDT0_DOSAGE_FORM_TYPE",
        columns=("DOSAGE_FORM_TYPE_ID", "DOSAGE_FORM_TYPE_DESC"),
        coercers={
            "DOSAGE_FORM_TYPE_ID": int,
            "DOSAGE_FORM_TYPE_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIDT0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Patient parameter requirement code descriptor
    TableSpec(
        table_name="RPEIPP0_PATIENT_PARAM_REQ_DESC",
        columns=("PATIENT_PARAM_REQ_CD", "PATIENT_PARAM_REQ_CD_DESC"),
        coercers={
            "PATIENT_PARAM_REQ_CD": int,
            "PATIENT_PARAM_REQ_CD_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIPP0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Route/labeled descriptor
    TableSpec(
        table_name="RPEIRL0_RT_LABELED_DESC",
        columns=("RT_LABELED_ID", "RT_LABELED_DESC"),
        coercers={
            "RT_LABELED_ID": int,
            "RT_LABELED_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIRL0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Strength/concentration type descriptor
    TableSpec(
        table_name="RPEIST0_STR_CONC_TYPE",
        columns=("STR_CONC_TYPE_ID", "STR_CONC_TYPE_DESC"),
        coercers={
            "STR_CONC_TYPE_ID": int,
            "STR_CONC_TYPE_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIST0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Unit-of-measure type descriptor
    TableSpec(
        table_name="RPEIUT0_UOM_TYPE_DESC",
        columns=("UOM_TYPE_CD", "UOM_TYPE_CD_DESC"),
        coercers={
            "UOM_TYPE_CD": int,
            "UOM_TYPE_CD_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPEIUT0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Currency code descriptor
    TableSpec(
        table_name="RPRDCC0_CURRENCY_CD_DESC",
        columns=("CURRENCY_CD", "CURRENCY_CD_DESC"),
        coercers={
            "CURRENCY_CD": str,
            "CURRENCY_CD_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPRDCC0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
    # Price attribute descriptor (4-column; PRICE_ATTRIBUTE_GROUP_CD nullable)
    TableSpec(
        table_name="RPRDPAD0_PRICE_ATTR_DESC",
        columns=(
            "PRICE_ATTRIBUTE_CD",
            "PRICE_ATTRIBUTE_DESC",
            "PRICE_ATTRIBUTE_TYPE_CD",
            "PRICE_ATTRIBUTE_GROUP_CD",
        ),
        coercers={
            "PRICE_ATTRIBUTE_CD": str,
            "PRICE_ATTRIBUTE_DESC": str,
            "PRICE_ATTRIBUTE_TYPE_CD": str,
            "PRICE_ATTRIBUTE_GROUP_CD": str,
        },
        nullable=frozenset({"PRICE_ATTRIBUTE_GROUP_CD"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RPRDPAD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    ),
]


__all__ = ["SPECS"]
