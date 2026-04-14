# pharmacy-directory

Phase 3 module. Pharmacy directory — NCPDP/NPPES data ingestion, lookup, network management, credentialing, performance metrics.

## Scope

- **Pharmacy directory** — shared NPI/NABP/name/geographic lookup; Redis cache with tenant-prefixed keys
- **Data pipelines** — NCPDP Provider Database parser + upsert; NPPES V2 pharmacy-filter integration; NCPDP data takes precedence when both sources have records
- **Geocoding** — mockable `GeocodingAdapter` ABC; haversine-based fallback distance calculation
- **Networks** — create/manage networks per tenant; add/remove pharmacies; bulk CSV import; contract terms (dispensing fee, brand/generic/specialty discounts)
- **Network adequacy** — CMS radii (urban 2mi, suburban 5mi, rural 15mi); haversine-based coverage calculation
- **Credentialing** — application → automated checks (NPI, state license, DEA, OIG/SAM) → risk-based routing → review → approve/deny; risk queue: fast_track (0-25, all pass), standard (26-50), enhanced (51+, ownership change, fraud flags)
- **Credential monitoring** — daily job; 90/60/30-day alerts; deduplication via `alert_sent_at`
- **PSAOs** — Pharmacy Services Administrative Organization tracking and membership
- **Performance metrics** — monthly snapshots with idempotent upsert; Decimal rounding (ROUND_HALF_UP)
- **Events** — publishes `pharmacy.*` events; consumes `fwa.*` events

## Events Published

| Event | Trigger |
|---|---|
| `pharmacy.created` | New pharmacy inserted |
| `pharmacy.updated` | Pharmacy record changed |
| `pharmacy.ownership_changed` | Ownership change detected |
| `pharmacy.deactivated` | Pharmacy deactivated |
| `pharmacy.network.added` | Pharmacy joined network |
| `pharmacy.network.removed` | Pharmacy terminated from network |
| `pharmacy.credential_expiring` | Credential expiry alert (90/60/30-day) |
| `pharmacy.credentialing_completed` | Application approved or denied |
| `pharmacy.application_submitted` | New credentialing application submitted |

## Events Consumed

| Event | Handler |
|---|---|
| `fwa.credentialing_risk_elevated` | Update credentialing risk score |
| `fwa.pharmacy_risk_elevated` | Flag pharmacy for review |

## API

`GET /api/v1/pharmacies/lookup/{npi}` — lookup by NPI  
`GET /api/v1/pharmacies/lookup/nabp/{nabp}` — lookup by NABP  
`GET /api/v1/pharmacies/search?q=...` — name search  
`GET /api/v1/pharmacies/nearby?lat=...&lng=...&radius_miles=...` — geographic search  
`POST /api/v1/pharmacies/batch` — batch NPI lookup  
`GET/POST /api/v1/pharmacies/networks` — list/create networks  
`GET/POST /api/v1/pharmacies/networks/{id}/pharmacies` — list/add network pharmacies  
`POST /api/v1/pharmacies/networks/{id}/bulk-add` — CSV bulk add  
`GET /api/v1/pharmacies/networks/{id}/adequacy` — adequacy calculation  
`GET/POST /api/v1/pharmacies/credentialing` — list/submit applications  
`GET /api/v1/pharmacies/credentialing/{id}` — get application  
`POST /api/v1/pharmacies/credentialing/{id}/approve` — approve  
`POST /api/v1/pharmacies/credentialing/{id}/deny` — deny  
`GET/POST /api/v1/pharmacies/psaos` — list/create PSAOs  
`GET /api/v1/pharmacies/stats` — directory statistics  

## Running Tests

```bash
python3.13 -m pytest modules/pharmacy-directory/tests/ \
  --cov=modules/pharmacy-directory/src \
  --cov-branch -q
```

Coverage: 96.56% (95% threshold met).

## Schema

PostgreSQL schema: `pharmacy_dir`. SQLite in-memory for tests (via `schema_translate_map`).

## Security

- Sensitive payment fields encrypted via `EncryptedString` (bank_name, routing_number, account_number, tax_id)
- Tenant isolation enforced on all Network, NetworkMembership, CredentialingApplication, CredentialMonitoring, PharmacyPaymentInfo tables
- `SecurityHeadersMiddleware` + `RateLimitMiddleware` mounted via `create_app()` (LESSON-006)
- NPI validated with Luhn check; DEA/NABP validated with `\\A...\\Z` regex anchors (LESSON-004)
