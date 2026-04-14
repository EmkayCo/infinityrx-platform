# Module: billing

## Purpose

The billing module manages the full financial life-cycle for a PBM: it receives
adjudicated pharmacy claims from the event bus, routes them through configurable
payment rules, generates NACHA ACH files, produces client invoices, maintains
accounts-payable (AP) and accounts-receivable (AR) ledgers, and keeps a
tamper-evident hash-chained journal of every financial entry. It supports
multi-route payment (ACH, check, wire, card), an 8-type fee engine, program
budget tracking with alert thresholds, and period-close controls for
month-end accounting.

## Dependencies

- `shared.db.session` — async SQLAlchemy session factory
- `shared.events.bus.EventBus` — event publishing (currently via local shim)
- `shared.utils.money` — `penny_allocate` for all splits
- `shared.crypto` — `EncryptedString` for any PHI columns
- PostgreSQL schema: `billing`
- RabbitMQ (local) / Azure Service Bus (prod) — event ingestion and publishing

External services consumed via event bus (see **Events consumed** below).

## How to run tests

```bash
uv run pytest modules/billing/tests -q
```

Integration tests (require live PostgreSQL + RabbitMQ) are marked
`@pytest.mark.integration` and excluded from the default run:

```bash
uv run pytest modules/billing/tests -q -m integration
```

## API endpoint summary

All routes are under `/billing/v1/`. The module is a separate FastAPI service
started from `modules/billing/src/main.py`.

| Group | Endpoints |
|---|---|
| Claims | `POST /claims` (ingest), `GET /claims`, `GET /claims/{id}` |
| Routing rules | `GET/POST /routing-rules`, `PUT /routing-rules/{id}`, `POST /routing-rules/test` |
| Accounts payable | `GET /ap-records`, `GET /ap-records/summary`, `GET /ap-records/{id}` |
| Payment batches | `GET/POST /payment-batches`, `GET /payment-batches/{id}`, `POST /payment-batches/{id}/validate`, `POST .../approve`, `POST .../submit`, `POST .../void` |
| Settlements | `GET /payment-batches/{id}/payments`, `POST /payments/{id}/settle`, `GET /unmatched-payments` |
| Invoicing config | `GET/POST /invoicing-configs`, `PUT /invoicing-configs/{id}` |
| Invoices | `GET/POST /invoices`, `GET /invoices/{id}`, `GET .../pdf`, `POST .../approve`, `POST .../send`, `POST .../void`, `GET .../line-items` |
| Accounts receivable | `GET /ar-records`, `GET /ar-records/aging`, `POST /ar-records/{id}/payment`, `POST .../dispute`, `POST .../write-off` |
| Journal | `GET /journal`, `GET /journal/summary`, `GET /journal/export`, `POST /journal/close-period` |
| Fee configs | `GET/POST /fee-configs`, `PUT /fee-configs/{id}` |
| Program budgets | `GET/POST /program-budgets`, `PUT /program-budgets/{id}`, `GET /program-budgets/dashboard`, `GET /program-budgets/snapshots`, `GET /program-budgets/alerts`, `POST /program-budgets/alerts/{id}/acknowledge` |

**Known gap (audit CR-07):** `main.py` mounts `app = FastAPI(...)` with no
middleware, no DLQ router, and no `create_app()` factory. SecurityHeaders,
RateLimitMiddleware, and tenant isolation are not active in production.

## Event topics produced

| Topic | Trigger |
|---|---|
| `claim.ingested` | Claim accepted and routed |
| `claim.classified` | Routing decision applied |
| `payment_batch.generated` | Batch created and ready for submission |
| `payment_batch.voided` | Batch voided |
| `invoice.generated` | Invoice issued to client |
| `ar.payment_received` | AR record updated with incoming payment |
| `budget.alert_fired` | Budget threshold crossed |

**Known issue (audit H-02):** Publishers define a module-local `EventBus`
Protocol instead of using `shared.events.bus.EventBus`.

## Event topics consumed

Handled via `billing/src/events/consumers.py`:

| Topic | Handler |
|---|---|
| `member.enrolled` | Seed billing record for new member |
| `claim.adjudicated` | Ingest adjudicated claim for AP routing |
| `payment.vendor_confirmed` | Mark AP record confirmed |
| `payment.ach_return_received` | Handle ACH return, update AP status |

**Known gap (audit CR-01):** `consumers.py` handlers exist but no
`bus.subscribe()` call is made at startup — these handlers are dead code
in production.
