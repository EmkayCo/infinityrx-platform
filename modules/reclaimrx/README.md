# Module: reclaimrx

## Purpose

ReclaimRx is the platform's fraud, waste, and abuse (FWA) detection and recovery
engine. It evaluates pharmacy claims in real-time against a configurable rule set,
applies an XGBoost ML scoring model for fraud probability, detects suspicious
dispensing communities via graph analysis (using NetworkX), manages investigations
through a full work-item life-cycle (open → activity → hold → resolve), tracks
financial recovery demands and collections, maintains provider and member risk
profiles, and accepts anonymous or identified tips. Recovery estimation uses
multiple statistical methodologies with a confidence-tier system for dispute
defensibility.

## Dependencies

- `shared.db.session` — SQLAlchemy session (module uses `_shim/db.py` until
  full integration with shared session factory)
- `shared.utils.money` — `penny_allocate` for recovery splits
- `shared.events.bus` — event publishing (via `_shim/events.py`)
- PostgreSQL schema: `reclaimrx`
- XGBoost, scikit-learn — ML scoring model
- NetworkX — graph community detection

**Known gap (audit CR-09 variant):** `_shim/db.py` defines its own
`_current_tenant` ContextVar disconnected from
`shared.db.tenant_context.current_tenant_id`, creating a silent tenant-isolation
gap. Migration to `shared.db.session` is tracked.

## How to run tests

```bash
uv run pytest modules/reclaimrx/tests -q
```

Property-based tests (Hypothesis) — included in the default run:

```bash
uv run pytest modules/reclaimrx/tests/property -q
```

Integration tests require live PostgreSQL:

```bash
uv run pytest modules/reclaimrx/tests -q -m integration
```

## API endpoint summary

**Known gap (audit CR-07):** ReclaimRx has no HTTP entry point (`main.py` or
`app.py`) — it cannot be deployed as a standalone service without one.

Routes are defined in `reclaimrx/src/api/router.py` (for embedding in a parent app):

| Group | Endpoints |
|---|---|
| Claim evaluation | `POST /evaluate` — real-time rule + ML scoring |
| Detection rules | `GET /rules`, `GET /rules/{id}` |
| Flagged claims | `GET /flags`, `GET /flags/{id}`, `PUT /flags/{id}` |
| Investigations | `GET/POST /investigations`, `GET /investigations/{id}`, `PUT .../{id}`, `GET .../timeline`, `POST .../activity` |
| Recoveries | `GET/POST /recoveries` |
| Holds | `POST /holds`, `GET /holds`, `DELETE /holds/{id}` |
| Risk profiles | `GET /pharmacy-profiles`, `GET /pharmacy-profiles/{id}`, `GET /prescriber-profiles`, `GET /member-profiles` |
| Accumulator detections | `GET /accumulator-detections` |
| Tips | `POST /tips`, `GET /tips` |

## Event topics produced

Published from `reclaimrx/src/events/publishers.py`:

| Topic | Trigger |
|---|---|
| `fwa.claim_flagged` | Rule or ML model flags a claim |
| `fwa.claim_blocked` | Claim blocked from payment |
| `fwa.investigation_opened` | New investigation work item created |
| `fwa.investigation_resolved` | Investigation closed with resolution |
| `fwa.recovery_demanded` | Recovery demand issued to pharmacy/prescriber |
| `fwa.recovery_collected` | Recovery payment received |
| `fwa.pharmacy_risk_elevated` | Pharmacy risk score crossed a threshold |
| `fwa.suspicious_community_detected` | Graph analysis detected a dispensing community |
| `fwa.tip_received` | Tip submitted |
| `fwa.watchlist_added` | Entity added to watchlist |

## Event topics consumed

Handled via `reclaimrx/src/events/consumers.py`:

| Topic | Handler |
|---|---|
| `claim.adjudicated` | Evaluate adjudicated claim for FWA |
| `claim.reversed` | Update flags on claim reversal |
| `ap.created` | Track AP creation for recovery context |
| `ap.settled` | Update recovery status on settlement |
| `exclusion.match_found` | Flag excluded entity claim |
| `payment.return_suspicious` | Correlate suspicious ACH return with FWA profile |
| `pharmacy.application_submitted` | Screen new pharmacy applicant |
| `pharmacy.ownership_changed` | Re-screen on ownership transfer |

**Known gap (audit CR-01):** `CONSUMER_ROUTING` dict is defined but
`bus.subscribe()` is never called at startup — all 8 consumer handlers are
unreachable in production.
