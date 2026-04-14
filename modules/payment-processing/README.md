# Module: payment-processing

## Purpose

The payment-processing module is responsible for all outbound ACH/check/wire
payment execution on behalf of the billing module. It manages vendor adapter
registrations (multiple clearinghouse integrations), generates NACHA fixed-width
ACH files, handles ACH return codes (80+ standard codes with configurable default
actions), applies OFAC sanctions screening before every submission, tracks the
full settlement life-cycle (submitted → settled → returned), maintains a
positive-pay register for check fraud prevention, and handles vendor enrollment
for new pharmacy bank accounts. A reconciliation service cross-checks bank
settlement reports against internal submission records.

## Dependencies

- `shared.db.session` — async SQLAlchemy session factory (session is per-request)
- `shared.events.bus` — event publishing (via `_shim/events.py` until shim retired)
- `shared.utils.money` — `penny_allocate` for batch splits
- PostgreSQL schema: `payment_processing`
- RabbitMQ (local) / Azure Service Bus (prod)

External service calls:
- OFAC SDN List API (screened on each submission)
- Clearinghouse vendor APIs (abstracted via `VendorAdapter`)

## How to run tests

```bash
uv run pytest modules/payment-processing/tests -q
```

Golden NACHA output test (requires `freezegun` for deterministic dates):

```bash
uv run pytest modules/payment-processing/tests/golden -q
```

Integration tests (require live infrastructure) are marked `@pytest.mark.integration`:

```bash
uv run pytest modules/payment-processing/tests -q -m integration
```

## API endpoint summary

All routes served from `modules/payment-processing/src/app.py`.

| Group | Endpoints |
|---|---|
| Vendor adapters | `GET /vendors`, `POST /vendors`, `PUT /vendors/{id}`, `GET /vendors/{id}/health` |
| Submissions | `GET /submissions`, `GET /submissions/{id}`, `POST /submissions/{id}/retry` |
| Settlements | `GET /settlements`, `GET /settlements/pending`, `POST /settlements/manual` |
| Returns | `GET /returns`, `POST /returns`, `GET /return-codes` |
| Enrollments | `GET /enrollments`, `POST /enrollments`, `GET /enrollments/unenrolled` |
| Dashboard | `GET /dashboard`, `GET /reconciliation` |

## Event topics produced

Published from `payment-processing/src/events/publishers.py`:

| Topic | Trigger |
|---|---|
| `payment.file_generated` | NACHA/check file written to SFTP staging |
| `payment.submitted` | Batch submitted to clearinghouse |
| `payment.settled` | Individual payment confirmed settled |
| `payment.returned` | ACH return code received |
| `payment.return_suspicious` | Return code pattern flagged (possible fraud) |
| `payment.failed` | Submission failed after retries |
| `vendor.status_changed` | Vendor adapter status transitioned |

## Event topics consumed

Subscribed via `payment-processing/src/events/consumers.py`:

| Topic | Handler |
|---|---|
| `payment_batch.submitted` | Trigger NACHA file generation for approved batch |
| `fwa.payment_hold_placed` | Hold payment submission pending investigation |
| `fwa.payment_hold_released` | Release held submission |

**Known gap (audit CR-01):** Consumer `CONSUMER_ROUTING` dict exists but no
`bus.subscribe()` is invoked at startup — handlers are unreachable in production.

**Known gap (audit CR-11):** Consumer handlers lack `@idempotent_handler`
decorator — duplicate event delivery can cause double-submission of ACH files.
