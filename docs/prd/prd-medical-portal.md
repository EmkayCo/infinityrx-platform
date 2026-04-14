# PRD — Module 20d: Medical Portal — FINAL

**Module:** Medical Portal (Medical Provider / Prescriber Facing)  
**Folder:** `portal/medical/`  
**Priority:** Phase 4B  
**Dependencies:** Core Platform (1), Prescriber Dir (4), Member Mgmt (5), Drug DB (2), Medical Claims (14), AI/NLP (21)  

---

## 1. Purpose

The Medical Portal serves physicians, nurse practitioners, and medical office staff. It provides prior authorization management, drug coverage verification, claim status, prescriber credential management, and patient eligibility checking. This portal reduces phone calls to PBM call centers by 60%+.

**Design philosophy:** medical offices are drowning in administrative burden. The #1 complaint is prior authorization delays. This portal makes PA submission, status checking, and coverage verification so fast that office staff prefer it over calling.

---

## 2. Tech Stack

Shared with Operator Portal. Deployed as `providers.infinityrx.com`.

---

## 3. Authentication

- Login via Core Platform auth (JWT + MFA)
- Provider user linked to prescriber NPI(s)
- Multi-provider practices: office staff can have access to all providers in the practice
- Roles: **Practice Admin** (full access + user management), **Prescriber** (PA + coverage + patient), **Office Staff** (PA submission + eligibility check + claim status)

---

## 4. Pages & Features

### 4.1 Dashboard
- **PA queue**: prior auths pending decision (count, oldest, average wait time)
- **PA decisions today**: approved, denied, pended — with quick-view detail
- **Action items**: PAs needing additional info, credentials expiring, pending claim responses
- **Quick actions**: large buttons — "Submit Prior Auth", "Check Coverage", "Check Patient Eligibility", "View PA Status"
- **Formulary alerts**: recent formulary changes affecting this prescriber's common prescriptions

### 4.2 Prior Authorization (THE #1 Feature)
**Submit PA — Wizard:**
1. **Patient**: enter member ID or search by name + DOB. System auto-fills demographics and coverage from Member Management.
2. **Medication**: search by drug name or NDC. System shows: covered? tier? PA required? quantity limits? step therapy? preferred alternatives?
3. **Clinical justification**: guided form based on payer's PA criteria for this drug. AI/NLP pre-fills from clinical note upload (OCR extraction). Shows checklist: "✅ Prior therapy tried: [drug name]", "❌ Missing: lab values for [test]".
4. **Supporting documents**: upload clinical notes, lab results, medical records. AI/NLP auto-extracts relevant clinical data and maps to PA criteria.
5. **Review and submit**: summary of all PA fields. Predicted approval probability (from AI/NLP denial prediction). "Submit" sends PA to payer via FHIR PA API or X12 278.

**PA Status Tracker:**
- All submitted PAs with status: submitted, pending review, approved, denied, pended (additional info needed)
- Timeline: submitted → acknowledged → decision with dates and turnaround time
- Approved PAs: show approval details (quantity, days supply, duration, renewal date)
- Denied PAs: show denial reason in plain English + "Submit Appeal" button
- Appeal wizard: pre-filled with original PA data + denial reason. AI/NLP drafts appeal letter. Prescriber reviews and submits.

### 4.3 Coverage Verification
- **Drug coverage lookup**: enter drug name or NDC → shows for a specific member or as a general formulary check:
  - Covered: yes/no
  - Tier and copay/coinsurance
  - Prior auth required: yes/no (with PA criteria summary)
  - Step therapy required: which drugs must be tried first
  - Quantity limits and days supply limits
  - Preferred alternatives with cost comparison
- **Real-time benefit check** (when EBV/EBI module available): shows patient's actual out-of-pocket cost for this drug at this pharmacy, including deductible status and copay assistance

### 4.4 Patient Eligibility
- **Eligibility check**: enter member ID + DOB (or search by name). Returns:
  - Eligible: yes/no
  - Plan name, BIN/PCN/Group
  - Coverage effective dates
  - Benefit summary (deductible met?, copay structure, OOP max)
  - COB information (primary/secondary payer)
- **Accumulator status**: deductible spent/remaining, OOP spent/remaining, benefit phase (for Part D)

### 4.5 Medical Claim Status
- **Claim search**: by claim number, patient, date of service
- **Claim detail**: HCPCS code, billed/allowed/paid amounts, status, denial reason (if applicable), payment date
- **Denial management**: denied claims with reason codes translated to plain English + recommended action

### 4.6 Prescriber Profile & Credentials
- **NPI detail**: view prescriber information from Prescriber Directory
- **DEA status**: current DEA registration status, expiry date, authorized schedules
- **Credential alerts**: approaching expiry on DEA, state license, or other credentials
- **Practice information**: address, phone, taxonomy, affiliated organization

### 4.7 Formulary Browser
- **Search by drug name, NDC, or therapeutic class**
- **Formulary view**: tier, copay, PA requirement, step therapy, quantity limits per drug per plan
- **Alternatives**: for non-covered or high-tier drugs, show covered alternatives in same therapeutic class with tier and cost comparison
- **Formulary change history**: what changed, when, which plans affected

### 4.8 Secure Messaging + AI Chatbot
- **Message center**: threaded conversations with IFX team (PA questions, coverage disputes, general inquiries)
- **AI chatbot**: "Ask about coverage" — answers formulary questions, PA requirements, eligibility questions in plain language
- **PA status bot**: "What's the status of PA #12345?" → instant answer from PA database

---

## 5. CMS-0057-F FHIR PA Integration

When FHIR PA API is available (Module 10 + EDI Module 13 FHIR bridge):
- **FHIR-based PA submission**: submit PA as FHIR Prior Authorization Request → system converts to X12 278 internally
- **FHIR PA status**: check PA status via FHIR API → returns decision with specific reason (required by CMS-0057-F)
- **Response time compliance**: system tracks 72-hour expedited / 7-day standard decision turnaround and alerts if SLA at risk

---

## 6. UX Patterns

- **PA submission in <5 minutes**: the guided wizard with AI-assisted clinical extraction should make PA submission faster than calling the PBM
- **AI-assisted documentation**: upload a clinical note → AI extracts diagnosis, medications, lab values, prior therapies → auto-fills PA criteria checklist. Prescriber verifies instead of re-typing.
- **Denial prevention**: before submitting, show predicted approval probability. If low, highlight missing criteria with "Add this information to increase approval likelihood."
- **Plain English everywhere**: no raw rejection codes. "CO-97" → "The benefit for this service is included in the payment/allowance for another service." Every code translated.
- **Mobile responsive**: prescribers check PA status from their phone between patients. PA status tracker and eligibility check must work on mobile.
- All shared UX patterns from Operator Portal

---

## 7. Session Decomposition

1. **Shell + auth + dashboard + PA wizard**: Next.js app, prescriber auth (NPI-scoped), dashboard with PA queue and quick actions, PA submission wizard (5-step with AI clinical extraction), PA status tracker with timeline
2. **Coverage + eligibility + claims**: drug coverage lookup with formulary data, patient eligibility check with accumulator status, medical claim status viewer, formulary browser with alternatives, denial management with plain-English translations
3. **Profile + messaging + FHIR**: prescriber profile from Prescriber Directory, credential alerts, formulary change notifications, secure messaging, AI chatbot, FHIR PA API integration (when available)
