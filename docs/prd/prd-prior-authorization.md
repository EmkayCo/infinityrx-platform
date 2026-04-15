# PRD — Module 10: Prior Authorization (FINAL)

**Module:** Prior Authorization
**Folder:** `modules/prior-authorization/`
**Phase:** 5, Wave 2 (parallel with Rules Engine)
**Dependencies:** Core Platform (1), Drug Database (2), Member Management (5), Plan Design (6)

---

## 1. Purpose

Prior Authorization manages the clinical review process for drugs requiring pre-approval. PA requests come from multiple channels — pharmacy claim rejects, prescriber ePA, manual entry, phone intake, FHIR API. The module handles the full lifecycle: intake, clinical criteria evaluation, approval/denial, appeals, letter generation, and real-time status lookup for the adjudication engine.

---

## 2. PA Workflow

```
PA Request Intake (pharmacy reject / ePA / manual / phone / FHIR)
  → Clinical Criteria Evaluation
    → Auto-approve (criteria met) → Approval
    → Route to reviewer (complex case)
      → Decision → Approval / Denial / Request More Info
        → If denied → Appeal (multi-level)
  → PA Status updated (consumed by Adjudication Engine real-time)
  → Letters generated → Notifications sent
```

---

## 3. Clinical Criteria Engine

Configurable criteria sets per drug/class/plan: diagnosis-based (ICD-10), step therapy evidence (configurable lookback), lab values, age/weight, quantity justification, prescriber specialty, site of care, custom criteria. Versioned and effective-dated. Old PAs evaluated against version at time of submission.

**GLP-1 PA criteria templates:** pre-built for GLP-1 drugs with BMI threshold, comorbidity requirements, prior lifestyle intervention documentation. Configurable per plan.

---

## 4. ePA Integration

### NCPDP SCRIPT 2023011 ePA (Required Jan 1, 2028)
- PAInitiationRequest/Response with enhanced clinical data fields
- EPCS support: electronic prescribing of controlled substances with DEA two-factor digital signature validation
- PDMP integration: query state Prescription Drug Monitoring Program for controlled substance PAs

### CoverMyMeds
- API integration for electronic PA submission and status tracking
- Real-time sync, formulary and criteria publishing

### SureScripts ePA
- NCPDP SCRIPT ePA messages, real-time processing, bi-directional status updates

### FHIR R4 PA API (CMS-0057-F Requirement)
- Da Vinci Prior Authorization Support (PAS) Implementation Guide
- EHRs submit PAs via FHIR API in addition to traditional ePA channels
- Enables payer-to-payer PA data sharing

### Copay ePA (First-Fill Buy-Down)
- Manufacturer funds first fill while PA is pending — patient starts therapy immediately
- PA process continues in background. If denied, manufacturer absorbs cost.
- Configurable per program.

---

## 5. Approval/Denial, Appeals & Letters

**Decisions:** auto-approval rules, reviewer assignment by drug type/workload, prioritized queue (urgent = 24hr fills), approve/deny/pend/request info, configurable duration (30-365 days), quantity limits, grandfathering when criteria change.

**Appeals:** multi-level (clinical reviewer → medical director → external review), regulatory deadline tracking per state and plan type, expedited (24-72hr), appeal documentation submission.

**Letters:** branded templates per tenant (approval, denial with reason/criteria/appeal rights, appeal decision, request for info). PDF generation, stored in doc management, sent via configured channel (email, fax, portal, mail).

---

## 6. Specialty Drug Hub Services Integration

- **Benefits investigation:** verify coverage before PA submission (via EBV/EBI module)
- **Copay assistance enrollment:** connect patients with manufacturer programs during PA process
- **Nurse support coordination:** for specialty drugs requiring clinical monitoring
- **REMS compliance:** track FDA REMS requirements per drug (certifications, monitoring, restricted distribution)
- **Specialty pharmacy coordination:** ensure PA-approved specialty drugs route to appropriate pharmacy

### FRM (Field Reimbursement Manager) Digital Tools
- Office-level dashboard: pending PAs, BVs, copay enrollment opportunities per practice
- One-click PA initiation from field with pre-populated criteria
- Activity logging: FRM logs visits, outcomes, follow-ups — visible on manufacturer portal

---

## 7. Data Models

```
pa_requests (with source including FHIR), pa_decisions, pa_appeals (with regulatory deadlines per state/plan type), pa_criteria_sets (versioned, with GLP-1 templates), pa_letters, epa_transactions (with SCRIPT version), fhir_pa_transactions, copay_epa_records (first-fill buy-down tracking), frm_activity_log, rems_requirements, hub_coordination_log
```

---

## 8. API, Events, Tests

**API:** submit PA, full PA detail, real-time status lookup (for adjudication), decide, appeal, reviewer queue, CRUD criteria, generate letter, FHIR PA endpoint (Da Vinci PAS), FRM dashboard.

**Events:** `pa.submitted`, `pa.approved`, `pa.denied`, `pa.appealed`, `pa.expired`, `pa.letter_generated`, `pa.copay_epa_first_fill`

**Subscribes to:** `claim.rejected` (auto-create PA), `member.eligibility_changed` (expire PAs), `formulary.updated` (flag PAs for tier-change drugs)

**Tests:** auto-approve when criteria met, denial letter correct, adjudication engine gets real-time status, appeal routing correct, ePA round-trip, FHIR PA round-trip, copay ePA first-fill, GLP-1 criteria evaluation, EPCS digital signature validation, PDMP query, REMS check, FRM one-click PA

**Edge cases:** duplicate PA, PA expires during claim processing, criteria updated while PA pending, urgent PA deadline calculation, FHIR and SCRIPT PA for same drug/patient

---

## 9. Session Decomposition

1. **PA lifecycle:** intake, criteria evaluation, auto-approval, reviewer queue, decisions, expiration
2. **Appeals & letters:** multi-level workflow, regulatory deadlines, letter template engine, PDF generation
3. **ePA integration:** CoverMyMeds, SureScripts, FHIR R4 (Da Vinci PAS), EPCS/PDMP, copay ePA first-fill
4. **Hub & specialty:** REMS compliance, specialty pharmacy coordination, FRM tools, hub integration
