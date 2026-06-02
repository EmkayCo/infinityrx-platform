# Pharmacy / Drug Dataflow Fix Plan

**Date:** 2026-05-20  
**Scope:** pharmacy-directory /search 500, drug-database CORS, prescriber-directory data path audit

---

## 1. Root Cause: pharmacy_dir.pharmacies Does Not Exist

### DB state (confirmed via `docker exec`)

| Table | Schema | Row count |
|---|---|---|
| `dataq_master` | `pharmacy_dir` | 82,643 |
| `ncpdp_pharmacy_services` | `pharmacy_dir` | 81,456 |
| `ncpdp_pharmacies` | `pharmacy_dir` | **does not exist** |
| `pharmacies` | `pharmacy_dir` | **does not exist** |

The `pharmacy_dir` schema has 27 tables — all `dataq_*` and `ncpdp_*` reference tables, plus `alembic_version`. `pharmacy_dir.pharmacies` was **never migrated**. The ORM `Pharmacy` class in `tables.py` targets that missing table.

### What the router queries (the failing endpoints)

| Endpoint | Model used | ORM table | Actual DB table | Status |
|---|---|---|---|---|
| `GET /api/v1/pharmacies/search` | `Pharmacy` | `pharmacy_dir.pharmacies` | missing | **500 UndefinedTableError** |
| `GET /api/v1/pharmacies/lookup/{npi}` | `Pharmacy` | `pharmacy_dir.pharmacies` | missing | **500** |
| `GET /api/v1/pharmacies/lookup/nabp/{nabp}` | `Pharmacy` | `pharmacy_dir.pharmacies` | missing | **500** |
| `GET /api/v1/pharmacies/nearby` | `Pharmacy` | `pharmacy_dir.pharmacies` | missing | **500** |
| `POST /api/v1/pharmacies/batch` | `Pharmacy` | `pharmacy_dir.pharmacies` | missing | **500** |
| `GET /api/v1/pharmacies/stats` | `Pharmacy` | `pharmacy_dir.pharmacies` | missing | **500** |
| `GET /api/v1/pharmacies/networks/{id}/pharmacies` | `Pharmacy` | `pharmacy_dir.pharmacies` | missing | **500** |
| `GET /api/v1/pharmacies/psaos/{id}/pharmacies` | `Pharmacy` | `pharmacy_dir.pharmacies` | missing | **500** |
| `GET /api/v1/pharmacies/networks` | `Network` | `pharmacy_dir.networks` | missing | **500** |
| `GET /api/v1/pharmacies/credentialing` | `CredentialingApplication` | `pharmacy_dir.credentialing_applications` | missing | **500** |

**All** `tables.py` models (`Pharmacy`, `Network`, `NetworkMembership`, `CredentialingApplication`, etc.) target `pharmacy_dir.*` tables that do not exist in DB.

---

## 2. Column Mapping: dataq_master → Pharmacy ORM

The seeded `dataq_master` table maps directly to the `Pharmacy` ORM fields needed by the router and `_pharmacy_to_dict()` serializer.

| `Pharmacy` ORM column | `dataq_master` column | Notes |
|---|---|---|
| `npi` | `npi` | exact match |
| `nabp_number` | — | not in dataq_master; available in `ncpdp_pharmacies` ORM model field `nabp_number` |
| `ncpdp_id` | `ncpdp_provider_id` | rename |
| `legal_name` | `legal_business_name` | rename |
| `dba_name` | `name` | `name` = DBA name in NCPDP format |
| `display_name` | `name` (fallback to `legal_business_name`) | derived |
| `pharmacy_type` | `primary_provider_type_code` | code (e.g. "01") vs. human string; needs lookup table |
| `chain_name` | — | not present |
| `chain_code` | — | not present |
| `store_number` | `store_number` | exact match |
| `address_line_1` | `physical_location_address_1` | rename |
| `address_line_2` | `physical_location_address_2` | rename |
| `city` | `physical_location_city` | rename |
| `state` | `physical_location_state_code` | rename |
| `zip_code` | `physical_location_zip_code` | rename |
| `county` | `physical_location_county_parish` | rename (FIPS code, not text — but closest match) |
| `latitude` | — | not in dataq_master |
| `longitude` | — | not in dataq_master |
| `phone` | `physical_location_phone_number` | rename |
| `fax` | `physical_location_fax` | rename |
| `email` | `physical_location_email_address` | rename |
| `website` | — | not present |
| `is_24_hour` | `physical_location_24_hour_operation_flag` | boolean, exact match |
| `status` | derived from `deactivation_code` | `NULL deactivation_code` → "active", non-null → "inactive" |
| `deactivation_date` | — | not explicit |

**Services (offers_*)**: available in `dataq_services_offered` table (linked by `ncpdp_provider_id`) or `ncpdp_pharmacy_services` ORM model (seeded, 81,456 rows).

---

## 3. Fix Options

### Option A — Repoint router/service to `NCPDPPharmacy` + `dataq_master` (RECOMMENDED)

Analogous to the drug-database fix (router repointed from `drug_products` to `drugs`).

**Files to change:**

| File | Change |
|---|---|
| `modules/pharmacy-directory/src/models/ncpdp_tables.py` | Already has `NCPDPPharmacy` mapped to `pharmacy_dir.ncpdp_pharmacies` — **but that table does not exist either**. This ORM model was written for a future ingest. DO NOT use. |
| `modules/pharmacy-directory/src/services/lookup.py` | Change all `select(Pharmacy)` → `select(DataqMaster)` with column aliasing |
| `modules/pharmacy-directory/src/api/router.py` | Import `DataqMaster` instead of `Pharmacy` for the three lookup handlers |
| `modules/pharmacy-directory/src/models/tables.py` or new `dataq_orm.py` | Add `DataqMaster` ORM class mapped to `pharmacy_dir.dataq_master` |

**Column translation in `_pharmacy_to_dict` equivalent:**

```python
def _dataq_to_dict(p: DataqMaster) -> dict:
    return {
        "id": p.ncpdp_provider_id,           # no UUID PK in dataq_master — use NCPDP ID
        "npi": p.npi or "",
        "nabp_number": None,                  # not in dataq_master
        "ncpdp_id": p.ncpdp_provider_id,
        "legal_name": p.legal_business_name or "",
        "dba_name": p.name,
        "display_name": p.name or p.legal_business_name or "",
        "pharmacy_type": p.primary_provider_type_code or "01",
        "chain_name": None,
        "chain_code": None,
        "store_number": p.store_number,
        "address_line_1": p.physical_location_address_1 or "",
        "address_line_2": p.physical_location_address_2,
        "city": p.physical_location_city or "",
        "state": p.physical_location_state_code or "",
        "zip_code": p.physical_location_zip_code or "",
        "county": p.physical_location_county_parish,
        "country": "US",
        "latitude": None,    # not in dataq_master
        "longitude": None,   # not in dataq_master
        "phone": p.physical_location_phone_number,
        "fax": p.physical_location_fax,
        "email": p.physical_location_email_address,
        "website": None,
        "is_24_hour": p.physical_location_24_hour_operation_flag or False,
        "accepts_electronic_rx": None,
        "dispenses_controlled": None,
        "offers_delivery": None,
        "offers_compounding": None,
        "offers_specialty": None,
        "offers_340b": None,
        "offers_immunizations": None,
        "offers_mtm": None,
        "status": "inactive" if p.deactivation_code else "active",
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
```

**Search filter translation:**

`search_by_name` currently: `Pharmacy.display_name.ilike(...)` and `Pharmacy.status == "active"`

New: `DataqMaster.name.ilike(...)` (DBA name) OR `DataqMaster.legal_business_name.ilike(...)`, combined with `DataqMaster.deactivation_code.is_(None)` for active filter.

**Issue with `id` field**: `dataq_master` has no UUID primary key. The `PharmacyResponse` schema expects `id: str`. Use `ncpdp_provider_id` (7-char string) as the surrogate key. This is compatible — `str` type satisfies the schema. Any join with `NetworkMembership.pharmacy_id` (UUID FK to `pharmacy_dir.pharmacies.id`) will be broken until a migration is run, but the lookup/search endpoints themselves will work.

### Option B — Run Alembic migration to create `pharmacy_dir.pharmacies` + ETL from `dataq_master`

This is the "intended path" if full tenant-scoped network/credentialing features are required. The `tables.py` model is feature-complete (UUID PK, all columns, proper indexes). The blocker is that migrations were never generated or run.

**Steps:**
1. `cd modules/pharmacy-directory && alembic revision --autogenerate -m "create pharmacies table"`
2. Review + run migration against `infinityrx_reference`
3. ETL: `INSERT INTO pharmacy_dir.pharmacies (id, npi, ncpdp_id, legal_name, dba_name, display_name, ...) SELECT gen_random_uuid(), npi, ncpdp_provider_id, legal_business_name, name, COALESCE(name, legal_business_name), ... FROM pharmacy_dir.dataq_master WHERE deactivation_code IS NULL`
4. No router/ORM changes needed post-migration

**Risk**: ETL script needs careful column mapping (see table above). Pharmacy type code `01` needs expansion. Lat/lon will be NULL until geocoded.

---

## 4. Recommendation

**Use Option A (repoint to `dataq_master`) for the immediate fix.** Rationale:

- Option B requires writing and running an Alembic migration + ETL script against a live reference DB. The ETL has data-quality risks (null NPIs, type code translation, 82K rows). Higher blast radius.
- Option A is the same class of surgical fix already successfully applied to drug-database. `dataq_master` has 82,643 rows, is already seeded, and has all fields needed by the `PharmacyResponse` schema (name, NPI, address, phone, status).
- Network/credentialing/PSAO endpoints that JOIN on `pharmacy_dir.pharmacies.id` (UUID FK) will still fail — but those require a full migration + data model anyway, regardless of which option is chosen for search/lookup.
- For the portal use case (search/lookup by name or NPI), Option A unblocks the page immediately.

**Exact files to edit for Option A:**

1. **`modules/pharmacy-directory/src/models/tables.py`** — Add `DataqMaster` class at top (or new file `dataq_orm.py`), mapped to `pharmacy_dir.dataq_master`, with columns from the DB schema above.
2. **`modules/pharmacy-directory/src/services/lookup.py`** — Replace all `from src.models.tables import Pharmacy` with `DataqMaster`; rewrite `search_by_name`, `get_by_npi`, `get_by_nabp`, `search_nearby` to use new column names; replace `_pharmacy_to_dict` with `_dataq_to_dict`.
3. **`modules/pharmacy-directory/src/api/router.py`** — Remove `Pharmacy` from import in stats/count queries (`func.count(Pharmacy.id)`); replace with `DataqMaster` or a literal count.

**Out of scope for Option A**: Network, NetworkMembership, CredentialingApplication, Psao, PsaoMembership endpoints — all still reference unmigrated tables. Those need Option B.

---

## 5. Drug-Database CORS Verdict

### Finding: CORS is BROKEN for browser fetches

**Code path** (`modules/drug-database/src/main.py`):

```python
cors_origins = getattr(settings, "CORS_ALLOW_ORIGINS", [])
if cors_origins:  # ← only mounts CORSMiddleware if list is non-empty
    app.add_middleware(CORSMiddleware, allow_origins=cors_origins, ...)
```

**Settings default** (`shared/config.py`):
```python
CORS_ALLOW_ORIGINS: list[str] = []  # default is empty list
```

**Environment files**: `.env.local` and `.env` have **no `CORS_ALLOW_ORIGINS` entry**.  
`.env.dev` has `CORS_ORIGINS=http://localhost:3000,http://localhost:3001` — note the wrong key name (`CORS_ORIGINS` vs `CORS_ALLOW_ORIGINS`). The Settings model ignores `CORS_ORIGINS` — it reads `CORS_ALLOW_ORIGINS` only.

**Result**: `CORSMiddleware` is **never mounted** when running locally. Browser preflight (`OPTIONS`) to `http://localhost:8011/api/v1/drugs/search` will receive no `Access-Control-Allow-Origin` header. Browsers will block the fetch with a CORS error, even though curl works.

**`DrugsListPage.tsx` fetch pattern**:
```ts
const url = `${drugDatabaseUrl}/api/v1/drugs/search?${params.toString()}`;
const resp = await fetch(url);  // direct browser → :8011, no proxy
```
No BFF/Next.js API route in between. No reverse proxy rewrites in `next.config.ts`.

**Fix**: In `.env.local` (or `.env`), add:
```
CORS_ALLOW_ORIGINS=http://localhost:3000,http://localhost:3001
```
The `_parse_cors_origins` validator handles comma-separated strings. This must be loaded by the drug-database process — confirm the service reads `.env.local` at startup (or set the env var directly when launching the service).

**Secondary fix** (the wrong-key bug in `.env.dev`): rename `CORS_ORIGINS` → `CORS_ALLOW_ORIGINS`.

---

## 6. Prescriber-Directory Data Path Verdict

**CLEAN — no mismatch.**

| Model class | ORM table | DB table | Row count |
|---|---|---|---|
| `Prescriber` | `prescriber_dir.prescribers` | **exists** | ~8.75M |
| `PrescriberAddress` | `prescriber_dir.prescriber_addresses` | **exists** | ~17.4M |
| `PrescriberTaxonomy` | `prescriber_dir.prescriber_taxonomies` | **exists** | ~10.9M |
| `PrescriberIdentifier` | `prescriber_dir.prescriber_identifiers` | **exists** | ~2.7M |

The prescriber router imports `Prescriber` from `src.models.tables` and queries `prescriber_dir.prescribers` directly. All seeded tables match their ORM models. The router is live and functional for search/lookup.

---

## 7. Summary Table

| Issue | Root Cause | Fix Required | Risk |
|---|---|---|---|
| Pharmacy `/search` 500 | `pharmacy_dir.pharmacies` never migrated | Repoint lookup service to `dataq_master` (Option A) | Low — surgical |
| Drug browser CORS failure | `CORS_ALLOW_ORIGINS` not set in `.env.local`; wrong key in `.env.dev` | Add `CORS_ALLOW_ORIGINS=http://localhost:3000` to `.env.local`; rename key in `.env.dev` | Trivial config |
| Prescriber data path | N/A — no mismatch | No action needed | — |
