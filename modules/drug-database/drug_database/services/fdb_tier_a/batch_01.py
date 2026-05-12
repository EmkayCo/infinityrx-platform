"""B9.B C6 — Tier A batch 01 (canonical template, 12 simple id+desc lookups).

This file is the AUTHORITATIVE pattern parallel B9.B agents replicate
for batches 02-10. Each batch:

  * 10-12 Tier A tables (≤5 columns, simple id+desc semantic)
  * `SPECS: list[TableSpec]` export at module level
  * Each TableSpec sets: tier=Tier.A, loader_group="fdb_tier_a",
    record_counts_key=<FDB key>, delta_semantics=UPSERT_BY_NATURAL_KEY
    (the dominant Tier A pattern — code→desc lookups upsert on the
    natural key; weekly delta = corrections).

Pattern notes:

  * Coercer choice: NUMERIC(n) → int; VARCHAR(n) → str. Tier A has no
    Decimal money columns and no Date columns (those are Tier B/C).
  * Nullable: the description column is nullable for several tables
    (RAHFSD1_DESC, RDCCD0_DRUG_CAT_DESC, etc.) — operator-entered
    descriptions can be missing. Reflect that via `nullable=frozenset({...})`.
  * record_counts_key: the FDB short key from RECORD_COUNTS.TXT. For
    most Tier A tables this is the same as the table name minus the
    `_DESC` suffix or matches the short FDB key. When uncertain, the
    full table_name is also accepted (see fdb_adapter.TableSpec).
"""
from __future__ import annotations

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    TableSpec,
    Tier,
)


SPECS: list[TableSpec] = [
    # AHFS classification descriptor (American Hospital Formulary Service)
    TableSpec(
        table_name="RAHFSD1_DESC",
        columns=("AHFS8", "AHFS_DESC"),
        coercers={"AHFS8": int, "AHFS_DESC": str},
        nullable=frozenset({"AHFS_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RAHFSD1",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('AHFS8',),
    ),
    # FDA application relation type
    TableSpec(
        table_name="RAPLRT0_APPL_RELATION_TYPE",
        columns=("APPL_RELATION_TYPE_ID", "APPL_RELATION_TYPE_DESC"),
        coercers={"APPL_RELATION_TYPE_ID": int, "APPL_RELATION_TYPE_DESC": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RAPLRT0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('APPL_RELATION_TYPE_ID',),
    ),
    # FDA application type
    TableSpec(
        table_name="RAPPLTD0_FDA_APPL_TYPE",
        columns=("APPL_TYPE_CD", "APPL_TYPE_CD_DESC"),
        coercers={"APPL_TYPE_CD": int, "APPL_TYPE_CD_DESC": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RAPPLTD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('APPL_TYPE_CD',),
    ),
    # Anatomical Therapeutic Chemical class
    TableSpec(
        table_name="RATCD0_ATC_DESC",
        columns=("ATC", "ATC_DESC"),
        coercers={"ATC": str, "ATC_DESC": str},
        nullable=frozenset({"ATC_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RATCD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('ATC',),
    ),
    # Biologic name grouper
    TableSpec(
        table_name="RBLANG0_NAME_GRP_DESC",
        columns=("BIOLOGIC_NAME_GROUPER_ID", "BIOLOGIC_NAME_GROUPER_DESC"),
        coercers={
            "BIOLOGIC_NAME_GROUPER_ID": int,
            "BIOLOGIC_NAME_GROUPER_DESC": str,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RBLANG0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('BIOLOGIC_NAME_GROUPER_ID',),
    ),
    # Biologic substance group
    TableSpec(
        table_name="RBLASG0_SUBSTANCE_GRP_DESC",
        columns=("SUBSTANCE_GROUP_ID", "SUBSTANCE_GROUP_DESC"),
        coercers={"SUBSTANCE_GROUP_ID": int, "SUBSTANCE_GROUP_DESC": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RBLASG0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('SUBSTANCE_GROUP_ID',),
    ),
    # Drug Category Class
    TableSpec(
        table_name="RDCCD0_DRUG_CAT_DESC",
        columns=("DCC", "DCC_DESC"),
        coercers={"DCC": str, "DCC_DESC": str},
        nullable=frozenset({"DCC_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RDCCD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('DCC',),
    ),
    # ETC change-type code (Enhanced Therapeutic Classification)
    TableSpec(
        table_name="RETCCTD0_ETC_CHANGE_TYPE_DESC",
        columns=("ETC_CHANGE_TYPE_CODE", "ETC_CHANGE_TYPE_CODE_DESC"),
        coercers={
            "ETC_CHANGE_TYPE_CODE": str,
            "ETC_CHANGE_TYPE_CODE_DESC": str,
        },
        nullable=frozenset({"ETC_CHANGE_TYPE_CODE_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RETCCTD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('ETC_CHANGE_TYPE_CODE',),
    ),
    # Generic Therapeutic Class
    TableSpec(
        table_name="RGTCD0_GEN_THERAP_CLASS_DESC",
        columns=("GTC", "GTC_DESC"),
        coercers={"GTC": int, "GTC_DESC": str},
        nullable=frozenset({"GTC_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RGTCD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('GTC',),
    ),
    # Ingredient status code
    TableSpec(
        table_name="RHICSCD0_ING_STAT_CD_DESC",
        columns=("ING_STATUS_CD", "ING_STATUS_CD_DESC"),
        coercers={"ING_STATUS_CD": int, "ING_STATUS_CD_DESC": str},
        nullable=frozenset({"ING_STATUS_CD_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RHICSCD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('ING_STATUS_CD',),
    ),
    # MEDID concept-id type descriptor
    TableSpec(
        table_name="RMEDCD0_MED_CONCEPT_TYP_DESC",
        columns=("MED_CONCEPT_ID_TYP", "MED_CONCEPT_ID_TYP_DESC"),
        coercers={"MED_CONCEPT_ID_TYP": int, "MED_CONCEPT_ID_TYP_DESC": str},
        nullable=frozenset({"MED_CONCEPT_ID_TYP_DESC"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMEDCD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('MED_CONCEPT_ID_TYP',),
    ),
    # MEDID move-reason code
    TableSpec(
        table_name="RMEDMRD0_MOVE_REASON_DESC",
        columns=("MOVE_REASON_CD", "MOVE_REASON_CD_DESC"),
        coercers={"MOVE_REASON_CD": int, "MOVE_REASON_CD_DESC": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMEDMRD0",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=('MOVE_REASON_CD',),
    ),
]


__all__ = ["SPECS"]
