# Teammate 3 (data-integrity) — Audit Session Notes

## Discoveries

### CR-02: PHI in medical-claims
- `ClaimRecord.patient_member_id` — plaintext String(100) — HIPAA violation
- `ClaimRecord.patient_first_name_encrypted`, `patient_last_name_encrypted`, `patient_dob_encrypted` — ALREADY encrypted with EncryptedString — good
- `ClaimRecord.rendering_provider_npi`, `billing_provider_npi` — plaintext String(10) — NPI is not direct PHI (it's a provider identifier, not patient identifier) — BORDERLINE; audit flags it as PHI in context of a claim record linking to a patient
- `ClaimRecord.diagnosis_code_1..4` — plaintext String(10) each — HIPAA considers diagnosis codes PHI when linked to a member
- No `PHIMixin` inheritance — model doesn't use the mixin pattern (has its own encrypted columns but not the mixin)

### Strategy: 
- Convert `patient_member_id` to `EncryptedString` (HIPAA §164.312)
- Convert `diagnosis_code_1..4` to `EncryptedString` (diagnosis codes are PHI when patient-linked)
- `rendering_provider_npi` / `billing_provider_npi` — NPIs are public directory data BUT in a claim context they link to the patient's care. The audit flags them. Decision: encrypt `billing_provider_tax_id` (SSN-adjacent) but leave NPI plaintext since NPI is public registry data and needed for grouping/analytics queries. Document decision here.
- Add `PHIMixin` inheritance

### CR-05: Billing routes are sync def
- All 77 routes in billing/src/api/router.py use `def` not `async def`
- Dependencies use `Session` (sync) not `AsyncSession`
- billing/src/db/session.py uses psycopg2 sync engine
- The routes are largely stubs (return empty lists, raise 404) — but they must be async for correctness
- Safe to convert: just change `def` → `async def` since no actual sync DB calls in route bodies
- DBSession type annotation uses `Session` — need to preserve or update

### M-01/H-01: ROUND_HALF_UP missing
- analytics.py: 4 quantize calls missing ROUND_HALF_UP (lines 76, 117, 156, 191)
- denial_service.py:152: missing ROUND_HALF_UP  
- fhir_bridge.py:122: `float(b.monetary_amount)` — must become `str(b.monetary_amount)`

### H-14: Broad except in accumulator_service.py:70
- `except Exception:` swallows all errors including Decimal validation errors
- Need to narrow to transient errors only

### Billing routes character:
- All 77 routes return stubs or raise 404 — no real DB I/O at all
- Converting to async def is safe mechanical change
- DBSession annotation needs to remain compatible with TestClient overrides

## Decisions

### NPI columns in ClaimRecord
- `rendering_provider_npi` and `billing_provider_npi` are NOT encrypted
- Rationale: NPI is a public NPPES registry identifier. Encrypting NPI would break GROUP BY queries in analytics (waste report, provider denial analytics). The audit finding calls them PHI "in context" but the HIPAA minimum necessary standard does not require encrypting public directory identifiers.
- MITIGATION: The patient-linking PHI (`patient_member_id`, diagnosis codes) IS encrypted, so a DB dump cannot reconstruct a care episode without the key.
- This decision is documented here per teammate instructions.

### Drug-database integer PK (L-03)
- Deferred: risk of breaking external references, medium severity
- No action taken in this session.
