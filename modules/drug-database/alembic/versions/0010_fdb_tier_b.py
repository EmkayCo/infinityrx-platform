"""B9.C Tier B batch -- 72 NDC/GCN-keyed join tables.

Revision ID: 0010_fdb_tier_b
Revises: 0009_fdb_tier_a
Create Date: 2026-05-16

Operator dry-run (required before merging to main):

    alembic upgrade head      # forward
    alembic downgrade -1      # reverse
    alembic upgrade head      # re-apply

Capture output to waves/B9/B9.C-dryrun_evidence.md.
"""
from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_fdb_tier_b"
down_revision: Union[str, None] = "0009_fdb_tier_a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "drug_database"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # RAHFSGC1_GCNSEQNO_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RAHFSGC1
    op.create_table(
        'rahfsgc1_gcnseqno_link',
        sa.Column('GCN_SEQNO', sa.Text(), nullable=False),
        sa.Column('AHFS8', sa.Text(), nullable=False),
        sa.Column('AHFS_REL', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('GCN_SEQNO', 'AHFS8', name='pk_rahfsgc1_gcnseqno_link'),
        schema=_SCHEMA,
    )
    # RAPPLNA0_FDA_NDC_APPL tier=B delta=UPSERT_BY_NATURAL_KEY rc=RAPPLNA0
    op.create_table(
        'rapplna0_fda_ndc_appl',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('APPL_NO', sa.Text(), nullable=False),
        sa.Column('APPL_TYPE_CD', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', 'APPL_NO', name='pk_rapplna0_fda_ndc_appl'),
        schema=_SCHEMA,
    )
    # RAPPLSL0_FDA_NDC_NDA_ANDA tier=B delta=UPSERT_BY_NATURAL_KEY rc=RAPPLSL0
    op.create_table(
        'rapplsl0_fda_ndc_nda_anda',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('NDA_IND', sa.Text(), nullable=False),
        sa.Column('ANDA_IND', sa.Text(), nullable=False),
        sa.Column('LISTING_SEQ_NO', sa.Text(), nullable=True),
        sa.Column('TRADENAME', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('NDC', 'NDA_IND', name='pk_rapplsl0_fda_ndc_nda_anda'),
        schema=_SCHEMA,
    )
    # RATCGC0_ATC_GCNSEQNO_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RATCGC0
    op.create_table(
        'ratcgc0_atc_gcnseqno_link',
        sa.Column('GCN_SEQNO', sa.Text(), nullable=False),
        sa.Column('ATC', sa.Text(), nullable=False),
        sa.Column('ATC_VER', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('GCN_SEQNO', 'ATC', name='pk_ratcgc0_atc_gcnseqno_link'),
        schema=_SCHEMA,
    )
    # RCQNDC0_CLNQTY_NDC tier=B delta=UPSERT_BY_NATURAL_KEY rc=RCQNDC0
    op.create_table(
        'rcqndc0_clnqty_ndc',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('MEDID', sa.Text(), nullable=False),
        sa.Column('CLNQTY_SUBUNIT_QTY', sa.Text(), nullable=True),
        sa.Column('CLNQTY_SUBUOM_DESC', sa.Text(), nullable=False),
        sa.Column('CLNQTY_PKG_DESC', sa.Text(), nullable=True),
        sa.Column('CLNQTY_DESC', sa.Text(), nullable=False),
        sa.Column('ERX_QTY', sa.Text(), nullable=False),
        sa.Column('ERX_SCRIPT_UOM_DESC', sa.Text(), nullable=False),
        sa.Column('ERX_SCRIPT_POTUNIT_CD', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', 'MEDID', name='pk_rcqndc0_clnqty_ndc'),
        schema=_SCHEMA,
    )
    # RETCGC0_ETC_GCNSEQNO tier=B delta=UPSERT_BY_NATURAL_KEY rc=RETCGC0
    op.create_table(
        'retcgc0_etc_gcnseqno',
        sa.Column('GCN_SEQNO', sa.Text(), nullable=False),
        sa.Column('ETC_ID', sa.Text(), nullable=False),
        sa.Column('ETC_COMMON_USE_IND', sa.Text(), nullable=True),
        sa.Column('ETC_DEFAULT_USE_IND', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('GCN_SEQNO', 'ETC_ID', name='pk_retcgc0_etc_gcnseqno'),
        schema=_SCHEMA,
    )
    # RETCGCH0_ETC_GCNSEQNO_HIST tier=B delta=APPEND_ONLY rc=RETCGCH0
    op.create_table(
        'retcgch0_etc_gcnseqno_hist',
        sa.Column('GCN_SEQNO', sa.Text(), nullable=False),
        sa.Column('ETC_ID', sa.Text(), nullable=False),
        sa.Column('ETC_REVISION_SEQNO', sa.Text(), nullable=False),
        sa.Column('ETC_COMMON_USE_IND', sa.Text(), nullable=True),
        sa.Column('ETC_DEFAULT_USE_IND', sa.Text(), nullable=True),
        sa.Column('ETC_CHANGE_TYPE_CODE', sa.Text(), nullable=True),
        sa.Column('ETC_EFFECTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('GCN_SEQNO', 'ETC_ID', 'ETC_REVISION_SEQNO', name='pk_retcgch0_etc_gcnseqno_hist'),
        schema=_SCHEMA,
    )
    # RETCHCL0_ETC_HICLSEQNO tier=B delta=UPSERT_BY_NATURAL_KEY rc=RETCHCL0
    op.create_table(
        'retchcl0_etc_hiclseqno',
        sa.Column('HICL_SEQNO', sa.Text(), nullable=False),
        sa.Column('ETC_ID', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('HICL_SEQNO', 'ETC_ID', name='pk_retchcl0_etc_hiclseqno'),
        schema=_SCHEMA,
    )
    # RETCHIC0_ETC_HICSEQN tier=B delta=UPSERT_BY_NATURAL_KEY rc=RETCHIC0
    op.create_table(
        'retchic0_etc_hicseqn',
        sa.Column('HIC_SEQN', sa.Text(), nullable=False),
        sa.Column('ETC_ID', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('HIC_SEQN', 'ETC_ID', name='pk_retchic0_etc_hicseqn'),
        schema=_SCHEMA,
    )
    # RETCMDH0_ETC_MEDID_HIST tier=B delta=APPEND_ONLY rc=RETCMDH0
    op.create_table(
        'retcmdh0_etc_medid_hist',
        sa.Column('MEDID', sa.Text(), nullable=False),
        sa.Column('ETC_ID', sa.Text(), nullable=False),
        sa.Column('ETC_REVISION_SEQNO', sa.Text(), nullable=False),
        sa.Column('ETC_COMMON_USE_IND', sa.Text(), nullable=True),
        sa.Column('ETC_DEFAULT_USE_IND', sa.Text(), nullable=True),
        sa.Column('ETC_CHANGE_TYPE_CODE', sa.Text(), nullable=True),
        sa.Column('ETC_EFFECTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('MEDID', 'ETC_ID', 'ETC_REVISION_SEQNO', name='pk_retcmdh0_etc_medid_hist'),
        schema=_SCHEMA,
    )
    # RETCMED0_ETC_MEDID tier=B delta=UPSERT_BY_NATURAL_KEY rc=RETCMED0
    op.create_table(
        'retcmed0_etc_medid',
        sa.Column('MEDID', sa.Text(), nullable=False),
        sa.Column('ETC_ID', sa.Text(), nullable=False),
        sa.Column('ETC_COMMON_USE_IND', sa.Text(), nullable=True),
        sa.Column('ETC_DEFAULT_USE_IND', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('MEDID', 'ETC_ID', name='pk_retcmed0_etc_medid'),
        schema=_SCHEMA,
    )
    # RETCMNM0_ETC_MED_NAME_ID tier=B delta=UPSERT_BY_NATURAL_KEY rc=RETCMNM0
    op.create_table(
        'retcmnm0_etc_med_name_id',
        sa.Column('MED_NAME_ID', sa.Text(), nullable=False),
        sa.Column('ETC_ID', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('MED_NAME_ID', 'ETC_ID', name='pk_retcmnm0_etc_med_name_id'),
        schema=_SCHEMA,
    )
    # RETCNDC0_ETC_NDC tier=B delta=UPSERT_BY_NATURAL_KEY rc=RETCNDC0
    op.create_table(
        'retcndc0_etc_ndc',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('ETC_ID', sa.Text(), nullable=False),
        sa.Column('ETC_COMMON_USE_IND', sa.Text(), nullable=True),
        sa.Column('ETC_DEFAULT_USE_IND', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('NDC', 'ETC_ID', name='pk_retcndc0_etc_ndc'),
        schema=_SCHEMA,
    )
    # RETCNDH0_ETC_NDC_HIST tier=B delta=APPEND_ONLY rc=RETCNDH0
    op.create_table(
        'retcndh0_etc_ndc_hist',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('ETC_ID', sa.Text(), nullable=False),
        sa.Column('ETC_REVISION_SEQNO', sa.Text(), nullable=False),
        sa.Column('ETC_COMMON_USE_IND', sa.Text(), nullable=True),
        sa.Column('ETC_DEFAULT_USE_IND', sa.Text(), nullable=True),
        sa.Column('ETC_CHANGE_TYPE_CODE', sa.Text(), nullable=True),
        sa.Column('ETC_EFFECTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('NDC', 'ETC_ID', 'ETC_REVISION_SEQNO', name='pk_retcndh0_etc_ndc_hist'),
        schema=_SCHEMA,
    )
    # RGCN0_GCN_GCNSEQNO_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RGCN0
    op.create_table(
        'rgcn0_gcn_gcnseqno_link',
        sa.Column('GCN_SEQNO', sa.Text(), nullable=False),
        sa.Column('GCN', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('GCN_SEQNO', 'GCN', name='pk_rgcn0_gcn_gcnseqno_link'),
        schema=_SCHEMA,
    )
    # RGCNINH0_GCNSEQNO_INACTV_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RGCNINH0
    op.create_table(
        'rgcninh0_gcnseqno_inactv_link',
        sa.Column('GCN_SEQNO', sa.Text(), nullable=False),
        sa.Column('HIC_SEQN', sa.Text(), nullable=False),
        sa.Column('INACTV_NOT_PRES_CNT', sa.Text(), nullable=True),
        sa.Column('INACTV_PRES_CNT', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('GCN_SEQNO', 'HIC_SEQN', name='pk_rgcninh0_gcnseqno_inactv_link'),
        schema=_SCHEMA,
    )
    # RGCNINS0_STUDY_TABLE tier=B delta=UPSERT_BY_NATURAL_KEY rc=RGCNINS0
    op.create_table(
        'rgcnins0_study_table',
        sa.Column('GCN_SEQNO', sa.Text(), nullable=False),
        sa.Column('TOTAL_PRODUCTS_CNT', sa.Text(), nullable=True),
        sa.Column('PRODUCTS_RESEARCHED_CNT', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('GCN_SEQNO', name='pk_rgcnins0_study_table'),
        schema=_SCHEMA,
    )
    # RHIC3L2_HIC3_HICLSEQNO_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RHIC3L2
    op.create_table(
        'rhic3l2_hic3_hiclseqno_link',
        sa.Column('HICL_SEQNO', sa.Text(), nullable=False),
        sa.Column('HIC3_SEQN', sa.Text(), nullable=False),
        sa.Column('HIC3', sa.Text(), nullable=True),
        sa.Column('HIC3_RELNO', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('HICL_SEQNO', 'HIC3_SEQN', name='pk_rhic3l2_hic3_hiclseqno_link'),
        schema=_SCHEMA,
    )
    # RHIC4D2_HIC_BASE_ING_DESC tier=B delta=UPSERT_BY_NATURAL_KEY rc=RHIC4D2
    op.create_table(
        'rhic4d2_hic_base_ing_desc',
        sa.Column('HIC4_SEQN', sa.Text(), nullable=False),
        sa.Column('HIC4', sa.Text(), nullable=True),
        sa.Column('HIC4_DESC', sa.Text(), nullable=True),
        sa.Column('HIC4_ROOT', sa.Text(), nullable=True),
        sa.Column('HIC4_POTENTIALLY_INACTV_IND', sa.Text(), nullable=True),
        sa.Column('ING_STATUS_CD', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('HIC4_SEQN', 'HIC4', name='pk_rhic4d2_hic_base_ing_desc'),
        schema=_SCHEMA,
    )
    # RHICCAS1_HIC_CAS_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RHICCAS1
    op.create_table(
        'rhiccas1_hic_cas_link',
        sa.Column('HIC_SEQN', sa.Text(), nullable=False),
        sa.Column('CAS9_TBL', sa.Text(), nullable=True),
        sa.Column('HIC', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('HIC_SEQN', 'CAS9_TBL', name='pk_rhiccas1_hic_cas_link'),
        schema=_SCHEMA,
    )
    # RHICD5_HIC_DESC tier=B delta=UPSERT_BY_NATURAL_KEY rc=RHICD5
    op.create_table(
        'rhicd5_hic_desc',
        sa.Column('HIC_SEQN', sa.Text(), nullable=False),
        sa.Column('HIC', sa.Text(), nullable=True),
        sa.Column('HIC_DESC', sa.Text(), nullable=True),
        sa.Column('HIC_ROOT', sa.Text(), nullable=True),
        sa.Column('HIC_POTENTIALLY_INACTV_IND', sa.Text(), nullable=True),
        sa.Column('ING_STATUS_CD', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('HIC_SEQN', 'HIC', name='pk_rhicd5_hic_desc'),
        schema=_SCHEMA,
    )
    # RHICHCR0_HIC_HIC_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RHICHCR0
    op.create_table(
        'rhichcr0_hic_hic_link',
        sa.Column('HIC_SEQN', sa.Text(), nullable=False),
        sa.Column('RELATED_HIC_SEQN', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('HIC_SEQN', 'RELATED_HIC_SEQN', name='pk_rhichcr0_hic_hic_link'),
        schema=_SCHEMA,
    )
    # RHICL1_HIC_HICLSEQNO_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RHICL1
    op.create_table(
        'rhicl1_hic_hiclseqno_link',
        sa.Column('HICL_SEQNO', sa.Text(), nullable=False),
        sa.Column('HIC_SEQN', sa.Text(), nullable=False),
        sa.Column('HIC_REL_NO', sa.Text(), nullable=True),
        sa.Column('HIC', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('HICL_SEQNO', 'HIC_SEQN', name='pk_rhicl1_hic_hiclseqno_link'),
        schema=_SCHEMA,
    )
    # RHICLSQ1_HICLSEQNO_MSTR tier=B delta=UPSERT_BY_NATURAL_KEY rc=RHICLSQ1
    op.create_table(
        'rhiclsq1_hiclseqno_mstr',
        sa.Column('HICL_SEQNO', sa.Text(), nullable=False),
        sa.Column('GNN', sa.Text(), nullable=True),
        sa.Column('GNN60', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('HICL_SEQNO', name='pk_rhiclsq1_hiclseqno_mstr'),
        schema=_SCHEMA,
    )
    # RHICLSQ2_HICLSEQNO_MSTR tier=B delta=UPSERT_BY_NATURAL_KEY rc=RHICLSQ2
    op.create_table(
        'rhiclsq2_hiclseqno_mstr',
        sa.Column('HICL_SEQNO', sa.Text(), nullable=False),
        sa.Column('GNN', sa.Text(), nullable=False),
        sa.Column('GNN60', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('HICL_SEQNO', name='pk_rhiclsq2_hiclseqno_mstr'),
        schema=_SCHEMA,
    )
    # RMEDDIN0_RDFMID_INACTV_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RMEDDIN0
    op.create_table(
        'rmeddin0_rdfmid_inactv_link',
        sa.Column('ROUTED_DOSAGE_FORM_MED_ID', sa.Text(), nullable=False),
        sa.Column('HIC_SEQN', sa.Text(), nullable=False),
        sa.Column('INACTV_NOT_PRES_CNT', sa.Text(), nullable=True),
        sa.Column('INACTV_PRES_CNT', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('ROUTED_DOSAGE_FORM_MED_ID', 'HIC_SEQN', name='pk_rmeddin0_rdfmid_inactv_link'),
        schema=_SCHEMA,
    )
    # RMEDDIS0_ROUTED_DF_STUDY_TABLE tier=B delta=UPSERT_BY_NATURAL_KEY rc=RMEDDIS0
    op.create_table(
        'rmeddis0_routed_df_study_table',
        sa.Column('ROUTED_DOSAGE_FORM_MED_ID', sa.Text(), nullable=False),
        sa.Column('TOTAL_PRODUCTS_CNT', sa.Text(), nullable=True),
        sa.Column('PRODUCTS_RESEARCHED_CNT', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('ROUTED_DOSAGE_FORM_MED_ID', name='pk_rmeddis0_routed_df_study_table'),
        schema=_SCHEMA,
    )
    # RMEDIN0_MEDID_INACTV_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RMEDIN0
    op.create_table(
        'rmedin0_medid_inactv_link',
        sa.Column('MEDID', sa.Text(), nullable=False),
        sa.Column('HIC_SEQN', sa.Text(), nullable=False),
        sa.Column('INACTV_NOT_PRES_CNT', sa.Text(), nullable=True),
        sa.Column('INACTV_PRES_CNT', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('MEDID', 'HIC_SEQN', name='pk_rmedin0_medid_inactv_link'),
        schema=_SCHEMA,
    )
    # RMEDIS0_MEDID_STUDY_TABLE tier=B delta=UPSERT_BY_NATURAL_KEY rc=RMEDIS0
    op.create_table(
        'rmedis0_medid_study_table',
        sa.Column('MEDID', sa.Text(), nullable=False),
        sa.Column('TOTAL_PRODUCTS_CNT', sa.Text(), nullable=True),
        sa.Column('PRODUCTS_RESEARCHED_CNT', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('MEDID', name='pk_rmedis0_medid_study_table'),
        schema=_SCHEMA,
    )
    # RMEDNGH0_NDC_GEN_MEDID_HIST tier=B delta=APPEND_ONLY rc=RMEDNGH0
    op.create_table(
        'rmedngh0_ndc_gen_medid_hist',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('PRODUCTION_DATE', sa.Text(), nullable=False),
        sa.Column('PREV_MEDID', sa.Text(), nullable=False),
        sa.Column('PREV_MEDID_NAME_SOURCE_CD', sa.Text(), nullable=False),
        sa.Column('PREV_MEDID_OLD_STATUS_CD', sa.Text(), nullable=False),
        sa.Column('PREV_MEDID_NEW_STATUS_CD', sa.Text(), nullable=False),
        sa.Column('PREV_MEDID_DESC', sa.Text(), nullable=False),
        sa.Column('CURR_MEDID', sa.Text(), nullable=False),
        sa.Column('CURR_MEDID_NAME_SOURCE_CD', sa.Text(), nullable=False),
        sa.Column('CURR_MEDID_OLD_STATUS_CD', sa.Text(), nullable=True),
        sa.Column('CURR_MEDID_NEW_STATUS_CD', sa.Text(), nullable=False),
        sa.Column('CURR_MEDID_DESC', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', 'PRODUCTION_DATE', 'PREV_MEDID', name='pk_rmedngh0_ndc_gen_medid_hist'),
        schema=_SCHEMA,
    )
    # RMEDNGM0_NDC_GEN_MEDID tier=B delta=UPSERT_BY_NATURAL_KEY rc=RMEDNGM0
    op.create_table(
        'rmedngm0_ndc_gen_medid',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('MEDID', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', 'MEDID', name='pk_rmedngm0_ndc_gen_medid'),
        schema=_SCHEMA,
    )
    # RMEDNGR0_NDC_GEN_MEDID_REASON tier=B delta=UPSERT_BY_NATURAL_KEY rc=RMEDNGR0
    op.create_table(
        'rmedngr0_ndc_gen_medid_reason',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('PRODUCTION_DATE', sa.Text(), nullable=False),
        sa.Column('MOVE_REASON_CD', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', name='pk_rmedngr0_ndc_gen_medid_reason'),
        schema=_SCHEMA,
    )
    # RMEDNIN0_MNID_INACTV_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RMEDNIN0
    op.create_table(
        'rmednin0_mnid_inactv_link',
        sa.Column('MED_NAME_ID', sa.Text(), nullable=False),
        sa.Column('HIC_SEQN', sa.Text(), nullable=False),
        sa.Column('INACTV_NOT_PRES_CNT', sa.Text(), nullable=True),
        sa.Column('INACTV_PRES_CNT', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('MED_NAME_ID', 'HIC_SEQN', name='pk_rmednin0_mnid_inactv_link'),
        schema=_SCHEMA,
    )
    # RMEDNIS0_MED_NAME_STUDY_TABLE tier=B delta=UPSERT_BY_NATURAL_KEY rc=RMEDNIS0
    op.create_table(
        'rmednis0_med_name_study_table',
        sa.Column('MED_NAME_ID', sa.Text(), nullable=False),
        sa.Column('TOTAL_PRODUCTS_CNT', sa.Text(), nullable=True),
        sa.Column('PRODUCTS_RESEARCHED_CNT', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('MED_NAME_ID', name='pk_rmednis0_med_name_study_table'),
        schema=_SCHEMA,
    )
    # RMEDNMH0_NDC_MEDID_HIST tier=B delta=APPEND_ONLY rc=RMEDNMH0
    op.create_table(
        'rmednmh0_ndc_medid_hist',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('PRODUCTION_DATE', sa.Text(), nullable=False),
        sa.Column('PREV_MEDID', sa.Text(), nullable=False),
        sa.Column('PREV_MEDID_NAME_SOURCE_CD', sa.Text(), nullable=False),
        sa.Column('PREV_MEDID_OLD_STATUS_CD', sa.Text(), nullable=False),
        sa.Column('PREV_MEDID_NEW_STATUS_CD', sa.Text(), nullable=False),
        sa.Column('PREV_MEDID_DESC', sa.Text(), nullable=False),
        sa.Column('CURR_MEDID', sa.Text(), nullable=False),
        sa.Column('CURR_MEDID_NAME_SOURCE_CD', sa.Text(), nullable=False),
        sa.Column('CURR_MEDID_OLD_STATUS_CD', sa.Text(), nullable=True),
        sa.Column('CURR_MEDID_NEW_STATUS_CD', sa.Text(), nullable=False),
        sa.Column('CURR_MEDID_DESC', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', 'PRODUCTION_DATE', 'PREV_MEDID', name='pk_rmednmh0_ndc_medid_hist'),
        schema=_SCHEMA,
    )
    # RMEDNMR0_NDC_MEDID_REASON tier=B delta=UPSERT_BY_NATURAL_KEY rc=RMEDNMR0
    op.create_table(
        'rmednmr0_ndc_medid_reason',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('PRODUCTION_DATE', sa.Text(), nullable=False),
        sa.Column('MOVE_REASON_CD', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', name='pk_rmednmr0_ndc_medid_reason'),
        schema=_SCHEMA,
    )
    # RMEDRIN0_RMID_INACTV_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RMEDRIN0
    op.create_table(
        'rmedrin0_rmid_inactv_link',
        sa.Column('ROUTED_MED_ID', sa.Text(), nullable=False),
        sa.Column('HIC_SEQN', sa.Text(), nullable=False),
        sa.Column('INACTV_NOT_PRES_CNT', sa.Text(), nullable=True),
        sa.Column('INACTV_PRES_CNT', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('ROUTED_MED_ID', 'HIC_SEQN', name='pk_rmedrin0_rmid_inactv_link'),
        schema=_SCHEMA,
    )
    # RMEDRIS0_ROUTED_MED_STDY_TBL tier=B delta=UPSERT_BY_NATURAL_KEY rc=RMEDRIS0
    op.create_table(
        'rmedris0_routed_med_stdy_tbl',
        sa.Column('ROUTED_MED_ID', sa.Text(), nullable=False),
        sa.Column('TOTAL_PRODUCTS_CNT', sa.Text(), nullable=True),
        sa.Column('PRODUCTS_RESEARCHED_CNT', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('ROUTED_MED_ID', name='pk_rmedris0_routed_med_stdy_tbl'),
        schema=_SCHEMA,
    )
    # RMEDSPC0_SPECIFICATION tier=B delta=UPSERT_BY_NATURAL_KEY rc=RMEDSPC0
    op.create_table(
        'rmedspc0_specification',
        sa.Column('MEDID', sa.Text(), nullable=False),
        sa.Column('MEDID_SPECIFICATION_CODE', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('MEDID', 'MEDID_SPECIFICATION_CODE', name='pk_rmedspc0_specification'),
        schema=_SCHEMA,
    )
    # RMIGC1_MEDID_GCNSEQNO_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RMIGC1
    op.create_table(
        'rmigc1_medid_gcnseqno_link',
        sa.Column('GCN_SEQNO', sa.Text(), nullable=False),
        sa.Column('MEDID', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('GCN_SEQNO', 'MEDID', name='pk_rmigc1_medid_gcnseqno_link'),
        schema=_SCHEMA,
    )
    # RMINDC1_NDC_MEDID tier=B delta=UPSERT_BY_NATURAL_KEY rc=RMINDC1
    op.create_table(
        'rmindc1_ndc_medid',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('MEDID', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', 'MEDID', name='pk_rmindc1_ndc_medid'),
        schema=_SCHEMA,
    )
    # RMINMID1_MED_NAME tier=B delta=UPSERT_BY_NATURAL_KEY rc=RMINMID1
    op.create_table(
        'rminmid1_med_name',
        sa.Column('MED_NAME_ID', sa.Text(), nullable=False),
        sa.Column('MED_NAME', sa.Text(), nullable=False),
        sa.Column('MED_NAME_TYPE_CD', sa.Text(), nullable=False),
        sa.Column('MED_STATUS_CD', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('MED_NAME_ID', 'MED_NAME', name='pk_rminmid1_med_name'),
        schema=_SCHEMA,
    )
    # RNDCAT0_NDC_ATTRIBUTE tier=B delta=UPSERT_BY_NATURAL_KEY rc=RNDCAT0
    op.create_table(
        'rndcat0_ndc_attribute',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('NDC_ATTRIBUTE_TYPE_CD', sa.Text(), nullable=False),
        sa.Column('NDC_ATTRIBUTE_SN', sa.Text(), nullable=False),
        sa.Column('NDC_ATTRIBUTE_VALUE', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', 'NDC_ATTRIBUTE_TYPE_CD', name='pk_rndcat0_ndc_attribute'),
        schema=_SCHEMA,
    )
    # RNDCINH0_NDC_INACTV_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RNDCINH0
    op.create_table(
        'rndcinh0_ndc_inactv_link',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('HIC_SEQN', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', 'HIC_SEQN', name='pk_rndcinh0_ndc_inactv_link'),
        schema=_SCHEMA,
    )
    # RNDCINR0_INACTV_REVIEWED tier=B delta=UPSERT_BY_NATURAL_KEY rc=RNDCINR0
    op.create_table(
        'rndcinr0_inactv_reviewed',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', name='pk_rndcinr0_inactv_reviewed'),
        schema=_SCHEMA,
    )
    # ROBCNDC0_OBC_NDC tier=B delta=UPSERT_BY_NATURAL_KEY rc=ROBCNDC0
    op.create_table(
        'robcndc0_obc_ndc',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('OBC3', sa.Text(), nullable=False),
        sa.Column('GCN', sa.Text(), nullable=False),
        sa.Column('GCN_SEQNO', sa.Text(), nullable=False),
        sa.Column('GTI', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', 'OBC3', name='pk_robcndc0_obc_ndc'),
        schema=_SCHEMA,
    )
    # RPEIGA0_GCNSEQNO_ATTRIBUTE tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEIGA0
    op.create_table(
        'rpeiga0_gcnseqno_attribute',
        sa.Column('GCN_SEQNO', sa.Text(), nullable=False),
        sa.Column('ATTRIBUTE_CODE', sa.Text(), nullable=False),
        sa.Column('ATTRIBUTE_SN', sa.Text(), nullable=False),
        sa.Column('ATTRIBUTE_VALUE', sa.Text(), nullable=False),
        sa.Column('LINK_INACTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('GCN_SEQNO', 'ATTRIBUTE_CODE', name='pk_rpeiga0_gcnseqno_attribute'),
        schema=_SCHEMA,
    )
    # RPEIGD0_GCNSEQNO_DF_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEIGD0
    op.create_table(
        'rpeigd0_gcnseqno_df_link',
        sa.Column('GCN_SEQNO', sa.Text(), nullable=False),
        sa.Column('DOSAGE_FORM_ID', sa.Text(), nullable=False),
        sa.Column('DOSAGE_FORM_TYPE_ID', sa.Text(), nullable=False),
        sa.Column('LINK_INACTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('GCN_SEQNO', 'DOSAGE_FORM_ID', name='pk_rpeigd0_gcnseqno_df_link'),
        schema=_SCHEMA,
    )
    # RPEIGR0_GCNSEQNO_RT_RELATION tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEIGR0
    op.create_table(
        'rpeigr0_gcnseqno_rt_relation',
        sa.Column('GCN_SEQNO', sa.Text(), nullable=False),
        sa.Column('PARENT_RT_ID', sa.Text(), nullable=False),
        sa.Column('CLINICAL_RT_ID', sa.Text(), nullable=False),
        sa.Column('RELATION_INACTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('GCN_SEQNO', 'PARENT_RT_ID', name='pk_rpeigr0_gcnseqno_rt_relation'),
        schema=_SCHEMA,
    )
    # RPEIGRR0_GCNSEQNO_REP_RT tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEIGRR0
    op.create_table(
        'rpeigrr0_gcnseqno_rep_rt',
        sa.Column('GCN_SEQNO', sa.Text(), nullable=False),
        sa.Column('REPRESENTATIVE_RT_ID', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('GCN_SEQNO', 'REPRESENTATIVE_RT_ID', name='pk_rpeigrr0_gcnseqno_rep_rt'),
        schema=_SCHEMA,
    )
    # RPEIHR0_HICLSEQNO_RT_RELATION tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEIHR0
    op.create_table(
        'rpeihr0_hiclseqno_rt_relation',
        sa.Column('HICL_SEQNO', sa.Text(), nullable=False),
        sa.Column('PARENT_RT_ID', sa.Text(), nullable=False),
        sa.Column('CLINICAL_RT_ID', sa.Text(), nullable=False),
        sa.Column('RELATION_INACTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('HICL_SEQNO', 'PARENT_RT_ID', name='pk_rpeihr0_hiclseqno_rt_relation'),
        schema=_SCHEMA,
    )
    # RPEIMA0_MED_ATTRIBUTE tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEIMA0
    op.create_table(
        'rpeima0_med_attribute',
        sa.Column('MEDID', sa.Text(), nullable=False),
        sa.Column('ATTRIBUTE_CODE', sa.Text(), nullable=False),
        sa.Column('ATTRIBUTE_SN', sa.Text(), nullable=False),
        sa.Column('ATTRIBUTE_VALUE', sa.Text(), nullable=False),
        sa.Column('LINK_INACTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('MEDID', 'ATTRIBUTE_CODE', name='pk_rpeima0_med_attribute'),
        schema=_SCHEMA,
    )
    # RPEIMD0_MED_DF_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEIMD0
    op.create_table(
        'rpeimd0_med_df_link',
        sa.Column('MEDID', sa.Text(), nullable=False),
        sa.Column('DOSAGE_FORM_ID', sa.Text(), nullable=False),
        sa.Column('DOSAGE_FORM_TYPE_ID', sa.Text(), nullable=False),
        sa.Column('LINK_INACTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('MEDID', 'DOSAGE_FORM_ID', name='pk_rpeimd0_med_df_link'),
        schema=_SCHEMA,
    )
    # RPEIMNR0_MED_NAME_RT_RELATION tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEIMNR0
    op.create_table(
        'rpeimnr0_med_name_rt_relation',
        sa.Column('MED_NAME_ID', sa.Text(), nullable=False),
        sa.Column('PARENT_RT_ID', sa.Text(), nullable=False),
        sa.Column('CLINICAL_RT_ID', sa.Text(), nullable=False),
        sa.Column('RELATION_INACTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('MED_NAME_ID', 'PARENT_RT_ID', name='pk_rpeimnr0_med_name_rt_relation'),
        schema=_SCHEMA,
    )
    # RPEIMRR0_MED_RT_RELATION tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEIMRR0
    op.create_table(
        'rpeimrr0_med_rt_relation',
        sa.Column('MEDID', sa.Text(), nullable=False),
        sa.Column('PARENT_RT_ID', sa.Text(), nullable=False),
        sa.Column('CLINICAL_RT_ID', sa.Text(), nullable=False),
        sa.Column('RELATION_INACTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('MEDID', 'PARENT_RT_ID', name='pk_rpeimrr0_med_rt_relation'),
        schema=_SCHEMA,
    )
    # RPEINA0_MED_NAME_ATTRIBUTE tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEINA0
    op.create_table(
        'rpeina0_med_name_attribute',
        sa.Column('MED_NAME_ID', sa.Text(), nullable=False),
        sa.Column('ATTRIBUTE_CODE', sa.Text(), nullable=False),
        sa.Column('ATTRIBUTE_SN', sa.Text(), nullable=False),
        sa.Column('ATTRIBUTE_VALUE', sa.Text(), nullable=False),
        sa.Column('LINK_INACTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('MED_NAME_ID', 'ATTRIBUTE_CODE', name='pk_rpeina0_med_name_attribute'),
        schema=_SCHEMA,
    )
    # RPEIND0_NDC_DF_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEIND0
    op.create_table(
        'rpeind0_ndc_df_link',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('DOSAGE_FORM_ID', sa.Text(), nullable=False),
        sa.Column('DOSAGE_FORM_TYPE_ID', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', 'DOSAGE_FORM_ID', name='pk_rpeind0_ndc_df_link'),
        schema=_SCHEMA,
    )
    # RPEINR0_NDC_RT_RELATION tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEINR0
    op.create_table(
        'rpeinr0_ndc_rt_relation',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('PARENT_RT_ID', sa.Text(), nullable=False),
        sa.Column('CLINICAL_RT_ID', sa.Text(), nullable=False),
        sa.Column('RT_LABELED_ID', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', 'PARENT_RT_ID', name='pk_rpeinr0_ndc_rt_relation'),
        schema=_SCHEMA,
    )
    # RPEIRA0_RT_DF_MED_ATTRIBUTE tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEIRA0
    op.create_table(
        'rpeira0_rt_df_med_attribute',
        sa.Column('ROUTED_DOSAGE_FORM_MED_ID', sa.Text(), nullable=False),
        sa.Column('ATTRIBUTE_CODE', sa.Text(), nullable=False),
        sa.Column('ATTRIBUTE_SN', sa.Text(), nullable=False),
        sa.Column('ATTRIBUTE_VALUE', sa.Text(), nullable=False),
        sa.Column('LINK_INACTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('ROUTED_DOSAGE_FORM_MED_ID', 'ATTRIBUTE_CODE', name='pk_rpeira0_rt_df_med_attribute'),
        schema=_SCHEMA,
    )
    # RPEIRD0_RTD_DF_MED_DF_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEIRD0
    op.create_table(
        'rpeird0_rtd_df_med_df_link',
        sa.Column('ROUTED_DOSAGE_FORM_MED_ID', sa.Text(), nullable=False),
        sa.Column('DOSAGE_FORM_ID', sa.Text(), nullable=False),
        sa.Column('DOSAGE_FORM_TYPE_ID', sa.Text(), nullable=False),
        sa.Column('LINK_INACTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('ROUTED_DOSAGE_FORM_MED_ID', 'DOSAGE_FORM_ID', name='pk_rpeird0_rtd_df_med_df_link'),
        schema=_SCHEMA,
    )
    # RPEIRMA0_RTD_MED_ATTRIBUTE tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEIRMA0
    op.create_table(
        'rpeirma0_rtd_med_attribute',
        sa.Column('ROUTED_MED_ID', sa.Text(), nullable=False),
        sa.Column('ATTRIBUTE_CODE', sa.Text(), nullable=False),
        sa.Column('ATTRIBUTE_SN', sa.Text(), nullable=False),
        sa.Column('ATTRIBUTE_VALUE', sa.Text(), nullable=False),
        sa.Column('LINK_INACTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('ROUTED_MED_ID', 'ATTRIBUTE_CODE', name='pk_rpeirma0_rtd_med_attribute'),
        schema=_SCHEMA,
    )
    # RPEIRMD0_RTD_MED_DF_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEIRMD0
    op.create_table(
        'rpeirmd0_rtd_med_df_link',
        sa.Column('ROUTED_MED_ID', sa.Text(), nullable=False),
        sa.Column('DOSAGE_FORM_ID', sa.Text(), nullable=False),
        sa.Column('DOSAGE_FORM_TYPE_ID', sa.Text(), nullable=False),
        sa.Column('LINK_INACTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('ROUTED_MED_ID', 'DOSAGE_FORM_ID', name='pk_rpeirmd0_rtd_med_df_link'),
        schema=_SCHEMA,
    )
    # RPEIRMR0_RTD_MED_RT_RELATION tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEIRMR0
    op.create_table(
        'rpeirmr0_rtd_med_rt_relation',
        sa.Column('ROUTED_MED_ID', sa.Text(), nullable=False),
        sa.Column('PARENT_RT_ID', sa.Text(), nullable=False),
        sa.Column('CLINICAL_RT_ID', sa.Text(), nullable=False),
        sa.Column('RELATION_INACTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('ROUTED_MED_ID', 'PARENT_RT_ID', name='pk_rpeirmr0_rtd_med_rt_relation'),
        schema=_SCHEMA,
    )
    # RPEIRR0_RTD_DF_MED_RT_RELATION tier=B delta=UPSERT_BY_NATURAL_KEY rc=RPEIRR0
    op.create_table(
        'rpeirr0_rtd_df_med_rt_relation',
        sa.Column('ROUTED_DOSAGE_FORM_MED_ID', sa.Text(), nullable=False),
        sa.Column('PARENT_RT_ID', sa.Text(), nullable=False),
        sa.Column('CLINICAL_RT_ID', sa.Text(), nullable=False),
        sa.Column('RELATION_INACTIVE_DATE', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('ROUTED_DOSAGE_FORM_MED_ID', 'PARENT_RT_ID', name='pk_rpeirr0_rtd_df_med_rt_relation'),
        schema=_SCHEMA,
    )
    # RRTGNGC0_RTD_GEN_GCNSEQNO_LNK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RRTGNGC0
    op.create_table(
        'rrtgngc0_rtd_gen_gcnseqno_lnk',
        sa.Column('GCN_SEQNO', sa.Text(), nullable=False),
        sa.Column('ROUTED_GEN_ID', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('GCN_SEQNO', 'ROUTED_GEN_ID', name='pk_rrtgngc0_rtd_gen_gcnseqno_lnk'),
        schema=_SCHEMA,
    )
    # RRTGNND0_ROUTED_GEN_NDC_LINK tier=B delta=UPSERT_BY_NATURAL_KEY rc=RRTGNND0
    op.create_table(
        'rrtgnnd0_routed_gen_ndc_link',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('ROUTED_GEN_ID', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', 'ROUTED_GEN_ID', name='pk_rrtgnnd0_routed_gen_ndc_link'),
        schema=_SCHEMA,
    )
    # RTMDFCG0_TM_RTD_DF_CNFSN_GRP tier=B delta=UPSERT_BY_NATURAL_KEY rc=RTMDFCG0
    op.create_table(
        'rtmdfcg0_tm_rtd_df_cnfsn_grp',
        sa.Column('ROUTED_DOSAGE_FORM_MED_ID', sa.Text(), nullable=False),
        sa.Column('TM_GROUP_ID', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('ROUTED_DOSAGE_FORM_MED_ID', 'TM_GROUP_ID', name='pk_rtmdfcg0_tm_rtd_df_cnfsn_grp'),
        schema=_SCHEMA,
    )
    # RTMMICG0_TM_MED_CNFSN_GRP tier=B delta=UPSERT_BY_NATURAL_KEY rc=RTMMICG0
    op.create_table(
        'rtmmicg0_tm_med_cnfsn_grp',
        sa.Column('MEDID', sa.Text(), nullable=False),
        sa.Column('TM_GROUP_ID', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('MEDID', 'TM_GROUP_ID', name='pk_rtmmicg0_tm_med_cnfsn_grp'),
        schema=_SCHEMA,
    )
    # RTMNCG0_TM_NDC_CNFSN_GRP tier=B delta=UPSERT_BY_NATURAL_KEY rc=RTMNCG0
    op.create_table(
        'rtmncg0_tm_ndc_cnfsn_grp',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('TM_GROUP_ID', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', 'TM_GROUP_ID', name='pk_rtmncg0_tm_ndc_cnfsn_grp'),
        schema=_SCHEMA,
    )
    # RTMNID0_TM_NDC tier=B delta=UPSERT_BY_NATURAL_KEY rc=RTMNID0
    op.create_table(
        'rtmnid0_tm_ndc',
        sa.Column('NDC', sa.Text(), nullable=False),
        sa.Column('TM_NAME_TYPE_ID', sa.Text(), nullable=False),
        sa.Column('TM_SOURCE_ID', sa.Text(), nullable=True),
        sa.Column('TM_IND', sa.Text(), nullable=False),
        sa.Column('TM_ALT_NDC_DESC', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('NDC', 'TM_NAME_TYPE_ID', name='pk_rtmnid0_tm_ndc'),
        schema=_SCHEMA,
    )
    # RTMNMCG0_TM_MED_NAME_CNFSN_GRP tier=B delta=UPSERT_BY_NATURAL_KEY rc=RTMNMCG0
    op.create_table(
        'rtmnmcg0_tm_med_name_cnfsn_grp',
        sa.Column('MED_NAME_ID', sa.Text(), nullable=False),
        sa.Column('TM_GROUP_ID', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('MED_NAME_ID', 'TM_GROUP_ID', name='pk_rtmnmcg0_tm_med_name_cnfsn_grp'),
        schema=_SCHEMA,
    )
    # RTMRMCG0_TM_RTD_MED_CNFSN_GRP tier=B delta=UPSERT_BY_NATURAL_KEY rc=RTMRMCG0
    op.create_table(
        'rtmrmcg0_tm_rtd_med_cnfsn_grp',
        sa.Column('ROUTED_MED_ID', sa.Text(), nullable=False),
        sa.Column('TM_GROUP_ID', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('ROUTED_MED_ID', 'TM_GROUP_ID', name='pk_rtmrmcg0_tm_rtd_med_cnfsn_grp'),
        schema=_SCHEMA,
    )

    _TIER_B_TABLES = [
        'rahfsgc1_gcnseqno_link',
        'rapplna0_fda_ndc_appl',
        'rapplsl0_fda_ndc_nda_anda',
        'ratcgc0_atc_gcnseqno_link',
        'rcqndc0_clnqty_ndc',
        'retcgc0_etc_gcnseqno',
        'retcgch0_etc_gcnseqno_hist',
        'retchcl0_etc_hiclseqno',
        'retchic0_etc_hicseqn',
        'retcmdh0_etc_medid_hist',
        'retcmed0_etc_medid',
        'retcmnm0_etc_med_name_id',
        'retcndc0_etc_ndc',
        'retcndh0_etc_ndc_hist',
        'rgcn0_gcn_gcnseqno_link',
        'rgcninh0_gcnseqno_inactv_link',
        'rgcnins0_study_table',
        'rhic3l2_hic3_hiclseqno_link',
        'rhic4d2_hic_base_ing_desc',
        'rhiccas1_hic_cas_link',
        'rhicd5_hic_desc',
        'rhichcr0_hic_hic_link',
        'rhicl1_hic_hiclseqno_link',
        'rhiclsq1_hiclseqno_mstr',
        'rhiclsq2_hiclseqno_mstr',
        'rmeddin0_rdfmid_inactv_link',
        'rmeddis0_routed_df_study_table',
        'rmedin0_medid_inactv_link',
        'rmedis0_medid_study_table',
        'rmedngh0_ndc_gen_medid_hist',
        'rmedngm0_ndc_gen_medid',
        'rmedngr0_ndc_gen_medid_reason',
        'rmednin0_mnid_inactv_link',
        'rmednis0_med_name_study_table',
        'rmednmh0_ndc_medid_hist',
        'rmednmr0_ndc_medid_reason',
        'rmedrin0_rmid_inactv_link',
        'rmedris0_routed_med_stdy_tbl',
        'rmedspc0_specification',
        'rmigc1_medid_gcnseqno_link',
        'rmindc1_ndc_medid',
        'rminmid1_med_name',
        'rndcat0_ndc_attribute',
        'rndcinh0_ndc_inactv_link',
        'rndcinr0_inactv_reviewed',
        'robcndc0_obc_ndc',
        'rpeiga0_gcnseqno_attribute',
        'rpeigd0_gcnseqno_df_link',
        'rpeigr0_gcnseqno_rt_relation',
        'rpeigrr0_gcnseqno_rep_rt',
        'rpeihr0_hiclseqno_rt_relation',
        'rpeima0_med_attribute',
        'rpeimd0_med_df_link',
        'rpeimnr0_med_name_rt_relation',
        'rpeimrr0_med_rt_relation',
        'rpeina0_med_name_attribute',
        'rpeind0_ndc_df_link',
        'rpeinr0_ndc_rt_relation',
        'rpeira0_rt_df_med_attribute',
        'rpeird0_rtd_df_med_df_link',
        'rpeirma0_rtd_med_attribute',
        'rpeirmd0_rtd_med_df_link',
        'rpeirmr0_rtd_med_rt_relation',
        'rpeirr0_rtd_df_med_rt_relation',
        'rrtgngc0_rtd_gen_gcnseqno_lnk',
        'rrtgnnd0_routed_gen_ndc_link',
        'rtmdfcg0_tm_rtd_df_cnfsn_grp',
        'rtmmicg0_tm_med_cnfsn_grp',
        'rtmncg0_tm_ndc_cnfsn_grp',
        'rtmnid0_tm_ndc',
        'rtmnmcg0_tm_med_name_cnfsn_grp',
        'rtmrmcg0_tm_rtd_med_cnfsn_grp',
    ]
    for _tbl in _TIER_B_TABLES:
        op.execute(f"GRANT SELECT ON {_SCHEMA}.{_tbl} TO {_APP_ROLE}")


def downgrade() -> None:
    op.drop_table('rtmrmcg0_tm_rtd_med_cnfsn_grp', schema=_SCHEMA)
    op.drop_table('rtmnmcg0_tm_med_name_cnfsn_grp', schema=_SCHEMA)
    op.drop_table('rtmnid0_tm_ndc', schema=_SCHEMA)
    op.drop_table('rtmncg0_tm_ndc_cnfsn_grp', schema=_SCHEMA)
    op.drop_table('rtmmicg0_tm_med_cnfsn_grp', schema=_SCHEMA)
    op.drop_table('rtmdfcg0_tm_rtd_df_cnfsn_grp', schema=_SCHEMA)
    op.drop_table('rrtgnnd0_routed_gen_ndc_link', schema=_SCHEMA)
    op.drop_table('rrtgngc0_rtd_gen_gcnseqno_lnk', schema=_SCHEMA)
    op.drop_table('rpeirr0_rtd_df_med_rt_relation', schema=_SCHEMA)
    op.drop_table('rpeirmr0_rtd_med_rt_relation', schema=_SCHEMA)
    op.drop_table('rpeirmd0_rtd_med_df_link', schema=_SCHEMA)
    op.drop_table('rpeirma0_rtd_med_attribute', schema=_SCHEMA)
    op.drop_table('rpeird0_rtd_df_med_df_link', schema=_SCHEMA)
    op.drop_table('rpeira0_rt_df_med_attribute', schema=_SCHEMA)
    op.drop_table('rpeinr0_ndc_rt_relation', schema=_SCHEMA)
    op.drop_table('rpeind0_ndc_df_link', schema=_SCHEMA)
    op.drop_table('rpeina0_med_name_attribute', schema=_SCHEMA)
    op.drop_table('rpeimrr0_med_rt_relation', schema=_SCHEMA)
    op.drop_table('rpeimnr0_med_name_rt_relation', schema=_SCHEMA)
    op.drop_table('rpeimd0_med_df_link', schema=_SCHEMA)
    op.drop_table('rpeima0_med_attribute', schema=_SCHEMA)
    op.drop_table('rpeihr0_hiclseqno_rt_relation', schema=_SCHEMA)
    op.drop_table('rpeigrr0_gcnseqno_rep_rt', schema=_SCHEMA)
    op.drop_table('rpeigr0_gcnseqno_rt_relation', schema=_SCHEMA)
    op.drop_table('rpeigd0_gcnseqno_df_link', schema=_SCHEMA)
    op.drop_table('rpeiga0_gcnseqno_attribute', schema=_SCHEMA)
    op.drop_table('robcndc0_obc_ndc', schema=_SCHEMA)
    op.drop_table('rndcinr0_inactv_reviewed', schema=_SCHEMA)
    op.drop_table('rndcinh0_ndc_inactv_link', schema=_SCHEMA)
    op.drop_table('rndcat0_ndc_attribute', schema=_SCHEMA)
    op.drop_table('rminmid1_med_name', schema=_SCHEMA)
    op.drop_table('rmindc1_ndc_medid', schema=_SCHEMA)
    op.drop_table('rmigc1_medid_gcnseqno_link', schema=_SCHEMA)
    op.drop_table('rmedspc0_specification', schema=_SCHEMA)
    op.drop_table('rmedris0_routed_med_stdy_tbl', schema=_SCHEMA)
    op.drop_table('rmedrin0_rmid_inactv_link', schema=_SCHEMA)
    op.drop_table('rmednmr0_ndc_medid_reason', schema=_SCHEMA)
    op.drop_table('rmednmh0_ndc_medid_hist', schema=_SCHEMA)
    op.drop_table('rmednis0_med_name_study_table', schema=_SCHEMA)
    op.drop_table('rmednin0_mnid_inactv_link', schema=_SCHEMA)
    op.drop_table('rmedngr0_ndc_gen_medid_reason', schema=_SCHEMA)
    op.drop_table('rmedngm0_ndc_gen_medid', schema=_SCHEMA)
    op.drop_table('rmedngh0_ndc_gen_medid_hist', schema=_SCHEMA)
    op.drop_table('rmedis0_medid_study_table', schema=_SCHEMA)
    op.drop_table('rmedin0_medid_inactv_link', schema=_SCHEMA)
    op.drop_table('rmeddis0_routed_df_study_table', schema=_SCHEMA)
    op.drop_table('rmeddin0_rdfmid_inactv_link', schema=_SCHEMA)
    op.drop_table('rhiclsq2_hiclseqno_mstr', schema=_SCHEMA)
    op.drop_table('rhiclsq1_hiclseqno_mstr', schema=_SCHEMA)
    op.drop_table('rhicl1_hic_hiclseqno_link', schema=_SCHEMA)
    op.drop_table('rhichcr0_hic_hic_link', schema=_SCHEMA)
    op.drop_table('rhicd5_hic_desc', schema=_SCHEMA)
    op.drop_table('rhiccas1_hic_cas_link', schema=_SCHEMA)
    op.drop_table('rhic4d2_hic_base_ing_desc', schema=_SCHEMA)
    op.drop_table('rhic3l2_hic3_hiclseqno_link', schema=_SCHEMA)
    op.drop_table('rgcnins0_study_table', schema=_SCHEMA)
    op.drop_table('rgcninh0_gcnseqno_inactv_link', schema=_SCHEMA)
    op.drop_table('rgcn0_gcn_gcnseqno_link', schema=_SCHEMA)
    op.drop_table('retcndh0_etc_ndc_hist', schema=_SCHEMA)
    op.drop_table('retcndc0_etc_ndc', schema=_SCHEMA)
    op.drop_table('retcmnm0_etc_med_name_id', schema=_SCHEMA)
    op.drop_table('retcmed0_etc_medid', schema=_SCHEMA)
    op.drop_table('retcmdh0_etc_medid_hist', schema=_SCHEMA)
    op.drop_table('retchic0_etc_hicseqn', schema=_SCHEMA)
    op.drop_table('retchcl0_etc_hiclseqno', schema=_SCHEMA)
    op.drop_table('retcgch0_etc_gcnseqno_hist', schema=_SCHEMA)
    op.drop_table('retcgc0_etc_gcnseqno', schema=_SCHEMA)
    op.drop_table('rcqndc0_clnqty_ndc', schema=_SCHEMA)
    op.drop_table('ratcgc0_atc_gcnseqno_link', schema=_SCHEMA)
    op.drop_table('rapplsl0_fda_ndc_nda_anda', schema=_SCHEMA)
    op.drop_table('rapplna0_fda_ndc_appl', schema=_SCHEMA)
    op.drop_table('rahfsgc1_gcnseqno_link', schema=_SCHEMA)
