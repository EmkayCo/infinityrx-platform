# Module: prescriber-directory

Separate FastAPI service. Owns the `prescriber_dir` PostgreSQL schema.
Communicates with other modules via API calls and event bus — no cross-schema queries.

See root `CLAUDE.md` for platform principles. Module PRD: `docs/prd/prd-prescriber-directory.md`.

## Purpose

Authoritative prescriber NPI registry for the platform. Provides real-time validation,
credential monitoring, controlled substance authority checks, and prescriber-pharmacy
relationship tracking from claim volume.

Capabilities:
- NPPES V2 CSV pipeline — 7.8M NPI bulk upsert (329-column format, batch of 500)
- Real-time prescriber lookup by NPI or DEA number (<10ms cached, <50ms DB)
- NPI Luhn validation + DEA check-digit validation
- NUCC taxonomy code reference with simplified specialty mapping (60+ codes)
- Controlled substance authority check (DEA active, schedule authorized, state rules)
- State prescribing authority for all 50 states + DC (NP/PA/MD/DO authority levels)
- Credential monitoring daily job (DEA/license expiry alerts at 90/60/30 days)
- Organization (Type 2) NPI handling + prescriber search
- Prescriber-pharmacy relationship tracking from `claim.ingested` events
- Exclusion marking from `exclusion.match_found` events

## Setup

```bash
# Environment variables required:
PRESCRIBER_DB_URL=postgresql+asyncpg://user:pass@localhost/prescriber_dir
```

## Running Tests

```bash
cd modules/prescriber-directory
python3.13 -m pytest tests/ --cov=src --cov-branch -q
```

Coverage requirement: 99% branch coverage on all active code.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/prescribers/lookup/{npi}` | Lookup prescriber by NPI |
| GET | `/api/v1/prescribers/lookup/dea/{dea}` | Lookup prescriber by DEA number |
| GET | `/api/v1/prescribers/search` | Search by name/state/specialty/status |
| GET | `/api/v1/prescribers/batch` | Batch lookup (up to 100 NPIs) |
| GET | `/api/v1/prescribers/validate/{npi}` | Validate NPI + credential status |
| GET | `/api/v1/prescribers/validate/{npi}/controlled/{schedule}` | Check controlled substance authority |
| GET | `/api/v1/prescribers/taxonomies` | List all NUCC taxonomy codes |
| GET | `/api/v1/prescribers/taxonomies/{code}` | Lookup taxonomy code details |
| GET | `/api/v1/prescribers/specialties` | List simplified specialty labels |
| GET | `/api/v1/prescribers/organizations` | Search organization NPIs |
| GET | `/api/v1/prescribers/organizations/{npi}` | Lookup organization by NPI |
| GET | `/api/v1/prescribers/relationships/{npi}/pharmacies` | Prescriber-pharmacy volumes |
| GET | `/api/v1/prescribers/relationships/{npi}/stats` | Relationship summary stats |
| GET | `/api/v1/prescribers/monitoring/alerts` | List credential alerts |
| PUT | `/api/v1/prescribers/monitoring/alerts/{id}/acknowledge` | Acknowledge alert |
| GET | `/api/v1/prescribers/stats` | Directory statistics |
| POST | `/api/v1/prescribers/refresh` | Trigger NPPES data refresh |
| GET | `/health` | Health check |

## Events Published

| Event | Trigger |
|-------|---------|
| `prescriber.created` | New NPI upsert |
| `prescriber.updated` | NPI record updated |
| `prescriber.deactivated` | NPI deactivated |
| `prescriber.dea_expired` | DEA expiry alert |
| `prescriber.excluded` | Exclusion match applied |
| `prescriber.relationship_updated` | Claim volume updated |

## Events Consumed

| Event | Handler | Action |
|-------|---------|--------|
| `claim.ingested` | `handle_claim_ingested` | Increment prescriber-pharmacy relationship claim count |
| `exclusion.match_found` | `handle_exclusion_match_found` | Mark prescriber as excluded |

## Data Model

- `Prescriber` — core NPI record (individual + organization, 60+ fields from NPPES V2)
- `TaxonomyCode` — NUCC taxonomy reference table
- `PracticeAffiliation` — prescriber → organization affiliations
- `CredentialAlert` — DEA/license expiry alerts (90/60/30-day thresholds)
- `DataRefreshLog` — NPPES import audit trail
- `PrescriberPharmacyRelationship` — monthly claim volume by prescriber-pharmacy pair
- `StatePrescribingRule` — controlled substance authority by state + provider type

## Middleware

- `SecurityHeadersMiddleware` — HSTS, CSP, X-Frame-Options, Cache-Control, X-Request-ID
- `RateLimitMiddleware` — token bucket per tenant_id, configurable RPM
