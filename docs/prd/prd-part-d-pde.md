# PRD — Module 24: Part D / PDE Compliance (FINAL)

**Module:** Part D / PDE Compliance
**Folder:** `modules/part-d/`
**Phase:** 5, Future (Wave 5+)
**Dependencies:** Core Platform (1), Claims Adjudication Engine (8), Member Management (5), Plan Design (6), EDI Compliance (13 — already built)

---

## 1. Purpose

Part D / PDE Compliance enables InfinityRx to serve Medicare Part D plan sponsors by generating, validating, and submitting Prescription Drug Event (PDE) records to CMS. PDEs are the Medicare equivalent of encounter data — every dispensing event must be reported to CMS for reconciliation, risk adjustment, and coverage gap discount program processing. This module also tracks IRA negotiated drug prices.

---

## 2. PDE Generation

After each claim is adjudicated for a Part D member, generate PDE record containing: adjudication date, ingredient cost, dispensing fee, patient pay amounts, coverage gap discount amounts, LIS (Low Income Subsidy) cost sharing, TrOOP (True Out of Pocket) accumulation, LICS amounts, CPP (Close Proximity Pharmacy) indicators, catastrophic coverage amounts, and all required CMS fields.

**Timing:** PDEs submitted within 30 days of date of service or date claim received (whichever is later). Configurable submission schedule (daily recommended).

---

## 3. PDE Validation

CMS-defined validation rules applied before submission: field-level (format, range, required), cross-field (coverage phase vs amounts), cross-PDE (duplicate detection, restacking requirements), member eligibility cross-reference (MBD — Medicare Beneficiary Database).

**Validation dashboard:** count of PDEs pending, validated, submitted, accepted, rejected. Drill-down into rejections by error code with resolution guidance.

---

## 4. Coverage Gap Discount Program (CGDP) / IRA Changes

Track manufacturer discounts applied in the coverage gap phase. For 2025+, the IRA restructured coverage gap and catastrophic phases. Module must track the evolving manufacturer discount percentages per phase per year as CMS updates them.

---

## 5. IRA Drug Price Negotiation Tracking

- Track drugs with CMS-negotiated Maximum Fair Prices (MFP) — 10 drugs effective Jan 2026, 15 more for 2027, expanding annually
- Flag drugs with negotiated prices in Drug Database
- At adjudication, apply MFP for Part D members instead of standard pricing
- Track savings from negotiated prices (difference between prior price and MFP)
- Dashboard: all negotiated drugs, effective dates, savings per drug per period
- Alert when new drugs are selected for future negotiation rounds (pipeline tracking)

---

## 6. Benefit Phase Tracking (Part D Specific)

Standard Part D phases: deductible → initial coverage → coverage gap → catastrophic. Track each member's TrOOP accumulation in real-time. Phase transitions trigger different cost-sharing rules. The plan configuration (Module 6) defines amounts per phase per year.

**Real-time accumulator:** Redis-cached TrOOP per member, updated on every claim. Sub-millisecond lookup during adjudication.

---

## 7. LIS and SPAP Integration

- Low Income Subsidy levels (1-4 + deemed) from CMS eligibility files
- State Pharmaceutical Assistance Programs — coordinate with Part D benefits
- Auto-apply correct cost sharing based on LIS level
- Track LIS changes mid-year (eligibility file updates)

---

## 8. DIR (Direct and Indirect Remuneration) Reporting

CMS requires annual DIR reporting: pharmacy performance-based adjustments, rebates, fees, price concessions. Generate DIR report from claims, rebate, and fee data. Submit via HPMS (Health Plan Management System) before CMS deadline.

Post-IRA: DIR at point-of-sale reform (pharmacy DIR fees must be reflected in POS pricing starting 2024+). Track POS DIR amounts per claim.

---

## 9. CMS Submissions and Reconciliation

- PDE submission via CMS-specified batch process
- Track CMS acceptance/rejection at individual PDE level
- Resubmit corrected PDEs for rejected records
- Annual reconciliation with CMS: compare InfinityRx claims data against CMS records, resolve discrepancies
- Prospective payment reconciliation: track CMS prospective payments vs actual costs

---

## 10. Audit Readiness (Part D Specific)

CMS audits Part D plans regularly. Maintain complete audit trail:
- Every PDE with source claim linkage
- Coverage determination records (PA approvals/denials)
- Formulary administration records (tier changes, PA criteria)
- Grievance and appeal records
- Beneficiary cost-sharing records with LIS documentation

---

## 11. Data Models

```
pde_records (with all CMS fields, submission_status, cms_response), pde_submissions (batch tracking), pde_validation_errors, troop_accumulators (Redis-backed), lis_eligibility, spap_records, dir_reports, dir_pos_amounts, ira_negotiated_prices (with ndc, mfp, effective_date, savings_tracking), cms_reconciliation_records, coverage_gap_discounts
```

---

## 12. API, Events, Tests

**API:** generate PDEs for period, validate PDEs, submit batch, PDE status, TrOOP lookup (real-time for adjudication), LIS level lookup, DIR report generation, IRA negotiated price lookup, reconciliation status.

**Events:** `pde.generated`, `pde.validated`, `pde.submitted`, `pde.accepted`, `pde.rejected`, `troop.phase_transition`, `ira.negotiated_price_applied`

**Subscribes to:** `claim.adjudicated` (generate PDE), `claim.reversed` (generate adjustment PDE), `member.lis_level_changed`, `drug.ira_price_negotiated`

**Tests:** PDE generated with correct fields from claim data, validation catches all CMS error types, TrOOP accumulation transitions benefit phases correctly, LIS cost sharing applied correctly for each level, coverage gap discount calculated correctly, IRA MFP applied for negotiated drugs, DIR POS amounts tracked, batch submission/acceptance round-trip

**Edge cases:** member LIS level changes mid-month, claim spanning benefit year, retroactive eligibility change requiring PDE restacking, PDE for compound claim, member dual-eligible (Medicare + Medicaid), catastrophic phase with manufacturer discount, IRA negotiated price for drug also subject to coverage gap discount

---

## 13. Session Decomposition

1. **PDE engine:** generation from claims, validation, batch submission, CMS response processing, resubmission
2. **Benefit tracking:** TrOOP accumulators (Redis), phase transitions, LIS/SPAP integration
3. **IRA & DIR:** negotiated price tracking and application, DIR reporting, POS DIR tracking, coverage gap discounts
4. **Compliance:** CMS reconciliation, audit readiness, reporting dashboards
