# PRD — Module 7: Rules Engine (FINAL)

**Module:** Rules Engine
**Folder:** `modules/rules-engine/`
**Phase:** 5, Wave 2 (after Plan Design)
**Dependencies:** Core Platform (1), Drug Database (2), Plan Design (6)

---

## 1. Purpose

The Rules Engine is the decision layer of the adjudication platform. Every claim passes through a configurable pipeline of rules that determine pricing, coverage, limits, and restrictions. Rules are templates — each rule type is defined once in code, then instantiated with parameters per tenant/plan/program. Adding a new rule instance is always a configuration change, never a code change.

---

## 2. Architecture

```
Claim enters → Rule Pipeline (ordered list per plan)
  → Rule 1: Eligibility → Rule 2: Formulary → Rule 3: PA check
  → Rule 4: Quantity limit → Rule 5: Copay → Rule 6: DUR → ...
  → Final pricing response
```

Rules execute in configurable order. Each rule can: PASS (continue), REJECT (stop with reject code), MODIFY (change pricing and continue), or FLAG (add warning and continue). Rule order is drag-and-drop configurable.

---

## 3. Rule Types (Template Library)

### Pricing Rules
- **Bill Cost Calculator:** ingredient cost + dispensing fee + markup. Configurable tiers. Source: AWP, WAC, NADAC, MAC, or custom.
- **Copay Rules:** flat, percentage, tiered, step-based, or custom formula.
- **Cost Calculator / Cost List:** configurable pricing schedules per drug/GPI/class.
- **Dispense Fee Rules:** flat or variable per pharmacy/drug/network tier.
- **MAC Pricing:** per drug/GPI, configurable update frequency, pharmacy appeal workflow.
- **Under-reimbursement / POS Adjustment:** compare DV+NQ against benchmark (WAC, manufacturer target, sales data, custom). Calculate delta. Communicate via configurable channel.

### Coverage Rules
- **Age Rules:** min/max age per drug/program.
- **Dispense Limit / Quantity Limits:** max quantity per fill, per day supply, per time period.
- **Refill Rules:** early refill threshold (% or days), vacation supply override.
- **Fill Rules:** max fills per time period, initial vs maintenance.
- **DAW:** penalties or copay differentials per DAW code.
- **Restriction Rules:** block or flag specific NDCs, GPIs, or classes.
- **Step Therapy:** require preferred drug trial before covering non-preferred. Configurable lookback.
- **Location Rules:** coverage varies by pharmacy/member/prescriber location.
- **Indication-Based Coverage:** same NDC, different coverage based on ICD-10 diagnosis code (critical for GLP-1s).

### Authorization Rules
- **Prior Authorization Triggers:** conditions requiring PA per drug/class/quantity threshold.
- **Process Rules:** auto-approve if criteria met, route to reviewer, etc.
- **COB:** primary/secondary/tertiary payer logic, configurable per plan.

### Specialty Rules
- **Compound Pricing:** per-ingredient with markup, min/max claim amount.
- **Coupon/Voucher:** discount amounts, max benefit per fill/year, eligible pharmacies.
- **Accumulator/Maximizer (Dual-Sided):** manufacturer defense (detect plans, calculate impact, adapt copay strategy) AND health plan implementation (configure accumulator/maximizer programs).
- **Workers Comp:** state-specific formularies and fee schedules.
- **340B Split Billing:** covered entity ID, contract pharmacy rules, duplicate discount prevention.
- **Biosimilar Auto-Substitution:** auto-substitute biosimilar for reference biologic with state law compliance check (50-state rules vary).
- **Therapeutic Alternative Routing (Drug Pathways):** identify lower-cost clinically equivalent alternatives and return them to pharmacy with cost comparison. Route to generic, biosimilar, preferred brand, or mail order as appropriate.
- **Site of Care Routing:** route to lowest-cost appropriate dispensing site per drug.
- **LDD Routing:** enforce limited distribution drug restrictions.

---

## 4. Rule Builder UI (Three Methods)

### Visual Drag-and-Drop Pipeline Builder
- Canvas view: rules as connected nodes in a flowchart
- **Branching logic:** if Rule A rejects, skip to Rule D. If Rule A passes, continue to Rule B. Visual branching paths.
- **Rule groups:** collapsible sections (Pricing, Coverage, UM, Specialty)
- **Live preview:** as you build, a sample claim runs through in real-time showing result at each step
- **Version comparison:** side-by-side diff of current pipeline vs proposed changes
- **Copy pipeline:** clone from one plan to another with one click
- Drag rules from library, reorder priority, configure parameters inline
- Color-coded by category

### Natural Language Rule Creation
- Describe in English: "Reject claims for members under 18 for NDCs in therapeutic class X"
- AI parses into rule definition (via AI/NLP module)
- User reviews and confirms before activation
- Audit trail records original natural language input

### BRD Config File Upload
- Upload completed Business Rules Document
- Parser validates against system rules
- Preview what will be created
- Apply with confirmation — bulk create dozens of rules in one operation

---

## 5. Rule Versioning, Governance & State Compliance

- Every change creates new version with effective date
- Rollback to any previous version
- Audit trail: who, what, when, why
- Approval workflow for material changes (configurable — some tenants require 4-eyes)
- Rule testing: test against sample claims before activating (via Testing Simulator)
- Rule conflict detection: warn when two rules produce contradictory outcomes
- **Bulk rule import:** upload spreadsheet of rule parameters to create instances in batch

### State Regulatory Compliance Engine
50-state variations on: biosimilar substitution laws, MAC appeal rights, prompt pay deadlines, PA response timelines, accumulator restrictions. Configurable `state_regulatory_rules` table with state code, rule category, parameters, effective date. Rules Engine checks applicable state rules during pipeline execution. Updated via periodic regulatory feed.

---

## 6. Data Models

```
rule_types, rule_instances (with plan_id, program_id, priority_order, version, effective_date), rule_versions, rule_pipelines (ordered_rule_ids per plan), rule_execution_log (claim_id, rule_id, result, input/output values, execution_time_ms), mac_prices, state_fee_schedules, state_regulatory_rules, biosimilar_substitution_laws, therapeutic_alternatives (source_ndc, alternative_ndc, savings_estimate)
```

---

## 7. API Endpoints

- `GET /api/v1/rule-types` — all available templates
- `GET/POST /api/v1/rules` — CRUD rule instances
- `GET/PUT /api/v1/plans/{id}/pipeline` — get/reorder rule pipeline
- `POST /api/v1/rules/{id}/test` — test against sample claim
- `POST /api/v1/rules/evaluate` — evaluate full pipeline (consumed by adjudication)
- `POST /api/v1/rules/import-brd` — parse BRD upload
- `POST /api/v1/rules/bulk-import` — bulk import from spreadsheet
- `GET /api/v1/rules/{id}/versions` — version history
- `POST /api/v1/rules/{id}/rollback/{version}` — rollback

---

## 8. Events

**Publishes:** `rule.created`, `rule.updated`, `rule.activated`, `rule.deactivated`, `pipeline.reordered`, `rule.conflict_detected`

**Subscribes to:** `plan.created` (create default pipeline), `formulary.updated` (invalidate cached results), `drug.price_updated` (recalculate MAC comparisons)

---

## 9. Test Scenarios

**Critical:** each rule type correct output, pipeline order respected, REJECT stops execution, MODIFY changes pricing, versioning old vs new, accumulator/maximizer tracking, under-reimbursement calculation, MAC pricing, biosimilar substitution with state law check, therapeutic alternative routing returns correct lower-cost option, indication-based coverage per diagnosis, bulk import creates 100 rules correctly

**Edge cases:** conflicting rules (priority determines), compound claim 5 ingredients, workers comp no fee schedule, future effective date rule not applied, pipeline with zero rules, branching logic (reject skips to specified rule), state law blocks biosimilar substitution in specific state

---

## 10. Session Decomposition

1. **Rule type library:** all rule type definitions, parameter schemas, executor classes
2. **Pipeline engine:** ordered execution, branching logic, result aggregation, conflict detection, caching
3. **Specialty rules:** accumulator/maximizer (both sides), workers comp, 340B, compound, POS adjustment, therapeutic alternatives, biosimilar substitution, indication-based, site-of-care, LDD
4. **Rule builder UI:** drag-and-drop with branching/live preview/version compare, NL creation, BRD import, bulk import, approval workflow, state compliance engine
