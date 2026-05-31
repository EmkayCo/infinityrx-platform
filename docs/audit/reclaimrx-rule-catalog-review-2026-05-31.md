# ReclaimRx Detection Rule Catalog — Review & Selection

**Date:** 2026-05-31
**Purpose:** Pick which rules to run on the 2.6M-row manufacturer-copay claims file (`allDataMinusPHI 1.csv`) now vs later. Mark the **PICK** column: `NOW` / `LATER` / `DROP`.
**Context:** the uploaded data is a **manufacturer copay-assistance** dataset (client_id "32" = 81% of rows, BIN 025706 = 99%). The program pays the ingredient cost, so several absolute-threshold rules fire on most claims (noise). The first full run flagged **~793K of 2.6M claims (~30%)** before being killed — that is the calibration problem this doc exists to fix.

## How to read this

| Column | Meaning |
|---|---|
| **Data** | ✅ CSV has the inputs · ⚠ partial · ❌ absent (needs an external feed) |
| **Fire risk** | On THIS copay dataset: 🟥 over-fires (noise) · 🟧 needs calibration · 🟩 narrow/precise · ⬜ can't fire (no data) |
| **Calibration** | What to change so it produces *actionable* signal (not 30% of claims) |

## Data economics (why absolute thresholds over-fire here)

- `nq = ingredient_cost_paid`, `extended_wac` = WAC×qty (total). In a copay program the program reimburses ingredient ≈ or above WAC, so **`(dv+nq)/extended_wac > 1.10` is normal, not fraud** → MFR-001 fires on most rows.
- Statistical rules (volume/cost/std-dev) computed a baseline per pharmacy×NDC etc. → **647K baseline scope-keys**; absolute "ratio > 2.0 / >3 std-dev / ≥99th pct" still flag a long tail across 2.6M.
- **Fix pattern for all calibratable rules:** flag only the **top 0.1–1% outliers** (percentile / z-score with a high floor + minimum sample size), not an absolute ratio. Target total flag rate **< ~1%** of claims.

---

## A. High-precision, CSV-native — fire narrowly, unambiguous (recommended NOW)

| Code | Name | Detects | Logic | Data | Fire risk | Calibration | PICK |
|---|---|---|---|---|---|---|---|
| ALL-001 | Duplicate Claim | same member+NDC+DOS, ≠ auth, both Paid | grouping, ≥2 distinct auth | ✅ | 🟩 | exclude Reversed/Duplicate-status lifecycle rows (done) | ___ |
| MFR-002 | Bill-Reverse-Rebill | B1→B2→B1 ≤14d, higher rebill NQ | grouping, sequence | ✅ | 🟩 | already narrow; keep 14d window | ___ |
| **NEW** Reject-resubmit | reject-code cycling per pharmacy | `reject_code`/`reject_message` sequences | grouping | ✅ | 🟩 | new rule; 472K rejected rows present | ___ |

## B. CSV-native but MUST be recalibrated (percentile/outlier) before NOW

| Code | Name | Detects | Current logic (over-fires) | Data | Fire risk | Calibration | PICK |
|---|---|---|---|---|---|---|---|
| MFR-001 | NQ Inflation | (DV+NQ) > WAC×qty | `nq_to_wac_ratio > 1.10` | ✅ | 🟥 | per-NDC: flag only top ~0.5% of nq_to_wac, or `> p99` of that NDC's distribution; absolute 1.10 is meaningless on copay data | ___ |
| MFR-003 | Contracted Rate Deviation | pharmacy rate vs own history | `deviation_pct > 0.15` | ✅ | 🟧 | own-prior-period z-score, min 30 prior fills, flag \|z\|>3 + dollar floor | ___ |
| MFR-004 | Volume Spike | pharmacy-NDC volume vs peers | `vol_vs_avg_ratio > 2.0` | ✅ | 🟧 | peer z-score, min peer count, top ~0.5% only | ___ |
| HP-005 | Prescriber Outlier | prescriber volume vs peers | `std_devs > 3.0` | ✅ | 🟧 | already std-dev; add min sample (≥20 peers) + min absolute volume floor | ___ |
| HP-008 | High-Cost Claimant | member cost top 1% | `cost_percentile ≥ 0.99` | ✅ | 🟧 | true percentile over population + dollar floor; cap per-member | ___ |
| ALL-006 | Weekend/Holiday Spike | pharmacy weekend vs weekday | `ratio > 2.0` | ✅ | 🟧 | min weekday volume floor; flag top outliers only | ___ |
| ALL-005 | Early Refill | refill before 75% days-supply | `refill_pct < 0.75` | ✅ (per-member history) | 🟧 | requires prior-fill join; flag clear cases (e.g. <50%) + repeat offenders | ___ |
| HP-010 | Refill Pattern Anomaly | fills exactly on day X | pattern | ✅ | 🟧 | needs ≥N fills per member; low priority | ___ |
| MFR-009 | U&C Min Gaming | U&C at min to max POS adj | pattern (no baseline yet) | ✅ | 🟧 | needs per-pharmacy U&C-min-rate baseline (not built) | ___ |
| TH-002 | Geographic Dispersion | prescriber across >10 states | `state_count > 10` + min_claims | ✅ | 🟧 | not telehealth-specific here; keep min_claims floor (20) | ___ |
| TH-005 | Prescriber→Pharmacy Affinity | >50% scripts at one pharmacy | `share > 0.5` + min_claims | ✅ | 🟧 | keep min_claims floor; raise to ≥0.7 share | ___ |
| ALL-004 | Days Supply Manipulation | qty vs days-supply inconsistent | `deviation_pct > 0.20` | ⚠ (needs NDC dosing norms) | 🟧 | needs drug-DB dosing reference; defer unless heuristic | ___ |

## C. Needs external data the CSV lacks — cannot run until a feed is added (LATER/DROP)

| Code | Name | Missing data | PICK |
|---|---|---|---|
| ALL-002 | Phantom Pharmacy | NCPDP/OIG-exclusion registry | ___ |
| ALL-003 | Phantom Prescriber | NPI/DEA/OIG validation | ___ |
| ALL-007 | Geographic Anomaly | member home address (only zip3 in CSV) | ___ |
| ALL-008 | Suspicious Network Cluster | graph build (separate engine) | ___ |
| ALL-009 | Auto-Hold on Critical | operational trigger, not a detection | ___ |
| ALL-010 | Predictive Watchlist | trained 30-day fraud-probability model | ___ |
| MFR-005 | eVoucher/Coupon Abuse | voucher codes (not in CSV) | ___ |
| MFR-006 | Phantom Patient | member enrollment records | ___ |
| MFR-007 | Accumulator/Maximizer | copay-assistance + deductible accumulation data | ___ |
| MFR-008 | Statement Credit Abuse | which pharmacies are statement-only (reference) | ___ |
| HP-001 | Network Leakage | in-network pharmacy geo | ___ |
| HP-002 | Formulary Non-Compliance | plan formulary + PA status | ___ |
| HP-003 | Therapeutic Duplication | therapeutic-class reference (partial via GPI) | ___ |
| HP-004 | Drug-Disease Contraindication | member diagnosis | ___ |
| HP-006 | Pharmacy Audit Trigger | depends on other rules' 30-day flag counts | ___ |
| HP-007 | Controlled Substance / MME | opioid MME conversion + schedule | ___ |
| HP-009 | Inappropriate Quantity | FDA max-dose reference | ___ |
| TPA-001..004 | Eligibility / COB / Plan-Design / Credential | member eligibility, COB, plan config, credential feeds | ___ |
| 340B-001..005 | 340B suite | HRSA/340B registry, contract-pharmacy list | ___ |
| WC-001..004 | Workers-Comp suite | state formulary, fee schedule, injury/treatment data | ___ |
| TH-001 | Telehealth Prescriber Volume | telehealth flag (not in CSV) | ___ |
| TH-003 | Telehealth + High-Cost Drug | telehealth flag + high-cost drug list | ___ |
| TH-004 | Telehealth + Controlled Substance | telehealth flag + CS schedule | ___ |

---

## Engineering rework (applies to whatever you PICK = NOW)

Independent of rule selection, the detection engine needs:
1. **Batched anomaly writes** — `execute_values` inserts (no savepoint-per-anomaly), drop per-fire eval-log spam (aggregate counts). The 793K-fire run was slow largely from this.
2. **Single-scan, multi-rule** — one streaming pass over `csv_upload_rows` evaluating all per-row rules together (today each rule does its own full 2.6M scan).
3. **Flag-rate guardrail** — the run aborts/warns if total flag rate exceeds a configurable cap (e.g. >5%) so a mis-calibrated rule can never silently flag 30% again.
4. **Percentile/z-score helpers** — shared calibration primitives so "top 0.5% / |z|>3 + min-sample + dollar-floor" is one reusable pattern.

## My recommendation for the NOW set
ALL-001, MFR-002, the new reject-resubmit rule (all 🟩 precise), **plus** MFR-001 and HP-008 **recalibrated to percentile** (the two highest-value FWA signals on copay data, once they flag only the top outliers). Everything else LATER. Target flag rate < 1%.

**Mark your picks in the PICK column and I'll spec the recalibration + perf rework around exactly that set.**
