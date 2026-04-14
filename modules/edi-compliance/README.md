# Module: edi-compliance

Phase 4 — X12 EDI transaction backbone for the InfinityRx Enterprise PBM Platform.

## Overview

Handles all HIPAA 5010 X12 EDI transactions: generation, parsing, 4-level validation, and auto-posting. Serves as the interchange layer between the PBM platform and external payers, clearinghouses, and trading partners.

## Session 1 — Implemented

- X12 engine core: delimiter detection, segment builder/parser, ISA fixed-width handling
- Envelope builder: ISA/GS/ST/SE/GE/IEA with SAVEPOINT-compatible control number sequences
- 835 Remittance Advice generator (005010X221A1) and parser
- 837P Professional Claim generator (005010X222A2)
- 270 Eligibility Inquiry generator (005010X279A1)
- 4-level validator: L1 Syntax, L2 IG, L3 Business rules (NPI Luhn), L4 Companion Guide
- 835 auto-posting service: emits `payment.auto_posted` events (event-driven, no direct Billing writes)
- REST API: generate (835/837P/270), parse (835/validate), trading partners, compliance dashboard
- Golden master tests: byte-for-byte deterministic comparison with fixed timestamps
- 193 tests, 99.48% coverage

## Sessions 2-4 — Planned

- Session 2: 837I/D, 271/276/277, code set validation, scrubbing, predictive denial scoring
- Session 3: 278 PA, 275 clinical attachments, 834 enrollment, 999/TA1 ack, FHIR R4 bridge, NCPDP Batch 1.2
- Session 4: AS2/SFTP transport, clearinghouse adapters, monitoring dashboard, certificate lifecycle

## Architecture

```
src/
  api/           — FastAPI route handlers (generate, parse, trading_partners, compliance)
  models/        — SQLAlchemy ORM models (edi schema)
  services/      — Business logic (auto_posting)
  x12/
    delimiters.py       — ISA delimiter auto-detection
    segments.py         — Segment builder/parser, ISA padding
    envelope.py         — Interchange/functional group envelope
    control_numbers.py  — Atomic SELECT FOR UPDATE sequence generation
    generators/         — gen_835, gen_837p, gen_270
    parsers/            — parse_835
    validators/         — 4-level validator
  transport/     — Future: AS2, SFTP adapters
  main.py        — FastAPI app factory (create_app)
migrations/
  versions/
    0001_edi_baseline.py   — Initial edi schema
tests/
  golden_master/ — Byte-for-byte reference files + tests
  integration/   — create_app() route tests (LESSON-006)
  unit/          — Component-level tests
```

## Key Design Decisions

- ISA06/ISA08 are NEVER stripped — 15-char fixed-width fields preserved per X12 spec
- Delimiter auto-detection from ISA bytes [3], [104], [105] — no assumed defaults
- Control numbers use `SELECT FOR UPDATE` for atomicity under 50+ concurrent requests
- 835 payment date: reads BPR16 (12 empty elements between BPR04 and BPR16) with DTM*405 fallback
- All amounts: `Decimal` with `ROUND_HALF_UP`, serialized as `str()` in event payloads
- Auto-posting is event-driven only — emits `payment.auto_posted`, never writes to Billing directly
- Python 3.9 compatible: `Optional[X]` not `X | None`, `List[X]` not `list[X]` in Pydantic models

## Running Tests

```bash
cd modules/edi-compliance
python3 -m pytest tests/ --cov=src --cov-report=term-missing
```

## Environment Variables

| Variable | Description |
|---|---|
| `ENCRYPTION_KEY_ACTIVE` | Base64 AES-256 key for PHI encryption |
| `JWT_SECRET` | JWT signing secret (32+ chars) |
| `DATABASE_URL` | PostgreSQL connection string |
