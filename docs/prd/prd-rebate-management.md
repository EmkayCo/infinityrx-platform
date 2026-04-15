# PRD — Module 22: Rebate Management (FINAL)

**Module:** Rebate Management
**Folder:** `modules/rebate-management/`
**Phase:** 5, Wave 1 (parallel with Plan Design and Program Config)
**Dependencies:** Core Platform (1), Drug Database (2), Plan Design (6), Billing (11 — already built)

---

## 1. Purpose

Rebate Management tracks, calculates, invoices, and reconciles manufacturer rebates across all programs. With CAA 2026 mandating 100% rebate pass-through and bona fide service fee (BFSF) only compensation for Part D, this module must provide complete transparency, auditability, and compliance from day one. It also provides the manufacturer GTN waterfall dashboard and performance benchmarking.

---

## 2. CAA 2026 Compliance (Effective Jan 1, 2028)

### 100% Rebate Pass-Through Ledger
- Every rebate dollar received from manufacturers tracked at NDC-11 level
- Full pass-through to plan sponsor with quarterly remittance
- Rebate categories: commercial rebates, market share rebates, formulary access fees, admin fees, price protection, alternative discounts — ALL must pass through
- Audit trail: manufacturer pays X → InfinityRx receives X → plan sponsor receives X. Dollar-for-dollar reconciliation.

### Bona Fide Service Fee (BFSF) Documentation
- PBM compensation limited to flat dollar BFSF at fair market value
- BFSF must reflect actual services performed (not linked to drug price or volume)
- Documentation: services catalog, fair market value assessment, fee schedule per service
- Annual BFSF attestation per client

### Semiannual Transparency Reporting
- For large employers (100+ employees), produce reports containing:
  - Net drug spending by drug/class/tier
  - Gross vs net drug costs
  - Manufacturer rebates received and passed through (by category)
  - Spread pricing arrangements (should be zero in pass-through model)
  - Formulary placement rationale
  - Affiliated pharmacy utilization metrics
- Quarterly upon client request
- Automated report generation from claims and rebate data

### Annual Audit Rights
- Plan sponsors can audit rebate compliance with their own auditors
- System must provide: all rebate contract terms, all payments received, all pass-throughs made, all BFSF invoices, affiliate transaction detail
- One-click data export in standard format for external audit firms

---

## 3. Rebate Contract Management

- Contract lifecycle: draft → negotiation → active → amendment → renewal → termination
- Contract types: formulary access, market share, volume-based, admin fee, price protection, combination
- Terms: effective/termination dates, payment frequency (monthly/quarterly), minimum volume thresholds, tier requirements
- NDC-11 level terms: rebate amount or percentage per NDC, with effective dates
- Amendment tracking with effective dates and approval workflow
- Contract comparison: side-by-side comparison of proposed vs current terms

---

## 4. Rebate Calculation Engine

- Aggregate qualifying claims by contract terms per period
- Apply rebate formula (flat per unit, % of WAC, % of invoice price, tiered by volume)
- Net against chargebacks and returns
- Generate rebate invoice to manufacturer
- Track payment against invoice
- Reconcile: expected rebate vs received vs passed through to plan

All Decimal with ROUND_HALF_UP.

---

## 5. Guaranteed Spend Cap / Performance Guarantees

Support for contractual spend cap models (Rightway SureSpend style):
- Set guaranteed ceiling based on projected total pharmacy spend
- Real-time tracking of actual vs ceiling
- If actual exceeds ceiling, calculate and track refund owed
- If under, track savings retained by plan
- Alert when trending toward ceiling breach
- Dashboard showing performance against all active guarantees

---

## 6. Manufacturer GTN Waterfall Dashboard

Real-time gross-to-net waterfall per drug, per program:

```
WAC (List Price): $500.00
  - Wholesaler discount: -$10.00
  - Prompt pay discount: -$10.00
  - Rebates to PBMs/plans: -$150.00
  - Chargebacks (340B, Medicaid): -$50.00
  - Copay assistance spend: -$80.00
  - Copay misuse/leakage (ReclaimRx): -$15.00
  - Admin fees: -$5.00
  ─────────────────────────
  Net price realized: $180.00
  GTN ratio: 64%
```

Drill-down: click any line to see detail. Click "Copay misuse" for ReclaimRx findings. Click "Rebates" for contract detail. Click "Chargebacks" for 340B/Medicaid breakdowns.

---

## 7. Program Performance Benchmarking

Compare program metrics against industry benchmarks and historical data:

| Metric | Your Program | Industry Avg | Delta |
|--------|-------------|--------------|-------|
| Enrollment rate | 45% | 38% | +7% |
| First fill rate | 82% | 74% | +8% |
| PDC (6-month adherence) | 71% | 65% | +6% |
| Abandonment rate | 8% | 12% | -4% |
| Avg copay per patient/year | $2,100 | $2,800 | -$700 |
| GTN ratio | 58% | 62% | -4% |
| Copay misuse rate | 2.1% | 4.8% | -2.7% |

---

## 8. Copay Program Analytics & Optimization (Four-Pillar Engine)

1. **Program Design Analytics:** evaluate offer amounts, caps, eligibility rules against real-world data. Flag where design intent diverges from actual results.
2. **Fraud Control Analytics:** real-time prevention results from ReclaimRx + retrospective audit findings. Track recovery pipeline and amounts.
3. **Accumulator/Maximizer Impact:** quantify financial impact per program. Track % of patients on accumulator/maximizer plans. Model mitigation strategies.
4. **Executive Optimization Cadence:** scheduled review sessions with scenario modeling. What-if: "If we reduce annual max from $15K to $12K, what happens to script lift?"

---

## 9. Fiduciary Compliance Dashboard

For plan sponsors, real-time compliance view:
- Total rebates received vs passed through (must be 100%)
- Spread pricing transparency (should be zero)
- Affiliated pharmacy utilization
- Drug-level net cost analysis
- Audit readiness status
- BFSF documentation completeness
- CAA 2026 reporting status (filed/pending/overdue)

---

## 10. Data Models

```
rebate_contracts (with bfsf_documentation, terms JSONB), rebate_contract_ndcs (with per-NDC rates), rebate_periods, rebate_calculations (per period per contract), rebate_invoices, rebate_payments, rebate_passthrough_ledger (dollar-for-dollar tracking), spend_cap_guarantees, spend_cap_tracking, gtn_waterfall_snapshots, program_benchmarks, transparency_reports (semiannual/quarterly), fiduciary_compliance_status, copay_program_analytics
```

---

## 11. API, Events, Tests

**API:** CRUD contracts, calculate rebates for period, generate invoice, record payment, pass-through ledger, GTN waterfall, performance benchmarks, transparency report generation, fiduciary dashboard, spend cap status, copay analytics.

**Events:** `rebate.calculated`, `rebate.invoice_generated`, `rebate.payment_received`, `rebate.passthrough_completed`, `rebate.audit_requested`, `spend_cap.threshold_approaching`, `fiduciary.report_due`

**Subscribes to:** `claim.adjudicated` (aggregate for rebate calculation), `claim.reversed` (adjust calculations), `reclaimrx.fraud_detected` (update GTN waterfall leakage line)

**Tests:** rebate calculation at NDC-11 level matches contract terms, pass-through ledger balances to penny, BFSF invoice separates fees from rebates, transparency report contains all required fields, fiduciary dashboard shows 100% pass-through, spend cap alert fires at 90% threshold, GTN waterfall drill-down returns correct detail, benchmark comparison calculates correctly

**Edge cases:** rebate for reversed claim (reduce next period), contract amendment mid-period (pro-rate), manufacturer disputes rebate amount (dispute workflow), zero-rebate contract (BFSF only), multiple contracts for same NDC (priority resolution)

---

## 12. Session Decomposition

1. **Contract management:** lifecycle, NDC-11 terms, amendments, versioning, comparison
2. **Calculation engine:** claims aggregation, formula application, invoice generation, payment tracking, reconciliation
3. **Compliance:** CAA 2026 pass-through ledger, BFSF documentation, semiannual reporting, audit support, fiduciary dashboard
4. **Manufacturer analytics:** GTN waterfall, program benchmarking, copay four-pillar optimization, spend cap tracking
