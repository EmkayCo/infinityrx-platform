"""B9.B C14 — Tier A batch 09 (APPEND_ONLY history template, 8 tables).

Every B9.B batch so far has used `UPSERT_BY_NATURAL_KEY`. The
history (`*_HIST`) tables are different: they capture WHEN an entity
was renumbered, replaced, or revised — each row is an immutable
historical fact, never updated. The delta-semantics class is
`APPEND_ONLY`, and the simulator + ACD cycle assert that every
transaction grows the history.

Shape:

  (REPL_ID, PREV_ID, EFFECTIVE_DATE)    — for *_REPL_HIST patterns
  (HIC_SEQN, ETC_ID, REVISION_SEQNO,
   CHANGE_TYPE_CODE, EFFECTIVE_DATE)    — for ETC_HIST patterns

DATE columns use `_parse_fdb_date` from fdb_adapter (same as
batch_05's RPEIDM0). Several DATE columns are nullable per the DDL.
"""
from __future__ import annotations

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    TableSpec,
    Tier,
    _parse_fdb_date,
)


SPECS: list[TableSpec] = [
    # ETC change history — HIC_SEQN-keyed
    TableSpec(
        table_name="RETCHCH0_ETC_HICSEQN_HIST",
        columns=(
            "HIC_SEQN",
            "ETC_ID",
            "ETC_REVISION_SEQNO",
            "ETC_CHANGE_TYPE_CODE",
            "ETC_EFFECTIVE_DATE",
        ),
        coercers={
            "HIC_SEQN": int,
            "ETC_ID": int,
            "ETC_REVISION_SEQNO": int,
            "ETC_CHANGE_TYPE_CODE": str,
            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
        },
        nullable=frozenset({"ETC_CHANGE_TYPE_CODE", "ETC_EFFECTIVE_DATE"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RETCHCH0",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=('HIC_SEQN', 'ETC_ID', 'ETC_REVISION_SEQNO'),
    ),
    # ETC change history — HICL_SEQNO-keyed
    TableSpec(
        table_name="RETCHLH0_ETC_HICLSEQNO_HIST",
        columns=(
            "HICL_SEQNO",
            "ETC_ID",
            "ETC_REVISION_SEQNO",
            "ETC_CHANGE_TYPE_CODE",
            "ETC_EFFECTIVE_DATE",
        ),
        coercers={
            "HICL_SEQNO": int,
            "ETC_ID": int,
            "ETC_REVISION_SEQNO": int,
            "ETC_CHANGE_TYPE_CODE": str,
            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
        },
        nullable=frozenset({"ETC_CHANGE_TYPE_CODE", "ETC_EFFECTIVE_DATE"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RETCHLH0",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=('HICL_SEQNO', 'ETC_ID', 'ETC_REVISION_SEQNO'),
    ),
    # ETC change history — MED_NAME_ID-keyed
    TableSpec(
        table_name="RETCNMH0_ETC_MED_NAME_ID_HIST",
        columns=(
            "MED_NAME_ID",
            "ETC_ID",
            "ETC_REVISION_SEQNO",
            "ETC_CHANGE_TYPE_CODE",
            "ETC_EFFECTIVE_DATE",
        ),
        coercers={
            "MED_NAME_ID": int,
            "ETC_ID": int,
            "ETC_REVISION_SEQNO": int,
            "ETC_CHANGE_TYPE_CODE": str,
            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
        },
        nullable=frozenset({"ETC_CHANGE_TYPE_CODE", "ETC_EFFECTIVE_DATE"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RETCNMH0",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=('MED_NAME_ID', 'ETC_ID', 'ETC_REVISION_SEQNO'),
    ),
    # Ingredient renumber history
    TableSpec(
        table_name="RHICRH0_ING_HIST",
        columns=("REPL_HIC_SEQN", "PREV_HIC_SEQN", "HIC_REPL_EFF_DT"),
        coercers={
            "REPL_HIC_SEQN": int,
            "PREV_HIC_SEQN": int,
            "HIC_REPL_EFF_DT": _parse_fdb_date,
        },
        nullable=frozenset({"HIC_REPL_EFF_DT"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RHICRH0",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=('REPL_HIC_SEQN', 'PREV_HIC_SEQN'),
    ),
    # Routed dose-form med id replacement history
    TableSpec(
        table_name="RMIDFRH1_ROUTED_DOSE_FORM_HIST",
        columns=(
            "MED_REPL_ROUTED_DF_MED_ID",
            "MED_PREV_ROUTED_DF_MED_ID",
            "MED_ROUTED_DF_MED_ID_REP_EF_DT",
        ),
        coercers={
            "MED_REPL_ROUTED_DF_MED_ID": int,
            "MED_PREV_ROUTED_DF_MED_ID": int,
            "MED_ROUTED_DF_MED_ID_REP_EF_DT": _parse_fdb_date,
        },
        nullable=frozenset({"MED_ROUTED_DF_MED_ID_REP_EF_DT"}),
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIDFRH1",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=('MED_REPL_ROUTED_DF_MED_ID', 'MED_PREV_ROUTED_DF_MED_ID'),
    ),
    # Med name id replacement history
    TableSpec(
        table_name="RMINMRH1_MED_NAME_HIST",
        columns=("MED_REPL_NAME_ID", "MED_PREV_NAME_ID", "MED_NAME_ID_REPL_EFF_DT"),
        coercers={
            "MED_REPL_NAME_ID": int,
            "MED_PREV_NAME_ID": int,
            "MED_NAME_ID_REPL_EFF_DT": _parse_fdb_date,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMINMRH1",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=('MED_REPL_NAME_ID', 'MED_PREV_NAME_ID', 'MED_NAME_ID_REPL_EFF_DT'),
    ),
    # MEDID replacement history
    TableSpec(
        table_name="RMIRH1_MED_HIST",
        columns=("MED_REPL_MEDID", "MED_PREV_MEDID", "MED_MEDID_REPL_EFF_DT"),
        coercers={
            "MED_REPL_MEDID": int,
            "MED_PREV_MEDID": int,
            "MED_MEDID_REPL_EFF_DT": _parse_fdb_date,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIRH1",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=('MED_REPL_MEDID', 'MED_PREV_MEDID', 'MED_MEDID_REPL_EFF_DT'),
    ),
    # Routed med id replacement history
    TableSpec(
        table_name="RMIRMRH1_ROUTED_MED_HIST",
        columns=(
            "MED_REPL_ROUTED_MED_ID",
            "MED_PREV_ROUTED_MED_ID",
            "MED_ROUTED_MED_ID_REPL_EFF_DT",
        ),
        coercers={
            "MED_REPL_ROUTED_MED_ID": int,
            "MED_PREV_ROUTED_MED_ID": int,
            "MED_ROUTED_MED_ID_REPL_EFF_DT": _parse_fdb_date,
        },
        tier=Tier.A,
        loader_group="fdb_tier_a",
        record_counts_key="RMIRMRH1",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=('MED_REPL_ROUTED_MED_ID', 'MED_PREV_ROUTED_MED_ID', 'MED_ROUTED_MED_ID_REPL_EFF_DT'),
    ),
]


__all__ = ["SPECS"]
