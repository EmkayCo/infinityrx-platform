# PRD — Module 4: Medical / Prescriber Directory — FINAL

**Module:** Medical / Prescriber Directory  
**Folder:** `modules/prescriber-directory/`  
**Priority:** Phase 3  
**Dependencies:** Core Platform (Module 1)  

---

## 1. Purpose

The Prescriber Directory is the authoritative source for prescriber and medical provider data. Every module that references a prescriber — adjudication (verify prescriber authority), ReclaimRx (prescriber profiling), billing (prescriber on claims), reporting (prescriber analytics), DataIQ (prescriber profiling) — queries this module.

**Data sources:**
1. **NPPES (CMS)** — primary, free. V2 monthly full download + weekly incremental. ~7.8M NPIs (Type 1 = individual, Type 2 = organization). Provider name, credentials, taxonomy (specialty), practice addresses, phone, enumeration date, deactivation status.
2. **DEA Registration** — controlled substance prescribing authority. NTIS subscription or manual verification.
3. **State Medical Board** — license verification. API where available (varies by state), manual for others.
4. **CMS PECOS** — Provider Enrollment, Chain, and Ownership System. Medicare enrollment status.
5. **OIG/SAM/OFAC** — exclusion screening (via Core Platform).
6. **Taxonomy code reference** — NUCC Health Care Provider Taxonomy Code Set. Maps taxonomy codes to specialty names.

**What this module provides:**
- Prescriber lookup by NPI, DEA number, name, specialty, location
- Prescriber validation (active NPI, valid DEA for controlled substances, not excluded)
- Specialty classification via taxonomy codes
- Prescriber credential monitoring (DEA expiry, license status)
- Prescriber-pharmacy relationship data (for ReclaimRx graph analysis)
- Prescriber performance metrics (for DataIQ prescriber profiling)
- Organization/group practice directory (Type 2 NPIs)

---

## 2. Data Model

```sql
CREATE SCHEMA prescriber_dir;

-- ═══════════════════════════════════════════════
-- PRESCRIBER RECORDS
-- ═══════════════════════════════════════════════

-- Individual prescribers (NPPES Type 1)
CREATE TABLE prescriber_dir.prescribers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- NPI
    npi VARCHAR(10) NOT NULL UNIQUE,
    entity_type VARCHAR(5) NOT NULL DEFAULT '1',       -- 1 = individual, 2 = organization
    
    -- Name
    last_name VARCHAR(255),
    first_name VARCHAR(255),
    middle_name VARCHAR(100),
    prefix VARCHAR(20),                                -- Dr., Mr., Ms.
    suffix VARCHAR(20),                                -- MD, DO, NP, PA, PharmD
    credential VARCHAR(100),                           -- from NPPES credential field
    display_name VARCHAR(500) NOT NULL,
    
    -- For Type 2 (organizations)
    organization_name VARCHAR(500),
    organization_type VARCHAR(100),                     -- hospital, clinic, group_practice, health_system
    authorized_official_name VARCHAR(255),
    authorized_official_title VARCHAR(100),
    
    -- Specialty (from taxonomy codes)
    primary_taxonomy_code VARCHAR(20),
    primary_taxonomy_description VARCHAR(255),
    primary_specialty VARCHAR(255),                     -- simplified specialty name
    taxonomy_codes JSONB,                               -- all taxonomy codes [{code, description, is_primary}]
    
    -- Gender
    gender VARCHAR(1),                                 -- M, F, or null
    
    -- Practice location (primary)
    practice_address_line_1 VARCHAR(255),
    practice_address_line_2 VARCHAR(255),
    practice_city VARCHAR(100),
    practice_state VARCHAR(2),
    practice_zip VARCHAR(10),
    practice_phone VARCHAR(20),
    practice_fax VARCHAR(20),
    practice_latitude DECIMAL(10,7),
    practice_longitude DECIMAL(10,7),
    
    -- Mailing address
    mailing_address_line_1 VARCHAR(255),
    mailing_address_line_2 VARCHAR(255),
    mailing_city VARCHAR(100),
    mailing_state VARCHAR(2),
    mailing_zip VARCHAR(10),
    
    -- Additional practice locations (from NPPES Practice Location Reference File)
    additional_locations JSONB,                         -- [{address, city, state, zip, phone}]
    
    -- DEA
    dea_number VARCHAR(9),
    dea_status VARCHAR(50),                            -- active, expired, revoked, surrendered
    dea_expiration_date DATE,
    dea_schedules JSONB,                               -- which schedules authorized [2, 2N, 3, 3N, 4, 5]
    dea_state VARCHAR(2),
    
    -- State license
    state_license_number VARCHAR(50),
    state_license_state VARCHAR(2),
    state_license_status VARCHAR(50),
    state_license_expiry DATE,
    additional_state_licenses JSONB,                    -- [{state, number, status, expiry}]
    
    -- Medicare
    pecos_enrolled BOOLEAN,
    medicare_participation BOOLEAN,
    medicare_opt_out BOOLEAN DEFAULT FALSE,
    
    -- Enumeration
    enumeration_date DATE,                             -- when NPI was first assigned
    last_update_date DATE,                             -- last NPPES update
    deactivation_date DATE,
    deactivation_reason VARCHAR(100),
    reactivation_date DATE,
    
    -- Telehealth
    offers_telehealth BOOLEAN DEFAULT FALSE,
    telehealth_states JSONB,                           -- states where telehealth authorized
    
    -- Status
    status VARCHAR(50) DEFAULT 'active',
    -- active, inactive, deactivated, excluded, deceased
    
    -- Data source tracking
    nppes_last_updated TIMESTAMPTZ,
    dea_last_verified TIMESTAMPTZ,
    license_last_verified TIMESTAMPTZ,
    manual_last_updated TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_prescriber_npi ON prescriber_dir.prescribers(npi);
CREATE INDEX idx_prescriber_name ON prescriber_dir.prescribers USING gin(to_tsvector('english', display_name));
CREATE INDEX idx_prescriber_last_name ON prescriber_dir.prescribers(last_name, first_name);
CREATE INDEX idx_prescriber_dea ON prescriber_dir.prescribers(dea_number);
CREATE INDEX idx_prescriber_specialty ON prescriber_dir.prescribers(primary_specialty);
CREATE INDEX idx_prescriber_taxonomy ON prescriber_dir.prescribers(primary_taxonomy_code);
CREATE INDEX idx_prescriber_state ON prescriber_dir.prescribers(practice_state);
CREATE INDEX idx_prescriber_geo ON prescriber_dir.prescribers(practice_latitude, practice_longitude);
CREATE INDEX idx_prescriber_status ON prescriber_dir.prescribers(status);

-- ═══════════════════════════════════════════════
-- TAXONOMY REFERENCE
-- ═══════════════════════════════════════════════

CREATE TABLE prescriber_dir.taxonomy_codes (
    code VARCHAR(20) PRIMARY KEY,
    classification VARCHAR(255) NOT NULL,               -- broad category
    specialization VARCHAR(255),                        -- specific specialty
    definition TEXT,
    display_name VARCHAR(255) NOT NULL,                 -- human-readable specialty name
    grouping VARCHAR(255),                              -- NUCC grouping
    
    -- Simplified mapping for our system
    simplified_specialty VARCHAR(100),                   -- internal standard name
    is_prescriber BOOLEAN DEFAULT FALSE,                -- can this taxonomy prescribe drugs?
    is_pharmacy BOOLEAN DEFAULT FALSE,
    is_hospital BOOLEAN DEFAULT FALSE,
    
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- GROUP PRACTICE AFFILIATIONS
-- ═══════════════════════════════════════════════

CREATE TABLE prescriber_dir.practice_affiliations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    prescriber_id UUID NOT NULL REFERENCES prescriber_dir.prescribers(id),
    organization_id UUID NOT NULL REFERENCES prescriber_dir.prescribers(id),  -- Type 2 NPI
    
    role VARCHAR(100),                                 -- attending, admitting, ordering, referring
    effective_date DATE,
    termination_date DATE,
    
    data_source VARCHAR(50) DEFAULT 'nppes',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- CREDENTIAL MONITORING
-- ═══════════════════════════════════════════════

CREATE TABLE prescriber_dir.credential_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prescriber_id UUID NOT NULL REFERENCES prescriber_dir.prescribers(id),
    
    alert_type VARCHAR(100) NOT NULL,
    -- dea_expiring, dea_expired, license_expiring, license_expired,
    -- oig_exclusion, sam_exclusion, npi_deactivated, status_change
    
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- DATA REFRESH TRACKING
-- ═══════════════════════════════════════════════

CREATE TABLE prescriber_dir.data_refresh_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_source VARCHAR(50) NOT NULL,
    refresh_type VARCHAR(50) NOT NULL,
    
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL,
    
    records_processed INTEGER DEFAULT 0,
    records_added INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_deactivated INTEGER DEFAULT 0,
    
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 3. Business Logic

### 3.1 NPPES Data Pipeline

**Monthly full refresh:**
1. Download NPPES V2 full replacement file from CMS (~8GB compressed)
2. Parse CSV (329 columns in V2 format)
3. For each NPI:
   - Normalize: extract name fields, parse taxonomy codes, format addresses
   - Classify: is_prescriber flag based on taxonomy code lookup
   - Upsert into `prescribers` table
4. Process supplementary files: Practice Location Reference, Other Name Reference, Endpoint Reference
5. Detect deactivations: NPIs in previous month but not in current → mark deactivated
6. Track: records processed/added/updated/deactivated
7. Duration target: <2 hours for full 7.8M NPI file

**Weekly incremental:**
1. Download weekly incremental file
2. Process only changed/new records
3. Apply same normalization and classification
4. Duration target: <15 minutes

**Geocoding:**
1. After address changes: geocode via Azure Maps or Google Geocoding API
2. Rate limit: batch geocode in off-hours (many addresses to process on initial load)
3. Cache results: same address → same coordinates (no re-geocode unless address changes)

### 3.2 Prescriber Validation (Real-Time)

Called by adjudication engine on every claim:

1. Input: prescriber NPI
2. Validate:
   - NPI exists and is active in the directory
   - NPI is Type 1 (individual) or authorized organization
   - Prescriber's taxonomy indicates prescribing authority
   - If controlled substance: DEA number active, authorized for that schedule
   - Not on OIG/SAM/OFAC exclusion list
3. Response: VALID / INVALID with reason codes
4. Redis-cached: TTL 24 hours (prescriber status doesn't change by the minute)
5. **Performance: <10ms from cache, <50ms from database**

### 3.3 Prescriber Search

1. **By NPI**: exact match, fastest path
2. **By DEA number**: exact match
3. **By name**: full-text search on display_name, last_name + first_name partial match
4. **By specialty**: taxonomy code or simplified specialty name
5. **By location**: PostGIS geographic search (lat/lng + radius) or state/city/zip
6. **Combined**: name + state + specialty (most common search pattern)
7. Filters: entity_type, status, telehealth, Medicare participation
8. Pagination with total count

### 3.4 Controlled Substance Authority Check

For DEA-scheduled drugs:

1. Input: prescriber NPI + DEA schedule (II, III, IV, V)
2. Check: prescriber has active DEA registration
3. Check: DEA registration covers the requested schedule
4. Check: DEA state matches prescribing state (some states require state-specific DEA)
5. Configurable: mid-level prescriber rules vary by state (NPs and PAs have different controlled substance authority in different states)
6. Returns: AUTHORIZED / NOT_AUTHORIZED with specific reason

### 3.5 Credential Monitoring

Scheduled daily job:

1. **DEA expiry**: check all prescribers with DEA expiry within 90/60/30 days → alert
2. **DEA expired**: check all prescribers with DEA expired and still processing claims → CRITICAL alert + flag for adjudication to reject controlled substance claims
3. **State license expiry**: same logic as DEA
4. **NPI deactivation**: detect newly deactivated NPIs from weekly NPPES refresh → alert
5. **Exclusion screening**: monthly re-screen all active prescribers against OIG/SAM (via Core Platform)
6. Alerts delivered via notification system and visible in monitoring dashboard

### 3.6 Prescriber-Pharmacy Relationship Data

Extracted from claims data (consumed from Billing module events):

1. Track: which prescribers send prescriptions to which pharmacies
2. Volume: number of claims per prescriber-pharmacy pair per period
3. Concentration: what % of a prescriber's scripts go to a single pharmacy
4. Geographic analysis: distance between prescriber practice and pharmacies they prescribe to
5. Fed to ReclaimRx: prescriber-pharmacy affinity data for graph analysis and telehealth fraud detection
6. Updated incrementally as claims flow through

### 3.7 Mid-Level Prescriber Supervisory Relationships

NPs and PAs may require supervising physicians in some states:

1. **Supervisor table**: prescriber_id (NP/PA), supervisor_id (MD/DO), state, relationship_type (supervisory, collaborative), effective_date, termination_date
2. **Controlled substance authority**: in states requiring supervision for controlled substances, adjudication verifies that the supervisor's DEA covers the prescribed schedule
3. **Source**: enrollment data from clients, manual entry, or state board APIs where available
4. **State rules table**: configurable per state — which provider types require supervision, for which actions

### 3.8 State-Specific Prescribing Authority Rules

Prescribing authority varies by state and provider type:

1. **Authority rules table**: state, provider_type (MD, DO, NP, PA, DDS, OD, etc.), can_prescribe_independently (BOOLEAN), requires_collaborative_agreement (BOOLEAN), controlled_substance_authority (none, limited, full), schedule_restrictions, notes
2. **Pre-loaded**: all 50 states + DC + territories with current rules
3. **Used by**: adjudication (controlled substance authority check), credentialing (verify provider has required agreements)
4. **Updates**: tracked for state law changes. Alert when a state changes prescribing authority rules.

### 3.9 Prescriber Panel Size

Track number of unique patients per prescriber:

1. **Calculated from claims data**: count distinct member_ids per prescriber NPI per period
2. **Stored as metric**: monthly snapshot for trending
3. **Used by**: ReclaimRx (outlier detection — too many patients may indicate fraud), DataIQ (prescriber profiling, capacity analysis), network adequacy (prescriber capacity)
4. **Peer comparison**: rank prescribers by panel size within same specialty and geography

### 3.10 Prescriber Communication Preferences

For PA outreach, formulary change notifications, clinical communications:

1. **Preference table**: prescriber_id, preferred_contact_method (fax, phone, portal, email, ehr_message), preferred_contact_value, preferred_times, do_not_contact (BOOLEAN), notes
2. **Per-tenant**: preferences may differ by which tenant is contacting
3. **Used by**: AI/NLP module (PA letter delivery), Prior Auth module (outreach), Portals (medical provider portal)

### 3.11 Prescriber Opt-Out Tracking

Providers who opt out of specific programs:

1. **Opt-out table**: prescriber_id, program_type (manufacturer_copay, clinical_trial, network_participation), program_id, opt_out_date, reason, opt_in_date
2. **Adjudication impact**: if prescriber opts out of a manufacturer program, claims from this prescriber should not be routed to that program
3. **Source**: client/program configuration, prescriber portal self-service

### 3.12 NPPES Data Staleness Detection

Flag records that may be outdated:

1. **Staleness threshold**: if `last_update_date` from NPPES is >2 years ago, flag as `potentially_stale`
2. **Impact**: stale records may have incorrect addresses, phone numbers, or even inactive practices
3. **Action**: stale records returned in search results with staleness indicator. For critical operations (credentialing, PA outreach), alert that data may be outdated.
4. **Re-verification**: stale records prioritized for manual or automated verification (state board lookup, phone verification)

---

## 4. API Endpoints

```
/api/v1/prescribers/

# Lookup
GET    /lookup/{npi}                    Prescriber detail by NPI
GET    /lookup/dea/{dea_number}         Prescriber by DEA number
GET    /search                          Search by name, specialty, location
GET    /nearby                          Geographic search (lat/lng + radius)
GET    /batch                           Batch lookup (up to 100 NPIs)

# Validation (called by adjudication engine)
GET    /validate/{npi}                  Validate prescriber (active, not excluded)
GET    /validate/{npi}/controlled/{schedule}  Validate controlled substance authority

# Taxonomy
GET    /taxonomies                      List taxonomy codes with descriptions
GET    /taxonomies/{code}               Taxonomy code detail
GET    /specialties                     List simplified specialty names

# Organizations
GET    /organizations                   Search organizations (Type 2 NPIs)
GET    /organizations/{npi}             Organization detail
GET    /organizations/{npi}/prescribers  Prescribers affiliated with organization

# Monitoring
GET    /monitoring/expiring             Credentials expiring within configurable window
GET    /monitoring/alerts               Active credential alerts
PUT    /monitoring/alerts/{id}/acknowledge  Acknowledge alert

# Relationships (consumed by ReclaimRx)
GET    /relationships/{npi}/pharmacies  Pharmacies this prescriber prescribes to
GET    /relationships/{npi}/stats       Prescribing volume and pattern summary

# Admin
GET    /refresh/status                  Last refresh status
POST   /refresh                         Trigger manual refresh
GET    /stats                           Directory statistics (total NPIs, by type, by state)
```

---

## 5. Events

### Published
- `prescriber.created` — new prescriber added
- `prescriber.updated` — prescriber data changed
- `prescriber.deactivated` — NPI deactivated
- `prescriber.dea_expired` — DEA registration expired
- `prescriber.license_expired` — state license expired
- `prescriber.excluded` — prescriber found on exclusion list
- `prescriber.credential_expiring` — credential approaching expiry
- `prescriber.relationship_updated` — prescriber-pharmacy relationship data updated

### Consumed
- `claim.ingested` — extract prescriber NPI, update relationship data
- `exclusion.match_found` — mark prescriber as excluded

---

## 6. Default Implementation

Ships fully functional:

- **NPPES V2 integration** — monthly full + weekly incremental. ~7.8M NPIs parsed and loaded.
- **Taxonomy code reference** — full NUCC taxonomy set with simplified specialty mapping
- **Prescriber validation** — real-time NPI + DEA + exclusion check, Redis-cached (<10ms)
- **Controlled substance authority** — DEA schedule verification with state-specific rules
- **Full-text search** — by name, specialty, location with PostGIS geographic search
- **Organization/group practice directory** — Type 2 NPIs with affiliations
- **Credential monitoring** — daily check for DEA/license expiry with 90/60/30-day alerts
- **Prescriber-pharmacy relationships** — incrementally built from claims data
- **Geocoding** — address to lat/lng for geographic search
- **Exclusion screening integration** — monthly re-screen via Core Platform

---

## 7. Performance Requirements

- Prescriber validation (cache): <10ms
- Prescriber validation (database): <50ms
- Name search: <200ms
- Geographic search: <500ms
- Batch lookup (100 NPIs): <1 second
- NPPES full refresh (7.8M NPIs): <2 hours
- NPPES weekly incremental: <15 minutes
- Credential monitoring job (all active prescribers): <30 minutes

---

## 8. Data Retention

- Prescriber records: indefinite (reference data — mark inactive, never delete)
- Practice affiliations: indefinite
- Credential alerts: 2 years
- Relationship data: 3 years (for trend analysis)
- Refresh logs: 2 years

---

## 9. Test Scenarios

### Critical Paths (100%)
- NPPES V2 file parsed correctly (all 329 columns, correct field mapping)
- Prescriber validation returns correct result for: active, inactive, deactivated, excluded NPIs
- Controlled substance check correctly verifies DEA schedule authority
- Name search returns relevant results and ranks by relevance
- Geographic search returns prescribers within radius and excludes outside
- Credential monitoring detects expiry at correct thresholds
- Exclusion match blocks prescriber from validation

### Edge Cases
- Prescriber with no DEA (non-controlled prescriber) → validation passes for non-scheduled drugs
- Prescriber deactivated then reactivated → status correctly updated
- Organization NPI used as prescriber → validation checks entity_type
- Same person with two NPIs (rare) → both records maintained separately
- Prescriber with practice location in 5 states → all locations indexed for geographic search

---

## 10. Session Decomposition

1. **Core directory + NPPES pipeline**: prescribers table, taxonomy reference, NPPES V2 downloader/parser (full + incremental), normalization, geocoding, NPI lookup, name search (full-text), geographic search (PostGIS), Redis caching
2. **Validation + credentials + DEA**: prescriber validation API (real-time), controlled substance authority check, DEA verification, state license tracking, credential monitoring (daily job), alert generation, exclusion screening integration
3. **Organizations + relationships + integration**: Type 2 NPI handling, practice affiliations, prescriber-pharmacy relationship tracking (from claims events), relationship statistics, event publishing, data refresh pipeline, batch lookup
