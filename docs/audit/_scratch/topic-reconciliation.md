# Event Topic Reconciliation (CR-01)

Generated: 2026-04-14 by Teammate 2 (event-wiring agent)

## RESOLVED: payment_batch.generated → payment_batch.submitted

**Producer:** `modules/billing/src/services/ap.py` (via `generate_batch`)
**Old topic:** `payment_batch.generated`
**New topic:** `payment_batch.submitted`
**Consumer:** `modules/payment-processing/src/events/consumers.py` expected `payment_batch.submitted`
**Action:** Updated `ap.py` direct bus call + `publishers.py` `publish_payment_batch_submitted`.
**Evidence:** `modules/payment-processing/src/utils/constants.py:69` defines `EVENT_PAYMENT_BATCH_SUBMITTED = "payment_batch.submitted"`

## Complete Topic Map (as of 2026-04-14)

### Publishers → Consumers

| Topic | Publisher Module | Consumer Modules | Status |
|-------|----------------|-----------------|--------|
| `claim.adjudicated` | adjudication-engine (TBD) | reclaimrx, member-management, billing, medical-claims | wire pending |
| `claim.reversed` | adjudication-engine (TBD) | reclaimrx, member-management, billing | wire pending |
| `claim.ingested` | billing | dataiq, reclaimrx | wire pending |
| `claim.classified` | billing | (no consumer yet) | wire pending |
| `payment_batch.submitted` | billing (was .generated) | payment-processing | FIXED CR-01 |
| `payment_batch.voided` | billing | (no consumer yet) | wire pending |
| `invoice.generated` | billing | (no consumer yet) | wire pending |
| `ar.payment_received` | billing | (no consumer yet) | wire pending |
| `budget.alert_fired` | billing | reporting | wire pending |
| `ap.created` | billing (ap.py) | reclaimrx | wire pending |
| `ap.settled` | billing | reclaimrx | wire pending |
| `fwa.claim_flagged` | reclaimrx | ai-nlp, reporting, dataiq | wire pending |
| `fwa.investigation_opened` | reclaimrx | ai-nlp, reporting | wire pending |
| `fwa.investigation_resolved` | reclaimrx | reporting | wire pending |
| `fwa.pharmacy_risk_elevated` | reclaimrx | pharmacy-directory | WIRED in pharmacy-directory.app |
| `fwa.credentialing_risk_elevated` | reclaimrx | pharmacy-directory | WIRED in pharmacy-directory.app |
| `fwa.payment_hold_placed` | reclaimrx | payment-processing | wire pending |
| `fwa.payment_hold_released` | reclaimrx | payment-processing | wire pending |
| `payment.auto_posted` | edi-compliance | billing | wire pending |
| `payment.unmatched_claim` | edi-compliance | billing | wire pending |
| `payment.settled` | payment-processing | dataiq | wire pending |
| `payment.return_suspicious` | payment-processing | reclaimrx | wire pending |
| `member.enrolled` | member-management | billing | wire pending |
| `pharmacy.application_submitted` | pharmacy-directory | reclaimrx | wire pending |
| `pharmacy.ownership_changed` | pharmacy-directory | reclaimrx | wire pending |
| `billing.journal_entries` | billing | reporting | wire pending |
| `prefund.critical` | billing? | reporting | wire pending |
| `quality.measure_at_risk` | reporting | reporting (self) | wire pending |

### Notes
- `billing.journal_entries` is in reporting consumers but billing publishers only has `claim.ingested`, not `billing.journal_entries`. Investigate.
- `prefund.critical` has no obvious publisher — likely billing or payment-processing should publish this.
- `fwa.pharmacy_risk_elevated` topic in reclaimrx publishers is `fwa.pharmacy_risk_elevated` but pharmacy-directory subscribes to `fwa.pharmacy_risk_elevated` — MATCH.
- `fwa.credentialing_risk_elevated` — reclaimrx does NOT publish this. Pharmacy-directory subscribes to it. Publisher needs to be added to reclaimrx.
