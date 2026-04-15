# PRD — Module 17: Program Configuration & Onboarding (FINAL)

**Module:** Program Configuration & Onboarding
**Folder:** `modules/program-config/`
**Phase:** 5, Wave 1 (parallel with Plan Design and Rebate)
**Dependencies:** Core Platform (1), Plan Design (6)

---

## 1. Purpose

Program Configuration handles everything from signed contract to live program. It provides tools to rapidly onboard new clients, configure programs, and launch without touching code. A BRD template system captures client requirements in a structured format that can be parsed directly into system configuration. For manufacturers, the Self-Service Program Builder lets them configure their own copay programs in a guided wizard with IFX review/approval.

---

## 2. BRD Template Engine (Full Lifecycle)

### Template Builder (Wizard — IFX Operator)
- Drag-and-drop form builder: add sections, fields (dropdown, text, checkbox, file upload), validation rules, conditional logic ("if program type = debit card, show debit card fields")
- Pre-built templates per program type (copay, voucher, bridge, debit card, specialty, workers comp, 340B, commercial, Medicare, Medicaid)
- Configurable sections: program basics, eligible population, drug list, pricing rules, claim limits, pharmacy network, reporting requirements, escalation contacts
- Versioned: template changes tracked

### Client-Facing BRD Portal
- Client logs into portal, sees assigned BRD template
- Fills out section by section with inline help text and validation
- Saves progress, completes over multiple sessions
- Attaches supporting documents (formulary, contract, drug lists)

### IFX Review Workflow
- Submitted BRD enters review queue
- Reviewer sees parsed data with AI-highlighted potential issues
- Approve/reject/request changes per section
- Client notified of change requests, resubmits

### Sign-Off
- All sections approved → both parties digitally sign
- BRD becomes locked, versioned document

### Auto-Configuration
- Signed BRD triggers automatic creation of: plan hierarchy, formulary entries, rule instances, BIN/PCN routes, network assignments, fee schedule, contract record
- **Diff view:** before promoting, operator sees exactly what will change — new plans, rules, formulary entries
- One-click promote or item-by-item approval
- Full rollback if anything goes wrong

---

## 3. Program Launch Wizard (Step-by-Step)

1. Program basics: name, type, client, dates, description
2. Drug configuration: NDC/GPI selection, search, bulk import
3. BIN/PCN/Group assignment: assign or auto-generate
4. Pricing rules: select templates, configure parameters
5. Eligibility criteria: age, diagnosis, insurance type, geographic (checkboxes, not code entry)
6. Pharmacy network: assign network, configure rules
7. Reporting: select reports, delivery schedule, recipients
8. Review & activate: summary, test with simulator, activate

Can save draft and resume. Non-linear navigation between steps.

---

## 4. Manufacturer Self-Service Program Builder

The ultimate simplicity play — manufacturer configures their own program:

1. "Let's set up your copay program" welcome screen
2. Drug selection: search by name, NDC, or class. Multi-select.
3. Program type: copay card, voucher, bridge, debit card, buy-and-bill, direct reimbursement (each explained in plain English)
4. Eligibility: checkboxes — "Patients must have commercial insurance"
5. Offer design: per-fill cap, annual max, target patient pay. **AI recommends optimal values** based on drug cost, payer mix, competitive landscape, and GTN budget
6. Accumulator strategy: choose how to handle accumulator/maximizer patients. AI recommends.
7. Pharmacy network: all, specialty only, or specific pharmacies
8. Reporting preferences
9. Review & submit for IFX review
10. IFX reviews, tests in sandbox, promotes to production. Manufacturer notified when live.

---

## 5. Contract Management

- Contract templates configurable per program type with standard terms
- Terms: effective/termination dates, auto-renewal, notice period
- SLAs: configurable per contract (processing time, uptime, report delivery)
- Fee schedules: per-claim fees, monthly admin, setup fees — linked to Billing module
- **Guaranteed spend cap (SureSpend model):** contractual ceiling on pharmacy spend with refund guarantee on overages
- **Bona fide service fee (BFSF) documentation:** for CAA 2026 compliance, document that fees reflect fair market value for services performed
- Amendments: tracked with effective dates, approval workflow
- Document storage: signed contracts encrypted, linked to program
- Renewal management: alerts before auto-renewal

---

## 6. Client Onboarding Workflow

Configurable steps from contract to go-live (default 12 steps):
1. Contract signed/uploaded → 2. BRD sent → 3. BRD returned/parsed → 4. Program configured → 5. Test claims in simulator → 6. Client reviews/approves test results → 7. BIN/PCN registered with switches → 8. Pharmacy network notified → 9. Member enrollment received → 10. Go-live confirmed → 11. Program activated → 12. Post-launch monitoring (30 days elevated alerting)

**Onboarding dashboard:** all programs in onboarding with status per step. SLA tracking. Bottleneck identification.

---

## 7. Data Models

```
programs (with status workflow), program_drugs, brd_templates (with form builder schema), brd_submissions (with parsed_data, validation_results), contracts (with sla, fees, amendments, spend_cap_config, bfsf_documentation), onboarding_workflows (with steps JSONB), onboarding_step_log, manufacturer_program_configs (self-service builder data)
```

---

## 8. API, Events, Tests

**API:** CRUD programs, launch wizard, CRUD BRD templates, upload/validate/apply BRD, CRUD contracts with SLAs, onboarding workflow status, manufacturer self-service builder, promote config.

**Events:** `program.created`, `program.activated`, `program.suspended`, `program.terminated`, `onboarding.step_completed`, `onboarding.go_live`, `contract.expiring_soon`

**Tests:** BRD parses correctly and creates valid plan/rules/formulary, invalid NDC fails validation, wizard creates complete config that passes adjudication test, onboarding can't skip required steps, contract auto-renewal fires alert, manufacturer self-service creates valid program, AI copay recommendations are reasonable, diff view shows correct changes, auto-config rollback works

**Edge cases:** BRD with duplicate NDCs (dedup with warning), program activated before onboarding complete (block), two programs same BIN/PCN (conflict detected), contract amendment mid-cycle (effective dating), BRD template updated while submission in progress (uses version at upload time)

---

## 9. Session Decomposition

1. **BRD engine:** template builder (drag-and-drop form builder), upload parser, validation, preview, atomic apply with diff view, client portal
2. **Program wizard:** step-by-step UI, drug config, BIN/PCN, save/resume
3. **Manufacturer self-service:** self-service builder with AI recommendations, accumulator strategy selector, submit-for-review workflow
4. **Contract & onboarding:** contract CRUD, SLA tracking, BFSF documentation, spend cap, amendments, renewal alerts, onboarding step tracker, dashboard
