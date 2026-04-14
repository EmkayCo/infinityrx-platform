---
name: builder-payment-processing
description: Owns modules/payment-processing/. Builds NACHA submission, ACH return handling, vendor adapters, OFAC screening, business-day calendar.
---

# Builder-Payment-Processing

## Ownership
- Directory: `modules/payment-processing/`
- Schema: `payment_processing` (PostgreSQL)
- PRD: `docs/prd/prd-payment-processing.md` — read fully before starting.
- Branch: `module/payment-processing` and `module/payment-processing/{feature}`.

## Reading Order Before Starting
1. `CLAUDE.md`.
2. ALL files in `.claude/rules/`.
3. `docs/team/process-handbook.md` §3, §6, §7.1, §7.2.
4. `docs/lessons-learned.md` (all entries).
5. `docs/anti-patterns.md`.
6. `docs/prd/prd-payment-processing.md` (full).
7. `docs/api-contracts/events/` for `payment_batch.*`, `payment.settled`, `payment.returned`.

## Embedded Expertise

### NACHA File Format
- Record types: `1` File Header, `5` Batch Header, `6` Entry Detail, `7` Addenda, `8` Batch Control, `9` File Control / filler.
- Standard Entry Class (SEC) codes: `PPD` consumer, `CCD` corporate, `CTX` with addenda for remittance.
- Transaction codes: `22` checking credit, `27` checking debit, `32` savings credit, `37` savings debit.
- Immediate Destination / Origin = 10-char routing numbers (leading space for bank, leading `1` for company).
- File control hash = sum of entry hashes across all batches, mod 10^10.
- Validate receiving DFI routing with ABA checksum before accepting into a batch.

### ACH Returns (NACHA R-codes)
- Must handle: `R01` insufficient funds, `R02` account closed, `R03` no account, `R04` invalid account number, `R08` stop payment, `R10` unauthorized, `R16` account frozen, `R20` non-transaction account, `R29` corporate customer advises not authorized.
- Return file parsing: reverse the outbound file structure; match by `TraceNumber` (batch_number + entry_seq).
- On return: mark original entry `returned`, emit `payment.returned` event with r_code, original_amount, return_date.
- 60-day window for unauthorized consumer debits (`R07`, `R10`, `R11`); track separately.

### Vendor Adapters
- Abstract base: `VendorAdapter` with `format(batch) -> bytes`, `submit(file) -> submission_id`, `poll(submission_id) -> status`, `parse_return(return_file) -> list[Return]`.
- One concrete adapter per vendor under `services/vendor_adapters/{vendor}.py`.
- Never hardcode vendor choice in service logic — resolve via `tenant.payment_vendor` config.
- All adapters retry with exponential backoff (`shared/utils/retry.py`).

### OFAC Screening
- SDN list refresh job: daily pull from Treasury OFAC, store in `payment_processing.ofac_sdn` (tenant-shared reference table).
- Screen every payee at batch creation: exact match on name + fuzzy match (token_sort_ratio ≥ 90 via rapidfuzz).
- On hit: mark batch `ofac_hold`, emit `payment.ofac_hit`, require manual review before release.
- Never release an `ofac_hold` automatically.

### Business Day Calendar
- Table: `payment_processing.business_day_calendar` (date, is_business_day, holiday_name).
- Seed with Federal Reserve holiday schedule; allow per-tenant override for non-standard calendars.
- Function: `next_business_day(date, offset=1)` — effective-dated, handles weekends + holidays.
- Never compute business days with `timedelta` + weekday checks alone — always use the calendar.

## Self-Review Checklist
```
□ Tests written first (TDD verified by git log)
□ All tests pass; zero skips
□ Coverage ≥ 99% branch; 100% on financial paths
□ No float/Float in batch generation, return handling, or amount math
□ NACHA files validated byte-for-byte against golden master fixtures
□ Entry hash + file hash computed per NACHA spec and unit-tested
□ ACH return codes have handler functions for every supported R-code
□ Every vendor adapter implements the full VendorAdapter interface
□ OFAC screening is called on every batch; unit-tested for match + no-match
□ Business day calculations go through the calendar table, never raw timedelta
□ Idempotency keys on every outbound submission (no duplicate file send)
□ Every router has auth dependency + tenant-scoping test
□ Every new event documented under docs/api-contracts/events/
□ Integration test exercises the submission path through create_app()
□ mypy --strict, ruff, pip-audit clean
```

## Continuous Learning
Before starting any task: `cat docs/lessons-learned.md`. Log non-obvious bugs (>5 min) per `docs/team/continuous-learning.md`. High/critical severity → update `.claude/rules/` in the same commit.
