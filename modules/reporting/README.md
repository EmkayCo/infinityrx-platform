# Module: reporting

## Purpose

The reporting module provides the platform's analytics and compliance reporting
surface. It manages report definitions, on-demand and scheduled report runs,
tenant-customizable dashboards, filter presets, and data-source field discovery.
Regulatory submission tracking (CMS, state) and actuarial repricing models are
built-in. The Star Ratings subsystem computes CMS Part D Star measure adherence
(PDC-based) and projects future ratings given current gap-closure pace. Reports
can be exported in Excel, PDF, or JSON formats; PDF reports containing PHI are
watermarked "CONFIDENTIAL — CONTAINS PHI" per `phi-compliance.md`.

## Dependencies

- `shared.db.session` — async SQLAlchemy session factory
- `shared.events.bus.EventBus` — event publishing and consumption
- `shared.crypto` — `EncryptedString` for PHI columns in report metadata
- `openpyxl` — Excel export
- `jinja2` — PDF report templating
- PostgreSQL schema: `reporting`
- RabbitMQ (local) / Azure Service Bus (prod)

## How to run tests

```bash
uv run pytest modules/reporting/tests -q
```

Integration tests require live PostgreSQL:

```bash
uv run pytest modules/reporting/tests -q -m integration
```

**Known gap (audit M-17):** No golden-master tests exist for generated financial
output formats (Excel, PDF). Correctness of rendered output is untested.

## API endpoint summary

All routes served from `modules/reporting/src/` (FastAPI app).

| Group | Endpoints |
|---|---|
| Reports | `GET /reports`, `GET /reports/{id}`, `POST /reports`, `POST /reports/{id}/run`, `GET /reports/{id}/runs`, `GET /runs/{id}` |
| Dashboards | `GET /dashboards`, `GET /dashboards/{id}`, `POST /dashboards`, `PUT /dashboards/{id}`, `POST /dashboards/my` |
| Filter presets | `GET /filter-presets`, `POST /filter-presets`, `DELETE /filter-presets/{id}` |
| Data sources | `GET /data-sources`, `GET /data-sources/{source}/fields` |
| Preview | `POST /preview` |
| Client summaries | `GET /client/claims`, `GET /client/billing`, `GET /client/program-performance`, `GET /client/fwa-summary` |
| Regulatory | `GET/POST /regulatory`, `PUT /regulatory/{id}`, `GET /regulatory/deadlines` |
| Actuarial | `GET /actuarial-models`, `POST /actuarial-models/{id}/reprice` |
| Star Ratings | `GET /star-ratings`, `GET /adherence/{measure}`, `GET /adherence-gaps`, `GET /star-projections` |

**Known gap (audit CR-01):** Scheduled report delivery is not wired at startup —
reports run on-demand only.

## Event topics produced

Published from `reporting/src/events/publishers.py`:

| Topic | Trigger |
|---|---|
| `report.generated` | Report run completed successfully |
| `report.delivered` | Report delivered via configured channel (email, SFTP) |
| `report.delivery_failed` | Delivery attempt failed |
| `regulatory.deadline_approaching` | Regulatory filing deadline is within warning window |
| `quality.measure_at_risk` | Star Rating measure PDC gap is approaching threshold |

## Event topics consumed

Handled via `reporting/src/events/consumers.py`:

| Topic | Handler |
|---|---|
| `billing.journal_entries` | Update billing data snapshots for financial reports |
| `fwa.claim_flagged` | Increment FWA metrics in dashboard |
| `fwa.investigation_opened` | Update investigation counts in FWA summary |
| `fwa.investigation_resolved` | Update resolution metrics |
| `prefund.critical` | Auto-trigger prefund alert report |
| `quality.measure_at_risk` | Auto-trigger PDC gap report for at-risk measure |

**Known gap (audit CR-01):** `CONSUMER_ROUTING` dict is defined but no
`bus.subscribe()` call is made at startup — consumer handlers are unreachable
in production.
