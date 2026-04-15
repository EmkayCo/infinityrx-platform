# PRD — Module 19: Eligibility & Benefit Verification / Real-Time Benefit Check (FINAL)

**Module:** EBV/EBI/RTBC
**Folder:** `modules/ebv-ebi/`
**Phase:** 5, Wave 3 (after Rules Engine)
**Dependencies:** Core Platform (1), Member Management (5), Plan Design (6), Drug Database (2)

---

## 1. Purpose

EBV/EBI/RTBC enables prescribers and pharmacies to verify patient coverage, check drug-specific benefits, and get real-time cost information BEFORE writing or filling a prescription. This module handles the full cycle: eligibility verification, benefit investigation, real-time prescription benefit checks, and member-facing cost transparency tools. It serves prescribers (via EHR integration), pharmacies (via switch), hub services (via API), and members (via portal/app).

---

## 2. Eligibility Verification (EBV)

**Inbound channels:** NCPDP E1 transaction (from pharmacy via switch), X12 270/271 (from provider/hub), API (from portal/hub partner), batch file (nightly eligibility feeds from payers).

**Response:** member active/inactive, plan details, group info, copay summary, pharmacy network, coverage dates, benefit phase status, deductible/OOP progress.

**Performance:** sub-500ms for real-time, batch within SLA window.

---

## 3. Benefit Investigation (EBI)

Deep coverage analysis for a specific drug for a specific member:

- Is drug covered? On formulary? Which tier?
- PA required? Step therapy? Quantity limit?
- Member cost estimate (copay, coinsurance, deductible remaining)
- Alternative drugs with lower cost (therapeutic alternatives from Rules Engine)
- Specialty pharmacy required?
- Site of care restrictions?
- **Accumulator/maximizer status:** is member on an accumulator or maximizer plan? If so, how much of the copay assistance benefit has been consumed?

Used by hub services teams, FRMs, and provider offices to determine coverage BEFORE prescribing. This accelerates time-to-therapy by identifying barriers upfront.

---

## 4. Real-Time Prescription Benefit Check (RTPB)

### NCPDP RTPB Standard Version 13 (Required Jan 1, 2027)

Patient-specific cost and coverage at point of prescribing. Prescriber queries from their EHR, InfinityRx returns:

- Patient-specific cost for requested drug
- Formulary status and tier
- Coverage restrictions (PA, ST, QL)
- **Alternative therapy response with cost comparison:** other drugs in same class with formulary tier and cost, showing potential savings
- Pharmacy options with price comparison (retail vs mail order vs specialty)
- Deductible/OOP progress

Integration via Surescripts RTPB network. Must comply with v13 standard format.

---

## 5. Member Cost Transparency Tools

Consumer-grade tools for the member portal and mobile app:

### Drug Cost Estimator
- Member enters drug name (search/autocomplete from Drug Database)
- Returns: cost under their plan, tier, any restrictions
- Shows lower-cost alternatives with savings amount

### Pharmacy Cost Comparison
- Same drug, different pharmacies, different prices
- Map view with distance and price
- Includes mail order and specialty options
- Shows which pharmacies are preferred/in-network

### Deductible/OOP Progress Tracker
- Visual progress bar showing where member is in benefit phases
- Deductible: $X of $Y met (XX%)
- OOP max: $X of $Y (XX%)
- Projected trajectory: based on current usage, when will they hit each phase?

### Refill Dashboard
- Current medications with next refill date
- One-tap refill request
- Drug interaction checker (self-service)
- Prescription transfer request

---

## 6. Hub Services Integration

For manufacturers using external hub services (ConnectiveRx, Mercalis, etc.):

- **Inbound API:** hub sends BV/BI requests, InfinityRx returns coverage details
- **Outbound API:** InfinityRx sends claim status updates, adherence alerts, accumulator detection alerts to hub
- **Standard RESTful API:** any hub provider can integrate (not proprietary)
- **For manufacturers without external hub:** InfinityRx provides built-in BV/BI/copay enrollment capabilities

---

## 7. Mobile App Features

Every competitive PBM now has a consumer-grade mobile app. The module provides backend APIs for:

- Digital ID card (always-current, replaces physical card)
- Drug cost lookup with pharmacy comparison
- Prescription management (current meds, refill history)
- Refill reminders with one-tap refill
- Drug interaction checker
- Deductible/OOP progress (visual bar)
- Pharmacy locator with real-time cost
- Secure messaging with pharmacist/care team
- PA status tracker
- Push notifications: lower-cost alternative found, refill due, PA decision, benefit phase change

---

## 8. Data Models

```
ebv_transactions (with response_time_ms), ebi_requests (with drug_ndc, coverage_result JSONB, alternatives JSONB, accumulator_status), rtpb_transactions (with v13 compliance flag), member_cost_lookups, pharmacy_cost_comparisons, hub_integration_log, digital_id_cards, member_notifications
```

---

## 9. API Endpoints

- `POST /api/v1/eligibility/verify` — real-time EBV (NCPDP E1 or API)
- `POST /api/v1/eligibility/batch` — batch verification
- `POST /api/v1/benefits/investigate` — drug-specific BV/BI
- `POST /api/v1/rtpb/check` — RTPB v13 transaction (Surescripts)
- `GET /api/v1/members/{id}/cost-estimate?ndc=` — member cost lookup
- `GET /api/v1/members/{id}/pharmacy-compare?ndc=&lat=&lng=` — pharmacy cost comparison
- `GET /api/v1/members/{id}/benefit-progress` — deductible/OOP tracker
- `GET /api/v1/members/{id}/medications` — current medications with refill dates
- `GET /api/v1/members/{id}/digital-card` — digital ID card data
- `POST /api/v1/hub/bv-request` — hub services BV/BI API
- `POST /api/v1/hub/status-update` — outbound to hub

---

## 10. Events

**Publishes:** `ebv.completed`, `ebi.coverage_verified`, `rtpb.response_sent`, `member.cost_lookup`, `member.alternative_found`, `member.refill_reminder_due`

**Subscribes to:** `member.enrolled`, `member.terminated`, `plan.updated`, `formulary.updated`, `claim.adjudicated` (update benefit progress)

---

## 11. Test Scenarios

**Critical:** EBV returns correct active/inactive, EBI returns correct tier and PA requirement, RTPB v13 response validates against standard, cost estimate matches actual adjudication result, pharmacy comparison returns correct prices sorted by distance, alternatives returned in cost order, accumulator status correctly reflected, hub API round-trip, digital card data correct

**Edge cases:** member with future effective date, drug not in formulary, member with zero claims (deductible fully remaining), specialty drug with site-of-care restriction, pharmacy cost comparison with zero in-network pharmacies nearby, RTPB timeout handling

---

## 12. Session Decomposition

1. **EBV/EBI engine:** eligibility verification (E1, 270/271, API, batch), benefit investigation with alternatives and accumulator detection
2. **RTPB:** Surescripts v13 integration, alternative therapy response, pharmacy cost comparison
3. **Member tools:** cost estimator, pharmacy comparison, deductible/OOP tracker, refill dashboard, digital ID card, notification engine
4. **Hub integration:** inbound/outbound API, hub partner management, built-in hub capabilities for manufacturers without external hub
