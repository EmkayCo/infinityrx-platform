"""Rule-type registry: 46-rule catalog + idempotent DB seeders.

Severity/confidence derivation (deterministic, from legacy confidence_scoring):
  "high" key, threshold >= 1.0  -> severity="critical", confidence=0.90
  "high" key, threshold < 1.0   -> severity="high",     confidence=min(threshold,0.90)
  "medium" key only              -> severity="medium",   confidence=0.70
  "low" key only                 -> severity="low",      confidence=0.50

Family mapping: pricing_integrity->A1, billing_pattern->A2, utilization->A3,
  eligibility->A4, controlled_substance->A5,
  network_compliance/340b/workers_comp/duplicate/accumulator->A6

Production seeding note: detection_rule_types is a global reference table (no
  tenant_id). App role must have INSERT, or run via migration/admin context.
  SQLite test fixtures use engine owner -- no grant issue in tests.

ML detector rows (ml_detector_registry) are pre-seeded by migration 0008_ml_detector_seed.
  The app role has SELECT-only on that table. register_rule_instances MUST NOT write to it.
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session
from src.models.detection_run_models import DetectionRuleInstance, DetectionRuleType

_CATEGORY_FAMILY: dict[str, str] = {
    "pricing_integrity": "A1", "billing_pattern": "A2", "utilization": "A3",
    "eligibility": "A4", "controlled_substance": "A5",
    "network_compliance": "A6", "340b": "A6", "workers_comp": "A6",
    "duplicate": "A6", "accumulator": "A6",
}

RULE_TYPE_CATALOG: list[dict] = [
    {"code":'ALL-001',"name":'Duplicate Claim',"description":'Same member, same NDC, same DOS, different auth number',"family":_CATEGORY_FAMILY['duplicate'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":False,"deferred_reason":'',"required_data_columns":['patient_unique_hash', 'ndc', 'date_of_service', 'auth_no_hash', 'transaction_code', 'transaction_status'],"default_parameters":{'pattern': 'duplicate_claim', 'threshold': 1.0}},
    {"code":'ALL-002',"name":'Phantom Pharmacy',"description":'NPI not in NCPDP database or OIG excluded',"family":_CATEGORY_FAMILY['eligibility'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires NCPDP registry and OIG exclusion list -- external data feeds not present in CSV',"required_data_columns":[],"default_parameters":{'pattern': 'phantom_pharmacy'}},
    {"code":'ALL-003',"name":'Phantom Prescriber',"description":'NPI invalid, DEA inactive, or OIG excluded',"family":_CATEGORY_FAMILY['eligibility'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires DEA active/inactive registry and OIG exclusion list -- external data feeds not present in CSV',"required_data_columns":[],"default_parameters":{'pattern': 'phantom_prescriber'}},
    {"code":'ALL-004',"name":'Days Supply Manipulation',"description":'Quantity and days supply inconsistent with NDC packaging/dosing',"family":_CATEGORY_FAMILY['billing_pattern'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires NDC packaging/dosing reference data to compute days_supply_deviation_pct',"required_data_columns":[],"default_parameters":{'field': 'days_supply_deviation_pct', 'operator': 'gt', 'threshold': 0.2}},
    {"code":'ALL-005',"name":'Early Refill',"description":'Fill date before configured percent of previous days supply',"family":_CATEGORY_FAMILY['billing_pattern'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":False,"requires_history":True,"deferred_data_feed":False,"deferred_reason":'',"required_data_columns":['patient_unique_hash', 'ndc', 'date_of_service', 'day_supply'],"default_parameters":{'field': 'refill_pct', 'operator': 'lt', 'threshold': 0.75}},
    {"code":'ALL-006',"name":'Weekend/Holiday Volume Spike',"description":'Pharmacy claims volume on weekend/holiday exceeds weekday average',"family":_CATEGORY_FAMILY['billing_pattern'],"parameter_schema_version":"1.0","default_severity":'low',"default_confidence":0.5,"requires_baseline":True,"requires_history":True,"deferred_data_feed":False,"deferred_reason":'',"required_data_columns":['pharmacy_npi', 'date_of_service'],"default_parameters":{'field': 'weekend_volume_vs_weekday_ratio', 'operator': 'gt', 'threshold': 2.0}},
    {"code":'ALL-007',"name":'Geographic Anomaly',"description":'Member filling at pharmacy more than 100 miles from home address',"family":_CATEGORY_FAMILY['billing_pattern'],"parameter_schema_version":"1.0","default_severity":'low',"default_confidence":0.5,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires member home address -- only zip3 available in CSV; full geo-distance cannot be computed',"required_data_columns":[],"default_parameters":{'field': 'geo_distance_miles', 'operator': 'gt', 'threshold': 100}},
    {"code":'ALL-008',"name":'Suspicious Network Cluster',"description":'Community of entities with >80% self-referral rate and geographic spread >200 miles',"family":_CATEGORY_FAMILY['billing_pattern'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires graph/network analysis infrastructure -- not computable from a single CSV batch',"required_data_columns":[],"default_parameters":{'self_referral_threshold': 0.8, 'geo_spread_miles': 200}},
    {"code":'ALL-009',"name":'Auto-Hold on Critical Investigation',"description":'When investigation reaches CRITICAL severity, automatically hold future payments',"family":_CATEGORY_FAMILY['billing_pattern'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Operational auto-hold requires live investigation state -- not applicable in CSV batch detection',"required_data_columns":[],"default_parameters":{'pattern': 'critical_investigation_auto_hold', 'auto_hold_enabled': True}},
    {"code":'ALL-010',"name":'Predictive Watchlist Trigger',"description":'Pharmacy 30-day fraud probability exceeds threshold',"family":_CATEGORY_FAMILY['billing_pattern'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires trained predictive ML model with 30-day rolling pharmacy scores -- not available from CSV alone',"required_data_columns":[],"default_parameters":{'field': 'fraud_probability_30d', 'operator': 'gt', 'threshold': 0.7, 'confidence_high': 0.9, 'confidence_medium': 0.7}},
    {"code":'MFR-001',"name":'NQ Inflation',"description":'(DV+NQ) exceeds WAC per unit x quantity',"family":_CATEGORY_FAMILY['pricing_integrity'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":False,"deferred_reason":'',"required_data_columns":['extended_wac', 'ingredient_cost_paid', 'dispensing_fee_paid', 'quantity_dispensed'],"default_parameters":{'field': 'nq_to_wac_ratio', 'operator': 'gt', 'threshold': 1.1, 'confidence_high': 1.5, 'confidence_medium': 1.2, 'confidence_low': 1.1}},
    {"code":'MFR-002',"name":'Bill-Reverse-Rebill',"description":'Same pharmacy, NDC, member -- reversal then rebill with higher NQ within 14 days',"family":_CATEGORY_FAMILY['billing_pattern'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":True,"deferred_data_feed":False,"deferred_reason":'',"required_data_columns":['patient_unique_hash', 'pharmacy_npi', 'ndc', 'transaction_code', 'reversed_check', 'date_added_timestamp', 'ingredient_cost_paid'],"default_parameters":{'pattern': 'bill_reverse_rebill', 'lookback_days': 14}},
    {"code":'MFR-003',"name":'Contracted Rate Deviation',"description":'Pharmacy rate deviates from their own historical baseline',"family":_CATEGORY_FAMILY['pricing_integrity'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":True,"requires_history":True,"deferred_data_feed":False,"deferred_reason":'',"required_data_columns":['pharmacy_npi', 'ndc', 'ingredient_cost_paid', 'extended_wac', 'date_of_service'],"default_parameters":{'field': 'contracted_rate_deviation_pct', 'operator': 'gt', 'threshold': 0.15, 'baseline_days': 90}},
    {"code":'MFR-004',"name":'Volume Spike',"description":'Pharmacy submits more claims for specific NDC vs rolling average',"family":_CATEGORY_FAMILY['utilization'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":True,"requires_history":True,"deferred_data_feed":False,"deferred_reason":'',"required_data_columns":['pharmacy_npi', 'ndc', 'date_of_service'],"default_parameters":{'field': 'volume_vs_avg_ratio', 'operator': 'gt', 'threshold': 2.0, 'rolling_days': 30}},
    {"code":'MFR-005',"name":'eVoucher/Coupon Abuse',"description":'Same voucher code used for multiple patients or exceeded max uses',"family":_CATEGORY_FAMILY['billing_pattern'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires voucher/coupon code data absent from standard pharmacy claim CSV',"required_data_columns":[],"default_parameters":{'pattern': 'voucher_abuse'}},
    {"code":'MFR-006',"name":'Phantom Patient',"description":'Claims for members with no matching enrollment record',"family":_CATEGORY_FAMILY['eligibility'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires enrollment records from member management system -- not present in CSV',"required_data_columns":[],"default_parameters":{'pattern': 'phantom_patient'}},
    {"code":'MFR-007',"name":'Accumulator/Maximizer Detection',"description":'Copay assistance not counting toward member deductible/OOP',"family":_CATEGORY_FAMILY['accumulator'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires copay-assistance program data and deductible/OOP tracking -- not present in CSV',"required_data_columns":[],"default_parameters":{'pattern': 'accumulator_maximizer', 'confidence_high': 0.97, 'confidence_medium': 0.8}},
    {"code":'MFR-008',"name":'Statement Credit Abuse',"description":'Statement account pharmacy submitting claims that should be statement-only',"family":_CATEGORY_FAMILY['billing_pattern'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":False,"deferred_reason":'',"required_data_columns":['statement_account', 'pharmacy_npi'],"default_parameters":{'pattern': 'statement_credit_abuse'}},
    {"code":'MFR-009',"name":'Under-Reimbursement Gaming',"description":'Pharmacy consistently submitting U&C at minimum to maximize POS adjustment',"family":_CATEGORY_FAMILY['pricing_integrity'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":True,"requires_history":True,"deferred_data_feed":False,"deferred_reason":'',"required_data_columns":['pharmacy_npi', 'u_c', 'pos_adjustment'],"default_parameters":{'pattern': 'uc_minimum_gaming'}},
    {"code":'HP-001',"name":'Network Leakage',"description":'Claims filled at out-of-network pharmacies when in-network available within 10 miles',"family":_CATEGORY_FAMILY['network_compliance'],"parameter_schema_version":"1.0","default_severity":'low',"default_confidence":0.5,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires in-network pharmacy geo-coverage map -- external data feed not present in CSV',"required_data_columns":[],"default_parameters":{'pattern': 'network_leakage', 'in_network_radius_miles': 10}},
    {"code":'HP-002',"name":'Formulary Non-Compliance',"description":'Non-formulary drug dispensed without prior authorization',"family":_CATEGORY_FAMILY['network_compliance'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires formulary list and PA approval status -- external data feeds not present in CSV',"required_data_columns":[],"default_parameters":{'pattern': 'formulary_non_compliance'}},
    {"code":'HP-003',"name":'Therapeutic Duplication',"description":'Member receiving two drugs from same therapeutic class simultaneously',"family":_CATEGORY_FAMILY['utilization'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires therapeutic class reference data -- drug classification not present in CSV',"required_data_columns":[],"default_parameters":{'pattern': 'therapeutic_duplication'}},
    {"code":'HP-004',"name":'Drug-Disease Contraindication',"description":'Drug inappropriate for member diagnosed conditions',"family":_CATEGORY_FAMILY['utilization'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires member diagnosis codes -- PHI data not present in CSV',"required_data_columns":[],"default_parameters":{'pattern': 'drug_disease_contraindication'}},
    {"code":'HP-005',"name":'Prescriber Outlier',"description":'Prescriber volume for specific drug exceeds peer group by 3 standard deviations',"family":_CATEGORY_FAMILY['utilization'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":True,"requires_history":True,"deferred_data_feed":False,"deferred_reason":'',"required_data_columns":['prescriber_npi', 'ndc', 'date_of_service'],"default_parameters":{'field': 'prescriber_volume_std_devs', 'operator': 'gt', 'threshold': 3.0}},
    {"code":'HP-006',"name":'Pharmacy Audit Trigger',"description":'Pharmacy flagged on multiple rules exceeding threshold in period',"family":_CATEGORY_FAMILY['billing_pattern'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Depends on prior rule-flag counts from other rules -- not independently computable from raw CSV',"required_data_columns":[],"default_parameters":{'field': 'flag_count_30d', 'operator': 'gt', 'threshold': 5, 'period_days': 30}},
    {"code":'HP-007',"name":'Controlled Substance Monitoring',"description":'Opioid MME exceeds CDC guideline, multiple prescribers/pharmacies',"family":_CATEGORY_FAMILY['controlled_substance'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires opioid MME conversion factors and drug schedule classification -- not present in CSV',"required_data_columns":[],"default_parameters":{'mme_threshold': 90, 'max_prescribers': 3, 'max_pharmacies': 3}},
    {"code":'HP-008',"name":'High-Cost Claimant',"description":'Member claims exceed configured threshold in period (top 1%)',"family":_CATEGORY_FAMILY['utilization'],"parameter_schema_version":"1.0","default_severity":'low',"default_confidence":0.5,"requires_baseline":True,"requires_history":True,"deferred_data_feed":False,"deferred_reason":'',"required_data_columns":['patient_unique_hash', 'total_paid_amt'],"default_parameters":{'field': 'cost_percentile', 'operator': 'gte', 'threshold': 0.99, 'percentile_threshold': 0.99}},
    {"code":'HP-009',"name":'Inappropriate Quantity',"description":'Quantity exceeds FDA max recommended or plan limits',"family":_CATEGORY_FAMILY['utilization'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires FDA max quantity per NDC reference data -- not present in CSV',"required_data_columns":[],"default_parameters":{'pattern': 'quantity_exceeds_limit'}},
    {"code":'HP-010',"name":'Refill Pattern Anomaly',"description":'Member consistently fills exactly on day X (possible auto-refill waste)',"family":_CATEGORY_FAMILY['utilization'],"parameter_schema_version":"1.0","default_severity":'low',"default_confidence":0.5,"requires_baseline":False,"requires_history":True,"deferred_data_feed":False,"deferred_reason":'',"required_data_columns":['patient_unique_hash', 'ndc', 'date_of_service'],"default_parameters":{'pattern': 'refill_pattern_anomaly'}},
    {"code":'TPA-001',"name":'Eligibility Mismatch',"description":'Claim paid for member not eligible on DOS',"family":_CATEGORY_FAMILY['eligibility'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires real-time eligibility check against member enrollment system -- not computable from CSV',"required_data_columns":[],"default_parameters":{'pattern': 'eligibility_mismatch'}},
    {"code":'TPA-002',"name":'COB Error',"description":'Primary/secondary payer assignment incorrect',"family":_CATEGORY_FAMILY['billing_pattern'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires coordination of benefits payer order from plan design -- not present in CSV',"required_data_columns":[],"default_parameters":{'pattern': 'cob_error'}},
    {"code":'TPA-003',"name":'Plan Design Violation',"description":'Benefit applied does not match plan configuration',"family":_CATEGORY_FAMILY['billing_pattern'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires plan design configuration data -- not present in CSV',"required_data_columns":[],"default_parameters":{'pattern': 'plan_design_violation'}},
    {"code":'TPA-004',"name":'Provider Credential Issue',"description":'Pharmacy or prescriber credentials expired or suspended',"family":_CATEGORY_FAMILY['eligibility'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires provider credential status from credentialing system -- external data feed not in CSV',"required_data_columns":[],"default_parameters":{'pattern': 'credential_issue'}},
    {"code":'340B-001',"name":'Duplicate Discount',"description":'340B discounted drug also subject to manufacturer rebate for same claim',"family":_CATEGORY_FAMILY['340b'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires HRSA 340B entity/drug eligibility registry -- external data feed not in CSV',"required_data_columns":[],"default_parameters":{'pattern': '340b_duplicate_discount'}},
    {"code":'340B-002',"name":'Contract Pharmacy Non-Compliance',"description":'Claim from pharmacy not registered as 340B contract pharmacy',"family":_CATEGORY_FAMILY['340b'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires HRSA 340B contract pharmacy registry -- external data feed not in CSV',"required_data_columns":[],"default_parameters":{'pattern': '340b_contract_pharmacy'}},
    {"code":'340B-003',"name":'Covered Entity Verification',"description":'Entity claiming 340B pricing not on HRSA database',"family":_CATEGORY_FAMILY['340b'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires HRSA 340B covered entity database -- external data feed not in CSV',"required_data_columns":[],"default_parameters":{'pattern': '340b_covered_entity'}},
    {"code":'340B-004',"name":'Split Billing Accuracy',"description":'340B vs non-340B classification does not match patient eligibility',"family":_CATEGORY_FAMILY['340b'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires 340B patient eligibility data from covered entity -- external data not in CSV',"required_data_columns":[],"default_parameters":{'pattern': '340b_split_billing'}},
    {"code":'340B-005',"name":'Diversion',"description":'Drug dispensed to non-eligible patient at 340B pricing',"family":_CATEGORY_FAMILY['340b'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires 340B patient eligibility list from covered entity -- external data not in CSV',"required_data_columns":[],"default_parameters":{'pattern': '340b_diversion'}},
    {"code":'WC-001',"name":'State Formulary Non-Compliance',"description":'Drug not on state workers compensation formulary',"family":_CATEGORY_FAMILY['workers_comp'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires state workers compensation formulary data -- external data feed not in CSV',"required_data_columns":[],"default_parameters":{'pattern': 'wc_formulary_non_compliance'}},
    {"code":'WC-002',"name":'Exceeds State Fee Schedule',"description":'Reimbursement exceeds state WC fee schedule',"family":_CATEGORY_FAMILY['workers_comp'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires state workers compensation fee schedule data -- external data feed not in CSV',"required_data_columns":[],"default_parameters":{'field': 'fee_schedule_ratio', 'operator': 'gt', 'threshold': 1.0}},
    {"code":'WC-003',"name":'Treatment Duration Exceeded',"description":'Fills exceed expected treatment duration for injury type',"family":_CATEGORY_FAMILY['workers_comp'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires injury type and expected treatment duration from workers comp claim -- external data not in CSV',"required_data_columns":[],"default_parameters":{'field': 'treatment_duration_ratio', 'operator': 'gt', 'threshold': 1.5}},
    {"code":'WC-004',"name":'Opioid Guidelines',"description":'Opioid prescribing exceeds state WC opioid guidelines',"family":_CATEGORY_FAMILY['controlled_substance'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires state WC opioid guideline thresholds and drug schedule classification -- external data not in CSV',"required_data_columns":[],"default_parameters":{'pattern': 'wc_opioid_guideline'}},
    {"code":'TH-001',"name":'Telehealth Prescriber Volume',"description":'Telehealth prescriber writing more than 50 scripts/day',"family":_CATEGORY_FAMILY['utilization'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires telehealth encounter flag -- not present in standard pharmacy claim CSV',"required_data_columns":[],"default_parameters":{'field': 'scripts_per_day', 'operator': 'gt', 'threshold': 50}},
    {"code":'TH-002',"name":'Telehealth Geographic Dispersion',"description":'Telehealth prescriber patients spread across more than 10 states',"family":_CATEGORY_FAMILY['billing_pattern'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":False,"requires_history":True,"deferred_data_feed":False,"deferred_reason":'',"required_data_columns":['prescriber_npi', 'patient_state'],"default_parameters":{'field': 'patient_state_count', 'operator': 'gt', 'threshold': 10}},
    {"code":'TH-003',"name":'Telehealth + High-Cost Drug',"description":'Telehealth prescriber writing high-cost specialty or GLP-1 drugs at >40% of volume',"family":_CATEGORY_FAMILY['utilization'],"parameter_schema_version":"1.0","default_severity":'medium',"default_confidence":0.7,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires drug-class classification list (specialty/GLP-1) -- external reference data not in CSV',"required_data_columns":[],"default_parameters":{'field': 'high_cost_drug_rate', 'operator': 'gt', 'threshold': 0.4}},
    {"code":'TH-004',"name":'Telehealth + Controlled Substance',"description":'Telehealth prescriber writing Schedule II-V controlled substances',"family":_CATEGORY_FAMILY['controlled_substance'],"parameter_schema_version":"1.0","default_severity":'critical',"default_confidence":0.9,"requires_baseline":False,"requires_history":False,"deferred_data_feed":True,"deferred_reason":'Requires DEA drug schedule classification and telehealth encounter flag -- external data not in CSV',"required_data_columns":[],"default_parameters":{'pattern': 'telehealth_controlled_substance'}},
    {"code":'TH-005',"name":'Telehealth Prescriber-Pharmacy Affinity',"description":'More than 50% of telehealth prescriber scripts filled at single pharmacy',"family":_CATEGORY_FAMILY['billing_pattern'],"parameter_schema_version":"1.0","default_severity":'high',"default_confidence":0.5,"requires_baseline":False,"requires_history":True,"deferred_data_feed":False,"deferred_reason":'',"required_data_columns":['prescriber_npi', 'pharmacy_npi'],"default_parameters":{'field': 'top_pharmacy_share', 'operator': 'gt', 'threshold': 0.5}}
]


def register_rule_types(db: Session) -> int:
    """Idempotent upsert of all RULE_TYPE_CATALOG entries into detection_rule_types.

    Existing rows (matched by code) are skipped. Returns count inserted.
    Production: run under a role with INSERT on reclaimrx.detection_rule_types,
    or via migration/admin context (same pattern as ml_detector_registry seeding).
    """
    from sqlalchemy import select
    inserted = 0
    for entry in RULE_TYPE_CATALOG:
        existing = db.execute(
            select(DetectionRuleType).where(DetectionRuleType.code == entry["code"])
        ).scalar_one_or_none()
        if existing is None:
            row = DetectionRuleType(
                code=entry["code"], name=entry["name"],
                description=entry["description"], family=entry["family"],
                parameter_schema_version=entry["parameter_schema_version"],
                default_severity=entry["default_severity"],
                default_confidence=entry["default_confidence"],
                requires_baseline=entry["requires_baseline"],
                requires_history=entry["requires_history"],
                deferred_data_feed=entry["deferred_data_feed"],
                deferred_reason=entry["deferred_reason"],
                required_data_columns=entry["required_data_columns"],
                default_parameters=entry["default_parameters"],
            )
            db.add(row)
            inserted += 1
    db.flush()
    return inserted

def register_rule_instances(
    db: Session,
    tenant_id: uuid.UUID,
    available_columns: set[str],
    created_by: uuid.UUID,
) -> int:
    """Idempotent creation of detection_rule_instance rows for a tenant.

    For each rule_type in the catalog where:
      - deferred_data_feed is False, AND
      - all required_data_columns are present in available_columns

    creates ONE DetectionRuleInstance for tenant_id if not already present.
    Idempotency key: (tenant_id, rule_type_code, instance_name).

    Deferred rules and rules whose required columns are not fully present in
    available_columns produce no instance.

    Does NOT touch ml_detector_registry — those rows are pre-seeded by
    migration 0008_ml_detector_seed and the app role is SELECT-only there.

    Returns count of rows inserted.
    """
    from sqlalchemy import and_, select

    inserted = 0
    for entry in RULE_TYPE_CATALOG:
        # Gate 1: skip deferred rules.
        if entry["deferred_data_feed"]:
            continue
        # Gate 2: skip if required columns are not all available.
        required_cols: list[str] = entry["required_data_columns"]
        if not set(required_cols) <= available_columns:
            continue

        code: str = entry["code"]
        instance_name = f"{code}-default"

        existing = db.execute(
            select(DetectionRuleInstance).where(
                and_(
                    DetectionRuleInstance.tenant_id == tenant_id,
                    DetectionRuleInstance.rule_type_code == code,
                    DetectionRuleInstance.instance_name == instance_name,
                )
            )
        ).scalar_one_or_none()

        if existing is None:
            row = DetectionRuleInstance(
                tenant_id=tenant_id,
                rule_type_code=code,
                instance_name=instance_name,
                parameters=entry["default_parameters"],
                enabled=True,
                effective_from=date.today(),
                created_by=created_by,
            )
            db.add(row)
            inserted += 1

    db.flush()
    return inserted
