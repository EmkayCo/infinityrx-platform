# PRD — Module 8: Claims Adjudication Engine (FINAL)

**Module:** Claims Adjudication Engine
**Folder:** `modules/adjudication-engine/`
**Phase:** 5, Wave 3 (after Rules Engine)
**Dependencies:** Core Platform (1), Drug Database (2), Pharmacy Directory (3), Member Management (5), Plan Design (6), Rules Engine (7)

---

## 1. Purpose

The adjudication engine is the core transaction processor. It receives a pharmacy claim (NCPDP D.0 format), determines member eligibility, resolves the plan, executes the rule pipeline, calculates pricing, and returns a response — all in sub-1-second. This module handles ALL claim types for ALL client types. It is the heart of the PBM platform.

---

## 2. Transaction Flow

```
Switch delivers NCPDP D.0 request
  → Parse all segments/fields (full standard)
  → Identify member (cardholder ID + person code + DOB)
  → Verify eligibility (plan active, coverage dates, benefit status)
  → Resolve plan (group → plan → subgroup, effective at date of service)
  → Resolve pricing model (per plan config — AWP, cost-plus, NADAC, net-cost, etc.)
  → Lookup claim history (Redis cache — refill checks, quantity, duplicate detection)
  → Check for active overrides (member + rule level — skip overridden rules)
  → Execute rule pipeline (Module 7 — ordered rules per plan, skipping overridden rules)
  → DUR screening (drug-drug interactions, therapeutic duplication, early refill)
  → COB processing (primary/secondary/tertiary)
  → Accumulator/maximizer detection (identify if patient's primary plan uses accumulator or maximizer)
  → Calculate final pricing using resolved pricing model
  → AI pre-adjudication scrub (optional — catch common errors before rejection)
  → Build NCPDP D.0 response with Reasons for Adjudication
  → Log transaction with full claim trace
  → Return response to switch
```

**Performance:** sub-1-second p95, sub-200ms p50. 100M claims/year baseline, architect for 300M+.

---

## 3. NCPDP D.0 Support

Full standard — all transaction types: B1 (Billing), B2 (Reversal), B3 (Rebill), E1 (Eligibility), P1-P4 (PA Request/Reversal/Inquiry/Appeal), N1 (Information Reporting), S1 (Controlled Substance Reporting). All segments parsed: header, insurance, patient, prescriber, claim, pricing, compound, DUR/PPS, clinical, COB. Every field mapped.

---

## 4. Pricing Calculation

All Decimal with ROUND_HALF_UP. Pricing model resolved from plan config:

```
Ingredient Cost = pricing_source × quantity (source per plan pricing model)
Dispensing Fee = per pharmacy/network config
Gross Amount = Ingredient Cost + Dispensing Fee + taxes/surcharges
Patient Pay = copay per plan benefit config
Plan Pay = Gross Amount - Patient Pay
```

**Cash-pay comparison:** if enabled on plan, calculate both insurance and cash price, return lower. Display both to pharmacy in response.

**IRA negotiated drug pricing:** if member is Part D and drug has CMS Maximum Fair Price, apply MFP instead of standard pricing.

---

## 5. Reasons for Adjudication (Plain English Explainer)

Every claim response includes `adjudication_reasons` array. Each entry explains in plain English what happened at each step. Example:

```
"Formulary check: Lipitor 10mg is Tier 3 (Non-Preferred Brand). Patient copay $45/30-day.
 Tier 1 alternative exists: Atorvastatin 10mg at $10 copay."
"Refill check: Last fill 03/15 (30-day supply). Today 04/10 (87% used). Threshold 75%. PASS."
"DUR: Drug-drug interaction with Tramadol (moderate). Informational — pharmacy notified."
```

This is for customer care reps who need to explain to members and pharmacies without technical knowledge.

### Full Claim Trace (for operators/clinical staff)

Stored with every claim — step-by-step visual trace of every rule that fired, what it checked, what it found, what it decided. Includes input values, output values, execution time per rule.

---

## 6. Claim-Level Rule Override / Bypass System

When a claim is rejected by a specific rule, the help desk operator can override that rule for that member without issuing a PA code or override code. The pharmacy simply rebills and the claim goes through.

### How It Works

1. **Claim rejects** — pharmacy calls help desk
2. **Operator pulls up the rejected claim** — sees full claim trace with every rule that fired and which one caused the rejection
3. **Operator clicks "Override Rule"** on the specific rejecting rule — a panel slides out asking for:
   - **Reason** (required — dropdown of common reasons + free text): "Pharmacy confirmed patient not on government plan," "Confirmed commercial coverage via phone," "Prescriber confirmed medical necessity," "Client authorized exception," etc.
   - **Duration** (required — how long does this override last):
     - One-time (this specific claim only — next rebill passes, but any subsequent fill re-evaluates normally)
     - Fixed period (7 days, 30 days, 90 days, custom)
     - Until end of benefit year
     - Permanent (until manually revoked)
   - **Supporting documentation** (optional — attach file, screenshot, call reference #)
   - **Scope** (defaults based on context, operator can adjust):
     - This member + this rule + this drug (most specific — default)
     - This member + this rule + any drug (broader — e.g., override age rule for this member on all drugs)
     - This member + this rule + this pharmacy (if override is pharmacy-specific)
4. **Approval workflow** (configurable per tenant):
   - Auto-approve: operator clicks override, it's immediately active (for low-risk rules like age, refill timing)
   - Supervisor approval: override goes to supervisor queue, pharmacy told to "rebill in 15 minutes" (for financial rules like pricing, coverage)
   - Configurable per rule type — tenant defines which rules need supervisor approval
5. **Pharmacy rebills** — the adjudication engine checks for active overrides for this member + rule before executing the rule pipeline. If an active override exists, the rule is SKIPPED with notation in the claim trace:

```
Step 3: Age Rule — SKIPPED (Override #OVR-2847)
  Overridden by: jsmith@infinityrx.com on 04/15/2026
  Reason: "Pharmacy confirmed patient has commercial coverage, not Medicare"
  Duration: Until 12/31/2026
  Original rejection: "Patient age 67 exceeds maximum age 65 for this program"
```

### Override Management UI

**Active Overrides Dashboard:**
- All active overrides across all members, filterable by: rule type, operator, date range, expiration, program
- Expiring soon alerts (overrides expiring in next 7/14/30 days)
- One-click revoke with reason
- Bulk revoke (e.g., revoke all overrides for a rule that was updated)

**Override History per Member:**
- Every override ever created for a member, with status (active/expired/revoked)
- Linked to the original rejected claim and the subsequent paid claim(s)
- Audit trail: created by, approved by (if supervisor approval), revoked by (if revoked)

**Override Reporting:**
- Volume by rule type (which rules get overridden most — may indicate rule needs adjustment)
- Volume by operator (who is overriding most — training indicator)
- Override-to-paid conversion rate (how many overrides resulted in paid claims)
- Financial impact of overrides (total dollars paid that would have been rejected)
- Flagging: if a rule gets overridden >X% of the time, alert the operator that the rule may need reconfiguration

### Data Model

```
claim_overrides: id, tenant_id, member_id, rule_id, rule_type, ndc (nullable), pharmacy_npi (nullable), scope (member_rule_drug | member_rule_any | member_rule_pharmacy), reason_code, reason_text, supporting_doc_path, duration_type (one_time | fixed_period | benefit_year | permanent), expires_at, status (pending_approval | active | expired | revoked), created_by, approved_by, approved_at, revoked_by, revoked_at, revoke_reason, original_claim_id, created_at
override_approval_config: id, tenant_id, rule_type, requires_approval (boolean), approver_role
```

### Safety Guardrails

- **Cannot override DUR hard stops** (drug-drug interaction severity = critical) — configurable per tenant, some DUR alerts are never overridable
- **Cannot override government exclusion rules** (OIG/SAM screening) — these are regulatory, never overridable
- **Automatic expiration** — no override lasts forever without review. "Permanent" overrides are flagged for annual review.
- **Override rate monitoring** — if a single operator creates >X overrides per day, alert supervisor
- **Financial ceiling** — if overrides for a single member exceed $X in total paid amount, require supervisor review regardless of rule type

---

## 7. Accumulator/Maximizer Detection & Adaptive Response

At adjudication time:
- **Detection signals:** OC2/OC8 claim type, other payer amount fields, benefit phase indicators
- **Classification:** flag as "accumulator plan," "maximizer plan," or "standard plan"
- **Adaptive copay response (manufacturer programs):** automatically adjust copay assistance:
  - Standard plan → full copay card benefit at POS
  - Accumulator detected → reduce POS benefit, route remainder to direct patient reimbursement
  - Maximizer detected → spread assistance across benefit year per maximizer structure
- **State law check:** 26 states have anti-accumulator laws — apply standard copay regardless if state prohibits

---

## 8. Copay ePA (First-Fill Buy-Down)

For manufacturer programs with copay ePA enabled: if PA is pending but first fill is needed, the manufacturer funds the first fill at POS. Patient starts therapy immediately. PA process continues in background. If PA ultimately denied, manufacturer absorbs cost. Configurable per program.

---

## 9. Real-Time Copay Fraud Prevention (ShieldRx Equivalent)

ReclaimRx detection rules extended for copay program misuse — runs DURING adjudication:
- Bill-reverse-rebill patterns to maximize copay capture
- Copay card usage inconsistent with legitimate patient use
- Prescription volume spikes from individual pharmacies tied to copay programs
- Prescriber-pharmacy collusion indicators
- Geographic anomalies (unreasonable patient travel distances)
- Identity verification (patient identity consistent across claims)

Pass/fail decision in seconds. Block suspect claims before payment.

---

## 10. Therapeutic Alternative Routing (Drug Pathways)

When claim adjudicates, automatically check for lower-cost clinically equivalent alternatives:
- Generic available for brand → return alternative with cost comparison
- Biosimilar available for reference biologic → return alternative
- 90-day mail order cheaper than 30-day retail → suggest
- Preferred brand available in same class → return alternative

Response includes: current drug cost, alternative drug, alternative cost, savings amount. Pharmacy sees this in the response to discuss with patient.

---

## 11. DUR, COB, Compound, Reprocessing

**DUR:** drug-drug interactions (severity from Drug Database), therapeutic duplication, early refill, excessive quantity, age contraindications, pregnancy/lactation. Configurable per plan: hard reject, soft reject (pharmacy override), or informational. **PDMP check:** optional DUR rule for Schedule II-V drugs — query state PDMP, return warning if potential misuse.

**COB:** determine payer order from submission code, apply other payer amounts, handle all OC types (01/02/03/04/08), configurable COB rules per plan.

**Compound:** parse ingredient list (up to 25), price each separately, apply compound pricing rules, sum costs + compound dispensing fee.

**Reprocessing/Restacking:** when retroactive changes occur (eligibility correction, pricing update, rule change), identify affected claims, re-adjudicate, calculate delta, generate adjustment transactions, feed to Billing module.

---

## 12. Drug Waste Prevention

Track and alert on:
- Abandoned prescriptions (sent to pharmacy, never picked up — especially high-cost specialty)
- Early therapy discontinuation (member starts but stops before therapeutic benefit)
- Dose optimization opportunities (high dose when lower would be clinically appropriate)
- Days supply waste (90-day fills for new starts — should trial with 30-day first)

Configurable alerting to pharmacist, prescriber, or plan sponsor.

---

## 13. Buy-and-Bill Copay Automation

For provider-administered drugs: provider orders → InfinityRx verifies eligibility → calculates copay assistance → provider administers → provider bills medical benefit → InfinityRx processes copay claim → provider receives reimbursement. Single provider portal interface for BV, PA, copay enrollment, claims submission.

---

## 14. Pharmacy Reimbursement Transparency

Show pharmacies exactly how reimbursement was calculated per claim: acquisition cost breakdown, markup, dispensing fee, member copay collected, amount due to pharmacy. The pharmacy equivalent of Reasons for Adjudication.

---

## 15. AFP Detection

Detect when patients are steered away from manufacturer programs into Alternative Funding Programs: patient fills at international pharmacy, charity PAP enrollment despite adequate commercial coverage, specialty carve-out indicators. Alert manufacturer, track lost revenue.

---

## 16. AI-Assisted Claim Scrubbing

Pre-adjudication AI check:
- Catch common errors (wrong quantity, wrong day supply, missing fields) — auto-correct or flag
- Denial prediction: ML model predicts which claims likely to be denied, why, enabling proactive intervention
- Smart auto-approval: for low-risk routine refills, streamline processing (configurable)

---

## 17. Data Models

```
claim_transactions (with adjudication_reasons JSONB, claim_trace JSONB, pricing_model_used, accumulator_detected boolean, copay_fraud_score decimal), claim_history_cache (Redis), claim_adjustments, compound_ingredients, dur_screening_log, copay_fraud_flags, drug_waste_alerts, afp_detection_log, pharmacy_reimbursement_detail
```

---

## 18. API Endpoints

- `POST /api/v1/claims/adjudicate` — primary endpoint (NCPDP D.0 in/out)
- `POST /api/v1/claims/reverse` — B2 reversal
- `POST /api/v1/claims/rebill` — B3 rebill
- `GET /api/v1/claims/{id}` — full claim detail with trace
- `GET /api/v1/claims/{id}/trace` — visual adjudication trace
- `GET /api/v1/claims/member/{member_id}` — member claim history
- `POST /api/v1/claims/reprocess` — trigger reprocessing
- `GET /api/v1/claims/stats` — real-time throughput/latency metrics

---

## 19. Events

**Publishes:** `claim.adjudicated`, `claim.reversed`, `claim.rebilled`, `claim.rejected`, `claim.reprocessed`, `claim.adjustment_created`, `claim.accumulator_detected`, `claim.copay_fraud_flagged`, `claim.waste_detected`, `claim.afp_detected`, `dur.alert_generated`

**Subscribes to:** `member.eligibility_changed` (restacking), `plan.updated`, `formulary.updated`, `drug.price_updated`, `rule.updated`, `drug.ira_price_negotiated`

---

## 20. Performance

| Metric | Target |
|--------|--------|
| Adjudication latency (p95) | < 1,000ms |
| Adjudication latency (p50) | < 200ms |
| Throughput | 100M claims/year (300M+ architecture) |
| Claim history lookup | < 5ms (Redis) |
| Availability | 99.95% |

---

## 21. Test Scenarios

**Critical:** standard B1 adjudication, B2 reversal, B3 rebill, DUR catches interaction, COB applies correctly, compound pricing, sub-1-second p95, reprocessing deltas, each pricing model, cash-pay comparison, accumulator detection, copay fraud flag, therapeutic alternative returned, reasons for adjudication in plain English, claim trace stored, PDMP check, IRA MFP applied for Part D, buy-and-bill workflow, pharmacy reimbursement transparency

**Edge cases:** terminated member, non-formulary drug, duplicate claim, reversal for nonexistent claim, 25-ingredient compound, concurrent claims same member (race condition), claim spanning benefit year, copay ePA first-fill buy-down, AFP detection, AI auto-correct on malformed claim
- Override: create override for age rule, rebill passes, claim trace shows SKIPPED with override details, override expires and next fill re-evaluates, supervisor approval workflow, cannot override DUR hard stop, override rate monitoring alert

---

## 22. Session Decomposition

1. **Transaction parser:** full NCPDP D.0 parser/builder, all transaction types/segments/fields
2. **Adjudication pipeline:** eligibility → plan resolution → pricing model → rule execution → DUR → COB → pricing → response with reasons + trace
3. **Manufacturer protections:** accumulator/maximizer detection + adaptive response, copay fraud prevention (ShieldRx equivalent), AFP detection, copay ePA first-fill, buy-and-bill automation
4. **Intelligence layer:** therapeutic alternative routing, AI claim scrubbing, drug waste prevention, pharmacy reimbursement transparency
5. **Lifecycle:** reversal, rebill, reprocessing, restacking, compound handling, Redis claim history cache
