# PRD — Module 6: Plan Design & Configuration (FINAL)

**Module:** Plan Design & Configuration
**Folder:** `modules/plan-design/`
**Phase:** 5, Wave 1 (parallel with Program Config and Rebate)
**Dependencies:** Core Platform (1), Drug Database (2), Member Management (5)

---

## 1. Purpose

Plan Design is the configuration backbone of the adjudication engine. Every claim is adjudicated against a plan — and a plan defines what's covered, how much the patient pays, what network applies, which formulary governs drug access, and what rules fire during processing. This module manages the entire plan hierarchy, benefit structures, formularies, network assignments, and pricing models for ALL client types: manufacturers, health plans, TPAs, 340B entities, and workers compensation programs.

---

## 2. Plan Hierarchy

Configurable depth per tenant. Standard hierarchy:

```
Organization (Carrier)
  └─ Group
       └─ Plan
            └─ SubGroup (optional)
```

Each level inherits from its parent unless overridden. A manufacturer copay program might use a flat structure (one org, one group, one plan). A health plan might have hundreds of groups with dozens of plans each. The hierarchy depth is tenant-configurable — never hardcoded.

**Key fields per level:**
- Organization: name, TIN, contact info, effective/termination dates
- Group: group_id, BIN/PCN assignment, billing entity reference, effective/termination dates
- Plan: benefit config, formulary assignment, network assignment, accumulator rules, program type, pricing model
- SubGroup: override any plan-level setting for a subset of members

---

## 3. Benefit Configuration

Per plan, configurable:

- **Copay structure:** flat dollar, percentage, tiered by drug type (generic/preferred/non-preferred/specialty), step-based (copay changes after N fills), or custom formula
- **Deductible:** annual amount, what counts toward it (all drugs, brand only, specialty only), family vs individual
- **Out-of-pocket maximum:** annual cap, what counts, family vs individual
- **Coinsurance:** percentage after deductible, configurable per tier
- **Benefit phases:** configurable — not limited to Part D phases. Can define custom phases (deductible → initial coverage → gap → catastrophic, or simpler structures for commercial plans)
- **Day supply rules:** 30/60/90 day supply limits per pharmacy type (retail vs mail order vs specialty)
- **Annual/lifetime maximums:** dollar or quantity limits per drug, per therapeutic class, or per plan

All monetary values stored as Decimal with ROUND_HALF_UP.

---

## 4. Pricing Models

The industry is moving from AWP-discount to cost-plus models. Every plan must specify its pricing model — configurable per plan AND per network tier within a plan:

| Model | Formula | Used By |
|-------|---------|---------|
| AWP Discount | AWP - X% + dispensing fee | Traditional PBM contracts |
| MAC | Maximum Allowable Cost (per drug list) | Generic pricing |
| Cost-Plus | Acquisition cost + % markup + dispensing fee | CVS CostVantage model |
| NADAC-Based | NADAC + markup + fee | OptumRx Cost Clarity |
| Net-Cost | Actual net drug cost after rebates + admin fee | Express Scripts ClearCareRx |
| Cost-Plus Specialty | Drug cost + patient management fee | Navitus Lumicera model |
| Direct Manufacturer | Manufacturer-set price (bypasses PBM spread) | LillyDirect, CivicaScript |
| Cash/Discount Card | Discounted cash price | GoodRx-style programs |

Each pricing model is a pluggable calculator. Adding a new model is a configuration + one calculator class.

**Cash-pay comparison:** at adjudication, if enabled, calculate both insurance price and cash/discount price, return the lower option. Configurable per plan.

---

## 5. Formulary Management

- Create unlimited formularies per tenant
- Drug tier assignment: assign NDCs or GPI ranges to tiers (configurable tier names and count)
- Therapeutic class management: group drugs by therapeutic class
- PA/step therapy/quantity limit flags per drug/tier
- Specialty drug designation
- Formulary versioning: every change creates new version, effective-dated, rollback capable
- **Biosimilar formulary tools:** reference product → biosimilar mapping, auto-substitution config, cost modeling for biosimilar-first strategy, state substitution law tracking
- **GLP-1 indication-based coverage:** same NDC, different coverage based on diagnosis (diabetes=covered, obesity=configurable, cardiovascular=configurable)
- **IRA negotiated drug tracking:** flag drugs with CMS Maximum Fair Prices, apply MFP for Part D members

### Formulary Optimization & P&T Committee Tools
- Model cost impact of tier changes before committing
- Therapeutic class review reports
- Auto-generate drug monographs from Drug Database + external clinical data
- P&T committee meeting packet: agenda, monographs, impact analyses, vote tracking, decision recording with rationale
- Formulary change notifications: push to pharmacies and prescribers

### Formulary Publishing (NCPDP F&B v60 — Required Jan 1, 2027)
- Generate F&B Version 60 files from formulary configuration
- Publish to Surescripts network on schedule or on-change
- Prescribers see formulary data in their EHR with coverage status, PA/ST/QL flags, and alternative recommendations

---

## 6. Network Assignment

- Assign one or more pharmacy networks per plan
- Tiered networks: preferred vs standard vs out-of-network, each with different cost sharing
- Network effective/termination dates
- Pharmacy type rules: retail, mail order, specialty, 340B, LTC
- **Specialty pharmacy tiers:** separate tier with accreditation tracking (URAC, ACHC)
- **Site of care configuration:** route patients to lowest-cost appropriate site per drug (retail vs mail order vs specialty vs home infusion vs clinic)
- **White/brown/clear bagging:** configure distribution model per drug per plan
- **Limited distribution drug (LDD) management:** track which drugs have restricted distribution, route accordingly
- Network lookup API consumed by adjudication engine

### Network Adequacy (CMS Requirement)
- Map member locations against pharmacy locations, calculate time/distance compliance by county/ZIP
- Gap identification: where network is inadequate
- Network change impact analysis: if a pharmacy leaves, how many members affected?

### Any Willing Pharmacy (CAA 2026 — Effective 2028)
- Application queue: any pharmacy meeting standard terms can apply to join
- Standard contract terms management
- Compliance tracking and reporting to CMS

---

## 7. Program Types

Fully configurable — not an enum. Each is a template with default rules:

Copay assistance, voucher/eVoucher, bridge/free goods, debit card (split adjudication), specialty pharmacy, statement account, workers compensation, commercial insurance, Medicare Part D/MA, Medicaid, 340B, cash/discount card, buy-and-bill copay (provider-administered drugs), direct patient reimbursement (for accumulator patients), custom (tenant-defined).

Adding a new program type is a configuration row, never a code change.

---

## 8. Plan Cloning, Templating & Bulk Operations

- Clone any plan with all settings — one click
- Plan templates: pre-configured starting points per program type
- Bulk operations: apply rule change across all plans in a group or org
- **Bulk import/export:** upload CSV/Excel to create/update hundreds of plans. Download configs, modify, re-upload.
- Import/export as JSON for backup and migration

### Benefit Design Modeling / What-If Simulator
Before committing any change:
- Model financial impact on plan costs AND member OOP
- Side-by-side: current vs proposed
- Member impact: how many affected, average OOP change
- Drug-level detail: which drugs see cost changes
- Save and compare multiple scenarios
- Export as presentation-ready materials for P&T or client review

---

## 9. Manufacturer Market Access Intelligence

- **Formulary coverage landscape:** which plans cover this drug, at what tier?
- **PA requirement mapping:** which plans require PA, what criteria?
- **Competitive positioning:** drug placement vs competitors in same class
- **Payer mix analysis:** % commercial vs Medicare vs Medicaid
- **Accumulator/maximizer exposure:** % of drug's commercially insured patients on accumulator/maximizer plans
- **Trend analysis:** formulary positioning improving or degrading over time?

---

## 10. Configuration Sandbox

Every change follows: Draft → Sandbox → Test → Promote

- **Draft:** changes in draft mode (not active)
- **Sandbox:** deployed to sandbox for testing
- **Test:** regression scenarios via Testing Simulator
- **Promote:** one click to production, full audit trail
- **Rollback:** one click to revert
- **Diff view:** before promoting, see exactly what changes

---

## 11. Data Models

```
organizations, groups, plans (with pricing_model, glp1_config, cash_pay_comparison_enabled), subgroups, formularies, formulary_drugs (with biosimilar_reference_ndc, indication_coverage JSONB), formulary_versions, networks (with any_willing_pharmacy_enabled), network_pharmacies (with specialty_accreditation, site_of_care_type, bagging_model), network_adequacy, awp_applications, plan_templates, pricing_models, plan_pricing, benefit_design_scenarios, pt_committee_meetings, fb_v60_publications, state_formulary_laws
```

---

## 12. API Endpoints

CRUD for orgs, groups, plans, subgroups, formularies, networks. Plus:
- `GET /api/v1/plans/{id}/resolve` — resolve effective config with inheritance
- `POST /api/v1/formularies/{id}/drugs/import` — bulk drug tier import
- `POST /api/v1/formularies/{id}/publish-fb60` — publish F&B v60 to Surescripts
- `POST /api/v1/plans/bulk-import` — bulk create/update from spreadsheet
- `GET /api/v1/networks/{id}/adequacy` — network adequacy report
- `POST /api/v1/networks/{id}/awp-applications` — AWP application
- `POST /api/v1/formularies/{id}/impact-analysis` — formulary change modeling
- `POST /api/v1/plans/{id}/what-if` — benefit design scenario
- `GET /api/v1/market-access/coverage?ndc=` — formulary landscape
- `GET /api/v1/market-access/competitive?gpi=` — competitive positioning
- `POST /api/v1/plans/{id}/promote` — promote sandbox to production
- `POST /api/v1/plans/{id}/rollback` — rollback to previous version

---

## 13. Events

**Publishes:** `plan.created`, `plan.updated`, `plan.terminated`, `plan.promoted_to_production`, `formulary.updated`, `formulary.drug_tier_changed`, `formulary.fb60_published`, `network.pharmacy_added`, `network.pharmacy_removed`, `network.awp_application_received`

**Subscribes to:** `member.enrolled`, `drug.price_updated`, `drug.biosimilar_approved`, `drug.ira_price_negotiated`

---

## 14. Test Scenarios

**Critical:** hierarchy inheritance, formulary lookup by effective date, network in/out check, all copay structures, plan cloning, version rollback, each pricing model, cash-pay comparison, F&B v60 validation, biosimilar mapping, GLP-1 indication coverage, bulk import (500 plans), what-if projections, network adequacy, AWP workflow

**Edge cases:** mid-year plan termination, mid-year tier change, open formulary, empty network, same NDC with two indications, cost-plus with missing acquisition cost (fallback), state anti-accumulator law blocking config

---

## 15. Session Decomposition

1. **Hierarchy engine:** org/group/plan/subgroup CRUD, inheritance, cloning, bulk import/export
2. **Formulary engine:** drug tier management, versioning, biosimilar mapping, indication coverage, F&B v60, P&T tools
3. **Network engine:** pharmacy assignment, specialty/site-of-care/bagging, adequacy, AWP queue
4. **Pricing & modeling:** all 8 pricing model calculators, cash-pay comparison, what-if simulator
5. **Market access & sandbox:** manufacturer intelligence APIs, sandbox draft/test/promote/rollback
