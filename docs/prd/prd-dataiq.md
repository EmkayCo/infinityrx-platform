# PRD — Module 23: DataIQ (Analytics & Business Intelligence) — FINAL

**Module:** DataIQ  
**Folder:** `modules/dataiq/`  
**Priority:** Phase 2, Batch B  
**Dependencies:** Core Platform (Module 1), reads from Billing (11), ReclaimRx (16), Reporting (15) read replica  

---

## 1. Purpose

DataIQ is the advanced analytics and business intelligence engine. While Reporting (Module 15) generates standard reports and regulatory filings, DataIQ provides the intelligence layer: real-time analytics, predictive modeling, data quality monitoring, benchmarking, self-service exploration, and automated insights.

**Reporting answers:** "What happened?" (claims processed, payments made, invoices sent)  
**DataIQ answers:** "Why did it happen? What will happen next? What should we do about it?"

**Competitive target:** Xevant — 12 modules, 300 dashboards, 3,500 reports, real-time alerts, PBM-specific analytics. We match their breadth and exceed their depth because we own the adjudication data (they only see claims files).

---

## 2. Core Capabilities

### 2.1 Real-Time Analytics Engine
Live analytics that update as claims flow through the system — not batch-processed overnight.

- **Live claim volume tracker**: claims per minute/hour/day by program, client, pharmacy, NDC. Trending vs historical baseline.
- **Live financial tracker**: dollars flowing through AP and AR in real-time. Prefund burn rate updating with every claim.
- **Live FWA tracker**: flags per hour, active investigations, recovery pipeline.
- **Anomaly detection**: statistical process control (SPC) on all key metrics. When a metric deviates beyond 2σ from its moving average, fire an alert before a human notices.

**Implementation:** Redis-backed counters and time-series updated by event consumers. Events from Billing, ReclaimRx, and other modules increment counters in real-time. Dashboard widgets read from Redis, not the database.

### 2.2 Drug Trend Analytics
The most asked-for analytics in PBM. Every client wants to understand what's driving their drug spend.

**Pre-built analyses:**
| Analysis | Description |
|---|---|
| Drug spend trending | Total spend by drug/class over time with YoY comparison |
| Brand vs generic ratio | Generic fill rate trending, savings opportunity quantification |
| Therapeutic class analysis | Spend and utilization by therapeutic class, identifying high-growth classes |
| New drug impact | Newly launched drugs: adoption rate, spend impact, displacement of existing therapies |
| GLP-1 tracking | Dedicated GLP-1/weight loss drug utilization and cost trending (top concern 2025-2026) |
| Specialty drug analysis | Specialty spend as % of total, per-script cost trending, therapy categories |
| Biosimilar adoption | Biosimilar vs reference biologic fill rates, conversion opportunity |
| Price inflation tracking | NDC-level price changes over time, WAC/AWP inflation rates |
| Rebate optimization | Formulary position vs rebate revenue, identifying switch opportunities |
| Top drugs by spend/volume | Pareto analysis: which drugs drive 80% of spend |

### 2.3 Network Analytics
Pharmacy network performance and optimization.

**Pre-built analyses:**
| Analysis | Description |
|---|---|
| Pharmacy performance scorecard | Cost, quality, adherence metrics per pharmacy |
| Network adequacy | Geographic coverage analysis (% of members within X miles of network pharmacy) |
| Network leakage | Out-of-network utilization with savings potential if converted |
| Cost variation | Same-drug cost comparison across pharmacies, identifying overpaying |
| Specialty pharmacy analysis | Specialty network performance, accreditation status, clinical outcomes |
| Mail order conversion | Members eligible for mail order with estimated savings |
| 340B analysis | 340B pharmacy participation and impact on plan cost |
| Pharmacy type distribution | Chain vs independent vs specialty vs mail, and cost/quality comparison |

### 2.4 Member Analytics
Understanding member behavior and outcomes.

**Pre-built analyses:**
| Analysis | Description |
|---|---|
| Adherence dashboard | PDC by drug class, by member segment, trending over time |
| High-cost claimant analysis | Top 1% members by cost, therapy profiles, intervention opportunities |
| Polypharmacy risk | Members on 5+ concurrent medications with interaction potential |
| Therapy gaps | Members who should be on a therapy but aren't (clinical opportunity) |
| Member migration | Members entering/leaving benefit phases (deductible, coverage gap, catastrophic) |
| Opioid utilization | MME tracking, doctor shopping, CDC guideline compliance |
| New-to-therapy | Members starting new medications, early adherence tracking |

### 2.5 Financial Analytics
Advanced financial intelligence beyond standard billing reports.

**Pre-built analyses:**
| Analysis | Description |
|---|---|
| Cost driver decomposition | What's driving spend changes: utilization, price, mix, or new drugs |
| PMPM trending | Per member per month cost trending with component breakdown |
| Spread analysis | Plan paid vs pharmacy reimbursement analysis (2026 CAA transparency) |
| Rebate ROI | Rebate revenue vs formulary restrictions impact on member access |
| Client profitability | Revenue (fees) vs cost (operations) per client, per program |
| Forecast modeling | 12-month cost projection using trend, seasonality, and known pipeline events |
| What-if scenarios | Model impact of formulary changes, network changes, benefit design changes |

### 2.6 Data Quality Monitoring
Automated monitoring of data flowing through the platform.

**Monitors:**
| Monitor | What It Checks | Alert Condition |
|---|---|---|
| Claim volume | Claims received per hour/day | <50% or >200% of 30-day average |
| Missing fields | % of claims with null required fields | >5% null rate on any required field |
| Invalid formats | NPI format, NDC format, date format failures | >1% invalid rate |
| Duplicate detection | Duplicate claim submissions within window | >0.1% duplicate rate |
| Amount reasonableness | Claim amounts vs historical distribution | Amount >5σ from mean for same NDC |
| Timeliness | Time from claim DOS to receipt | >30 days for >10% of claims |
| Source consistency | Claims from each source match expected volume | Source drops to zero or spikes >300% |
| Referential integrity | Foreign key references (pharmacy NPI, prescriber NPI, member ID) | >2% unmatched references |

Data quality score: 0-100 per tenant per day. Aggregated from all monitors. Dashboard shows trend. Alert when score drops below configurable threshold (default: 95).

### 2.7 Benchmarking Engine
Compare any metric against configurable benchmarks.

**Benchmark types:**
- **Internal:** compare program A vs program B, client A vs client B, pharmacy A vs pharmacy B
- **Historical:** compare this period vs same period last year
- **Target:** compare against configurable target values (SLA thresholds, budget targets)
- **Industry:** compare against configurable industry benchmark data (loaded from external sources or manually entered)

**Benchmark configuration:**
- Any metric can have benchmarks attached
- Benchmarks are configurable per tenant
- Visual: green/yellow/red status based on performance vs benchmark
- Alerts when performance crosses benchmark thresholds

### 2.8 Self-Service Exploration
Power users can explore data without waiting for custom reports.

- **Pivot table builder**: select dimensions (drug, pharmacy, prescriber, program, date), select measures (claim count, total cost, average cost, utilization rate), pivot/filter/drill
- **Cohort analysis**: define a member cohort by criteria (diagnosis, medication, demographics), track outcomes over time
- **Ad-hoc query**: for technical users, write SQL queries against the read replica. Results returned as table or chart. Query timeout enforced. PHI access logged.
- **Saved explorations**: save pivot configurations and queries for reuse. Share with other users in the tenant.

---

## 3. Data Model

```sql
CREATE SCHEMA dataiq;

-- Real-time metrics (Redis-backed, this table is the persistent store)
CREATE TABLE dataiq.metric_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    metric_key VARCHAR(255) NOT NULL UNIQUE,           -- e.g., 'claim_volume.hourly', 'spend.daily.by_program'
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100) NOT NULL,
    
    -- Calculation
    calculation_type VARCHAR(50) NOT NULL,              -- counter, gauge, histogram, derived
    source_event VARCHAR(100),                          -- which event updates this metric
    aggregation VARCHAR(50),                            -- sum, count, avg, min, max, percentile
    dimensions JSONB,                                   -- which dimensions to break down by
    
    -- SPC (statistical process control)
    spc_enabled BOOLEAN DEFAULT FALSE,
    spc_window_days INTEGER DEFAULT 30,
    spc_sigma_threshold DECIMAL(4,2) DEFAULT 2.00,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Metric snapshots (for historical trend analysis)
CREATE TABLE dataiq.metric_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    metric_definition_id UUID NOT NULL REFERENCES dataiq.metric_definitions(id),
    
    snapshot_date DATE NOT NULL,
    snapshot_hour INTEGER,                              -- 0-23, null for daily snapshots
    
    dimensions JSONB,                                   -- {program_id: X, client_id: Y}
    
    value DECIMAL(18,4) NOT NULL,
    sample_count INTEGER,
    
    -- SPC
    moving_average DECIMAL(18,4),
    standard_deviation DECIMAL(18,4),
    upper_control_limit DECIMAL(18,4),
    lower_control_limit DECIMAL(18,4),
    is_anomalous BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_metrics_tenant_date ON dataiq.metric_snapshots(tenant_id, metric_definition_id, snapshot_date DESC);

-- Data quality scores
CREATE TABLE dataiq.data_quality_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    score_date DATE NOT NULL,
    
    overall_score DECIMAL(5,2) NOT NULL,
    
    -- Component scores
    volume_score DECIMAL(5,2),
    completeness_score DECIMAL(5,2),
    format_score DECIMAL(5,2),
    timeliness_score DECIMAL(5,2),
    consistency_score DECIMAL(5,2),
    referential_score DECIMAL(5,2),
    
    -- Details
    issues JSONB,                                       -- [{monitor, metric, threshold, actual, severity}]
    
    UNIQUE(tenant_id, score_date)
);

-- Benchmarks
CREATE TABLE dataiq.benchmarks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    name VARCHAR(255) NOT NULL,
    metric_key VARCHAR(255) NOT NULL,
    benchmark_type VARCHAR(50) NOT NULL,                -- internal, historical, target, industry
    
    target_value DECIMAL(18,4),
    warning_threshold DECIMAL(18,4),
    critical_threshold DECIMAL(18,4),
    comparison_operator VARCHAR(10) DEFAULT 'gte',      -- gte, lte, eq, between
    
    -- For internal benchmarks
    comparison_entity_type VARCHAR(100),
    comparison_entity_id UUID,
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Saved explorations
CREATE TABLE dataiq.saved_explorations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    
    name VARCHAR(255) NOT NULL,
    exploration_type VARCHAR(50) NOT NULL,              -- pivot, cohort, query
    configuration JSONB NOT NULL,                       -- full config to reproduce
    
    is_shared BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insight alerts (auto-generated when analytics detect something noteworthy)
CREATE TABLE dataiq.insight_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    insight_type VARCHAR(100) NOT NULL,
    -- spend_spike, utilization_change, new_drug_adoption, adherence_drop,
    -- network_leakage_increase, data_quality_degradation, benchmark_breach,
    -- trend_reversal, anomaly_detected, forecast_deviation
    
    severity VARCHAR(20) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    
    metric_key VARCHAR(255),
    metric_value DECIMAL(18,4),
    threshold_value DECIMAL(18,4),
    
    -- Context
    affected_entity_type VARCHAR(100),
    affected_entity_id UUID,
    affected_entity_name VARCHAR(255),
    
    -- Action
    recommended_action TEXT,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Forecast models
CREATE TABLE dataiq.forecast_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    name VARCHAR(255) NOT NULL,
    forecast_type VARCHAR(100) NOT NULL,                -- cost_projection, utilization_forecast, trend_extrapolation
    
    -- Input
    metric_key VARCHAR(255) NOT NULL,
    input_period_months INTEGER DEFAULT 24,
    
    -- Model
    model_type VARCHAR(50) NOT NULL,                    -- linear, exponential, seasonal_decomposition, prophet
    model_parameters JSONB,
    
    -- Results
    forecast_values JSONB,                              -- [{date, predicted, lower_bound, upper_bound}]
    confidence_interval DECIMAL(5,2) DEFAULT 0.95,
    mape DECIMAL(8,4),                                  -- mean absolute percentage error
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 4. Business Logic

### 4.1 Real-Time Metric Updates

Event-driven architecture:
1. Modules emit events (claim.ingested, ap.created, payment.settled, fwa.claim_flagged, etc.)
2. DataIQ event consumers update Redis counters and time-series in real-time
3. Every hour: snapshot Redis values to `metric_snapshots` table for persistent history
4. Every day: calculate SPC control limits from 30-day rolling window, flag anomalies
5. Dashboard widgets read from Redis (real-time) with fallback to metric_snapshots (historical)

### 4.2 Statistical Process Control (SPC)

For every enabled metric:
1. Calculate 30-day rolling mean and standard deviation from daily snapshots
2. Upper Control Limit = mean + (sigma_threshold × std_dev)
3. Lower Control Limit = mean - (sigma_threshold × std_dev)
4. If today's value exceeds UCL or falls below LCL → anomaly detected → insight alert generated
5. Configurable: sigma threshold (default: 2σ for warning, 3σ for critical)
6. Western Electric rules (optional): detect patterns beyond single-point violations (7+ consecutive points above/below mean, 2 of 3 consecutive points beyond 2σ)

### 4.3 Data Quality Scoring

Daily job calculates data quality score per tenant:

1. Run each monitor (volume, completeness, format, timeliness, consistency, referential integrity)
2. Each monitor produces a score 0-100 based on pass rate
3. Overall score = weighted average (configurable weights, default: equal weight)
4. Store in `data_quality_scores` with component breakdown
5. If overall score drops below threshold → alert tenant admin and data operations team
6. Quality trend: show 90-day history of daily scores

### 4.4 Drug Trend Decomposition

Decompose spend change into components:

```
Total spend change = Utilization effect + Price effect + Mix effect + New drug effect

Where:
- Utilization effect = (change in claim volume) × (prior period average cost)
- Price effect = (change in per-unit cost) × (current period volume)
- Mix effect = (change in brand/generic/specialty mix) × (current volume)
- New drug effect = spend on drugs not in prior period
```

This answers "why did spend go up 12%?" with "8% was price inflation, 3% was a new GLP-1 drug, 1% was higher utilization."

### 4.5 Forecast Modeling

Pre-built forecast models:

- **Linear trend**: simple linear regression on historical data. Good for stable, slow-changing metrics.
- **Exponential smoothing**: Holt-Winters with seasonal decomposition. Good for metrics with seasonal patterns.
- **Cost projection**: specialized model that factors in known pipeline events (drug launches, patent expirations, formulary changes)
- Forecast output: predicted value + confidence interval (upper/lower bound) for each future period
- Model accuracy: track MAPE (mean absolute percentage error) on historical predictions vs actuals
- Auto-retrain: monthly recalculation with latest data

### 4.6 What-If Scenario Engine

Model the financial impact of hypothetical changes:

- **Formulary change**: "What if we move Drug X from Tier 3 to Tier 2?" → model impact on utilization, cost, and rebate revenue
- **Network change**: "What if we add Pharmacy Chain Y to the network?" → model impact on claim volume, cost, and member access
- **Benefit design change**: "What if we increase the deductible from $250 to $500?" → model impact on member cost, plan cost, and utilization
- **Pricing change**: "What if AWP for Drug X increases 10%?" → model impact on spend by program and client

Scenario engine uses historical data + configurable elasticity assumptions. Results presented as: baseline vs scenario with delta and percentage change.

### 4.7 Claims Repricing Engine

Xevant's BidLogic equivalent — reprice any set of claims against different rate scenarios:

1. Upload or select a claim set (client's historical claims, prospect's data file, or live claims from a date range)
2. Define pricing scenarios: different AWP discount, different MAC list, different dispensing fees, different network
3. Engine reprices every claim under each scenario using Decimal/ROUND_HALF_UP
4. Output: side-by-side comparison of current cost vs scenario cost, with savings by drug, by pharmacy, by therapeutic class
5. Used for: underwriting (what will this client cost us?), RFP support (here's your projected savings), contract renegotiation (here's what different rates would save)
6. Repricing engine processes 1M claims in <5 minutes

### 4.8 Underwriting Analytics

For evaluating prospective clients and managing risk:

1. **Risk scoring**: given a prospect's claims data, calculate risk score based on: specialty drug concentration, high-cost claimant count, trend trajectory, generic fill rate, network alignment
2. **Margin calculation**: projected revenue (admin fees, spread if applicable) minus projected cost (claims + operations) = projected margin
3. **Break-even analysis**: minimum admin fee needed to achieve target margin
4. **Competitive positioning**: how does our projected cost compare to the prospect's current PBM cost?
5. **Renewal modeling**: for existing clients approaching renewal, model retention scenarios with different pricing concessions
6. **Pipeline dashboard**: all prospects with risk scores, projected margins, and status

### 4.9 Contract Guarantee Monitoring

Track contractual commitments vs actual performance:

1. Define guarantees per client contract: generic fill rate minimum, brand AWP discount minimum, generic MAC effective rate, rebate per brand script minimum, admin fee cap, mail order conversion target
2. Monthly: calculate actual performance against each guarantee
3. Status: green (meeting), yellow (within 5% of miss), red (missing)
4. Alert when any guarantee is at risk of being missed
5. Year-end reconciliation: if guarantees missed, calculate penalty amount per contract terms
6. Dashboard: all clients, all guarantees, current status, trending

### 4.10 Natural Language Query

Integration with AI/NLP module:

1. User types a question in plain English: "Show me the top 10 drugs by total spend in Q1 2026 for Client X"
2. AI/NLP module translates the question into a structured query (SQL or API call)
3. Query validated for: tenant scoping (can't query other tenants), PHI permissions, read-only, query complexity (timeout prevention)
4. Results returned as table + auto-suggested chart type
5. User can refine: "Now break that down by pharmacy type" → query modified
6. Conversation history maintained within session for iterative exploration

### 4.11 Data Catalog / Field Dictionary

Searchable reference for self-service exploration:

1. Every field across all modules registered with: field name, display label, description, data type, source module, source table, PHI flag, example values
2. Auto-generated from SQLAlchemy models (field name, type) + manually enriched (descriptions, examples)
3. Searchable via API and exploration UI: "What field has deductible information?" → returns matching fields with descriptions
4. Used by: pivot builder (field picker shows descriptions), natural language query (helps AI map questions to fields), report builder

### 4.12 Insight Alert Delivery

Integration with Core Platform notification and webhook systems:

1. When an insight alert is generated (anomaly, benchmark breach, data quality drop), automatically:
   - Create notification in Core Platform notification service for relevant users
   - Deliver via webhook to configured endpoints
   - Send email to configured recipients (for critical severity)
2. Configurable per tenant: which insight types trigger which delivery channels
3. Digest mode: instead of individual alerts, send daily digest of all insights (configurable)
4. Deduplication: same insight type for same entity within 24 hours → don't re-alert

### 4.13 Prescriber Profiling

Prescribing pattern analytics:

1. **Prescriber scorecard**: volume, cost per script, generic rate, formulary compliance, top drugs prescribed, specialty mix
2. **Peer comparison**: rank prescriber against peers in same specialty and geography
3. **Outlier detection**: prescribers whose patterns deviate significantly from peers (high cost, low generic, unusual drug mix)
4. **Trend analysis**: prescriber's patterns over time (is their generic rate improving or declining?)
5. **Network analysis**: which pharmacies does this prescriber's patients use? (feeds into ReclaimRx relationship graph)
6. **Intervention targeting**: identify prescribers where outreach could shift behavior (academic detailing, P&T committee)

### 4.14 Geographic Analytics

Map-based visualization:

1. **Claim density map**: heat map of claims by zip code / county / state
2. **Pharmacy access map**: pharmacy locations with member density overlay. Identify access deserts.
3. **Network adequacy map**: % of members within X miles of network pharmacy, by region
4. **FWA hotspot map**: flagged claims by geography (feeds from ReclaimRx)
5. **Cost variation map**: average claim cost by region, identifying high-cost areas
6. **Implementation**: GeoJSON boundaries, Leaflet/Mapbox for visualization, PostGIS for spatial queries

### 4.15 Embedded Analytics

For clients who want DataIQ charts in their own portals:

1. **Widget embed endpoint**: `/api/v1/dataiq/embed/{widget_id}?token={embed_token}` returns an HTML snippet with the chart
2. **Embed token**: tenant-scoped, time-limited, read-only, specific to the widget
3. **Configurable**: which widgets are embeddable (tenant admin controls this)
4. **Responsive**: embedded widgets adapt to container size
5. **Branding**: embedded widgets use the tenant's white-label colors

### 4.16 Data Export API

For clients using external BI tools (Tableau, Power BI, Looker):

1. **Bulk export endpoints**: export claims, billing, member, pharmacy data as CSV or Parquet
2. **Incremental export**: export only records changed since last export (using updated_at timestamps)
3. **PHI controls**: export respects user's PHI masking level. Full PHI only for authorized users.
4. **Rate limiting**: export endpoints rate-limited to prevent overload on read replica
5. **Scheduled export**: configure recurring exports delivered via SFTP or S3
6. **Data format documentation**: OpenAPI spec + data dictionary bundled with every export

### 4.17 MTM Targeting

Identify members who would benefit from Medication Therapy Management:

1. **CMS MTM criteria**: members meeting CMS eligibility (multiple chronic conditions, multiple Part D drugs, above cost threshold)
2. **Comprehensive Medication Review (CMR) candidates**: members eligible but not yet completed CMR this year
3. **Targeted Medication Review (TMR) candidates**: members with specific medication issues (adherence gaps, drug interactions, therapeutic duplications)
4. **Prioritization scoring**: rank candidates by: Star Ratings impact potential, cost savings potential, clinical risk
5. **Outreach list generation**: generate member lists with: name, phone, medications, identified issues, recommended interventions
6. **Impact tracking**: after MTM intervention, track adherence change, cost change, and Star Ratings measure improvement

### 4.18 Annotation System

Users add context to data points:

1. Any data point on any chart or table can be annotated
2. Annotation includes: text note, author, timestamp, tags
3. Annotations visible to all users viewing the same data (tenant-scoped)
4. Annotations appear as markers on charts (hover to read)
5. Common use: "January spike caused by flu season", "March drop caused by formulary change effective 3/1"
6. Searchable: find all annotations for a date range, a metric, or a tag

### 4.19 Performance Requirements

- Real-time metric read (from Redis): <50ms
- Historical metric query (30 days): <2 seconds
- Drug trend analysis (1 year, single client): <10 seconds
- Claims repricing (100K claims, single scenario): <60 seconds
- Claims repricing (1M claims, single scenario): <5 minutes
- Data quality scoring (daily job): <10 minutes per tenant
- SPC anomaly detection (daily job): <5 minutes per tenant
- Pivot query (against read replica): <10 seconds
- Natural language query translation: <3 seconds
- Data export (100K records): <30 seconds
- Geographic query (PostGIS): <5 seconds

### 4.20 Data Retention

- Metric snapshots: 3 years (for long-term trend analysis), then archive
- Data quality scores: 2 years
- Insight alerts: 1 year, then archive
- Saved explorations: indefinite (user data)
- Annotations: indefinite (institutional knowledge)
- Forecast models: 2 years
- Repricing results: 90 days (large datasets, can be regenerated)
- Cost summaries: indefinite

---

## 5. API Endpoints

```
/api/v1/dataiq/

# Real-Time Metrics
GET    /metrics                         List metric definitions
GET    /metrics/{key}/current           Current value (from Redis)
GET    /metrics/{key}/history           Historical values with SPC bands
GET    /metrics/{key}/anomalies         Anomaly history

# Drug Trend
GET    /drug-trend/spend                Drug spend trending
GET    /drug-trend/decomposition        Spend change decomposition
GET    /drug-trend/top-drugs            Top drugs by spend/volume
GET    /drug-trend/glp1                 GLP-1 specific tracking
GET    /drug-trend/biosimilar           Biosimilar adoption analysis
GET    /drug-trend/new-drugs            New drug impact analysis
GET    /drug-trend/price-inflation      NDC-level price tracking

# Network Analytics
GET    /network/scorecard               Pharmacy performance scorecard
GET    /network/adequacy                Network adequacy analysis
GET    /network/leakage                 Out-of-network utilization
GET    /network/cost-variation          Same-drug cost comparison

# Member Analytics
GET    /member/adherence                Adherence dashboard
GET    /member/high-cost                High-cost claimant analysis
GET    /member/polypharmacy             Polypharmacy risk
GET    /member/therapy-gaps             Therapy gap analysis
GET    /member/opioid                   Opioid utilization monitoring

# Financial Analytics
GET    /financial/cost-drivers          Cost driver decomposition
GET    /financial/pmpm                  PMPM trending
GET    /financial/spread                Spread analysis
GET    /financial/profitability         Client profitability

# Forecasting
POST   /forecast/create                 Create forecast model
GET    /forecast/{id}                   Get forecast results
GET    /forecast/{id}/accuracy          Forecast accuracy metrics

# What-If Scenarios
POST   /scenarios/formulary             Model formulary change impact
POST   /scenarios/network               Model network change impact
POST   /scenarios/benefit-design        Model benefit design change impact
POST   /scenarios/pricing               Model pricing change impact

# Data Quality
GET    /data-quality                    Current data quality score
GET    /data-quality/history            Historical quality scores
GET    /data-quality/issues             Active data quality issues

# Benchmarking
GET    /benchmarks                      List benchmarks
POST   /benchmarks                      Create benchmark
PUT    /benchmarks/{id}                 Update benchmark
GET    /benchmarks/status               All benchmarks with current status (green/yellow/red)

# Insight Alerts
GET    /insights                        List insight alerts
PUT    /insights/{id}/acknowledge       Acknowledge alert
GET    /insights/summary                Summary of unacknowledged insights

# Self-Service
POST   /explore/pivot                   Execute pivot query
POST   /explore/cohort                  Execute cohort analysis
POST   /explore/query                   Execute ad-hoc SQL (read-only, against replica)
GET    /explore/saved                   List saved explorations
POST   /explore/saved                   Save exploration
```

---

## 6. Events

### Published
- `dataiq.anomaly_detected` — SPC anomaly on any metric
- `dataiq.data_quality_degraded` — quality score dropped below threshold
- `dataiq.benchmark_breach` — metric crossed benchmark threshold
- `dataiq.insight_generated` — auto-generated insight from analytics
- `dataiq.forecast_deviation` — actual value deviates from forecast by >X%

### Consumed
- `claim.ingested`, `claim.classified` — update claim volume, drug trend counters
- `ap.created`, `ap.settled`, `payment.settled` — update financial counters
- `ar.created`, `ar.payment_received` — update AR counters
- `fwa.claim_flagged`, `fwa.investigation_opened` — update FWA counters
- `invoice.generated` — update billing counters
- All events from all modules — for real-time metric updates

---

## 7. Default Implementation

Ships fully functional:

- **Real-time analytics engine** — Redis-backed counters with hourly snapshots
- **Statistical process control** on all key metrics with 2σ/3σ alerting
- **10 drug trend analyses** pre-built
- **8 network analytics** pre-built
- **7 member analytics** pre-built
- **5 financial analytics** pre-built
- **Drug trend decomposition** (utilization + price + mix + new drug)
- **Data quality monitoring** with 8 monitors and daily scoring
- **Benchmarking engine** with 4 benchmark types
- **Forecast modeling** with 3 model types
- **What-if scenario engine** for formulary, network, benefit design, and pricing changes
- **Self-service exploration** — pivot builder, cohort analysis, ad-hoc SQL
- **Insight alerts** with delivery via notifications, email, and webhooks
- **Claims repricing engine** — reprice claims against unlimited rate scenarios (Xevant BidLogic equivalent)
- **Underwriting analytics** — risk scoring, margin calculation, pipeline management
- **Contract guarantee monitoring** — track guarantees vs actuals with alerts
- **Natural language query** — plain English to SQL via AI/NLP integration
- **Data catalog / field dictionary** — searchable reference for all platform data fields
- **Prescriber profiling** — prescribing patterns, peer comparison, outlier detection
- **Geographic analytics** — map-based visualization with PostGIS
- **Embedded analytics** — tenant-scoped embeddable widgets for client portals
- **Data export API** — CSV/Parquet for external BI tools (Tableau, Power BI)
- **MTM targeting** — identify and prioritize members for medication therapy management
- **Annotation system** — user-added context on any data point

New tenant: real-time metrics start immediately. Drug trend and network analytics available after 30 days. Forecasting after 90 days. Repricing available immediately with claims data.

---

## 8. Test Scenarios (100% Coverage Required)

### Critical Paths (100%)
- Real-time counter increments correctly on event receipt
- SPC control limits calculated correctly (verify against hand-calculated values)
- Anomaly detection fires when value exceeds UCL/LCL
- Drug trend decomposition: utilization + price + mix + new drug = total change (exact, Decimal)
- Data quality monitors detect known-bad data (inject test records with issues)
- Benchmark status correctly evaluates green/yellow/red
- Forecast MAPE calculated correctly against holdout data
- What-if scenario calculates correct deltas (verify against hand-calculated values)
- Self-service SQL queries execute against read replica only (never primary)
- PHI access logged for any member-level analytics

### Edge Cases
- Metric with zero history (new tenant) → SPC returns "insufficient data", no alert
- All claims for a day are reversals (net volume = 0) → data quality doesn't false-alarm
- Forecast on metric with <90 days history → returns "insufficient data" instead of bad forecast
- Ad-hoc SQL with expensive query → timeout after configurable limit, user warned
- Division by zero in PMPM calculation (zero members in period) → handled gracefully

---

## 9. Session Decomposition

1. **Real-time engine + data quality + infrastructure**: Redis counter framework, event consumers, hourly snapshot job, SPC engine, 8 data quality monitors, daily scoring job, metric definitions, data catalog/field dictionary, annotation system, PostGIS setup for geographic queries
2. **Drug trend + financial + network + member + prescriber analytics**: all pre-built analysis endpoints, drug trend decomposition, PMPM, spread analysis, cost drivers, pharmacy scorecard, adherence (PDC), prescriber profiling, MTM targeting, geographic analytics, all Decimal math
3. **Repricing + underwriting + forecasting + scenarios**: claims repricing engine (1M claims in <5 min), underwriting risk scoring and margin calculation, contract guarantee monitoring, forecast model training/serving, what-if scenario engine, benchmark engine with guarantee tracking
4. **Self-service + integration + export**: pivot builder, cohort analysis, ad-hoc SQL (read replica), natural language query (AI/NLP integration), saved explorations, embedded analytics widget endpoints, data export API (CSV/Parquet), insight alert delivery, scheduled analytics
