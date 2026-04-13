# PRD — Module 16: ReclaimRx (FWA Detection & Recovery) — FINAL

**Module:** ReclaimRx  
**Folder:** `modules/reclaimrx/`  
**Priority:** Phase 2, Batch A  
**Dependencies:** Core Platform (Module 1), consumes events from Billing (Module 11)  

---

## 1. Purpose

ReclaimRx is the fraud, waste, and abuse (FWA) detection, recovery, and audit engine. It serves ALL client types — manufacturers, health plans, TPAs, 340B entities, and workers comp programs. It operates at two speeds:

1. **Real-time detection** — during claims adjudication (Module 8). Because InfinityRx IS the adjudicator, ReclaimRx can flag, block, or modify claims at the point of adjudication. No other hub, copay platform, or FWA vendor has this capability. They all analyze claims after the fact.

2. **Post-adjudication detection** — batch analysis of historical claims data. Pattern detection, statistical anomaly scoring, and behavioral profiling across claim history. This is what every competitor does. We do it too — but with better data because we have the raw adjudication stream, not a delayed claims file.

**Competitive positioning:** TrialCard's RxSpotlight is rules-based post-adjudication. Paysign's Dynamic Business Rules detects accumulator/maximizer on first fill at 97%. Neither operates inside the adjudicator. Our real-time detection during adjudication is unique in the market.

---

## 2. Architecture

```
                    REAL-TIME PATH                    POST-ADJUDICATION PATH
                    ══════════════                    ══════════════════════
                    
Claim arrives ──► Adjudication Engine               Scheduled Job / On-Demand
                        │                                     │
                   ReclaimRx API call                    Pull claims batch
                        │                                     │
                  ┌─────┴──────┐                    ┌────────┴────────┐
                  │            │                    │                 │
             Deterministic  ML Risk              Deterministic    ML Anomaly
             Rules Check    Score                Batch Rules      Detection
                  │            │                    │                 │
                  └─────┬──────┘                    └────────┬────────┘
                        │                                    │
                   Risk Assessment                    Flagged Claims
                        │                                    │
                  ┌─────┴──────┐                    ┌────────┴────────┐
                  │            │                    │                 │
               PASS      FLAG/BLOCK             Queue for         Auto-alert
               (proceed)  (action)              Investigation      if critical
                                                     │
                                              ┌──────┴──────┐
                                              │             │
                                         Recovery       Audit
                                         Workflow       Management
                                              │             │
                                         Estimation    Letters/Tracking
                                              │             │
                                         Collections   Recoupment
```

---

## 3. Core Concepts

### 3.1 Detection Rule
A configurable logic unit that evaluates one or more claims against a specific fraud/waste/abuse pattern. Every rule has:
- **Definition**: what pattern to look for
- **Match criteria**: which claims/entities to evaluate (filterable by program, client type, claim type, NDC, pharmacy, etc.)
- **Parameters**: configurable thresholds (e.g., "flag when NQ exceeds 110% of WAC")
- **Confidence scoring**: how confident is the flag (High/Medium/Low based on threshold proximity)
- **Action**: what to do on match — flag for review, block claim, alert, auto-recover, log only
- **Client type applicability**: which client types this rule applies to (manufacturer, health plan, TPA, 340B, workers comp, or all)

Rules are pre-built with researched defaults. Tenants can adjust parameters, enable/disable, or create custom rules.

### 3.2 Detection Profile
A collection of detection rules configured for a specific client type or tenant. Profiles are templates that can be assigned to tenants:
- **Manufacturer Copay Profile**: NQ inflation, bill-reverse-rebill, accumulator/maximizer detection, phantom claims
- **Health Plan Profile**: network leakage, formulary non-compliance, inappropriate utilization, prescriber outliers, controlled substance monitoring
- **TPA Profile**: claims validation, eligibility verification, duplicate detection, COB accuracy
- **340B Profile**: duplicate discount detection, contract pharmacy compliance, covered entity verification
- **Workers Comp Profile**: state formulary compliance, treatment guideline adherence, duration monitoring

Tenants can use a standard profile, customize it, or build their own from the rule library.

### 3.3 Risk Score
Every claim and every entity (pharmacy, prescriber, member) gets a risk score from 0-100:
- 0-25: Low risk (normal behavior)
- 26-50: Elevated (monitor, no action)
- 51-75: High (flag for investigation)
- 76-100: Critical (immediate action — block or alert)

Thresholds configurable per tenant.

### 3.4 Entity Profile
A behavioral baseline for each pharmacy, prescriber, and member. Built from historical claims data:
- **Pharmacy profile**: average claim value, average contracted rate, NDC concentration, reversal rate, volume patterns, geographic patterns, weekend/holiday activity
- **Prescriber profile**: prescribing patterns by therapeutic class, average quantity/days supply, DEA schedule distribution, patient volume, geographic patterns
- **Member profile**: fill frequency, pharmacy utilization pattern, drug interaction history, coverage pattern

Deviations from an entity's own baseline trigger alerts. Cross-entity comparison identifies outliers within networks.

### 3.5 Recovery
When FWA is confirmed, the system calculates the recovery amount:
- **Conservative**: only amounts with confirmed methodology and high confidence
- **Mid**: includes statistically estimated amounts with medium confidence
- **Aggressive**: includes all flagged amounts including informational flags

Every recovery estimate carries a confidence tier and a methodology tag explaining how it was calculated. These numbers must be defensible to a CFO, an auditor, or in litigation.

---

## 4. Data Model

```sql
CREATE SCHEMA reclaimrx;

-- ═══════════════════════════════════════════════
-- DETECTION RULES
-- ═══════════════════════════════════════════════

CREATE TABLE reclaimrx.detection_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID,                                  -- null = system-wide (available to all tenants)
    
    -- Identity
    rule_code VARCHAR(50) NOT NULL UNIQUE,            -- e.g., MFR-001, HP-003, ALL-007
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    -- Categories: pricing_integrity, billing_pattern, utilization,
    --            controlled_substance, network_compliance, accumulator,
    --            eligibility, duplicate, 340b, workers_comp, custom
    
    -- Applicability
    client_types JSONB NOT NULL DEFAULT '["all"]',    -- manufacturer, health_plan, tpa, 340b, workers_comp, all
    detection_mode VARCHAR(50) NOT NULL,              -- real_time, post_adjudication, both
    
    -- Logic
    rule_type VARCHAR(50) NOT NULL,                   -- threshold, pattern, comparison, statistical, composite
    rule_logic JSONB NOT NULL,                        -- the actual rule definition (see section 5)
    
    -- Parameters (configurable per tenant)
    default_parameters JSONB NOT NULL,                -- default thresholds, windows, etc.
    
    -- Actions
    default_action VARCHAR(50) NOT NULL,              -- flag, block, alert, log, auto_recover
    confidence_scoring JSONB,                         -- how to assign High/Medium/Low
    
    -- Status
    is_system BOOLEAN DEFAULT FALSE,                  -- system rules can't be deleted
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Tenant-specific rule configurations (overrides defaults)
CREATE TABLE reclaimrx.tenant_rule_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    detection_rule_id UUID NOT NULL REFERENCES reclaimrx.detection_rules(id),
    
    is_enabled BOOLEAN DEFAULT TRUE,
    custom_parameters JSONB,                          -- overrides default_parameters
    custom_action VARCHAR(50),                        -- overrides default_action
    custom_confidence JSONB,                          -- overrides confidence_scoring
    
    applies_to_programs JSONB,                        -- null = all programs for this tenant
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, detection_rule_id)
);

-- Detection profiles (template collections of rules)
CREATE TABLE reclaimrx.detection_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    client_type VARCHAR(50) NOT NULL,
    rule_ids JSONB NOT NULL,                          -- array of detection_rule IDs
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- FLAGGED CLAIMS (detection results)
-- ═══════════════════════════════════════════════

CREATE TABLE reclaimrx.flagged_claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    -- Source claim
    claim_id UUID,                                    -- ref to adjudication or billing claim
    auth_number VARCHAR(50) NOT NULL,
    date_of_service DATE NOT NULL,
    
    -- Claim data snapshot
    pharmacy_npi VARCHAR(10) NOT NULL,
    pharmacy_name VARCHAR(255),
    prescriber_npi VARCHAR(10),
    member_id VARCHAR(100),
    ndc VARCHAR(11),
    drug_name VARCHAR(255),
    quantity DECIMAL(10,3),
    days_supply INTEGER,
    
    -- Amounts
    billed_amount DECIMAL(12,2),
    paid_amount DECIMAL(12,2),
    expected_amount DECIMAL(12,2),                    -- what the system thinks it should be
    variance_amount DECIMAL(12,2),                    -- paid minus expected
    
    -- Detection
    detection_rule_id UUID REFERENCES reclaimrx.detection_rules(id),
    rule_code VARCHAR(50) NOT NULL,
    rule_name VARCHAR(255) NOT NULL,
    detection_mode VARCHAR(50) NOT NULL,              -- real_time or post_adjudication
    
    -- Risk assessment
    risk_score INTEGER NOT NULL,                      -- 0-100
    confidence_tier VARCHAR(20) NOT NULL,             -- high, medium, low
    severity VARCHAR(20) NOT NULL,                    -- critical, high, medium, low, informational
    
    -- Evidence
    evidence JSONB NOT NULL,                          -- what triggered the flag (specifics vary by rule)
    comparison_data JSONB,                            -- baseline data used for comparison
    
    -- Action taken
    action_taken VARCHAR(50),                         -- flagged, blocked, alerted, auto_recovered, logged
    action_detail TEXT,
    
    -- Investigation
    investigation_status VARCHAR(50) DEFAULT 'open',
    -- open, under_review, confirmed_fraud, confirmed_waste, confirmed_abuse,
    -- false_positive, inconclusive, recovered, closed
    
    assigned_to UUID,
    assigned_at TIMESTAMPTZ,
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    resolution TEXT,
    
    -- Recovery
    recovery_estimate_id UUID,
    
    -- Grouping
    investigation_id UUID,                            -- groups related flags into one investigation
    
    -- Program context
    client_id UUID,
    program_id UUID,
    program_name VARCHAR(255),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_flagged_tenant_status ON reclaimrx.flagged_claims(tenant_id, investigation_status);
CREATE INDEX idx_flagged_pharmacy ON reclaimrx.flagged_claims(tenant_id, pharmacy_npi);
CREATE INDEX idx_flagged_prescriber ON reclaimrx.flagged_claims(tenant_id, prescriber_npi);
CREATE INDEX idx_flagged_member ON reclaimrx.flagged_claims(tenant_id, member_id);
CREATE INDEX idx_flagged_rule ON reclaimrx.flagged_claims(tenant_id, rule_code);
CREATE INDEX idx_flagged_severity ON reclaimrx.flagged_claims(tenant_id, severity);

-- ═══════════════════════════════════════════════
-- ENTITY PROFILES (behavioral baselines)
-- ═══════════════════════════════════════════════

CREATE TABLE reclaimrx.pharmacy_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    pharmacy_npi VARCHAR(10) NOT NULL,
    pharmacy_name VARCHAR(255),
    
    -- Volume metrics
    avg_daily_claims DECIMAL(10,2),
    avg_weekly_claims DECIMAL(10,2),
    avg_monthly_claims DECIMAL(10,2),
    total_claims_lifetime INTEGER,
    
    -- Financial metrics
    avg_claim_amount DECIMAL(12,2),
    avg_ingredient_cost DECIMAL(12,2),
    avg_dispensing_fee DECIMAL(12,2),
    avg_nq_to_wac_ratio DECIMAL(8,4),
    avg_contracted_rate DECIMAL(8,4),
    
    -- Behavioral metrics
    reversal_rate DECIMAL(8,4),                       -- % of claims reversed
    rejection_rate DECIMAL(8,4),
    weekend_holiday_rate DECIMAL(8,4),                -- % of claims on weekends/holidays
    new_patient_rate DECIMAL(8,4),
    controlled_substance_rate DECIMAL(8,4),
    
    -- NDC concentration
    top_ndcs JSONB,                                   -- top 10 NDCs by volume with %
    ndc_diversity_score DECIMAL(8,4),                 -- how concentrated vs diverse
    
    -- Comparison
    network_peer_group VARCHAR(100),                  -- chain, independent, specialty, etc.
    percentile_rank_volume INTEGER,
    percentile_rank_claim_value INTEGER,
    percentile_rank_reversal_rate INTEGER,
    
    -- Risk
    composite_risk_score INTEGER DEFAULT 0,            -- 0-100
    risk_trend VARCHAR(20),                            -- increasing, stable, decreasing
    
    -- Flags
    is_flagged BOOLEAN DEFAULT FALSE,
    flag_count INTEGER DEFAULT 0,
    confirmed_fraud_count INTEGER DEFAULT 0,
    
    last_calculated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, pharmacy_npi)
);

CREATE TABLE reclaimrx.prescriber_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    prescriber_npi VARCHAR(10) NOT NULL,
    prescriber_name VARCHAR(255),
    
    avg_daily_scripts DECIMAL(10,2),
    avg_quantity DECIMAL(10,2),
    avg_days_supply DECIMAL(10,2),
    
    -- Prescribing patterns
    top_therapeutic_classes JSONB,
    controlled_substance_rate DECIMAL(8,4),
    schedule_ii_rate DECIMAL(8,4),
    brand_vs_generic_rate DECIMAL(8,4),
    
    -- Patient metrics
    unique_patient_count INTEGER,
    avg_scripts_per_patient DECIMAL(8,2),
    patient_geographic_spread DECIMAL(8,4),
    
    composite_risk_score INTEGER DEFAULT 0,
    risk_trend VARCHAR(20),
    
    last_calculated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, prescriber_npi)
);

CREATE TABLE reclaimrx.member_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    member_id VARCHAR(100) NOT NULL,
    
    fill_frequency_days DECIMAL(8,2),
    pharmacy_count INTEGER,
    prescriber_count INTEGER,
    avg_days_supply INTEGER,
    
    controlled_substance_fills INTEGER,
    early_refill_count INTEGER,
    pharmacy_shopping_score INTEGER,                   -- 0-100
    
    -- Accumulator/maximizer
    is_accumulator_plan BOOLEAN DEFAULT FALSE,
    accumulator_plan_detected_at TIMESTAMPTZ,
    accumulator_impact_amount DECIMAL(12,2),
    
    composite_risk_score INTEGER DEFAULT 0,
    
    last_calculated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, member_id)
);

-- Profile snapshots for trend analysis
CREATE TABLE reclaimrx.profile_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    entity_type VARCHAR(20) NOT NULL,                 -- pharmacy, prescriber, member
    entity_id VARCHAR(100) NOT NULL,
    snapshot_date DATE NOT NULL,
    metrics JSONB NOT NULL,                            -- all profile metrics at this point in time
    risk_score INTEGER,
    UNIQUE(tenant_id, entity_type, entity_id, snapshot_date)
);

-- ═══════════════════════════════════════════════
-- ML MODEL MANAGEMENT
-- ═══════════════════════════════════════════════

CREATE TABLE reclaimrx.ml_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID,                                   -- null = system-wide base model
    
    model_name VARCHAR(255) NOT NULL,
    model_type VARCHAR(100) NOT NULL,                 -- xgboost_classifier, isolation_forest, custom
    purpose VARCHAR(100) NOT NULL,                    -- claim_risk_scoring, pharmacy_anomaly, prescriber_anomaly, accumulator_detection
    
    -- Training
    training_data_start DATE,
    training_data_end DATE,
    training_sample_count INTEGER,
    feature_set JSONB NOT NULL,                        -- which features the model uses
    hyperparameters JSONB,
    
    -- Performance
    accuracy DECIMAL(8,4),
    precision_score DECIMAL(8,4),
    recall DECIMAL(8,4),
    f1_score DECIMAL(8,4),
    auc_roc DECIMAL(8,4),
    confusion_matrix JSONB,
    
    -- Status
    status VARCHAR(50) DEFAULT 'training',            -- training, validating, active, retired, failed
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT FALSE,
    
    -- Model artifact
    model_artifact_path TEXT,                          -- path to serialized model
    
    deployed_at TIMESTAMPTZ,
    retired_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Model performance monitoring
CREATE TABLE reclaimrx.ml_predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id UUID NOT NULL REFERENCES reclaimrx.ml_models(id),
    tenant_id UUID NOT NULL,
    
    claim_id UUID,
    entity_type VARCHAR(20),
    entity_id VARCHAR(100),
    
    risk_score INTEGER NOT NULL,
    feature_values JSONB,                              -- input features for explainability
    feature_importance JSONB,                          -- which features drove the score
    
    -- Outcome tracking (for retraining)
    actual_outcome VARCHAR(50),                        -- confirmed_fraud, confirmed_clean, unknown
    outcome_recorded_at TIMESTAMPTZ,
    
    predicted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- INVESTIGATIONS & RECOVERY
-- ═══════════════════════════════════════════════

CREATE TABLE reclaimrx.investigations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    investigation_number VARCHAR(50) NOT NULL,
    title VARCHAR(500) NOT NULL,
    
    -- Subject
    subject_type VARCHAR(50) NOT NULL,                -- pharmacy, prescriber, member, program
    subject_entity_id VARCHAR(100) NOT NULL,
    subject_name VARCHAR(255),
    
    -- Scope
    investigation_type VARCHAR(100) NOT NULL,
    -- desk_audit, field_audit, fraud_investigation, waste_review,
    -- abuse_investigation, 340b_audit, accumulator_analysis, compliance_review
    
    date_range_start DATE,
    date_range_end DATE,
    flagged_claim_count INTEGER DEFAULT 0,
    
    -- Amounts
    total_flagged_amount DECIMAL(15,2) DEFAULT 0,
    recovery_estimate_conservative DECIMAL(15,2) DEFAULT 0,
    recovery_estimate_mid DECIMAL(15,2) DEFAULT 0,
    recovery_estimate_aggressive DECIMAL(15,2) DEFAULT 0,
    actual_recovered DECIMAL(15,2) DEFAULT 0,
    
    -- Status
    status VARCHAR(50) DEFAULT 'open',
    -- open, in_progress, pending_response, escalated,
    -- recovery_in_progress, recovered, closed_no_action, closed_referred
    
    priority VARCHAR(20) DEFAULT 'medium',
    
    -- Assignment
    assigned_to UUID,
    assigned_at TIMESTAMPTZ,
    
    -- Timeline
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    first_contact_at TIMESTAMPTZ,
    response_due_date DATE,
    resolved_at TIMESTAMPTZ,
    
    -- Resolution
    resolution_type VARCHAR(100),
    -- full_recovery, partial_recovery, corrective_action, no_action,
    -- referred_to_legal, referred_to_law_enforcement, network_termination
    resolution_notes TEXT,
    
    -- Documents
    documents JSONB,                                   -- array of file IDs (letters, evidence, responses)
    
    client_id UUID,
    program_id UUID,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Investigation timeline / activity log
CREATE TABLE reclaimrx.investigation_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES reclaimrx.investigations(id),
    tenant_id UUID NOT NULL,
    
    activity_type VARCHAR(100) NOT NULL,
    -- note_added, status_changed, letter_sent, response_received,
    -- document_attached, assigned, escalated, recovery_recorded,
    -- audit_scheduled, audit_completed
    
    description TEXT NOT NULL,
    performed_by UUID,
    file_id UUID,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Recovery records
CREATE TABLE reclaimrx.recoveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES reclaimrx.investigations(id),
    tenant_id UUID NOT NULL,
    
    recovery_method VARCHAR(100) NOT NULL,
    -- offset_from_payment, direct_payment, prefund_adjustment,
    -- credit_memo, network_termination_forfeiture
    
    amount DECIMAL(15,2) NOT NULL,
    confidence_tier VARCHAR(20) NOT NULL,              -- high, medium, low
    methodology_tag VARCHAR(255) NOT NULL,             -- how amount was calculated
    
    status VARCHAR(50) DEFAULT 'estimated',
    -- estimated, demanded, disputed, agreed, collected, written_off
    
    demand_date DATE,
    demand_letter_file_id UUID,
    response_date DATE,
    collection_date DATE,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Letter templates
CREATE TABLE reclaimrx.letter_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID,                                    -- null = system-wide
    name VARCHAR(255) NOT NULL,
    letter_type VARCHAR(100) NOT NULL,
    -- initial_notification, demand_letter, audit_notification,
    -- audit_findings, appeal_response, final_demand, network_termination
    
    template_content TEXT NOT NULL,                     -- with merge fields
    merge_fields JSONB,                                -- available merge fields
    regulatory_notes TEXT,                              -- state-specific legal requirements
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- ACCUMULATOR / MAXIMIZER
-- ═══════════════════════════════════════════════

CREATE TABLE reclaimrx.accumulator_detections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    member_id VARCHAR(100) NOT NULL,
    plan_bin VARCHAR(10),
    plan_pcn VARCHAR(10),
    plan_group VARCHAR(15),
    
    -- Detection
    detection_method VARCHAR(100) NOT NULL,            -- first_fill_analysis, pattern_analysis, plan_database_match
    detection_fill_number INTEGER,                     -- which fill triggered detection (1 = first fill)
    detection_confidence DECIMAL(8,4),                 -- 0-1.0 confidence score
    
    -- Classification
    program_type VARCHAR(50),                          -- accumulator, maximizer, unknown
    
    -- Financial impact
    copay_assistance_amount DECIMAL(12,2),
    amount_applied_to_deductible DECIMAL(12,2),
    amount_not_applied DECIMAL(12,2),
    projected_annual_impact DECIMAL(12,2),
    
    -- Recommended action
    recommended_action VARCHAR(255),
    action_taken VARCHAR(255),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- EXTERNAL VERIFICATION INTEGRATIONS
-- ═══════════════════════════════════════════════

CREATE TABLE reclaimrx.verification_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    vendor_type VARCHAR(100) NOT NULL,                 -- bpg_patientlens, complete_bi, custom
    vendor_name VARCHAR(255) NOT NULL,
    
    api_endpoint VARCHAR(500),
    api_credentials_ref VARCHAR(255),
    
    cost_per_inquiry DECIMAL(8,2),                     -- track costs
    monthly_inquiry_limit INTEGER,
    inquiries_used_this_month INTEGER DEFAULT 0,
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE reclaimrx.verification_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    verification_config_id UUID REFERENCES reclaimrx.verification_configs(id),
    
    claim_id UUID,
    member_id VARCHAR(100),
    ndc VARCHAR(11),
    
    request_data JSONB,
    response_data JSONB,
    
    result_summary VARCHAR(500),
    cost DECIMAL(8,2),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- REPORTING
-- ═══════════════════════════════════════════════

CREATE TABLE reclaimrx.report_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    name VARCHAR(255) NOT NULL,
    report_type VARCHAR(100) NOT NULL,
    -- fwa_summary, pharmacy_scorecard, recovery_report,
    -- accumulator_impact, 340b_compliance, investigation_status,
    -- trend_analysis, regulatory_submission
    
    schedule VARCHAR(50),                              -- daily, weekly, monthly, quarterly, on_demand
    delivery_method VARCHAR(50),
    delivery_recipients JSONB,
    
    filters JSONB,                                     -- default filters for this report
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 5. Pre-Built Detection Rules

### 5.1 Universal Rules (All Client Types)

| Code | Rule | Default Threshold | Confidence | Action |
|------|------|-------------------|------------|--------|
| ALL-001 | **Duplicate claim** — same member, same NDC, same DOS, different auth | Exact match | High | Block (real-time), Flag (post) |
| ALL-002 | **Phantom pharmacy** — NPI not in NCPDP database or OIG excluded | Any match | High | Block |
| ALL-003 | **Phantom prescriber** — NPI invalid, DEA inactive, or OIG excluded | Any match | High | Block |
| ALL-004 | **Days supply manipulation** — quantity and days supply inconsistent with NDC packaging/dosing | >20% deviation from expected | Medium | Flag |
| ALL-005 | **Early refill** — fill date < configured % of previous days supply | <75% of days supply | Medium | Flag (or apply plan's refill-too-soon rules) |
| ALL-006 | **Weekend/holiday volume spike** — pharmacy claims volume on weekend/holiday exceeds weekday average | >200% of weekday avg | Low | Log |
| ALL-007 | **Geographic anomaly** — member filling at pharmacy >100 miles from home address | >100 miles | Low | Flag |

### 5.2 Manufacturer Program Rules

| Code | Rule | Default Threshold | Confidence | Action |
|------|------|-------------------|------------|--------|
| MFR-001 | **NQ inflation** — (DV+NQ) exceeds WAC per unit × quantity | NQ > 110% WAC: Low, >120%: Med, >150%: High | Tiered | Flag |
| MFR-002 | **Bill-reverse-rebill** — same pharmacy, same NDC, same member, reversal followed by rebill with higher NQ or different DV within X days | Within 14 days, NQ increased or DV changed | High | Flag + Alert |
| MFR-003 | **Contracted rate deviation** — pharmacy's (DV+NQ)/(AWP×qty) deviates from their own historical baseline | >15% deviation from 90-day avg | Medium | Flag |
| MFR-004 | **Volume spike** — pharmacy submits >X% more claims for specific NDC vs rolling average | >200% of 30-day rolling avg | Medium | Alert |
| MFR-005 | **eVoucher/coupon abuse** — same voucher code used for multiple patients or exceeded max uses | Any violation | High | Block |
| MFR-006 | **Phantom patient** — claims for members with no matching enrollment record or unverifiable identity | No enrollment match | High | Block + Alert |
| MFR-007 | **Accumulator/maximizer detection** — copay assistance not counting toward member's deductible/OOP | First-fill analysis (see 5.7) | Configurable | Alert + Recommend action |
| MFR-008 | **Statement credit abuse** — statement account pharmacy submitting claims that should be statement-only | Program config mismatch | High | Block |
| MFR-009 | **Under-reimbursement gaming** — pharmacy consistently submitting U&C at minimum to maximize POS adjustment | U&C < acquisition cost pattern | Medium | Flag |

### 5.3 Health Plan Rules

| Code | Rule | Default Threshold | Confidence | Action |
|------|------|-------------------|------------|--------|
| HP-001 | **Network leakage** — claims filled at out-of-network pharmacies when in-network options available | Within 10 miles of in-network pharmacy | Low | Log + Report |
| HP-002 | **Formulary non-compliance** — non-formulary drug dispensed without PA | PA not on file | Medium | Flag |
| HP-003 | **Therapeutic duplication** — member receiving two drugs from same therapeutic class simultaneously | Same TC1 code, overlapping fills | Medium | Flag |
| HP-004 | **Drug-disease contraindication** — drug inappropriate for member's diagnosed conditions (if available) | Known contraindication | High | Alert |
| HP-005 | **Prescriber outlier** — prescriber's volume for a specific drug exceeds peer group by >3 standard deviations | >3 SD from peer avg | Medium | Flag |
| HP-006 | **Pharmacy audit trigger** — pharmacy flagged on multiple rules exceeding threshold in period | >5 flags in 30 days | High | Trigger desk audit |
| HP-007 | **Controlled substance monitoring** — opioid MME exceeds CDC guideline, multiple prescribers, multiple pharmacies | >90 MME/day, >3 prescribers, >3 pharmacies | High | Alert |
| HP-008 | **High-cost claimant** — member's claims exceed configured threshold in period | Top 1% by cost | Low | Report |
| HP-009 | **Inappropriate quantity** — quantity exceeds FDA max recommended or plan limits | >FDA max or plan limit | Medium | Flag |
| HP-010 | **Refill pattern anomaly** — member consistently fills exactly on day X (possible auto-refill waste) | <3 days supply remaining at each fill | Low | Log |

### 5.4 TPA Rules

| Code | Rule | Default Threshold | Confidence | Action |
|------|------|-------------------|------------|--------|
| TPA-001 | **Eligibility mismatch** — claim paid for member not eligible on DOS | No active coverage on DOS | High | Flag + Recovery |
| TPA-002 | **COB error** — primary/secondary payer assignment incorrect | Incorrect COB sequence | Medium | Flag |
| TPA-003 | **Plan design violation** — benefit applied doesn't match plan configuration | Copay, deductible, or OOP mismatch | High | Flag |
| TPA-004 | **Provider credential issue** — pharmacy or prescriber credentials expired or suspended | Credential expired/suspended | High | Block |

### 5.5 340B Rules

| Code | Rule | Default Threshold | Confidence | Action |
|------|------|-------------------|------------|--------|
| 340B-001 | **Duplicate discount** — 340B discounted drug also subject to manufacturer rebate for same claim | Same claim, both discounts | High | Block + Alert |
| 340B-002 | **Contract pharmacy non-compliance** — claim from pharmacy not registered as 340B contract pharmacy | No active contract pharmacy agreement | High | Flag |
| 340B-003 | **Covered entity verification** — entity claiming 340B pricing not on HRSA database | Not in HRSA OPA | High | Block |
| 340B-004 | **Split billing accuracy** — 340B vs non-340B classification doesn't match patient eligibility | Eligibility mismatch | Medium | Flag |
| 340B-005 | **Diversion** — drug dispensed to non-eligible patient at 340B pricing | Patient not eligible for CE's services | High | Flag + Alert |

### 5.6 Workers Compensation Rules

| Code | Rule | Default Threshold | Confidence | Action |
|------|------|-------------------|------------|--------|
| WC-001 | **State formulary non-compliance** — drug not on state's WC formulary | Not on formulary | Medium | Flag |
| WC-002 | **Exceeds state fee schedule** — reimbursement exceeds state's WC fee schedule | >100% of state max | High | Flag |
| WC-003 | **Treatment duration exceeded** — fills exceed expected treatment duration for injury type | >150% expected duration | Medium | Flag |
| WC-004 | **Opioid guidelines** — opioid prescribing exceeds state WC opioid guidelines | Exceeds state threshold | High | Alert |

### 5.7 Accumulator/Maximizer Detection (First-Fill)

This is the rule that must match or beat Paysign's 97% accuracy:

**Method 1 — Plan database match**: Maintain database of known accumulator/maximizer plans by BIN/PCN/Group. On first fill, check if member's plan is in the database. Fastest, highest accuracy for known plans.

**Method 2 — First-fill analysis**: On the first fill, compare the copay amount against expected patient pay. If copay assistance is applied but the member's deductible/OOP credit is $0 or doesn't match the copay amount, flag as accumulator.

**Method 3 — Pattern analysis**: After 2-3 fills, compare accumulation patterns. If copay assistance amount is not accumulating toward deductible/OOP, flag as accumulator/maximizer.

**Default behavior**: Run all three methods. Method 1 fires on first fill (if plan is known). Method 2 fires on first fill. Method 3 fires on third fill as confirmation.

---

## 6. ML Anomaly Detection

### 6.1 Claim Risk Scoring Model (XGBoost)

**Features** (configurable per tenant):
- NQ/WAC ratio
- DV/AWP ratio
- Claim amount percentile (within pharmacy and across network)
- Days since last fill (for this member + NDC)
- Pharmacy volume percentile for this NDC
- Pharmacy's reversal rate
- Prescriber's volume percentile for this NDC
- Member's fill frequency
- Geographic distance (member to pharmacy)
- Day of week / time of day
- Claim amount vs pharmacy's average
- NDC concentration at pharmacy

**Training**: Train per tenant on confirmed outcomes (confirmed fraud, confirmed clean). Requires minimum 10,000 labeled claims before first model deployment. Until then, deterministic rules only.

**Output**: Risk score 0-100, plus top 3 feature importances (for explainability).

**Retraining**: Monthly automatic retrain when new confirmed outcomes are available. Performance metrics tracked: accuracy, precision, recall, F1, AUC-ROC. Alert if performance degrades below threshold.

### 6.2 Pharmacy Anomaly Model (Isolation Forest)

Unsupervised model that identifies pharmacies behaving differently from peers:
- Input: pharmacy profile metrics (20+ features)
- Output: anomaly score (-1 to 1, where -1 = most anomalous)
- No labeled data required — works from day one
- Recalculated monthly

### 6.3 Model Governance
- Every model version stored with training data reference, hyperparameters, and performance metrics
- Active model clearly marked; retired models preserved
- A/B testing support: run new model in shadow mode (score but don't act) alongside active model
- Human review required before any model is promoted to active
- All predictions logged with feature values for auditability and explainability

---

## 7. Investigation & Recovery Workflow

### 7.1 Investigation Lifecycle

1. **Creation**: Auto-created when flagged claims exceed threshold for an entity (e.g., >5 flags for same pharmacy in 30 days), or manually created by analyst
2. **Assignment**: Assigned to investigator (configurable routing by type/severity)
3. **Research**: Investigator reviews flagged claims, entity profiles, claim history, external verification results
4. **Contact**: Initial notification sent to subject (pharmacy/prescriber) using configurable letter template. Response period starts.
5. **Response tracking**: System tracks response due date, documents received, communication history
6. **Determination**: Investigator classifies: confirmed fraud, confirmed waste, confirmed abuse, false positive, or inconclusive
7. **Recovery calculation**: If confirmed, calculate recovery using conservative/mid/aggressive methodology
8. **Demand**: Generate demand letter with recovery amount, deadline, and payment instructions
9. **Collection**: Track payment receipt. If not received, escalation workflow (second demand → final demand → referral to legal/collections → network termination)
10. **Resolution**: Record outcome, update entity profiles, feed back to ML model as confirmed outcome

### 7.2 Audit Management

For formal pharmacy audits (desk or field):

1. **Audit initiation**: Select pharmacy, date range, claim sample
2. **Notification**: Send audit notification letter (must comply with state audit laws — configurable per state)
3. **Document request**: Specify required documents (prescriptions, signature logs, inventory records)
4. **Receipt tracking**: Track documents received, missing, late
5. **Review**: Analyst reviews documents against claims
6. **Findings**: Document findings per claim (confirmed, adjusted, dismissed)
7. **Report**: Generate audit findings report with total discrepancy amount
8. **Response period**: State-mandated response period for pharmacy (configurable per state)
9. **Appeal**: If pharmacy appeals, track appeal with evidence
10. **Final determination**: Confirmed recovery amount after appeals
11. **Recoupment**: Offset from future payments or direct collection

### 7.3 Recovery Estimation

Every recovery estimate includes:
- **Amount**: calculated to the penny using Decimal/ROUND_HALF_UP
- **Confidence tier**: High (confirmed methodology), Medium (statistical estimate), Low (informational)
- **Methodology tag**: exactly how the amount was calculated (e.g., "NQ excess over 110% WAC × quantity across 847 claims")
- **Supporting data**: claim IDs, amounts, calculations
- **Defensibility**: every estimate must be reproducible from the underlying data

### 7.4 Letter Generation

Pre-built templates for all letter types with configurable merge fields:
- Initial notification
- Demand letter
- Audit notification (state-specific variants)
- Audit findings
- Appeal response
- Final demand
- Network termination notice

Templates configurable per tenant. System generates PDF using tenant's branding. All letters tracked in investigation timeline.

---

## 8. API Endpoints

```
/api/v1/reclaimrx/

# Real-time API (called by adjudication engine)
POST   /evaluate                        Evaluate claim against rules (real-time path)

# Detection Rules
GET    /rules                           List all rules (system + tenant)
GET    /rules/{id}                      Get rule detail
POST   /rules                           Create custom rule
PUT    /rules/{id}                      Update rule (or tenant override)
GET    /profiles                        List detection profiles
POST   /profiles/{id}/assign            Assign profile to tenant

# Flagged Claims
GET    /flags                           List flagged claims (filterable by severity, rule, entity, status)
GET    /flags/{id}                      Flag detail with evidence
PUT    /flags/{id}                      Update investigation status
POST   /flags/{id}/assign               Assign to investigator
POST   /flags/{id}/dismiss              Dismiss as false positive

# Entity Profiles
GET    /pharmacy-profiles               List pharmacy profiles (sortable by risk score)
GET    /pharmacy-profiles/{npi}         Pharmacy profile detail
GET    /prescriber-profiles             List prescriber profiles
GET    /prescriber-profiles/{npi}       Prescriber profile detail
GET    /member-profiles                 List member profiles
GET    /member-profiles/{id}            Member profile detail
GET    /profiles/{type}/{id}/history    Profile history (snapshots)

# Investigations
GET    /investigations                  List investigations
POST   /investigations                  Create investigation
GET    /investigations/{id}             Investigation detail
PUT    /investigations/{id}             Update investigation
GET    /investigations/{id}/timeline    Activity timeline
POST   /investigations/{id}/activity    Add activity
POST   /investigations/{id}/letter      Generate letter from template

# Recoveries
GET    /recoveries                      List recoveries
POST   /recoveries                      Create recovery record
PUT    /recoveries/{id}                 Update recovery status
GET    /recoveries/summary              Recovery summary by period/client/type

# Accumulator
GET    /accumulator/detections          List accumulator detections
GET    /accumulator/impact              Financial impact summary
GET    /accumulator/plan-database       Known accumulator/maximizer plans

# ML Models
GET    /models                          List models
GET    /models/{id}                     Model detail with performance metrics
POST   /models/{id}/retrain             Trigger retraining
GET    /models/{id}/predictions         Recent predictions

# External Verification
POST   /verify                          Run external verification (BPG, Complete BI)
GET    /verification-results            List verification results
GET    /verification/usage              Usage tracking and costs

# Reports
GET    /reports/fwa-summary             FWA summary dashboard data
GET    /reports/pharmacy-scorecard      Pharmacy scorecard (risk-ranked)
GET    /reports/recovery-report         Recovery amounts by period
GET    /reports/accumulator-impact      Accumulator financial impact
GET    /reports/340b-compliance         340B compliance report
GET    /reports/trend-analysis          FWA trend analysis
GET    /reports/rule-effectiveness      Which rules are catching the most

# Network Graph Analysis
GET    /graph/communities               List detected suspicious communities
GET    /graph/entity/{type}/{id}        Relationship map around an entity
GET    /graph/visualization/{community_id}  Visual graph data for investigation UI

# Payment Holds
POST   /holds                           Place payment hold on entity
GET    /holds                           List active holds
DELETE /holds/{id}                      Release hold (with reason)

# Tipline
POST   /tips                            Submit anonymous tip
GET    /tips                            List tips (investigator view)
PUT    /tips/{id}                       Review tip (dismiss/convert to investigation)

# Regulatory Reporting
POST   /regulatory-reports              Generate regulatory report from investigation
GET    /regulatory-reports              List submitted reports
PUT    /regulatory-reports/{id}         Update report status
GET    /regulatory-reports/deadlines    Upcoming reporting deadlines

# Credentialing
POST   /credentialing-score             Generate credentialing risk score for pharmacy

# Watchlist
GET    /watchlist                        List watchlisted entities
POST   /watchlist/{entity_id}/acknowledge  Acknowledge watchlist entry
GET    /watchlist/predictions            Predictive risk scores

# Network Intelligence
GET    /network-risk/{npi}              Network-level risk score (anonymized cross-tenant)
```

---

## 9. Events

### Published
- `fwa.claim_flagged` — claim flagged by any rule
- `fwa.claim_blocked` — claim blocked at adjudication (real-time)
- `fwa.investigation_opened` — new investigation created
- `fwa.investigation_resolved` — investigation resolved
- `fwa.recovery_demanded` — demand letter sent
- `fwa.recovery_collected` — recovery amount received
- `fwa.accumulator_detected` — accumulator/maximizer plan identified
- `fwa.pharmacy_risk_elevated` — pharmacy risk score crossed threshold
- `fwa.model_performance_degraded` — ML model accuracy dropped below threshold
- `fwa.payment_hold_placed` — payment hold placed on entity (consumed by Billing)
- `fwa.payment_hold_released` — payment hold lifted
- `fwa.tip_received` — anonymous tip submitted
- `fwa.regulatory_report_due` — regulatory reporting deadline approaching
- `fwa.regulatory_report_submitted` — report sent to agency
- `fwa.credentialing_risk_elevated` — pharmacy credentialing score increased (consumed by Pharmacy Directory)
- `fwa.suspicious_community_detected` — graph analysis found suspicious network cluster
- `fwa.watchlist_added` — entity added to predictive watchlist
- `fwa.cross_program_pattern` — same entity flagged across multiple programs

### Consumed
- `claim.adjudicated` — evaluate post-adjudication rules
- `claim.reversed` — update related flags/investigations
- `ap.created` — claims entering billing (cross-check)
- `ap.settled` — payment made, update hold tracking
- `exclusion.match_found` — entity on exclusion list
- `pharmacy.application_submitted` — trigger credentialing risk score (from Pharmacy Directory)
- `pharmacy.ownership_changed` — re-evaluate risk and consider watchlist

---

## 10. Competitive Gap Capabilities (From Market Research)

### 10.1 Relationship / Network Graph Analysis

Individual entity profiling catches solo bad actors. Graph analysis catches RINGS — pharmacy + prescriber + patient colluding together. A pharmacy that looks normal individually might be part of a network where one prescriber routes all patients to one distant pharmacy.

**Implementation:**
- Build a relationship graph: nodes = pharmacies, prescribers, members. Edges = claim relationships (prescriber wrote script → pharmacy filled it → for member).
- Weight edges by volume, frequency, and dollar amount.
- Community detection algorithm identifies tight clusters of entities that interact disproportionately with each other compared to the broader network.
- Anomalous communities flagged: unusual geographic spread (prescriber in State A, pharmacy in State B, patients from State C), unusually high volume within the cluster, financial outliers within the cluster.
- Graph rebuilt nightly from claims data. Visualization available in investigation UI — investigator can see the relationship map around any flagged entity.
- **Default rule:** `ALL-008` — **Suspicious network cluster** — community of entities with >80% self-referral rate and geographic spread >200 miles. Confidence: Medium. Action: Flag for investigation.

### 10.2 Prepay Claim Hold / Payment Suspension

When there's credible evidence of fraud, the system holds payment BEFORE it goes out — not just flag after payment.

**Implementation:**
- When a pharmacy or prescriber is under active investigation with severity HIGH or CRITICAL, the system can place a **payment hold** on all claims involving that entity.
- Payment hold = claims are adjudicated normally but the AP record in Billing is created with a `held` status. The payment batch skips held APs.
- Hold is configurable: all claims for entity, only claims matching specific rules, or only claims above a dollar threshold.
- Hold requires investigator or admin authorization. Automatic hold can be configured for CRITICAL severity investigations.
- Hold releases: investigator lifts hold (with reason), or hold auto-expires after configurable period (default: 90 days).
- Integration with Billing module: emit `fwa.payment_hold_placed` event. Billing module listens and marks affected APs as `held`.
- **Default rule:** `ALL-009` — **Auto-hold on critical investigation** — when an investigation reaches CRITICAL severity, automatically hold future payments for the subject entity. Configurable per tenant.

### 10.3 Anonymous Tipline / Fraud Reporting Intake

CMS requires Medicare plans to have anonymous fraud reporting. Industry best practice for all plan types.

**Implementation:**
- Secure web form accessible from all portals (client, pharmacy, medical, member) and via a public URL.
- Fields: what are you reporting (provider, pharmacy, member, other), description of suspected activity, date range, supporting details. Reporter info optional.
- Anonymous submissions: no login required, no IP logging on tip submissions (privacy).
- Each tip creates a `tip_record` in ReclaimRx. Tips are reviewed by investigators.
- Tips can be: dismissed (no basis), converted to investigation (creates investigation with tip as evidence), or merged into existing investigation.
- Configurable: phone number intake tracking (for clients who want a compliance hotline number that routes to the tip system).
- **Data model addition:** `reclaimrx.tip_records` table with: tenant_id, tip_type, subject_description, detail_text, reporter_name (optional), reporter_contact (optional), is_anonymous, status (new/reviewed/converted/dismissed), investigation_id (if converted), created_at.

### 10.4 Regulatory / Law Enforcement Reporting

For Medicare/Medicaid clients, confirmed FWA must be reported to external agencies.

**Implementation:**
- Configurable reporting destinations per tenant: CMS MEDIC, state Medicaid Fraud Control Units (MFCU), OIG, state boards of pharmacy, DEA (controlled substance fraud), law enforcement.
- Report templates per destination (each agency has different requirements and formats).
- One-click report generation from investigation: pre-populates with investigation findings, evidence, recovery amounts.
- Submission tracking: date sent, to whom, status (submitted/acknowledged/in_review/closed), reference numbers.
- Regulatory reporting timeline compliance: configurable deadlines (e.g., CMS requires reporting within 60 days of identification for Medicare).
- Alert when reporting deadline approaches.
- **Data model addition:** `reclaimrx.regulatory_reports` table with: investigation_id, destination_type, destination_name, report_content, submitted_at, status, reference_number, deadline_date.

### 10.5 Pharmacy Credentialing Risk Score

Feed FWA intelligence INTO pharmacy network admission decisions (Module 3).

**Implementation:**
- When a new pharmacy applies to join a network, ReclaimRx generates a **credentialing risk score** based on:
  - OIG/SAM exclusion check (from Core Platform)
  - Prior fraud history (if pharmacy NPI has been flagged in any tenant's data — anonymized cross-tenant signal)
  - Ownership change detection (new NPI owner vs established pharmacy)
  - Geographic risk factors (pharmacy in high-fraud zip code based on historical data)
  - License status and disciplinary history (state board of pharmacy data)
- Score: 0-100. Low risk = fast-track admission. Medium = standard review. High = enhanced review with additional documentation required.
- Ongoing monitoring: if a credentialed pharmacy's risk score crosses a threshold, alert network management.
- **API:** `POST /api/v1/reclaimrx/credentialing-score` — called by Pharmacy Directory module when processing new pharmacy applications.
- **Event:** `fwa.credentialing_risk_elevated` — when an existing pharmacy's risk score increases significantly.

### 10.6 Telehealth Fraud Detection Rules

Telehealth-enabled fraud is a growing CMS concern — prescribers writing high-volume scripts via telehealth without proper patient evaluation.

**Pre-built rules:**

| Code | Rule | Default Threshold | Confidence | Action |
|------|------|-------------------|------------|--------|
| TH-001 | **Telehealth prescriber volume** — telehealth prescriber writing >X scripts/day | >50 scripts/day | Medium | Flag |
| TH-002 | **Telehealth geographic dispersion** — telehealth prescriber's patients spread across >X states | >10 states | Medium | Flag |
| TH-003 | **Telehealth + high-cost drug** — telehealth prescriber writing high-cost specialty or GLP-1 drugs at >X% of their volume | >40% of volume | Medium | Flag |
| TH-004 | **Telehealth + controlled substance** — telehealth prescriber writing Schedule II-V controlled substances | Any | High | Alert |
| TH-005 | **Telehealth prescriber-pharmacy affinity** — >X% of telehealth prescriber's scripts filled at a single pharmacy | >50% at one pharmacy | High | Flag + investigate |

### 10.7 Cross-Program / Cross-Tenant Intelligence

A pharmacy committing fraud on one program is likely doing it on others.

**Within a tenant (cross-program):**
- When a pharmacy is flagged on Program A, automatically check all other programs the pharmacy participates in for similar patterns.
- Cross-program flag summary: "Pharmacy X flagged on 3 of 5 programs for NQ inflation."
- Cross-program investigation: combine evidence from all programs into a single investigation.

**Across tenants (anonymized network intelligence):**
- Maintain a **network risk registry** — anonymized aggregate risk data. Each pharmacy NPI has a network-level risk score derived from all tenants' data without exposing any tenant's specific claims or findings.
- When Tenant A flags a pharmacy, the network risk score for that NPI increases. Tenant B sees the elevated network risk score (but NOT Tenant A's specific findings or data).
- Network risk score factored into credentialing and real-time detection.
- **Privacy:** No claim-level data shared. No tenant identifiers. Only aggregate risk signals. Tenants can opt out of contributing to network intelligence.

### 10.8 Predictive Risk / Early Warning

Beyond detecting current fraud, predict which entities are trending toward fraud before rules trigger.

**Implementation:**
- **Predictive model** (separate from the detection XGBoost model): trained on the SEQUENCE of behavioral changes that preceded confirmed fraud in historical data.
- Features: rate of change in volume, new high-cost NDC adoption, ownership change recency, claim pattern variability, geographic expansion, reversal rate trend.
- Output: 30/60/90-day fraud probability score for each pharmacy.
- Pharmacies above threshold placed on **watchlist** — increased monitoring frequency, lower detection thresholds.
- Watchlist visible in investigation dashboard. Investigators can proactively review watched pharmacies before rules trigger.
- **Default rule:** `ALL-010` — **Predictive watchlist trigger** — pharmacy's 30-day fraud probability exceeds configurable threshold. Action: add to watchlist + alert.

### 10.9 False Positive Rate Tracking

- Track false positive rate per detection rule: (dismissed flags / total flags) per rule per period.
- Dashboard: rule effectiveness matrix showing detection rate vs false positive rate.
- Rules with >20% false positive rate (configurable threshold) auto-flagged for threshold review.
- When an investigator dismisses a flag as false positive, the system logs which rule generated it and the dismissal reason.
- Monthly job: recalculate false positive rates per rule, recommend threshold adjustments for rules above target.
- Target: <10% false positive rate per rule. New rules start with conservative thresholds (more false positives) and tighten as confirmed outcomes accumulate.

### 10.10 State Audit Law Compliance Engine

Pre-loaded table of state-specific pharmacy audit rules:

| State Rule | Example | System Behavior |
|------------|---------|----------------|
| Advance notice period | TX: 14 days, NY: 10 days | Block audit notification letter if notice period not met |
| Lookback period limit | FL: 2 years, CA: 2 years | Prevent selecting claims outside lookback window |
| Audit frequency limit | Some states: 1 per 12 months per pharmacy | Block audit initiation if frequency exceeded |
| Appeal deadline | Varies: 30-90 days | Track appeal deadline, alert when approaching |
| Documentation requirements | Varies by state | Checklist of required documents per state |
| Extrapolation limits | Some states prohibit extrapolation from sample | Flag when investigation uses extrapolation in restricted state |
| On-site audit notice | Some states require advance notice for on-site | Block on-site scheduling if notice not sent |

Table configurable per tenant. System validates compliance before any audit action proceeds. Non-compliant actions BLOCKED with explanation of which state rule is violated.

### 10.11 Statute of Limitations Tracking

- Every investigation and recovery demand tracks the applicable statute of limitations.
- Statute varies by: state, claim type, fraud vs waste vs abuse, federal vs state program.
- Pre-loaded table with statutes by state and type.
- Alert when statute approaches (configurable: default 90 days before expiration).
- BLOCK recovery demand filing if statute has expired (with admin override for documented exceptions).
- Dashboard: investigations approaching statute deadline, sorted by urgency.

### 10.12 Corrective Action Plans

Not all findings require recovery. Some require education and process improvement:

1. **Corrective action issuance**: generate corrective action letter identifying the issue, required changes, and compliance deadline.
2. **Action items**: specific steps the pharmacy/prescriber must take (e.g., "implement dual verification for controlled substance prescriptions").
3. **Compliance tracking**: track whether each action item is completed by deadline.
4. **Follow-up**: if action items not completed by deadline, escalate to recovery demand or network termination.
5. **Re-monitoring**: after corrective action period, automatically run detection rules at enhanced sensitivity for the entity for configurable period (default: 6 months).
6. **Templates**: pre-built corrective action letter templates by issue type.

### 10.13 Investigation Cost-Benefit Tracking

- Track costs per investigation: staff hours (configurable hourly rate per role), external verification fees, legal fees, travel costs (field audits).
- Track recoveries per investigation: estimated, demanded, collected.
- ROI calculation: (collected amount - investigation cost) / investigation cost.
- Dashboard: investigation ROI by type, by rule, by entity type.
- Minimum ROI threshold: configurable per tenant. Investigations projected below threshold flagged for cost-benefit review before proceeding.
- Aggregate reporting: total investment in FWA program vs total recoveries by period.

### 10.14 Claim-Level Pending (Real-Time)

Separate from entity-wide payment holds (section 10.2). For individual high-risk claims:

- During real-time evaluation, certain rules can PEND a claim instead of blocking or flagging.
- Pended claim = adjudication response tells the pharmacy "claim is under review" (using NCPDP reject code configurable per tenant).
- Pended claims queued for manual review. Reviewer can: approve (claim processes normally), deny (claim rejected), or request additional information.
- Configurable timeout: if pended claim not reviewed within X hours (default: 24), auto-approve or auto-deny (configurable per rule).
- Track pend rate per rule to ensure it doesn't create operational bottleneck.

### 10.15 Performance Requirements
- Real-time rule evaluation: <100ms total (all applicable rules combined)
- Post-adjudication batch analysis: process 1M claims in <30 minutes
- Graph analysis (community detection): complete rebuild in <2 hours for 10M claims
- Entity profile recalculation: <5 minutes for all active entities
- ML model inference: <50ms per claim
- Investigation search/filter: <3 seconds

### 10.16 Data Retention
- Flagged claims: retained per tenant policy (default: 7 years)
- Investigations and recoveries: retained for 10 years (legal requirement for some recovery types)
- Entity profiles: current profile always available; snapshots retained per policy
- ML model artifacts: all versions retained for audit trail (model governance)
- Tip records: retained for 7 years
- Regulatory reports: retained permanently

### 10.17 ML Model Fairness / Bias Monitoring
- Track detection rates by pharmacy type: independent, chain, specialty, mail order, PSAO-affiliated.
- Track detection rates by geographic region, pharmacy size (claim volume), and years in operation.
- Alert if detection rate for any category exceeds 2x the overall average — potential bias in the model.
- Monthly fairness report: detection rate, false positive rate, and confirmed fraud rate broken down by pharmacy characteristics.
- If bias detected: retrain model with balanced sampling or adjusted features. Document remediation.
- Fairness metrics included in model performance dashboard alongside accuracy/precision/recall.

### 10.18 Litigation Hold
- When litigation is pending or reasonably anticipated related to an investigation:
  - Legal team places a litigation hold flag on the investigation.
  - ALL documents associated with the investigation (flags, evidence, communications, letters, notes, verification results) are preserved indefinitely regardless of normal retention schedules.
  - Archival and deletion BLOCKED for held investigations.
  - Alert if any user attempts to modify or delete held investigation records.
  - Hold persists until legal team explicitly releases it with documented authorization.
- Litigation hold log: who placed it, when, reason, who released it, when.
- System prevents accidental data loss during active litigation.

### 10.19 Adversarial Adaptation Monitoring
- Track detection rule effectiveness over time: flags per rule per month, confirmed fraud per rule per month.
- If a rule's detection rate drops >50% over 90 days without threshold changes: alert — possible adversarial adaptation.
- Track fraud pattern evolution: new schemes that don't match existing rules.
- Quarterly "detection gap analysis": compare total confirmed fraud vs fraud that was caught by rules. Estimate what's being missed.
- Recommend new rules or threshold adjustments based on adaptation trends.
- Feed into ML model retraining: if rule-based detection drops, ML should compensate by learning the new patterns from labeled data.

---

## 11. Default Implementation

Ships fully functional with:

- **50+ pre-built detection rules** across 9 categories (universal, manufacturer, health plan, TPA, 340B, workers comp, accumulator, telehealth, predictive)
- **5 detection profiles** ready to assign (manufacturer, health plan, TPA, 340B, workers comp)
- **All rules active with researched default thresholds** — tenants refine, not build from scratch
- **Entity profiling** — pharmacy, prescriber, and member profiles built automatically from claims data
- **Relationship graph analysis** — network/community detection to identify fraud rings
- **XGBoost risk scoring model** — ships with base model, auto-retrains per tenant when labeled data available
- **Isolation Forest pharmacy anomaly detection** — works immediately with no labeled data
- **Predictive risk model** — 30/60/90-day fraud probability scores, watchlist management
- **Investigation workflow** — full lifecycle from flag to recovery with configurable steps
- **Prepay payment hold** — suspend payments to entities under critical investigation
- **Anonymous tipline** — secure web intake for fraud reports from any source
- **Audit management** — desk and field audit workflows with state-compliant letter templates
- **Recovery estimation** — three-tier (conservative/mid/aggressive) with methodology tags
- **10+ letter templates** — including regulatory reporting templates for CMS MEDIC, MFCU, OIG
- **Regulatory reporting** — configurable destinations, deadline tracking, submission management
- **Accumulator/maximizer detection** — three-method approach targeting 97%+ first-fill accuracy
- **Pharmacy credentialing risk score** — API for network admission decisions
- **Cross-program intelligence** — intra-tenant cross-program analysis
- **Network risk registry** — anonymized cross-tenant risk signals (opt-in)
- **Telehealth fraud rules** — 5 pre-built rules for telehealth-specific patterns
- **External verification integration** — BPG PatientLens and Complete BI pre-built
- **Real-time and post-adjudication** detection paths
- **Claim-level pending** for high-risk claims during real-time evaluation
- **False positive rate tracking** per rule with auto-threshold adjustment recommendations
- **50-state audit law compliance table** pre-loaded (notice periods, lookback limits, frequency limits, appeal deadlines)
- **Statute of limitations tracking** with expiration alerts and filing blocks
- **Corrective action plan workflow** with compliance tracking and re-monitoring
- **Investigation cost-benefit tracking** with ROI per investigation and per rule
- **Data retention** defaults: 7 years flags, 10 years investigations, permanent regulatory reports

New tenant setup: assign a detection profile (or customize), configure alert routing, and go. Rules start detecting immediately with default thresholds. Refine thresholds from real data over time.

---

## 11. Test Scenarios (100% Coverage Required)

### Detection Rules (100% — every rule individually tested)
- Each of 39 rules tested with: known-positive claim (should flag), known-negative claim (should not flag), threshold boundary claim
- Threshold override: tenant custom threshold correctly replaces default
- Rule enable/disable: disabled rule does not fire
- Confidence scoring: correct tier assigned based on threshold proximity

### Financial (100%)
- Recovery calculations penny-perfect (Decimal/ROUND_HALF_UP)
- NQ inflation math: (DV+NQ) vs WAC × qty calculated correctly
- Accumulator impact: projected annual impact calculated correctly
- Verification cost tracking accurate

### Critical Paths (100%)
- Real-time evaluation returns in <100ms (must not slow adjudication)
- Tenant isolation: Tenant A's flags/profiles/investigations invisible to Tenant B
- ML model predictions logged with feature values
- Investigation lifecycle: all status transitions valid
- Letter generation: merge fields populate correctly

### Edge Cases
- Claim that triggers multiple rules — all flags created, highest severity wins
- Pharmacy with zero history — profile returns defaults, no division by zero
- ML model not yet trained for tenant — gracefully falls back to deterministic rules only
- External verification API timeout — degrades gracefully, flags for retry
- Rule with custom parameters AND tenant override — correct precedence
- Payment hold placed and then investigation dismissed — hold auto-releases, APs resume normal flow
- Anonymous tip with no actionable information — properly dismissed without investigation
- Graph analysis on new tenant with <100 claims — gracefully returns no communities (insufficient data)
- Cross-tenant network risk — tenant opts out, their data excluded, other tenants unaffected
- Regulatory report deadline approaching — alert fires at correct days-before threshold
- Predictive model score for pharmacy with recent ownership change — ownership recency factored correctly

---

## 13. Session Decomposition

1. **Detection engine + prepay hold**: Rule evaluation engine (deterministic), routing rules, real-time API endpoint, post-adjudication batch job, rule configuration, tenant overrides, detection profiles, payment hold integration with Billing module, telehealth rules
2. **Entity profiling + ML + graph**: Pharmacy/prescriber/member profile builders, snapshot jobs, XGBoost model training/serving, Isolation Forest, predictive risk model, relationship graph builder, community detection, credentialing risk score API, network risk registry, model management, prediction logging
3. **Investigation + recovery + regulatory**: Investigation lifecycle, activity log, recovery estimation (3-tier), demand workflow, audit management, letter generation, collections tracking, anonymous tipline intake, regulatory reporting (CMS MEDIC, MFCU, OIG), cross-program analysis
4. **Accumulator + verification + reporting**: Accumulator detection (3 methods), plan database, external verification integrations (BPG, Complete BI), all reporting endpoints, dashboard data, watchlist management
