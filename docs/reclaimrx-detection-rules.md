# ReclaimRx Detection Rules — Complete Catalog

> Generated from `modules/reclaimrx/src/detection/rule_type_registry.py` (`RULE_TYPE_CATALOG`) — the single source of truth. Regenerate with the catalog if rules change.

**Total rules:** 48  |  **Live (RUN):** 16  |  **Deferred (need external data):** 32

- **Live (RUN)** = `deferred_data_feed: false` — evaluated on every detection run.
- **Deferred** = needs an external data feed not present in the standard claim CSV (registry, formulary, eligibility, etc.).
- **Family** maps to the engineered category (A1–A6).

## Family legend

| Family | Category |
|---|---|
| A1 | pricing_integrity |
| A2 | billing_pattern |
| A3 | utilization |
| A4 | eligibility |
| A5 | controlled_substance |
| A6 | accumulator |

## Live fire rates — full 2.6M dataset (dev run, guardrail bypassed, UNCALIBRATED)

From the `allDataMinusPHI` run over 2,611,415 claims. Only these rules fired (others need columns/feeds absent from this CSV). MFR-001 dominates — the primary calibration target.

| Rule | Anomalies | Fire rate |
|---|---:|---:|
| MFR-001 | 403,377 | 15.45% |
| TH-005 | 15,881 | 0.61% |
| ALL-001 | 2,477 | 0.09% |
| HP-005 | 290 | 0.01% |
| MFR-004 | 109 | 0.00% |
| ALL-006 | 31 | 0.00% |
| TH-002 | 28 | 0.00% |
| **TOTAL** | **422,193** | **16.17%** |

> ⚠ The 1% safety guardrail is bypassed in dev to show this volume. Calibrate MFR-001 before production.

## All rules — summary

| Code | Name | Family | Severity | Conf | Status | Baseline | History |
|---|---|---|---|---|---|---|---|
| `ALL-001` | Duplicate Claim | A6 | critical | 0.9 | LIVE | - | - |
| `ALL-002` | Phantom Pharmacy | A4 | critical | 0.9 | LIVE | - | - |
| `ALL-003` | Phantom Prescriber | A4 | critical | 0.9 | LIVE | - | - |
| `ALL-004` | Days Supply Manipulation | A2 | medium | 0.7 | deferred | - | - |
| `ALL-005` | Early Refill | A2 | medium | 0.7 | LIVE | - | yes |
| `ALL-006` | Weekend/Holiday Volume Spike | A2 | low | 0.5 | LIVE | yes | yes |
| `ALL-007` | Geographic Anomaly | A2 | low | 0.5 | deferred | - | - |
| `ALL-008` | Suspicious Network Cluster | A2 | medium | 0.7 | deferred | - | - |
| `ALL-009` | Auto-Hold on Critical Investigation | A2 | critical | 0.9 | deferred | - | - |
| `ALL-010` | Predictive Watchlist Trigger | A2 | critical | 0.9 | deferred | - | - |
| `MFR-001` | NQ Inflation | A1 | critical | 0.9 | LIVE | - | - |
| `MFR-002` | Bill-Reverse-Rebill | A2 | critical | 0.9 | LIVE | - | yes |
| `MFR-003` | Contracted Rate Deviation | A1 | medium | 0.7 | LIVE | yes | yes |
| `MFR-004` | Volume Spike | A3 | medium | 0.7 | LIVE | yes | yes |
| `MFR-005` | eVoucher/Coupon Abuse | A2 | critical | 0.9 | deferred | - | - |
| `MFR-006` | Phantom Patient | A4 | critical | 0.9 | deferred | - | - |
| `MFR-007` | Accumulator/Maximizer Detection | A6 | critical | 0.9 | deferred | - | - |
| `MFR-008` | Statement Credit Abuse | A2 | critical | 0.9 | deferred | - | - |
| `MFR-009` | Under-Reimbursement Gaming | A1 | medium | 0.7 | LIVE | yes | yes |
| `HP-001` | Network Leakage | A6 | low | 0.5 | deferred | - | - |
| `HP-002` | Formulary Non-Compliance | A6 | medium | 0.7 | deferred | - | - |
| `HP-003` | Therapeutic Duplication | A3 | medium | 0.7 | deferred | - | - |
| `HP-004` | Drug-Disease Contraindication | A3 | critical | 0.9 | deferred | - | - |
| `HP-005` | Prescriber Outlier | A3 | medium | 0.7 | LIVE | yes | yes |
| `HP-006` | Pharmacy Audit Trigger | A2 | critical | 0.9 | deferred | - | - |
| `HP-007` | Controlled Substance Monitoring | A5 | critical | 0.9 | deferred | - | - |
| `HP-008` | High-Cost Claimant | A3 | low | 0.5 | LIVE | yes | yes |
| `HP-009` | Inappropriate Quantity | A3 | medium | 0.7 | deferred | - | - |
| `HP-010` | Refill Pattern Anomaly | A3 | low | 0.5 | LIVE | - | yes |
| `TPA-001` | Eligibility Mismatch | A4 | critical | 0.9 | deferred | - | - |
| `TPA-002` | COB Error | A2 | medium | 0.7 | deferred | - | - |
| `TPA-003` | Plan Design Violation | A2 | critical | 0.9 | deferred | - | - |
| `TPA-004` | Provider Credential Issue | A4 | critical | 0.9 | deferred | - | - |
| `340B-001` | Duplicate Discount | A6 | critical | 0.9 | deferred | - | - |
| `340B-002` | Contract Pharmacy Non-Compliance | A6 | critical | 0.9 | deferred | - | - |
| `340B-003` | Covered Entity Verification | A6 | critical | 0.9 | deferred | - | - |
| `340B-004` | Split Billing Accuracy | A6 | medium | 0.7 | deferred | - | - |
| `340B-005` | Diversion | A6 | critical | 0.9 | deferred | - | - |
| `WC-001` | State Formulary Non-Compliance | A6 | medium | 0.7 | deferred | - | - |
| `WC-002` | Exceeds State Fee Schedule | A6 | critical | 0.9 | deferred | - | - |
| `WC-003` | Treatment Duration Exceeded | A6 | medium | 0.7 | deferred | - | - |
| `WC-004` | Opioid Guidelines | A5 | critical | 0.9 | deferred | - | - |
| `TH-001` | Telehealth Prescriber Volume | A3 | medium | 0.7 | deferred | - | - |
| `TH-002` | Telehealth Geographic Dispersion | A2 | medium | 0.7 | LIVE | - | yes |
| `TH-003` | Telehealth + High-Cost Drug | A3 | medium | 0.7 | deferred | - | - |
| `TH-004` | Telehealth + Controlled Substance | A5 | critical | 0.9 | deferred | - | - |
| `TH-005` | Telehealth Prescriber-Pharmacy Affinity | A2 | high | 0.5 | LIVE | - | yes |
| `REJECT-75-70` | Reject-75->70 Fast Rebill | A2 | high | 0.8 | LIVE | - | yes |

## Rule details

### ALL-001 — Duplicate Claim  (**LIVE**)

Same member, same NDC, same DOS, different auth number

- **Family:** A6 (accumulator)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** `patient_unique_hash`, `ndc`, `date_of_service`, `auth_no_hash`, `transaction_code`, `transaction_status`
- **Live fire (2.6M run):** 2,477 (0.09%)
- **Default parameters:** `{"pattern": "duplicate_claim", "threshold": 1.0}`

### ALL-002 — Phantom Pharmacy  (**LIVE**)

NPI not in NCPDP database or OIG excluded

- **Family:** A4 (eligibility)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Default parameters:** `{"pattern": "phantom_pharmacy"}`

### ALL-003 — Phantom Prescriber  (**LIVE**)

NPI invalid, DEA inactive, or OIG excluded

- **Family:** A4 (eligibility)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Default parameters:** `{"pattern": "phantom_prescriber"}`

### ALL-004 — Days Supply Manipulation  (**DEFERRED**)

Quantity and days supply inconsistent with NDC packaging/dosing

- **Family:** A2 (billing_pattern)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires NDC packaging/dosing reference data to compute days_supply_deviation_pct
- **Default parameters:** `{"field": "days_supply_deviation_pct", "operator": "gt", "threshold": 0.2}`

### ALL-005 — Early Refill  (**LIVE**)

Fill date before configured percent of previous days supply

- **Family:** A2 (billing_pattern)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** False  |  **Requires history:** True
- **Required columns:** `patient_unique_hash`, `ndc`, `date_of_service`, `day_supply`
- **Default parameters:** `{"field": "refill_pct", "operator": "lt", "threshold": 0.75}`

### ALL-006 — Weekend/Holiday Volume Spike  (**LIVE**)

Pharmacy claims volume on weekend/holiday exceeds weekday average

- **Family:** A2 (billing_pattern)
- **Severity:** low  |  **Confidence:** 0.5
- **Requires baseline:** True  |  **Requires history:** True
- **Required columns:** `pharmacy_npi`, `date_of_service`
- **Live fire (2.6M run):** 31 (0.00%)
- **Default parameters:** `{"field": "weekend_volume_vs_weekday_ratio", "operator": "gt", "threshold": 2.0}`

### ALL-007 — Geographic Anomaly  (**DEFERRED**)

Member filling at pharmacy more than 100 miles from home address

- **Family:** A2 (billing_pattern)
- **Severity:** low  |  **Confidence:** 0.5
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires member home address -- only zip3 available in CSV; full geo-distance cannot be computed
- **Default parameters:** `{"field": "geo_distance_miles", "operator": "gt", "threshold": 100}`

### ALL-008 — Suspicious Network Cluster  (**DEFERRED**)

Community of entities with >80% self-referral rate and geographic spread >200 miles

- **Family:** A2 (billing_pattern)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires graph/network analysis infrastructure -- not computable from a single CSV batch
- **Default parameters:** `{"self_referral_threshold": 0.8, "geo_spread_miles": 200}`

### ALL-009 — Auto-Hold on Critical Investigation  (**DEFERRED**)

When investigation reaches CRITICAL severity, automatically hold future payments

- **Family:** A2 (billing_pattern)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Operational auto-hold requires live investigation state -- not applicable in CSV batch detection
- **Default parameters:** `{"pattern": "critical_investigation_auto_hold", "auto_hold_enabled": true}`

### ALL-010 — Predictive Watchlist Trigger  (**DEFERRED**)

Pharmacy 30-day fraud probability exceeds threshold

- **Family:** A2 (billing_pattern)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires trained predictive ML model with 30-day rolling pharmacy scores -- not available from CSV alone
- **Default parameters:** `{"field": "fraud_probability_30d", "operator": "gt", "threshold": 0.7, "confidence_high": 0.9, "confidence_medium": 0.7}`

### MFR-001 — NQ Inflation  (**LIVE**)

(DV+NQ) exceeds WAC per unit x quantity

- **Family:** A1 (pricing_integrity)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** `extended_wac`, `ingredient_cost_paid`, `dispensing_fee_paid`, `quantity_dispensed`
- **Live fire (2.6M run):** 403,377 (15.45%)
- **Default parameters:** `{"field": "nq_to_wac_ratio", "operator": "gt", "threshold": 1.1, "confidence_high": 1.5, "confidence_medium": 1.2, "confidence_low": 1.1}`

### MFR-002 — Bill-Reverse-Rebill  (**LIVE**)

Same pharmacy, NDC, member -- reversal then rebill with higher NQ within 14 days

- **Family:** A2 (billing_pattern)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** True
- **Required columns:** `patient_unique_hash`, `pharmacy_npi`, `ndc`, `transaction_code`, `reversed_check`, `date_added_timestamp`, `ingredient_cost_paid`
- **Default parameters:** `{"pattern": "bill_reverse_rebill", "lookback_days": 14}`

### MFR-003 — Contracted Rate Deviation  (**LIVE**)

Pharmacy rate deviates from their own historical baseline

- **Family:** A1 (pricing_integrity)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** True  |  **Requires history:** True
- **Required columns:** `pharmacy_npi`, `ndc`, `ingredient_cost_paid`, `extended_wac`, `date_of_service`
- **Default parameters:** `{"field": "contracted_rate_deviation_pct", "operator": "gt", "threshold": 0.15, "baseline_days": 90}`

### MFR-004 — Volume Spike  (**LIVE**)

Pharmacy submits more claims for specific NDC vs rolling average

- **Family:** A3 (utilization)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** True  |  **Requires history:** True
- **Required columns:** `pharmacy_npi`, `ndc`, `date_of_service`
- **Live fire (2.6M run):** 109 (0.00%)
- **Default parameters:** `{"field": "volume_vs_avg_ratio", "operator": "gt", "threshold": 2.0, "rolling_days": 30}`

### MFR-005 — eVoucher/Coupon Abuse  (**DEFERRED**)

Same voucher code used for multiple patients or exceeded max uses

- **Family:** A2 (billing_pattern)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires voucher/coupon code data absent from standard pharmacy claim CSV
- **Default parameters:** `{"pattern": "voucher_abuse"}`

### MFR-006 — Phantom Patient  (**DEFERRED**)

Claims for members with no matching enrollment record

- **Family:** A4 (eligibility)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires enrollment records from member management system -- not present in CSV
- **Default parameters:** `{"pattern": "phantom_patient"}`

### MFR-007 — Accumulator/Maximizer Detection  (**DEFERRED**)

Copay assistance not counting toward member deductible/OOP

- **Family:** A6 (accumulator)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires copay-assistance program data and deductible/OOP tracking -- not present in CSV
- **Default parameters:** `{"pattern": "accumulator_maximizer", "confidence_high": 0.97, "confidence_medium": 0.8}`

### MFR-008 — Statement Credit Abuse  (**DEFERRED**)

Statement account pharmacy submitting claims that should be statement-only

- **Family:** A2 (billing_pattern)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Needs statement-only-pharmacy reference data (which pharmacies are contractually statement-only); a populated statement_account is normal, not fraud. No such reference feed in the CSV.
- **Default parameters:** `{"pattern": "statement_credit_abuse"}`

### MFR-009 — Under-Reimbursement Gaming  (**LIVE**)

Pharmacy consistently submitting U&C at minimum to maximize POS adjustment

- **Family:** A1 (pricing_integrity)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** True  |  **Requires history:** True
- **Required columns:** `pharmacy_npi`, `u_c`, `pos_adjustment`
- **Default parameters:** `{"pattern": "uc_minimum_gaming"}`

### HP-001 — Network Leakage  (**DEFERRED**)

Claims filled at out-of-network pharmacies when in-network available within 10 miles

- **Family:** A6 (accumulator)
- **Severity:** low  |  **Confidence:** 0.5
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires in-network pharmacy geo-coverage map -- external data feed not present in CSV
- **Default parameters:** `{"pattern": "network_leakage", "in_network_radius_miles": 10}`

### HP-002 — Formulary Non-Compliance  (**DEFERRED**)

Non-formulary drug dispensed without prior authorization

- **Family:** A6 (accumulator)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires formulary list and PA approval status -- external data feeds not present in CSV
- **Default parameters:** `{"pattern": "formulary_non_compliance"}`

### HP-003 — Therapeutic Duplication  (**DEFERRED**)

Member receiving two drugs from same therapeutic class simultaneously

- **Family:** A3 (utilization)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires therapeutic class reference data -- drug classification not present in CSV
- **Default parameters:** `{"pattern": "therapeutic_duplication"}`

### HP-004 — Drug-Disease Contraindication  (**DEFERRED**)

Drug inappropriate for member diagnosed conditions

- **Family:** A3 (utilization)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires member diagnosis codes -- PHI data not present in CSV
- **Default parameters:** `{"pattern": "drug_disease_contraindication"}`

### HP-005 — Prescriber Outlier  (**LIVE**)

Prescriber volume for specific drug exceeds peer group by 3 standard deviations

- **Family:** A3 (utilization)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** True  |  **Requires history:** True
- **Required columns:** `prescriber_npi`, `ndc`, `date_of_service`
- **Live fire (2.6M run):** 290 (0.01%)
- **Default parameters:** `{"field": "prescriber_volume_std_devs", "operator": "gt", "threshold": 3.0}`

### HP-006 — Pharmacy Audit Trigger  (**DEFERRED**)

Pharmacy flagged on multiple rules exceeding threshold in period

- **Family:** A2 (billing_pattern)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Depends on prior rule-flag counts from other rules -- not independently computable from raw CSV
- **Default parameters:** `{"field": "flag_count_30d", "operator": "gt", "threshold": 5, "period_days": 30}`

### HP-007 — Controlled Substance Monitoring  (**DEFERRED**)

Opioid MME exceeds CDC guideline, multiple prescribers/pharmacies

- **Family:** A5 (controlled_substance)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires opioid MME conversion factors and drug schedule classification -- not present in CSV
- **Default parameters:** `{"mme_threshold": 90, "max_prescribers": 3, "max_pharmacies": 3}`

### HP-008 — High-Cost Claimant  (**LIVE**)

Member claims exceed configured threshold in period (top 1%)

- **Family:** A3 (utilization)
- **Severity:** low  |  **Confidence:** 0.5
- **Requires baseline:** True  |  **Requires history:** True
- **Required columns:** `patient_unique_hash`, `total_paid_amt`
- **Default parameters:** `{"field": "cost_percentile", "operator": "gte", "threshold": 0.99, "percentile_threshold": 0.99}`

### HP-009 — Inappropriate Quantity  (**DEFERRED**)

Quantity exceeds FDA max recommended or plan limits

- **Family:** A3 (utilization)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires FDA max quantity per NDC reference data -- not present in CSV
- **Default parameters:** `{"pattern": "quantity_exceeds_limit"}`

### HP-010 — Refill Pattern Anomaly  (**LIVE**)

Member consistently fills exactly on day X (possible auto-refill waste)

- **Family:** A3 (utilization)
- **Severity:** low  |  **Confidence:** 0.5
- **Requires baseline:** False  |  **Requires history:** True
- **Required columns:** `patient_unique_hash`, `ndc`, `date_of_service`
- **Default parameters:** `{"pattern": "refill_pattern_anomaly"}`

### TPA-001 — Eligibility Mismatch  (**DEFERRED**)

Claim paid for member not eligible on DOS

- **Family:** A4 (eligibility)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires real-time eligibility check against member enrollment system -- not computable from CSV
- **Default parameters:** `{"pattern": "eligibility_mismatch"}`

### TPA-002 — COB Error  (**DEFERRED**)

Primary/secondary payer assignment incorrect

- **Family:** A2 (billing_pattern)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires coordination of benefits payer order from plan design -- not present in CSV
- **Default parameters:** `{"pattern": "cob_error"}`

### TPA-003 — Plan Design Violation  (**DEFERRED**)

Benefit applied does not match plan configuration

- **Family:** A2 (billing_pattern)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires plan design configuration data -- not present in CSV
- **Default parameters:** `{"pattern": "plan_design_violation"}`

### TPA-004 — Provider Credential Issue  (**DEFERRED**)

Pharmacy or prescriber credentials expired or suspended

- **Family:** A4 (eligibility)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires provider credential status from credentialing system -- external data feed not in CSV
- **Default parameters:** `{"pattern": "credential_issue"}`

### 340B-001 — Duplicate Discount  (**DEFERRED**)

340B discounted drug also subject to manufacturer rebate for same claim

- **Family:** A6 (accumulator)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires HRSA 340B entity/drug eligibility registry -- external data feed not in CSV
- **Default parameters:** `{"pattern": "340b_duplicate_discount"}`

### 340B-002 — Contract Pharmacy Non-Compliance  (**DEFERRED**)

Claim from pharmacy not registered as 340B contract pharmacy

- **Family:** A6 (accumulator)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires HRSA 340B contract pharmacy registry -- external data feed not in CSV
- **Default parameters:** `{"pattern": "340b_contract_pharmacy"}`

### 340B-003 — Covered Entity Verification  (**DEFERRED**)

Entity claiming 340B pricing not on HRSA database

- **Family:** A6 (accumulator)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires HRSA 340B covered entity database -- external data feed not in CSV
- **Default parameters:** `{"pattern": "340b_covered_entity"}`

### 340B-004 — Split Billing Accuracy  (**DEFERRED**)

340B vs non-340B classification does not match patient eligibility

- **Family:** A6 (accumulator)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires 340B patient eligibility data from covered entity -- external data not in CSV
- **Default parameters:** `{"pattern": "340b_split_billing"}`

### 340B-005 — Diversion  (**DEFERRED**)

Drug dispensed to non-eligible patient at 340B pricing

- **Family:** A6 (accumulator)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires 340B patient eligibility list from covered entity -- external data not in CSV
- **Default parameters:** `{"pattern": "340b_diversion"}`

### WC-001 — State Formulary Non-Compliance  (**DEFERRED**)

Drug not on state workers compensation formulary

- **Family:** A6 (accumulator)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires state workers compensation formulary data -- external data feed not in CSV
- **Default parameters:** `{"pattern": "wc_formulary_non_compliance"}`

### WC-002 — Exceeds State Fee Schedule  (**DEFERRED**)

Reimbursement exceeds state WC fee schedule

- **Family:** A6 (accumulator)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires state workers compensation fee schedule data -- external data feed not in CSV
- **Default parameters:** `{"field": "fee_schedule_ratio", "operator": "gt", "threshold": 1.0}`

### WC-003 — Treatment Duration Exceeded  (**DEFERRED**)

Fills exceed expected treatment duration for injury type

- **Family:** A6 (accumulator)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires injury type and expected treatment duration from workers comp claim -- external data not in CSV
- **Default parameters:** `{"field": "treatment_duration_ratio", "operator": "gt", "threshold": 1.5}`

### WC-004 — Opioid Guidelines  (**DEFERRED**)

Opioid prescribing exceeds state WC opioid guidelines

- **Family:** A5 (controlled_substance)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires state WC opioid guideline thresholds and drug schedule classification -- external data not in CSV
- **Default parameters:** `{"pattern": "wc_opioid_guideline"}`

### TH-001 — Telehealth Prescriber Volume  (**DEFERRED**)

Telehealth prescriber writing more than 50 scripts/day

- **Family:** A3 (utilization)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires telehealth encounter flag -- not present in standard pharmacy claim CSV
- **Default parameters:** `{"field": "scripts_per_day", "operator": "gt", "threshold": 50}`

### TH-002 — Telehealth Geographic Dispersion  (**LIVE**)

Telehealth prescriber patients spread across more than 10 states

- **Family:** A2 (billing_pattern)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** False  |  **Requires history:** True
- **Required columns:** `prescriber_npi`, `patient_state`
- **Live fire (2.6M run):** 28 (0.00%)
- **Default parameters:** `{"field": "patient_state_count", "operator": "gt", "threshold": 10, "min_claims": 20}`

### TH-003 — Telehealth + High-Cost Drug  (**DEFERRED**)

Telehealth prescriber writing high-cost specialty or GLP-1 drugs at >40% of volume

- **Family:** A3 (utilization)
- **Severity:** medium  |  **Confidence:** 0.7
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires drug-class classification list (specialty/GLP-1) -- external reference data not in CSV
- **Default parameters:** `{"field": "high_cost_drug_rate", "operator": "gt", "threshold": 0.4}`

### TH-004 — Telehealth + Controlled Substance  (**DEFERRED**)

Telehealth prescriber writing Schedule II-V controlled substances

- **Family:** A5 (controlled_substance)
- **Severity:** critical  |  **Confidence:** 0.9
- **Requires baseline:** False  |  **Requires history:** False
- **Required columns:** _(none / sourced from reference feeds)_
- **Deferred reason:** Requires DEA drug schedule classification and telehealth encounter flag -- external data not in CSV
- **Default parameters:** `{"pattern": "telehealth_controlled_substance"}`

### TH-005 — Telehealth Prescriber-Pharmacy Affinity  (**LIVE**)

More than 50% of telehealth prescriber scripts filled at single pharmacy

- **Family:** A2 (billing_pattern)
- **Severity:** high  |  **Confidence:** 0.5
- **Requires baseline:** False  |  **Requires history:** True
- **Required columns:** `prescriber_npi`, `pharmacy_npi`
- **Live fire (2.6M run):** 15,881 (0.61%)
- **Default parameters:** `{"field": "top_pharmacy_share", "operator": "gt", "threshold": 0.5, "min_claims": 20}`

### REJECT-75-70 — Reject-75->70 Fast Rebill  (**LIVE**)

PA-required reject (75) followed by not-covered reject (70) for same Rx within 24h -- group key rx_number_hash (locked decision #1)

- **Family:** A2 (billing_pattern)
- **Severity:** high  |  **Confidence:** 0.8
- **Requires baseline:** False  |  **Requires history:** True
- **Required columns:** `rx_number_hash`, `reject_code`, `date_added_timestamp`
- **Default parameters:** `{"bucket_le12h_enabled": true, "bucket_12_24h_enabled": true}`
