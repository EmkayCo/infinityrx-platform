# Member Management Module

**Phase:** 3  
**Status:** Session 3 implemented (accumulator DB persistence, benefit year reset, member merge, events, jobs)

## Overview

Member enrollment, eligibility, and benefit tracking. Answers: "Is this person covered, and what are their benefits?"

## Capabilities (Sessions 1–3)

- **Groups/employers** — group enrollment with default plan assignment
- **Members** — demographics with PHI encrypted at rest (AES-256-GCM via `EncryptedString`)
- **Coverage periods** — effective/termination dating, plan assignment, benefit year
- **Accumulators** — deductible, OOP max, MOOP, TrOOP, copay cap, benefit max (Decimal, penny-perfect)
- **Accumulator ledger** — every change audit-logged with running total
- **Part D benefit phase engine** — deductible → initial coverage → coverage gap → catastrophic
- **Copay assistance tracking** — standard / accumulator / maximizer plan types
- **LEP calculation** — Part D Late Enrollment Penalty
- **834 EDI parser** — pluggable loop handler design
- **CSV/Excel enrollment parser** — configurable field mapping per client
- **FastAPI app** — `create_app()` with SecurityHeadersMiddleware, RateLimitMiddleware, DLQ router
- **Eligibility check service** — real-time check, <5ms cached, <25ms DB
- **Redis eligibility cache** — `tenant:{tenant_id}:eligibility:{member_id}:{bin}:{pcn}:{group}`
- **COB management** — primary/secondary/tertiary payer sequencing, active-date filtering, duplicate sequence validation
- **270/271 HIPAA X12 transactions** — parse inbound 270, build eligible/ineligible 271 response
- **Coverage period API** — GET/POST/PUT coverage periods per member
- **COB API** — GET/POST/PUT/DELETE COB records per member
- **Accumulator DB service** — `AccumulatorDbService` wires math to ORM; every apply/reverse writes a ledger row with `running_total` invariant enforced
- **Benefit year reset job** — resets expired accumulators with configurable carryover rules per `accumulator_type`
- **Member merge workflow** — cross-tenant-isolated; transfers coverage periods, accumulators, COB to surviving member; sets `status="merged"` and `merged_into_id`
- **Event publishing** — all 9 event types (`member.enrolled`, `.updated`, `.terminated`, `.plan_changed`, `.accumulator_updated`, `.benefit_phase_changed`, `.cob_changed`, `.merged`, `.retroactive_enrollment`) via `EventEnvelope` (ordering_key=member_id, Decimals as str)
- **Event consuming** — `claim.adjudicated` and `claim.reversed` with `idempotent_handler`, unknown fields ignored
- **Dependent aging job** — daily termination of dependents reaching plan age limit
- **Retroactive enrollment detection** — flags enrollments with past effective dates, configurable max lookback days

## Key Technical Decisions

### Financial Precision
All accumulator math uses `Decimal` with `ROUND_HALF_UP`. No floats anywhere. 100% branch coverage on every financial path.

### PHI Encryption
- PHI columns (`first_name`, `last_name`, `date_of_birth`, `ssn`, address, phone, email) use `EncryptedString` (AES-256-GCM)
- `PHIMixin` from `shared/db/models/phi_mixin.py` for standard encrypted columns
- Tenant-scoped AAD binds ciphertext to tenant — cross-tenant decryption fails

### 834 Parser Design
Pluggable `BaseLoopHandler` design: register handlers per X12 loop ID (2000, 2100, etc.). The default `_Loop2000Handler` handles member-level segments (INS, REF, DTP, NM1, PER, N3, N4, DMG, HD). Custom handlers can be registered for additional loops without modifying core parse logic.

### Eligibility Cache
Key pattern: `tenant:{tenant_id}:eligibility:{member_id}:{bin}:{pcn}:{group}`
Default TTL: 1 hour. Cache invalidated on enrollment/COB change via `EligibilityService.invalidate_cache()`.
Falls back to direct DB query when Redis is unavailable (redis=None).

### 270/271 Design
`X12Parser.parse_270()` extracts: member_id, date_of_service, date_of_birth, payer_id, trace_number, service_type_codes.
`X12ResponseBuilder.build_eligible_271()` / `build_ineligible_271()` emit standards-compliant 005010X279A1 transactions.

### Security
- Input validation uses `re.fullmatch()` / `\A...\Z` anchors (LESSON-004) for BIN, SSN, person_code, state
- All PHI access requires explicit `PhiAccessLevel` parameter (full/partial/redacted)
- `Cache-Control: no-store` on every response containing PHI
- COB payer_sequence validated against enum at API layer

## Running Tests

```bash
.venv/bin/pytest modules/member-management/tests/ --cov=modules/member-management/src --cov-branch
```

## Directory Structure

```
modules/member-management/
├── src/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── members.py       # member CRUD
│   │   │   ├── groups.py        # group management
│   │   │   ├── enrollment.py    # file upload/preview/process
│   │   │   ├── eligibility.py   # GET /eligibility, POST /eligibility/270
│   │   │   ├── coverage.py      # coverage periods
│   │   │   └── cob.py           # COB records
│   │   └── schemas/             # Pydantic request/response models
│   ├── infrastructure/          # SecurityHeadersMiddleware, RateLimitMiddleware
│   ├── models/                  # SQLAlchemy ORM (member_mgmt schema)
│   ├── events/
│   │   ├── publishers.py        # MemberEventPublisher — all 9 event types
│   │   └── consumers.py         # ClaimAdjudicatedConsumer, ClaimReversedConsumer
│   ├── jobs/
│   │   ├── benefit_year_reset.py   # BenefitYearResetJob — carryover rules
│   │   ├── dependent_aging.py      # DependentAgingJob — age-out termination
│   │   └── retroactive_enrollment.py  # RetroactiveEnrollmentDetector
│   ├── services/
│   │   ├── accumulator.py       # AccumulatorService, PartDPhaseEngine, calculate_lep
│   │   ├── accumulator_db.py    # AccumulatorDbService — DB persistence + ledger invariant
│   │   ├── cob_service.py       # CobService — payer sequencing, active-date filtering
│   │   ├── csv_parser.py        # CsvEnrollmentParser with FieldMapping
│   │   ├── edi_834_parser.py    # Edi834Parser (pluggable loop handlers)
│   │   ├── eligibility_service.py  # EligibilityService — cache + DB check
│   │   ├── member_service.py    # PHI masking, member CRUD
│   │   ├── merge_service.py     # MergeService — cross-tenant-isolated member merge
│   │   └── x12_270_271.py       # X12Parser (270) + X12ResponseBuilder (271)
│   └── main.py                  # create_app() with all middleware
└── tests/
    ├── integration/             # create_app() middleware tests (LESSON-006)
    └── unit/                    # accumulator math+DB, events, merge, jobs, parsers, PHI, routes
```
