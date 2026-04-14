# PRD — Module 2: Drug Database — FINAL

**Module:** Drug Database  
**Folder:** `modules/drug-database/`  
**Priority:** Phase 3  
**Dependencies:** Core Platform (Module 1)  

---

## 1. Purpose

The Drug Database is the drug reference foundation for the entire platform. Every module that touches a drug — adjudication, billing, ReclaimRx, reporting, DataIQ, prior auth, plan design — queries this module for drug information. It does NOT store claims. It stores drug reference data: what the drug IS, what it COSTS, what it DOES, and how it's classified.

**Data sources (priority order):**
1. **First DataBank (FDB)** — primary commercial drug database. Pricing (AWP, WAC, NADAC), clinical data (interactions, indications, dosing), therapeutic classification, Orange Book equivalents. *(Integration spec TBD — fields stubbed until FDB spec received)*
2. **FDA NDC Directory** — free, public. NDC codes, drug names, labeler, dosage form, route, strength, packaging, marketing status. Updated daily.
3. **CMS NADAC** — National Average Drug Acquisition Cost. Free, public. Weekly update. Used for Medicaid and benchmark pricing.
4. **FDA Orange Book** — therapeutic equivalence ratings. Free, public. Identifies generic equivalents.
5. **Drug Pipeline** — FDA approval calendar, patent expiration dates, expected generics/biosimilars. Manual + automated feed.

**What this module provides to other modules:**
- NDC lookup with full drug detail
- Drug pricing (AWP, WAC, NADAC, FUL) with effective dates
- Therapeutic classification (GPI, AHFS, USP, ATC)
- Drug interactions (severity levels)
- Therapeutic equivalence / generic substitution
- Formulary classification support (brand, generic, specialty, compound, OTC)
- Drug-specific rules data (max quantity, max days supply, age limits, gender limits)
- Package size and unit dose information

---

## 2. Data Model

```sql
CREATE SCHEMA drug_db;

-- ═══════════════════════════════════════════════
-- CORE DRUG IDENTITY
-- ═══════════════════════════════════════════════

-- Drug products (one row per NDC-11)
CREATE TABLE drug_db.drug_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- NDC (all 3 formats stored for matching flexibility)
    ndc_11 VARCHAR(11) NOT NULL UNIQUE,               -- 5-4-2 concatenated (no dashes)
    ndc_formatted VARCHAR(13),                         -- 5-4-2 with dashes
    labeler_code VARCHAR(5) NOT NULL,
    product_code VARCHAR(4) NOT NULL,
    package_code VARCHAR(2) NOT NULL,
    
    -- Drug identity
    proprietary_name VARCHAR(500),                     -- brand name
    nonproprietary_name VARCHAR(500),                  -- generic name
    drug_name_display VARCHAR(500) NOT NULL,           -- what to show in UI
    
    -- Classification
    dea_schedule VARCHAR(5),                           -- CI, CII, CIII, CIV, CV, or null
    otc_rx VARCHAR(3),                                 -- OTC, Rx, or Both
    drug_type VARCHAR(50),                             -- brand, generic, biosimilar, OTC, compound, specialty
    
    -- Physical
    dosage_form VARCHAR(100),                          -- tablet, capsule, injection, etc.
    route_of_administration VARCHAR(100),
    strength VARCHAR(255),
    strength_number DECIMAL(12,4),
    strength_unit VARCHAR(50),
    
    -- Packaging
    package_description VARCHAR(500),
    package_quantity DECIMAL(10,3),
    package_size DECIMAL(10,3),
    package_size_unit VARCHAR(50),
    unit_dose BOOLEAN DEFAULT FALSE,
    
    -- Labeler / manufacturer
    labeler_name VARCHAR(500),
    
    -- Marketing
    marketing_status VARCHAR(50),                      -- active, discontinued, pending
    marketing_start_date DATE,
    marketing_end_date DATE,
    
    -- Therapeutic classification
    gpi_code VARCHAR(14),                              -- Generic Product Identifier (FDB)
    gpi_description VARCHAR(500),
    ahfs_code VARCHAR(20),                             -- AHFS Pharmacologic-Therapeutic Classification
    ahfs_description VARCHAR(500),
    usp_category VARCHAR(255),                         -- USP Drug Classification
    atc_code VARCHAR(7),                               -- WHO Anatomical Therapeutic Chemical
    atc_description VARCHAR(500),
    therapeutic_class_1 VARCHAR(255),                  -- broad (e.g., "Cardiovascular")
    therapeutic_class_2 VARCHAR(255),                  -- specific (e.g., "ACE Inhibitors")
    therapeutic_class_3 VARCHAR(255),                  -- granular (e.g., "Lisinopril")
    
    -- Specialty drug indicators
    is_specialty BOOLEAN DEFAULT FALSE,
    specialty_category VARCHAR(100),                    -- oncology, rare_disease, autoimmune, etc.
    is_limited_distribution BOOLEAN DEFAULT FALSE,
    is_biosimilar BOOLEAN DEFAULT FALSE,
    reference_biologic_ndc VARCHAR(11),                -- for biosimilars: NDC of reference product
    
    -- GLP-1 / weight management flag (high-interest 2025-2026)
    is_glp1 BOOLEAN DEFAULT FALSE,
    glp1_indication VARCHAR(100),                      -- diabetes, weight_management, both
    
    -- Data source tracking
    fdb_product_id VARCHAR(50),                        -- FDB product identifier (when available)
    fda_application_number VARCHAR(20),
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    data_source VARCHAR(50) NOT NULL,                  -- fdb, fda_ndc, manual
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_drug_ndc ON drug_db.drug_products(ndc_11);
CREATE INDEX idx_drug_name ON drug_db.drug_products(drug_name_display);
CREATE INDEX idx_drug_gpi ON drug_db.drug_products(gpi_code);
CREATE INDEX idx_drug_labeler ON drug_db.drug_products(labeler_code);
CREATE INDEX idx_drug_type ON drug_db.drug_products(drug_type);
CREATE INDEX idx_drug_nonproprietary ON drug_db.drug_products(nonproprietary_name);

-- ═══════════════════════════════════════════════
-- PRICING
-- ═══════════════════════════════════════════════

CREATE TABLE drug_db.drug_pricing (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ndc_11 VARCHAR(11) NOT NULL,
    
    price_type VARCHAR(20) NOT NULL,                   -- AWP, WAC, NADAC, FUL, MAC
    price_per_unit DECIMAL(12,6) NOT NULL,             -- per billing unit
    unit_type VARCHAR(50),                             -- EA, ML, GM, etc.
    package_price DECIMAL(12,2),
    
    effective_date DATE NOT NULL,
    termination_date DATE,
    
    data_source VARCHAR(50) NOT NULL,                  -- fdb, cms_nadac, state_mac, manual
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(ndc_11, price_type, effective_date, data_source)
);

CREATE INDEX idx_pricing_ndc_type ON drug_db.drug_pricing(ndc_11, price_type, effective_date DESC);

-- Pricing history (for trend analysis — every price change preserved)
CREATE TABLE drug_db.drug_pricing_history (
    id BIGSERIAL PRIMARY KEY,
    ndc_11 VARCHAR(11) NOT NULL,
    price_type VARCHAR(20) NOT NULL,
    
    old_price DECIMAL(12,6),
    new_price DECIMAL(12,6) NOT NULL,
    change_percentage DECIMAL(8,4),
    
    effective_date DATE NOT NULL,
    data_source VARCHAR(50) NOT NULL,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pricing_history_ndc ON drug_db.drug_pricing_history(ndc_11, effective_date DESC);

-- ═══════════════════════════════════════════════
-- CLINICAL DATA (FDB — stubbed until spec received)
-- ═══════════════════════════════════════════════

-- Drug interactions
CREATE TABLE drug_db.drug_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    drug_1_identifier VARCHAR(50) NOT NULL,            -- GPI, ingredient, or NDC
    drug_1_identifier_type VARCHAR(20) NOT NULL,
    drug_1_name VARCHAR(500),
    
    drug_2_identifier VARCHAR(50) NOT NULL,
    drug_2_identifier_type VARCHAR(20) NOT NULL,
    drug_2_name VARCHAR(500),
    
    severity VARCHAR(20) NOT NULL,                     -- contraindicated, severe, moderate, mild
    interaction_description TEXT,
    clinical_significance TEXT,
    management_recommendation TEXT,
    
    data_source VARCHAR(50) DEFAULT 'fdb',
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Drug-disease contraindications
CREATE TABLE drug_db.drug_disease_contraindications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    drug_identifier VARCHAR(50) NOT NULL,
    drug_identifier_type VARCHAR(20) NOT NULL,
    drug_name VARCHAR(500),
    
    disease_code VARCHAR(20) NOT NULL,                  -- ICD-10 or proprietary
    disease_code_type VARCHAR(20) NOT NULL,
    disease_name VARCHAR(500),
    
    severity VARCHAR(20) NOT NULL,
    contraindication_description TEXT,
    
    data_source VARCHAR(50) DEFAULT 'fdb',
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Drug dosing limits (for DUR — drug utilization review)
CREATE TABLE drug_db.drug_dosing_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ndc_11 VARCHAR(11),
    gpi_code VARCHAR(14),
    
    max_daily_dose DECIMAL(10,3),
    max_daily_dose_unit VARCHAR(50),
    max_single_dose DECIMAL(10,3),
    max_single_dose_unit VARCHAR(50),
    max_days_supply INTEGER,
    max_quantity_per_fill DECIMAL(10,3),
    
    min_age_years INTEGER,
    max_age_years INTEGER,
    gender_restriction VARCHAR(10),                     -- M, F, or null
    
    pregnancy_category VARCHAR(5),                      -- A, B, C, D, X, N/A
    lactation_risk VARCHAR(50),
    
    data_source VARCHAR(50) DEFAULT 'fdb',
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- THERAPEUTIC EQUIVALENCE (FDA Orange Book)
-- ═══════════════════════════════════════════════

CREATE TABLE drug_db.therapeutic_equivalence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    brand_ndc VARCHAR(11),
    brand_name VARCHAR(500),
    generic_ndc VARCHAR(11),
    generic_name VARCHAR(500),
    
    te_code VARCHAR(5) NOT NULL,                       -- AB, AN, AP, AT, BC, BD, etc.
    is_therapeutically_equivalent BOOLEAN,              -- AB-rated = true
    
    application_number VARCHAR(20),
    
    data_source VARCHAR(50) DEFAULT 'fda_orange_book',
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- DRUG PIPELINE & PATENT TRACKING
-- ═══════════════════════════════════════════════

CREATE TABLE drug_db.drug_pipeline (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    drug_name VARCHAR(500) NOT NULL,
    generic_name VARCHAR(500),
    labeler_name VARCHAR(500),
    
    pipeline_stage VARCHAR(50) NOT NULL,                -- phase_1, phase_2, phase_3, nda_submitted, approved, launched
    therapeutic_area VARCHAR(255),
    indication VARCHAR(500),
    
    expected_approval_date DATE,
    actual_approval_date DATE,
    expected_launch_date DATE,
    actual_launch_date DATE,
    
    patent_expiration_date DATE,
    exclusivity_expiration_date DATE,
    expected_generic_date DATE,
    
    estimated_annual_cost DECIMAL(12,2),
    estimated_patient_population INTEGER,
    
    notes TEXT,
    
    data_source VARCHAR(50),
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- DATA REFRESH TRACKING
-- ═══════════════════════════════════════════════

CREATE TABLE drug_db.data_refresh_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    data_source VARCHAR(50) NOT NULL,
    refresh_type VARCHAR(50) NOT NULL,                  -- full, incremental
    
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL,                        -- running, completed, failed
    
    records_processed INTEGER DEFAULT 0,
    records_added INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_deactivated INTEGER DEFAULT 0,
    price_changes_detected INTEGER DEFAULT 0,
    
    error_message TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 3. Business Logic

### 3.1 Data Refresh Pipeline

**FDA NDC Directory (free, daily):**
1. Scheduled job downloads FDA NDC Directory daily from `https://download.open.fda.gov/`
2. Parse JSON/CSV feed
3. For each NDC: upsert into `drug_products` (create if new, update if changed)
4. Track: records processed, added, updated
5. Detect discontinued products (present in last refresh, absent in current) → mark `marketing_status = discontinued`

**CMS NADAC (free, weekly):**
1. Download weekly NADAC file from CMS
2. Parse CSV
3. For each NDC + NADAC rate: upsert into `drug_pricing` with `price_type = 'NADAC'`
4. Compare to previous NADAC: detect price changes → write to `drug_pricing_history`
5. Calculate change percentage for significant changes (>5%) → generate alert

**FDA Orange Book (free, periodic):**
1. Download Orange Book from FDA
2. Parse therapeutic equivalence evaluations
3. Upsert into `therapeutic_equivalence`
4. New AB-rated generics → generate alert (opportunity for formulary/substitution updates)

**FDB (commercial, per contract — STUBBED):**
1. *(Integration details TBD when FDB spec received)*
2. Expected: periodic data feed (daily or weekly) with full drug monograph data
3. Parsing: per FDB specification
4. Fields populated: GPI codes, AHFS codes, AWP/WAC pricing, drug interactions, dosing limits, clinical data
5. FDB product IDs linked to NDC-11 for cross-referencing

**Drug Pipeline (manual + automated):**
1. FDA approval calendar scraped or manually entered
2. Patent expiration data from Orange Book and public sources
3. Alerts when: patent expires within 12 months, generic approved, biosimilar launched

### 3.2 NDC Lookup Service

The most-called API in the platform. Must be FAST.

1. Input: NDC (any format — 11-digit, 5-4-2, 10-digit with inferred segment)
2. Normalize to NDC-11
3. Redis cache: check cache first (TTL: 24 hours). Cache hit → return immediately.
4. Cache miss → query `drug_products` + current pricing → cache result → return
5. Response includes: full drug detail, current pricing (all types), classification, specialty flags
6. **Performance target:** <10ms from cache, <50ms from database

### 3.3 Drug Pricing Lookup

1. Input: NDC-11, price_type (AWP, WAC, NADAC, FUL, MAC), effective_date (optional, default: today)
2. Query: most recent price where `effective_date <= requested_date` and `termination_date IS NULL OR termination_date > requested_date`
3. Return: price_per_unit, unit_type, effective_date, data_source
4. If no price found for requested type: return null with `available_price_types` list
5. All prices use Decimal — no float contamination

### 3.4 Drug Interaction Check

1. Input: list of drug identifiers (NDCs or GPIs)
2. For each pair: check `drug_interactions` table
3. Return: list of interactions with severity, description, and management recommendation
4. Sorted by severity (contraindicated first)
5. Used by: DUR processing in adjudication engine

### 3.5 Therapeutic Equivalence Lookup

1. Input: NDC-11
2. Query: all therapeutically equivalent products (AB-rated generics, biosimilars)
3. Return: list of equivalent NDCs with TE code, name, and current pricing
4. Used by: generic substitution in adjudication, formulary management, savings analysis

### 3.6 Drug Search

Full-text search across drug database:

1. Input: search term (drug name, NDC, GPI, labeler)
2. Search across: proprietary_name, nonproprietary_name, ndc_11, gpi_code, labeler_name
3. PostgreSQL full-text search with ranking
4. Filters: drug_type, dea_schedule, specialty, marketing_status, therapeutic_class
5. Pagination: limit/offset with total count
6. Used by: formulary builder, report filters, manual claim entry

### 3.7 Price Change Detection & Alerting

Daily job after pricing refresh:

1. Compare current pricing to previous day for all NDCs
2. Significant changes (configurable threshold, default: >5% change):
   - Write to `drug_pricing_history`
   - Generate `drug.price_change` event
   - Alert: "NDC XXXXX (Drug Name) AWP changed from $X.XX to $Y.YY (+Z%)"
3. Aggregate reporting: top 20 price increases by dollar impact across the platform
4. Used by: DataIQ drug trend analytics, billing validation (flag claims with stale pricing)

### 3.8 Multi-Tenant Pricing Overrides

Some tenants have contracted pricing that differs from published AWP/WAC:

1. Table: `drug_db.tenant_pricing_overrides` — tenant_id, NDC, price_type, custom_price, effective_date
2. Pricing lookup checks tenant overrides FIRST, then falls back to standard pricing
3. Used for: MAC lists (tenant-specific maximum allowable cost), contracted pricing
4. Override management: tenant admin can upload MAC list as CSV, system validates and applies

### 3.9 REMS (Risk Evaluation and Mitigation Strategy) Tracking

~74 drugs have FDA-mandated REMS requirements that affect dispensing:

1. **REMS drug table**: NDC (or ingredient), REMS program name, REMS status (active/modified/released)
2. **REMS requirements per drug**:
   - Certified pharmacy required (BOOLEAN) — only REMS-enrolled pharmacies can dispense
   - Certified prescriber required (BOOLEAN) — only REMS-enrolled prescribers can prescribe
   - Patient registry required (BOOLEAN)
   - Lab testing required before dispensing (BOOLEAN + lab type)
   - Restricted distribution (BOOLEAN) — specialty pharmacy only
   - Patient agreement/consent required (BOOLEAN)
3. **Adjudication integration**: when a claim is for a REMS drug, adjudication checks pharmacy REMS certification and prescriber REMS certification before approving
4. **Data source**: FDA REMS database (manual load + periodic refresh from FDA website)
5. **Alerts**: new REMS approved, REMS modified, REMS released

### 3.10 Drug Shortage Tracking

FDA Active Drug Shortage list affects dispensing and substitution:

1. **Shortage table**: NDC/ingredient, shortage status (active/resolved), start date, expected resolution date, reason, alternative NDCs
2. **Data source**: FDA Drug Shortage Database (API or scrape, updated as shortages are reported)
3. **Adjudication impact**: when a drug is in shortage, alternative NDC submissions should not be rejected for "wrong drug" if the alternative is FDA-approved equivalent
4. **Alerts**: new shortage reported, shortage resolved, shortage duration exceeds 90 days

### 3.11 Compound Ingredient Support

Compound claims contain multiple ingredient NDCs:

1. **Ingredient lookup**: given a list of ingredient NDCs, return full drug detail + pricing for each
2. **Compound interaction check**: check all pairwise interactions across all ingredients
3. **Compound pricing**: sum ingredient costs using per-unit pricing for each component
4. **Used by**: adjudication (compound claim processing), billing (compound claim pricing)

### 3.12 Unit Conversion Factors

Billing units differ from packaging units:

1. **Conversion table**: NDC, packaging_unit, packaging_quantity, billing_unit, billing_quantity, conversion_factor
2. **Example**: NDC XXXXX: 1 vial = 10 ML, billing unit = ML, conversion_factor = 10
3. **Used by**: adjudication (verify submitted quantity matches packaging), pricing (per billing unit calculation)
4. **Source**: FDB (when available), FDA NDC Directory packaging data, manual

### 3.13 Multi-Source Generic Indicator

Affects MAC pricing eligibility:

1. **Calculation**: count distinct labelers (manufacturers) for each active generic product (same nonproprietary_name + strength + dosage_form)
2. **Multi-source flag**: 3+ manufacturers → multi_source = TRUE (eligible for MAC pricing)
3. **Single-source flag**: 1 manufacturer → single_source = TRUE (not MAC eligible)
4. **Recalculated**: on every FDA NDC refresh (new generics entering market)

### 3.14 Biosimilar Interchangeability

FDA designates some biosimilars as interchangeable:

1. **Interchangeability flag**: per biosimilar NDC. TRUE = can be substituted at pharmacy without prescriber intervention. FALSE = requires prescriber approval.
2. **Source**: FDA Purple Book (Biological Products)
3. **Used by**: adjudication (generic substitution rules), formulary management, DataIQ biosimilar adoption analytics

### 3.15 NDC-to-Therapeutic-Class Crosswalk (FDB Fallback)

Until FDB integration is complete, provide therapeutic classification via public data:

1. **RxNorm integration**: map NDC → RxCUI → ATC classification via NLM RxNorm API
2. **FDA pharmacologic class**: from FDA NDC structured product labels (SPL)
3. **Crosswalk table**: NDC, therapeutic_class_source, class_code, class_description
4. **When FDB arrives**: FDB GPI codes take priority, crosswalk becomes fallback

### 3.16 Drug Image References

For portal display and member identification:

1. **Image URL table**: NDC, image_url, image_source (dailymed, fdb, manual), image_type (front, back, packaging)
2. **Source**: DailyMed SPL images (free, public), FDB drug images (when available)
3. **Used by**: member portal (pill identification), pharmacy portal (dispensing verification)

### 3.17 Data Source Priority Rules

When multiple sources provide conflicting data for the same field:

| Field | Priority (highest first) |
|---|---|
| AWP pricing | FDB → manual override |
| WAC pricing | FDB → manual override |
| NADAC pricing | CMS NADAC (authoritative) |
| Drug name | FDB → FDA NDC → manual |
| NDC status | FDA NDC (authoritative for marketing status) |
| Therapeutic class | FDB GPI → RxNorm ATC → FDA pharmacologic class |
| Interaction data | FDB (authoritative) |
| TE ratings | FDA Orange Book (authoritative) |

Configurable per tenant: tenant can override priority for specific fields.

---

## 4. API Endpoints

```
/api/v1/drugs/

# Lookup
GET    /lookup/{ndc}                    Full drug detail by NDC (any format)
GET    /lookup/batch                    Batch lookup (up to 100 NDCs)
GET    /search                          Full-text drug search with filters

# Pricing
GET    /pricing/{ndc}                   Current pricing (all types) for NDC
GET    /pricing/{ndc}/{price_type}      Specific price type for NDC
GET    /pricing/{ndc}/history           Price history for NDC
GET    /pricing/changes                 Recent price changes (filterable by date, threshold)

# Clinical
GET    /interactions                    Check interactions between drug list
GET    /contraindications/{ndc}         Drug-disease contraindications
GET    /dosing/{ndc}                    Dosing limits and restrictions

# Equivalence
GET    /equivalents/{ndc}              Therapeutic equivalents (AB-rated generics, biosimilars)

# Classification
GET    /classification/{ndc}            Full classification (GPI, AHFS, ATC, USP)
GET    /classes                         List therapeutic classes (hierarchical)
GET    /classes/{code}/drugs            Drugs in a therapeutic class

# Pipeline
GET    /pipeline                        Drug pipeline (upcoming approvals, patent expirations)
GET    /pipeline/alerts                 Pipeline events in next 12 months

# Tenant overrides
GET    /overrides                       Tenant's pricing overrides (MAC list)
POST   /overrides/upload                Upload MAC list (CSV)
PUT    /overrides/{id}                  Update override
DELETE /overrides/{id}                  Remove override

# Admin
GET    /refresh/status                  Last refresh status per data source
POST   /refresh/{source}               Trigger manual refresh
GET    /stats                           Database statistics (NDC count, active, pricing coverage)
```

---

## 5. Events

### Published
- `drug.price_change` — significant price change detected (>threshold)
- `drug.new_product` — new NDC added to database
- `drug.discontinued` — drug marked discontinued
- `drug.generic_available` — new AB-rated generic detected
- `drug.biosimilar_launched` — biosimilar entered market
- `drug.pipeline_approval` — FDA approval for pipeline drug
- `drug.refresh_completed` — data source refresh finished
- `drug.interaction_updated` — interaction data changed

### Consumed
- None directly — this is a reference data module. Other modules query it.

---

## 6. Default Implementation

Ships fully functional:

- **FDA NDC Directory integration** — daily automated refresh, full drug product catalog
- **CMS NADAC integration** — weekly automated refresh, acquisition cost benchmark
- **FDA Orange Book integration** — therapeutic equivalence ratings
- **FDB integration** — stubbed interface ready for spec. When FDB spec received: implement adapter, populate GPI/AHFS/AWP/WAC/interactions/dosing.
- **Drug pipeline tracker** — manual entry + FDA calendar feed
- **NDC lookup with Redis caching** — <10ms response from cache
- **Drug pricing with history** — all price types, effective date logic, change detection
- **Drug interaction checker** — severity-ranked pairwise check
- **Therapeutic equivalence** — AB-rated generic lookup
- **Full-text drug search** — by name, NDC, GPI, labeler with filters
- **Price change alerting** — daily detection, configurable threshold
- **Multi-tenant MAC list support** — CSV upload for tenant-specific pricing overrides
- **Data refresh tracking** — full audit trail of every refresh job

---

## 7. Performance Requirements

- NDC lookup (cache hit): <10ms
- NDC lookup (cache miss): <50ms
- Batch lookup (100 NDCs): <500ms
- Drug search: <200ms
- Pricing lookup: <20ms
- Interaction check (10 drugs, 45 pairs): <100ms
- Full data refresh (FDA NDC, ~300K NDCs): <30 minutes
- NADAC refresh (~50K NDCs): <10 minutes

---

## 8. Data Retention

- Drug products: indefinite (reference data, never delete — mark inactive)
- Pricing: indefinite (current + all historical for trend analysis)
- Pricing history: indefinite (price change events)
- Interactions: current only (replaced on each FDB refresh)
- Pipeline: indefinite
- Refresh logs: 2 years

---

## 9. Test Scenarios (100% Coverage Required)

### Critical Paths (100%)
- NDC lookup returns correct drug for all format variations (11-digit, 5-4-2, 10-digit)
- Pricing lookup returns most recent effective price, not future or expired price
- Interaction check detects known interactions and returns correct severity
- Therapeutic equivalence returns AB-rated generics only (not BC, BD)
- Data refresh creates new records, updates changed records, deactivates removed records
- Price change detection catches changes above threshold and ignores below
- MAC list upload validates and applies correctly, overrides standard pricing

### Edge Cases
- NDC with no pricing in any source → return drug detail with empty pricing array, not error
- NDC format with leading zeros stripped → normalization handles correctly
- Two price changes on same day for same NDC → both recorded in history
- Drug discontinued then re-marketed → status correctly updated on each refresh
- Interaction check with single drug → returns empty list (no self-interaction)
- MAC list with duplicate NDC → reject with clear error indicating which row

---

## 10. Session Decomposition

1. **Core data model + FDA integration**: drug_products table, FDA NDC Directory downloader/parser, data refresh pipeline, NDC normalization utility, Redis caching layer, NDC lookup API, drug search (full-text)
2. **Pricing + clinical + equivalence**: drug_pricing tables, CMS NADAC integration, Orange Book integration, price change detection, pricing lookup API, interaction checker, dosing limits, therapeutic equivalence, pricing history, tenant MAC list overrides
3. **FDB stub + pipeline + alerting**: FDB adapter interface (stubbed), drug pipeline table and API, price change alerting, data refresh tracking, stats endpoint, batch lookup, classification endpoints
