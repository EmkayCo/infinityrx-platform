# PRD — Module 20c: Pharmacy Portal — FINAL

**Module:** Pharmacy Portal (Pharmacy-Facing)  
**Folder:** `portal/pharmacy/`  
**Priority:** Phase 4B  
**Dependencies:** Core Platform (1), Billing (11), Payment (12), Pharmacy Dir (3), Drug DB (2), EDI (13)  

---

## 1. Purpose

The Pharmacy Portal is the external-facing interface for network pharmacies. Pharmacists and pharmacy staff use it to check claim status, view remittance, manage credentialing, verify drug coverage, and communicate with InfinityRx. It replaces phone calls, faxes, and email for 90% of pharmacy-to-PBM interactions.

**Design philosophy:** pharmacists are BUSY. They have a patient at the counter waiting. Every task must be completable in ≤60 seconds. Search-first design — pharmacist types a claim number or member ID and gets an instant answer.

---

## 2. Tech Stack

Shared with Operator Portal. Deployed as `pharmacy.infinityrx.com`.

---

## 3. Authentication

- Login via Core Platform auth (JWT + MFA)
- Pharmacy user linked to pharmacy NPI(s) — can only see claims for their pharmacy
- Multi-location support: chain pharmacy users can have access to multiple NPIs
- Roles: **Pharmacy Admin** (full access + user management), **Pharmacist** (claims + coverage + messaging), **Billing Staff** (payments + remittance only)

---

## 4. Pages & Features

### 4.1 Dashboard
- **Today's claims**: count and dollar total of claims processed today for this pharmacy
- **Pending payments**: total outstanding, next expected payment date and amount
- **Action items**: claims needing attention (reversals, rejections, PA required), credentialing documents expiring
- **Quick actions**: large buttons — "Check Claim Status", "Verify Coverage", "View Remittance", "Submit Question"
- **Announcements**: network changes, formulary updates, system notifications

### 4.2 Claim Lookup (THE #1 Feature)
- **Search bar** (prominent, top of page): enter claim number, auth number, Rx number, member ID, or date range
- **Instant results**: claim detail shows: status (paid/pending/rejected/reversed), amounts (billed, allowed, paid, patient pay), drug, date of service, rejection reason (if rejected), payment date and check/EFT number (if paid)
- **Claim history**: all claims for this pharmacy, filterable by date range, drug, member, status
- **Rejection help**: if claim was rejected, show: rejection code, plain-English explanation, recommended action ("Resubmit with prior auth number" or "Contact prescriber for new prescription")
- **Reversal tracking**: reversed claims show original claim + reversal reason

### 4.3 Remittance / Payment
- **Payment history**: all payments received with check/EFT number, date, amount
- **835 remittance viewer**: view electronic remittance advice in human-readable format (not raw X12)
  - Claim-by-claim breakdown: claim number, drug, billed amount, paid amount, adjustments with reason codes, patient responsibility
  - Totals: total paid, total adjustments by category (contractual, patient, other)
  - Download: PDF, CSV, or raw 835 EDI
- **Payment discrepancy tool**: if pharmacist believes a claim was underpaid, submit a payment inquiry with supporting documentation
- **Reconciliation**: match payments to submitted claims. Highlight unmatched claims.

### 4.4 Coverage / Formulary Verification
- **Drug coverage check**: enter drug name or NDC → shows: covered (yes/no), tier, copay, prior auth required, quantity limits, step therapy requirements, preferred alternatives
- **Member eligibility check**: enter member ID + DOB → shows: eligible (yes/no), plan name, BIN/PCN/Group, benefit summary (not full PHI — just coverage status)
- **Formulary search**: browse formulary by therapeutic class. Show preferred drugs with tier and copay.
- **PA status check**: enter PA number → shows: status (approved/pending/denied), approval date, expiry date, approved quantity/days

### 4.5 Credentialing & Network
- **Credentialing status**: current status (active, pending, under review), credential checklist with expiry dates
- **Document upload**: upload required documents (state license, DEA certificate, liability insurance, W-9) via drag-and-drop
- **Renewal reminders**: credentials expiring within 90 days highlighted with "Upload Renewal" button
- **Network participation**: which InfinityRx networks this pharmacy belongs to, contract terms (view-only), effective dates

### 4.6 Pharmacy Profile
- **Demographics**: address, phone, fax, hours, pharmacist-in-charge (view from Pharmacy Directory, request changes)
- **Banking**: view payment method on file (masked account number). Request banking change (goes to IFX operator for verification).
- **Remittance preferences**: choose delivery method (portal, email, SFTP, fax)
- **Contacts**: manage pharmacy staff users (Pharmacy Admin only)

### 4.7 Secure Messaging
- **Message center**: threaded conversations with IFX team
- **Categories**: claim inquiry, payment discrepancy, credentialing question, general question, PA request
- **Attachments**: upload supporting documents (prescription copies, invoices)
- **Response SLA**: show expected response time per category (24 hours for claims, 48 hours for credentialing)

### 4.8 AI-Powered Help (from AI/NLP Module)
- **Chatbot**: "Ask InfinityRx" button opens chatbot for common questions:
  - "Why was claim #12345 rejected?" → pulls rejection reason and explains in plain English
  - "When will I receive payment for batch #789?" → checks payment processing status
  - "What's the copay for Lisinopril 10mg for member ID X?" → runs coverage check
- **Escalation**: if chatbot can't answer, seamlessly creates a secure message to IFX team with conversation context

---

## 5. UX Patterns

- **Speed-first**: claim lookup returns results in <1 second. No pagination — instant search.
- **Search-prominent**: search bar is the largest element on every page. Pharmacist should never need more than 1 click + 1 search to find a claim.
- **835 humanization**: remittance advice displayed as a clean table, NOT raw X12. Adjustment codes translated to plain English. "CO-45: Charges exceed your contracted/legislated fee arrangement" → "Contractual adjustment: your billed amount exceeded the contracted rate."
- **Mobile responsive**: pharmacists may check claim status from a tablet behind the counter. Claim lookup and coverage check must work on tablet.
- **Offline resilience**: if API is slow, show cached data from last visit with "Data from [timestamp]" indicator.
- All shared UX patterns from Operator Portal (skeleton loading, error boundaries, export, tooltips, dark mode, accessibility)

---

## 6. Session Decomposition

1. **Shell + auth + dashboard + claim lookup**: Next.js app, pharmacy auth (NPI-scoped), dashboard with today's claims and quick actions, claim search with instant results, claim detail page, rejection reason helper
2. **Remittance + coverage + credentialing**: 835 remittance viewer (humanized), payment history, payment discrepancy tool, drug coverage check, member eligibility check, formulary search, PA status check, credentialing status page, document upload wizard
3. **Profile + messaging + chatbot**: pharmacy profile management, banking change request, remittance preferences, secure messaging center, AI chatbot integration, announcements
