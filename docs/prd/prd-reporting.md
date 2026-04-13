# PRD — Module 15: Reporting & Analytics — FINAL

**Module:** Reporting & Analytics  
**Folder:** `modules/reporting/`  
**Priority:** Phase 2, Batch A  
**Dependencies:** Core Platform (Module 1), Billing (Module 11)  

---

## 1. Purpose

Reporting is the intelligence layer of the InfinityRx platform. It aggregates data from all modules into actionable reports, dashboards, and analytics. It serves three audiences:

1. **Internal operators** — need operational reports to run the business (billing summaries, claims volume, payment status, FWA activity)
2. **Clients** — need program performance reports, financial summaries, and regulatory compliance reports delivered on schedule
3. **External regulators** — need standardized reports in mandated formats (2026 CAA transparency reports, CMS quality measures, state regulatory submissions)

The module does NOT store its own claim/billing/member data. It queries other modules' schemas (read-only) and the financial journal (from Billing) to produce reports. It's a consumer of data, not a source.

---

## 2. Core Concepts

### 2.1 Report Library
Pre-built reports organized by domain. Each report has a standard definition (columns, filters, groupings, calculations) that works out of the box. Tenants can customize any report or create new ones.

### 2.2 Report Builder
Drag-and-drop custom report creation. Select data source (claims, billing, members, pharmacies, FWA), choose dimensions (group by client, program, pharmacy, date, NDC), add measures (count, sum, average, percentage), apply filters, and preview. Save for reuse.

### 2.3 Dashboards
Configurable visual dashboards with widgets (charts, KPIs, tables, alerts). Each user can customize their dashboard layout. Pre-built dashboards for common roles (operator, client admin, executive).

### 2.4 Scheduled Delivery
Any report can be scheduled for automatic delivery on a recurring basis. Configurable: frequency, format (Excel, PDF, CSV), delivery method (email, portal, SFTP, API), recipients.

### 2.5 Client Reporting API
Authenticated REST endpoints that clients integrate with their own systems. Each endpoint returns data scoped to the client's tenant and permissions. Rate-limited and documented with OpenAPI spec.

---

## 3. Data Model

```sql
CREATE SCHEMA reporting;

-- Report definitions (pre-built + custom)
CREATE TABLE reporting.report_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID,                                   -- null = system-wide (available to all)
    
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100) NOT NULL,
    -- claims, billing_ap, billing_ar, financial, fwa, utilization,
    -- member, pharmacy, prescriber, program, regulatory, actuarial, quality
    
    -- Data source
    data_source VARCHAR(100) NOT NULL,                -- which module's data
    base_query TEXT,                                   -- SQL or query definition
    
    -- Structure
    columns JSONB NOT NULL,                            -- [{field, label, type, format, sortable, filterable}]
    default_filters JSONB,                             -- pre-applied filters
    default_groupings JSONB,                           -- default group-by fields
    default_sort JSONB,                                -- default sort order
    
    -- Calculations
    calculated_fields JSONB,                           -- derived fields (percentages, ratios, running totals)
    summary_row JSONB,                                 -- totals/averages at bottom
    
    -- Visualization
    chart_type VARCHAR(50),                            -- bar, line, pie, area, none
    chart_config JSONB,                                -- chart-specific settings
    
    -- Access
    required_permission VARCHAR(100),                   -- which permission needed to run this report
    is_system BOOLEAN DEFAULT FALSE,                   -- system reports can't be deleted
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Report schedules
CREATE TABLE reporting.report_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    report_definition_id UUID NOT NULL REFERENCES reporting.report_definitions(id),
    
    name VARCHAR(255) NOT NULL,
    
    -- Schedule
    frequency VARCHAR(50) NOT NULL,                    -- daily, weekly, biweekly, monthly, quarterly, annually
    day_of_week INTEGER,                               -- for weekly
    day_of_month INTEGER,                              -- for monthly
    time_of_day TIME DEFAULT '06:00',
    timezone VARCHAR(50) DEFAULT 'America/New_York',
    
    -- Filters applied for this schedule
    filters JSONB,                                     -- date range is auto-calculated based on frequency
    
    -- Output
    output_format VARCHAR(50) NOT NULL,                -- excel, pdf, csv
    
    -- Delivery
    delivery_method VARCHAR(50) NOT NULL,               -- email, portal, sftp, api_webhook
    delivery_recipients JSONB,                          -- emails, SFTP path, webhook URL
    sftp_config_id UUID,                               -- if SFTP delivery
    
    -- Branding
    template_id UUID,                                  -- branded template for PDF
    include_cover_page BOOLEAN DEFAULT FALSE,
    include_charts BOOLEAN DEFAULT TRUE,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    last_run_status VARCHAR(50),
    next_run_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Report execution history
CREATE TABLE reporting.report_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    report_definition_id UUID NOT NULL,
    schedule_id UUID,                                  -- null if ad-hoc run
    
    -- Execution
    status VARCHAR(50) NOT NULL,                       -- running, completed, failed
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    
    -- Input
    filters_applied JSONB,
    requested_by UUID,                                 -- user who triggered (null for scheduled)
    
    -- Output
    row_count INTEGER,
    output_format VARCHAR(50),
    output_file_id UUID,                               -- ref to core.files
    
    -- Delivery
    delivered_at TIMESTAMPTZ,
    delivery_status VARCHAR(50),
    delivery_error TEXT,
    
    error_message TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Dashboard definitions
CREATE TABLE reporting.dashboards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID,                                    -- null = system-wide default
    
    name VARCHAR(255) NOT NULL,
    description TEXT,
    role_target VARCHAR(100),                          -- which role this dashboard is designed for
    
    layout JSONB NOT NULL,                             -- widget positions, sizes, configuration
    -- [{widget_type, position: {x, y, w, h}, config: {report_id, chart_type, filters, refresh_interval}}]
    
    is_default BOOLEAN DEFAULT FALSE,                  -- default dashboard for a role
    is_system BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- User dashboard customizations
CREATE TABLE reporting.user_dashboards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    dashboard_id UUID REFERENCES reporting.dashboards(id),
    
    custom_layout JSONB,                               -- user's customized widget layout
    pinned_filters JSONB,                              -- user's saved filter presets
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, dashboard_id)
);

-- Saved filter presets
CREATE TABLE reporting.filter_presets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID,                                      -- null = shared preset
    
    name VARCHAR(255) NOT NULL,
    filters JSONB NOT NULL,
    applies_to JSONB,                                  -- which reports this preset works with
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Regulatory report tracking
CREATE TABLE reporting.regulatory_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    report_type VARCHAR(100) NOT NULL,
    -- caa_transparency_semiannual, cms_quality_measures, star_ratings,
    -- state_regulatory, dir_reporting, pde_summary, custom_regulatory
    
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    
    status VARCHAR(50) DEFAULT 'draft',
    -- draft, in_review, approved, submitted, accepted, rejected
    
    due_date DATE NOT NULL,
    submitted_at TIMESTAMPTZ,
    accepted_at TIMESTAMPTZ,
    
    file_id UUID,
    submission_reference VARCHAR(255),
    
    reviewed_by UUID,
    approved_by UUID,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Actuarial models (for RFP support)
CREATE TABLE reporting.actuarial_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    name VARCHAR(255) NOT NULL,
    model_type VARCHAR(100) NOT NULL,
    -- cost_projection, formulary_impact, network_savings,
    -- rebate_optimization, trend_analysis, risk_scoring
    
    -- Input
    input_data_source TEXT,
    input_parameters JSONB,
    
    -- Output
    results JSONB,
    confidence_interval DECIMAL(8,2),
    methodology TEXT,
    
    -- Status
    status VARCHAR(50) DEFAULT 'draft',
    
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 4. Pre-Built Report Library

### 4.1 Claims Reports
| Report | Description | Default Schedule |
|--------|-------------|-----------------|
| Claims Volume Summary | Total claims by program, by date, with trend | Daily |
| Claims Detail | All claims with full field detail, filterable | On-demand |
| Top Pharmacies by Volume | Pharmacy ranking by claim count and dollars | Monthly |
| Top NDCs by Volume | Drug ranking by claim count and dollars | Monthly |
| Top Prescribers by Volume | Prescriber ranking by script count | Monthly |
| Reversal Report | All reversals with original claim reference | Weekly |
| Compound Claims | All compound claims with ingredient detail | Monthly |
| Claims by Therapeutic Class | Volume and cost grouped by therapeutic class | Monthly |

### 4.2 Billing / AP Reports
| Report | Description | Default Schedule |
|--------|-------------|-----------------|
| AP Summary | Total payables by pay-to entity, by period | Per billing cycle |
| Payment Batch Summary | Batch totals, payment counts, by vendor | Per batch |
| Settlement Status | Payments pending, settled, returned | Daily |
| ACH Return Report | All returns with codes and actions taken | Weekly |
| Carryover Report | Outstanding carryovers by entity | Monthly |
| Pharmacy Payment History | All payments to a specific pharmacy over time | On-demand |
| Payment Method Distribution | Volume by payment method (ACH, Echo, check) | Monthly |

### 4.3 Billing / AR Reports
| Report | Description | Default Schedule |
|--------|-------------|-----------------|
| Invoice Summary | All invoices by client, by status | Monthly |
| AR Aging | Outstanding receivables by aging bucket | Weekly |
| Client Payment History | All payments received from a client | On-demand |
| Fee Summary | Fees calculated by type, by program | Monthly |
| Revenue by Client | Total revenue (fees) by client, by period | Monthly |
| Overdue Invoices | Invoices past due date with days outstanding | Daily |

### 4.4 Financial Reports (from Journal)
| Report | Description | Default Schedule |
|--------|-------------|-----------------|
| Financial Journal Summary | All journal entries by category, by period | Monthly |
| Cash Flow Report | Payments out (AP) vs payments in (AR) by period | Monthly |
| Client Profitability | Fees collected minus operational costs per client | Quarterly |
| Prefund Status | Current balance, burn rate, projection per client | Daily |
| Program Financial Summary | Total spend, fees, recoveries per program | Monthly |
| Period Close Report | Full financial summary for closed period | Monthly |
| GL Export Report | Journal entries formatted for accounting export | Per export |
| 1099 Summary | Annual payment totals by payee for tax reporting | Annual |

### 4.5 FWA Reports
| Report | Description | Default Schedule |
|--------|-------------|-----------------|
| FWA Summary Dashboard | Flags by severity, by rule, by entity type | Daily |
| Pharmacy Risk Scorecard | All pharmacies ranked by composite risk score | Monthly |
| Investigation Status | Open investigations by type, by priority, by age | Weekly |
| Recovery Report | Recovery amounts by status (estimated, demanded, collected) | Monthly |
| Accumulator Impact | Financial impact of accumulators by plan, by member | Monthly |
| Rule Effectiveness | Which detection rules produce the most confirmed findings | Quarterly |
| Audit Summary | Audit findings by pharmacy, by type, by outcome | Per audit completion |

### 4.6 Utilization Reports
| Report | Description | Default Schedule |
|--------|-------------|-----------------|
| Drug Utilization Review | Utilization patterns by drug, class, with trends | Monthly |
| Generic vs Brand | Generic fill rate by program, by pharmacy | Monthly |
| Specialty Drug Report | High-cost specialty medication utilization | Monthly |
| Prior Authorization Summary | PA requests, approvals, denials, turnaround time | Monthly |
| Refill Adherence | PDC (proportion of days covered) by member, by drug class | Quarterly |
| GLP-1 Utilization | GLP-1 specific utilization and cost trending | Monthly |

### 4.7 Regulatory Reports
| Report | Description | Default Schedule |
|--------|-------------|-----------------|
| 2026 CAA Transparency Report | Net drug spending, rebates, spread pricing per HHS/DOL/Treasury format | Semiannual (mandated) |
| DIR Reporting | Direct and indirect remuneration for Medicare Part D | Per CMS schedule |
| State Regulatory Submissions | State-specific PBM reporting requirements | Per state schedule |
| Government Exclusion Screening Report | OIG/SAM screening results and matches | Monthly |

### 4.8 Quality / Star Ratings
| Report | Description | Default Schedule |
|--------|-------------|-----------------|
| Star Ratings Dashboard | Medicare quality measures tracking (D-Star measures) | Monthly |
| PDC Adherence Measures | Adherence rates for statins, RAS antagonists, diabetes meds | Monthly |
| MTM Completion Rate | CMR completion tracking for Star Ratings | Monthly |
| CAHPS Indicators | Member satisfaction indicators correlated with pharmacy benefit | Quarterly |

### 4.9 Actuarial / RFP Support
| Report | Description | Default Schedule |
|--------|-------------|-----------------|
| Prospective Cost Model | Project costs under different formulary/network scenarios | On-demand |
| Formulary Impact Analysis | Model cost impact of moving drugs between tiers | On-demand |
| Network Savings Analysis | Compare pharmacy network configurations by cost | On-demand |
| Rebate Optimization | Model rebate revenue under different formulary strategies | On-demand |
| Trend Analysis | Historical cost and utilization trends with projections | Quarterly |
| Program Benchmarking | Compare program performance vs configurable benchmarks | Quarterly |

---

## 5. Business Logic

### 5.1 Report Execution

1. User requests report (ad-hoc or scheduled trigger)
2. Load report definition (columns, filters, groupings, calculations)
3. Apply user's filters on top of default filters
4. Execute query against source module's schema (read-only connection)
5. Apply calculated fields (percentages, ratios, running totals)
6. Apply groupings and aggregations
7. Generate summary row if configured
8. Format output (Excel, PDF, CSV)
9. If PDF: apply branded template (tenant logo, colors, headers/footers)
10. Store output file
11. Deliver per schedule config (email, portal, SFTP, API webhook)
12. Log execution in report_runs

### 5.2 Dashboard Rendering

1. Load dashboard definition (widgets, layout)
2. For each widget:
   - Execute the widget's data query with the widget's filters
   - Return data in the format needed by the chart type (series data, labels, colors)
3. Configurable refresh interval per widget (default: 5 minutes for real-time, 1 hour for summary)
4. Drill-down: clicking a chart element opens the underlying report filtered to that data point
5. Date range selector: all widgets respond to a global date range filter
6. Export: each widget can be exported individually (PNG for charts, Excel for tables)

### 5.3 Report Builder (Custom Reports)

1. User selects data source (claims, billing AP, billing AR, journal, FWA, members, pharmacies)
2. Available fields presented based on data source
3. User drags fields to: columns, rows (groupings), filters, measures
4. Measures: count, sum, average, min, max, percentage of total, running total
5. Preview shows live data (limited to 100 rows)
6. Save as new report definition
7. Can schedule saved report for recurring delivery
8. Shared or private (user can share custom reports with their tenant)

### 5.4 Actuarial Modeling

For health plan prospect RFPs and underwriting:

1. **Import prospect's claims data** — accept claims file in standard or custom format
2. **Reprice claims** — apply InfinityRx's formulary, MAC list, network discounts, and rebate estimates to the prospect's claims
3. **Project costs** — calculate projected annual spend under InfinityRx vs current PBM
4. **Scenario comparison** — model multiple scenarios (different formulary, different network, different rebate terms)
5. **Output** — professional PDF report comparing current vs projected costs with savings breakdown
6. **Sensitivity analysis** — show how results change with different utilization growth rates

### 5.5 PBM Transparency Reporting (2026 CAA)

The Consolidated Appropriations Act of 2026 mandates semiannual reporting:

1. **Net drug spending**: total drug costs net of rebates, by drug/class
2. **Rebate disclosure**: total rebates received from manufacturers, by drug
3. **Spread pricing**: difference between what plan paid PBM and what PBM paid pharmacy
4. **Affiliated pharmacy steering**: benefit design parameters that encourage/require use of PBM-affiliated pharmacies
5. **Format**: per HHS/DOL/Treasury standard (to be defined by rulemaking — configurable template)
6. **Auto-generated** from financial journal and claims data
7. **Review workflow**: draft → internal review → client approval → submission
8. **Deadline tracking**: alerts when submission deadline approaches

### 5.6 Star Ratings Tracking

For Medicare Advantage / Part D plan clients:

1. **D-Star measures tracked**:
   - D01: Statin adherence (PDC ≥ 0.80)
   - D02: Diabetes medication adherence (PDC ≥ 0.80)
   - D03: RAS antagonist adherence (PDC ≥ 0.80)
   - D04: MTM program completion rate
   - D05-D12: Other Part D measures as applicable
2. **Real-time tracking**: current period adherence rates vs targets vs prior year
3. **Member-level drill-down**: which members are below threshold, opportunity for intervention
4. **Gap closure**: identify members who need outreach to improve adherence before measurement period ends
5. **Projections**: based on current trajectory, project year-end Star Rating
6. **Dashboards**: visual scorecards with red/yellow/green status per measure

### 5.7 Data Warehouse / Read Replica Strategy

Reporting queries MUST NOT hit the operational database directly. At 100M+ claims/year, a complex report query could slow adjudication or billing.

**Implementation:**
- **Read replica**: PostgreSQL streaming replication from operational database to a dedicated reporting replica. Reports query the replica only.
- **Sync lag**: replica is typically <1 second behind operational. Acceptable for all reports except real-time dashboards.
- **Real-time dashboards**: for widgets that need sub-second freshness (e.g., live claim count), query Redis cached metrics instead of the database.
- **Heavy reports**: reports spanning large date ranges or full-table scans run against the replica with query timeout (configurable, default: 5 minutes).
- **Reporting schema**: dedicated `reporting` schema with materialized views for common aggregations, refreshed on schedule (hourly for claims, daily for financial).

### 5.8 Data Freshness Indicators

Every report and dashboard widget displays:
- "Data as of: [timestamp]" — when the underlying data was last synced
- For real-time widgets (Redis-cached): "Live" indicator
- For materialized views: "Refreshed: [timestamp], next refresh: [timestamp]"
- If data is stale (>2x normal refresh interval), display warning indicator

### 5.9 PHI Handling in Reports

Reports containing PHI (member name, DOB, address, prescription details) require additional controls:

- **Watermark**: PDF reports containing PHI auto-watermarked "CONFIDENTIAL — CONTAINS PROTECTED HEALTH INFORMATION"
- **Access logging**: every report view, download, or delivery logged with user_id, timestamp, and report_id. Queryable by compliance team.
- **PHI masking levels**: configurable per user role:
  - Full detail: authorized users (tenant admin, operator with PHI permission)
  - Partially masked: member name shown, DOB/address masked
  - Fully masked: all PHI replaced with "[REDACTED]" — for client portal users where PHI should not be visible
- **Export controls**: PHI-containing reports can be restricted from export (configurable per report and per role)
- **Auto-classification**: system identifies which reports contain PHI fields and auto-applies PHI controls

### 5.10 Comparison / Trend Mode

Every report supports built-in comparison functionality:

- **Period over period**: this month vs last month, this quarter vs last quarter, this year vs last year
- **Custom comparison**: any two date ranges side by side
- **Benchmark comparison**: this program vs configurable benchmark (industry average, tenant average, or custom target)
- **Variance display**: absolute difference and percentage change, color-coded (green = improvement, red = deterioration)
- **Trend lines**: for any time-series metric, add a trend line and projected next period value
- **Comparison is a toggle on any report** — not a separate report type. User clicks "Compare" and selects the comparison period.

### 5.11 Alert-Triggered Reports

Auto-generate and deliver reports when specific conditions are met:

- Configurable alert-to-report mappings per tenant. Example mappings:
  - `fwa.pharmacy_risk_elevated` → auto-generate and email Pharmacy Risk Scorecard for that pharmacy
  - `prefund.critical` → auto-generate and email Prefund Status Report for that client
  - `ar.overdue` → auto-generate and email AR Aging Report for overdue invoices
  - `quality.measure_at_risk` → auto-generate and email Star Ratings Gap Report
- Alert source: any event from any module
- Report: any report definition with the relevant entity pre-filtered
- Delivery: per schedule config (email, portal, SFTP)
- Deduplication: don't send the same alert-triggered report more than once per configurable window (default: 24 hours)

### 5.12 Performance Requirements
- Dashboard load: <3 seconds for all widgets
- Standard report execution: <30 seconds for periods up to 1 year
- Large report execution: <5 minutes for multi-year or full-tenant scans
- Client API response: <2 seconds per request
- Report builder preview: <5 seconds for limited row preview
- Scheduled report generation: complete all scheduled reports within 2-hour window

### 5.13 Data Retention
- Report definitions: retained indefinitely (they're configuration, not data)
- Report execution history: 2 years (operational)
- Report output files: configurable per tenant (default: 1 year, then archive)
- Dashboard configurations: retained indefinitely
- Regulatory submissions: retained permanently
- Actuarial models: retained for 7 years

### 5.14 Report Output Size Management
- Maximum row limits per output format:
  - Excel: 1,000,000 rows (Excel format limit). System warns at 500K.
  - CSV: 10,000,000 rows. System warns at 5M.
  - PDF: 10,000 pages. System warns at 5K.
- If estimated output exceeds limit: warn user before generation with options to add filters, switch to CSV, or paginate into multiple files.
- Auto-pagination: for reports exceeding limits, generate multiple files (Part 1 of N, Part 2 of N) with consistent headers.
- Streaming export: for very large CSV exports, stream to file rather than building in memory. Prevents server OOM.

### 5.15 Concurrent Report Execution Queue
- Configurable concurrent report execution limit per tenant (default: 5 simultaneous reports).
- When limit reached: additional reports queued with estimated wait time shown to user.
- Priority queue: scheduled reports get priority over ad-hoc. Regulatory reports get highest priority.
- Queue dashboard: operators can see queued reports, cancel or reprioritize.
- Individual report timeout: configurable per report (default: 5 minutes for standard, 30 minutes for heavy). Reports exceeding timeout cancelled with partial results available.
- Read replica connection pool sized for configured concurrency (prevent connection exhaustion).

### 5.16 Webhook Delivery System
- Clients can register webhook endpoints to receive events programmatically.
- Configurable per tenant per event type: claim.ingested, payment.settled, invoice.generated, fwa.claim_flagged, etc.
- Webhook payload: JSON with event type, timestamp, tenant_id, and event-specific data.
- Authentication: HMAC-SHA256 signature on each webhook payload using a shared secret per endpoint.
- Retry on failure: 3 attempts with exponential backoff (1 min, 5 min, 30 min). After 3 failures, disable endpoint and alert tenant admin.
- Webhook log: every delivery attempt recorded (success/failure, response code, response time).
- Test endpoint: tenant can send a test webhook to verify their endpoint is working.
- Note: webhook delivery system implemented in Core Platform (Module 1) but configured and triggered from all modules. Listed here because Reporting is where clients first encounter it.

---

## 6. API Endpoints

```
/api/v1/reporting/

# Reports
GET    /reports                         List available report definitions
GET    /reports/{id}                    Report definition detail
POST   /reports                         Create custom report
PUT    /reports/{id}                    Update report definition
POST   /reports/{id}/run                Execute report (ad-hoc)
GET    /reports/{id}/runs               Execution history
GET    /reports/runs/{run_id}           Run detail
GET    /reports/runs/{run_id}/download  Download output file

# Schedules
GET    /schedules                       List report schedules
POST   /schedules                       Create schedule
PUT    /schedules/{id}                  Update schedule
DELETE /schedules/{id}                  Deactivate schedule
POST   /schedules/{id}/run-now         Trigger immediate run

# Dashboards
GET    /dashboards                      List dashboards
GET    /dashboards/{id}                 Dashboard definition
POST   /dashboards                      Create dashboard
PUT    /dashboards/{id}                 Update dashboard layout
GET    /dashboards/{id}/data            Dashboard widget data (all widgets)
GET    /dashboards/{id}/widget/{widget_id}/data  Single widget data

# User Customization
GET    /my/dashboard                    Current user's dashboard
PUT    /my/dashboard                    Save user's dashboard customization
GET    /my/filter-presets               User's saved filter presets
POST   /my/filter-presets               Save filter preset
DELETE /my/filter-presets/{id}          Delete filter preset

# Report Builder
GET    /builder/data-sources            Available data sources
GET    /builder/fields/{source}         Available fields for a data source
POST   /builder/preview                 Preview custom report (limited rows)

# Client Reporting API (for external client integration)
GET    /client-api/claims               Claims data (client-scoped, paginated)
GET    /client-api/billing              Billing summary (client-scoped)
GET    /client-api/program-performance  Program metrics (client-scoped)
GET    /client-api/fwa-summary          FWA summary (client-scoped)

# Regulatory
GET    /regulatory                      List regulatory submissions
POST   /regulatory                      Generate regulatory report
PUT    /regulatory/{id}                 Update status
POST   /regulatory/{id}/submit          Mark as submitted
GET    /regulatory/deadlines            Upcoming deadlines

# Actuarial
POST   /actuarial/import-claims         Import prospect claims data
POST   /actuarial/reprice               Reprice claims under scenarios
GET    /actuarial/models                List saved models
GET    /actuarial/models/{id}           Model detail and results
POST   /actuarial/models/{id}/scenario  Run new scenario

# Quality / Star Ratings
GET    /quality/star-ratings            Current Star Ratings status
GET    /quality/adherence/{measure}     Adherence detail by measure
GET    /quality/gaps                    Members below adherence threshold
GET    /quality/projections             Year-end Star Rating projections

# Export
POST   /export                          Export any dataset (Excel, PDF, CSV)
```

---

## 7. Events

### Published
- `report.generated` — report execution completed
- `report.delivered` — report sent to recipients
- `report.delivery_failed` — delivery failed
- `regulatory.deadline_approaching` — regulatory submission due soon
- `quality.measure_at_risk` — Star Rating measure trending below target

### Consumed
- All events from all modules — for real-time dashboard updates
- `billing.journal_entries` — for financial reports
- `fwa.claim_flagged` — for FWA dashboard
- `fwa.investigation_opened` / `fwa.investigation_resolved` — for investigation status reports

---

## 8. Default Implementation

Ships fully functional:

- **50+ pre-built reports** across 9 categories (claims, AP, AR, financial, FWA, utilization, regulatory, quality, actuarial)
- **5 pre-built dashboards**: operator, client admin, executive, FWA analyst, quality manager
- **Report builder** with drag-and-drop field selection, live preview
- **Scheduled delivery** with 4 output formats (Excel, PDF, CSV, API webhook) and 4 delivery methods (email, portal, SFTP, API)
- **2026 CAA transparency reports** auto-generated from financial journal
- **Star Ratings tracking** with all D-Star measures, gap closure lists, and projections
- **Actuarial modeling** for prospective cost analysis and RFP support
- **Client reporting API** with OpenAPI documentation, rate limiting, tenant scoping
- **Program benchmarking** with configurable benchmark targets
- **Branded PDF templates** with white-label support
- **Regulatory submission tracking** with deadline alerts
- **Read replica architecture** — reporting queries never hit operational database
- **Data freshness indicators** on every report and widget
- **PHI controls** — watermarking, access logging, configurable masking levels, export restrictions
- **Comparison mode** built into every report (period-over-period, benchmark)
- **Alert-triggered reports** — auto-generate on configurable events
- **Performance**: dashboards <3 seconds, standard reports <30 seconds

New tenant setup: pre-built dashboards and reports available immediately. Configure scheduled delivery for the reports the client needs. Custom reports via builder.

---

## 9. Test Scenarios (100% Coverage Required)

### Financial (100%)
- All financial report totals match financial journal totals (penny-perfect)
- AR aging bucket calculations correct at all boundaries
- Prefund projection math verified against manual calculation
- Actuarial repricing produces correct results against known test data

### Critical Paths (100%)
- Scheduled report executes at correct time, generates correct output, delivers successfully
- Dashboard widget data matches underlying report data
- Client API returns only that client's data (tenant isolation)
- Report builder preview returns correct data for custom field combinations
- Regulatory report content matches mandated format
- Star Ratings PDC calculation matches CMS methodology

### Edge Cases
- Report with zero rows — generates valid empty file with headers, not an error
- Scheduled report when underlying data source is unavailable — fails gracefully, retries, alerts
- Dashboard with 20+ widgets — loads progressively, doesn't timeout
- Client API rate limit exceeded — returns 429 with retry-after header
- Custom report with expensive query — timeout after configurable limit, suggest narrower filters

---

## 10. Session Decomposition

1. **Report engine + library**: report definitions, execution engine, query builder, output formatting (Excel, PDF, CSV), pre-built report library (all 50+ reports)
2. **Dashboards + builder**: dashboard definitions, widget rendering, user customization, report builder UI data flow, filter presets
3. **Delivery + regulatory + actuarial**: scheduled delivery, email/SFTP/portal/API delivery, regulatory report generation and tracking, actuarial modeling engine, Star Ratings calculation, client reporting API
