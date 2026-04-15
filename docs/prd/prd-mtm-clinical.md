# PRD — Module 25: Medication Therapy Management / Clinical Programs (FINAL)

**Module:** MTM / Clinical Programs
**Folder:** `modules/mtm-clinical/`
**Phase:** 5, Future (Wave 5+)
**Dependencies:** Core Platform (1), Drug Database (2), Member Management (5), Claims Adjudication Engine (8), AI/NLP (21 — already built)

---

## 1. Purpose

MTM/Clinical Programs manages clinical intervention programs that improve health outcomes and reduce costs. This includes CMS-required MTM for Part D, employer-focused medication optimization, adherence programs, population health analytics, and the pharmacist workbench for clinical intervention management. This module turns claims data into clinical intelligence and clinical interventions into measurable outcomes.

---

## 2. MTM Program Management (CMS-Required for Part D)

### Comprehensive Medication Review (CMR)
- Identify eligible members per CMS targeting criteria (multiple chronic conditions, multiple Part D drugs, projected annual cost threshold)
- Schedule and track CMRs (annual requirement)
- Pre-populate CMR with prescription history from claims data
- Generate Medication Action Plan (MAP) and Personal Medication List (PML) automatically
- Track completion rates against CMS benchmarks
- Compensation tracking: auto-queue payment to pharmacist upon successful CMR

### Targeted Medication Review (TMR)
- Ongoing review based on drug utilization patterns
- Flag members with: adherence gaps, drug-drug interactions, therapeutic duplication, high-risk medication use, dosing concerns
- Route alerts to clinical pharmacist for review
- Track interventions and outcomes

---

## 3. Population Health Engine / Risk Stratification

Beyond basic adherence monitoring — population-level intelligence:

- **Risk scoring:** assign each member a risk score based on: number of chronic conditions, number of medications, medication complexity, adherence history, recent hospitalizations, social determinants of health
- **Intervention targeting:** identify which members benefit most from clinical intervention (highest ROI). Rank by projected cost savings × probability of intervention success.
- **Drug mix optimization:** analyze a population's drug mix and identify where therapeutic alternatives could reduce cost while maintaining or improving outcomes
- **Guaranteed savings tracking:** track intervention outcomes against savings guarantees (EmpiRx-style dollar-for-dollar reimbursement if guarantee missed)
- **Cohort analysis:** group members by condition, medication class, risk level. Compare outcomes across cohorts.

---

## 4. Medication Guidance / Clinical Navigation

Platform support for human-in-the-loop clinical guidance (WithMe Health / Rightway model):

### Pharmacist Workbench
- Dashboard showing members flagged for intervention, prioritized by risk score and ROI
- Member context: full claims history, medical history (if available), lab data, current medications, adherence patterns, social determinants
- Intervention workflow: pharmacist documents recommendation, sends to prescriber for approval, tracks outcome
- Templates for common interventions (therapy switch, dose optimization, adherence counseling, deprescribing)

### Peer-to-Peer Prescriber Collaboration
- Pharmacist works directly with prescribing physician to optimize therapy
- Structured communication: proposed change, clinical rationale, cost impact, prescriber decision
- Track acceptance/rejection rates per prescriber (quality metric)

### Multi-Data-Source Integration
- Pharmacy claims (primary — always available)
- Medical claims (via Medical Claims module 14 — already built)
- Lab data (if available via integration)
- Patient-reported outcomes (via portal/app)
- Social determinants of health (from member demographics + external data sources)

---

## 5. Adherence Programs

### PDC (Proportion of Days Covered) Tracking
- Real-time PDC calculation per member per drug class
- Dashboard: population-level adherence rates by drug class
- CMS star ratings alignment: track adherence for star rating drug classes (diabetes, RAS antagonists, statins)

### Adherence Interventions
- Auto-flag members below PDC threshold (configurable — typically 80%)
- Intervention types: reminder call/text, pharmacist outreach, prescriber notification, benefit adjustment
- Track intervention → outcome (did adherence improve?)
- Multi-channel delivery: app push, SMS, email, letter, phone (configurable per member preference)

### Medication Synchronization (Med Sync)
- Identify members with multiple maintenance medications on different fill schedules
- Recommend synchronized fill dates (all meds filled on same day each month)
- Coordinate with pharmacy for pickup

---

## 6. Clinical Programs Library

Pre-built program templates, configurable per tenant:

- **Diabetes management:** A1C monitoring, insulin optimization, GLP-1 management, blood glucose test strip coverage
- **Cardiovascular:** statin optimization, beta-blocker adherence, anticoagulant monitoring
- **Behavioral health:** antidepressant adherence, antipsychotic monitoring, opioid management
- **Specialty drug monitoring:** hepatotoxicity screening, immunosuppressant levels, biosimilar transition
- **Polypharmacy review:** members on 10+ medications, deprescribing candidates, fall risk reduction
- **Opioid stewardship:** morphine milligram equivalent (MME) tracking, naloxone co-prescribing, taper protocols
- **GLP-1 management:** dose escalation tracking, indication verification, oral vs injectable comparison
- **High-cost member management:** top 1% of spenders, care coordination, specialty drug optimization

---

## 7. Outcomes Tracking & Reporting

- Clinical outcomes: adherence rates, A1C improvement, hospitalization reduction, ER visit reduction
- Financial outcomes: cost savings from interventions, generic conversion savings, therapeutic alternative savings
- Operational outcomes: interventions completed, prescriber acceptance rates, member engagement rates
- CMS star rating alignment: track all Part D star rating measures
- **Return on investment (ROI):** per program, per intervention type, per pharmacist. "Every dollar spent on this clinical program saved $X in total cost of care."
- Unified pharmacy + medical analytics: see how pharmacy interventions affect medical costs

---

## 8. Member Communication Engine (Proactive Outreach)

Multi-channel, proactive member outreach beyond adherence reminders:

- **Lower-cost alternative:** "A generic version of your medication is now available. Save $X/month."
- **Refill gap approaching:** "Your supply of [drug] runs out in 5 days."
- **New biosimilar:** "A biosimilar for [brand drug] is now on your formulary at Tier 1."
- **Benefit phase transition:** "You've reached your deductible. Your copays are now lower."
- **Benefit year transition:** "Your new plan year starts Jan 1. Here's what's changing."
- **GLP-1 new formulation:** "An oral version of your injectable medication is now available."

Channels: app push, SMS, email, portal message, letter. Configurable per member preference with opt-out. Campaign management tools for bulk outreach.

---

## 9. Data Models

```
mtm_eligible_members, cmr_records (with map, pml, completion_status), tmr_alerts, risk_scores (with calculation_factors JSONB), intervention_records (with type, recommendation, prescriber_response, outcome), adherence_tracking (pdc per member per class), clinical_programs (templates), program_enrollments, member_communications (with channel, template, delivery_status, response), outcomes_metrics, roi_calculations, med_sync_records, population_cohorts
```

---

## 10. API, Events, Tests

**API:** MTM eligibility, CMR records, risk scores, intervention management, PDC lookup, clinical program enrollment, communication campaigns, outcomes reports, pharmacist workbench data.

**Events:** `mtm.member_eligible`, `cmr.completed`, `intervention.created`, `intervention.prescriber_responded`, `adherence.below_threshold`, `communication.sent`, `communication.responded`

**Subscribes to:** `claim.adjudicated` (update adherence, risk scores), `member.enrolled` (check MTM eligibility), `formulary.updated` (lower-cost alternative notifications)

**Tests:** MTM eligibility criteria match CMS rules, CMR generates correct MAP/PML, PDC calculation correct with gaps and overlaps, risk score formula produces expected results, intervention workflow round-trip (create → prescriber notification → response → outcome), adherence alert fires at threshold, communication delivered via correct channel, ROI calculation matches expected formula, population cohort segmentation correct

**Edge cases:** member eligible for MTM but opts out, CMR with no refillable medications, intervention for discontinued medication, PDC calculation for PRN medications, communication to member with no email/phone (fall back to letter), prescriber who never responds (escalation), member on 25+ medications (performance of risk calculation)

---

## 11. Session Decomposition

1. **MTM engine:** eligibility targeting, CMR workflow, TMR alerts, CMS compliance tracking, compensation
2. **Population health:** risk scoring, cohort analysis, drug mix optimization, savings guarantee tracking
3. **Clinical workbench:** pharmacist dashboard, intervention workflow, prescriber collaboration, multi-data integration, templates
4. **Adherence & communication:** PDC tracking, med sync, proactive outreach engine (multi-channel), campaign management
5. **Outcomes:** tracking, ROI calculation, star rating alignment, unified pharmacy + medical analytics
