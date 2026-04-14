# PRD Compliance — Audit Findings

## Methodology

For each module: (1) read PRD section headers via `grep "^#\|^##\|^###"` to identify feature areas; (2) `find modules/<name>/src -name "*.py"` to catalog implemented files; (3) targeted `grep` for key classes, route handlers, and service functions corresponding to each PRD section; (4) spot-check `@router.` endpoint lists against PRD API sections; (5) check `grep -n "^class "` on model files to verify data model coverage. Scores are based on proportion of PRD-specified features with corresponding code artifacts (services + models + routes). "Missing" means no evidence of implementation; "Partial" means models/constants exist but no service logic or route handlers.

---

## Module Scores Table

| Module | Score | Coverage % | Notes |
|---|---|---|---|
| core-platform | 72/100 | 72% | Auth/audit/MFA/DLQ/jobs/files/exclusions/bank_holidays implemented; webhooks, feature flags, SSO/SAML, FIDO2 completion, break-glass, circuit breaker missing; auth+audit+notification routers NOT mounted in main.py |
| billing | 70/100 | 70% | Claims, AP, AR, journal, NACHA, 835, routing engine, fee engine solid; 50-state compliance tables, accounting adapters (QB/NetSuite/Sage/Xero), DIR fee service, spread pricing, escheatment rules all missing from code |
| payment-processing | 85/100 | 85% | Vendor adapters (NACHA, Echo, Zelis, check), OFAC, business-day calendar, ACH returns, positive pay, reconciliation, payee enrollment all present; fraud monitoring job partial |
| reclaimrx | 80/100 | 80% | Core detection rules, ML scoring (XGBoost + Isolation Forest), investigation lifecycle, recovery, letter service, payment holds, graph analysis, tipline, statute of limitations, corrective action plans, state audit rules all modeled; competitive gap features (cross-tenant intelligence, predictive risk, bias monitoring, adversarial adaptation) missing from router/services |
| reporting | 72/100 | 72% | Reports, dashboards, report builder, actuarial, quality/Star Ratings, CAA transparency, PHI controls present; schedule delivery routes missing from router, webhook delivery not wired, concurrent execution queue missing |
| ai-nlp | 48/100 | 48% | Chat/RAG, document extraction, text classify, content generation, guardrails, anomaly narrative (event-driven) implemented; denial prediction, clinical criteria matching, NLP auto-coding, FHIR PA support, model management endpoints, human feedback loop, batch document processing, fax bundle splitting, consensus scoring, self-correction loops, paper EOB→835 pipeline all missing |
| dataiq | 62/100 | 62% | KPI counters, drug trend decomposition, SPC, repricing, geo analytics, data quality, benchmarking, insight alerts implemented; what-if scenarios, natural language query, forecast API endpoints, prescriber profiling, annotation system, embedded analytics, MTM targeting, data catalog/export API endpoints missing from router |
| drug-database | 82/100 | 82% | NDC lookup, pricing, interactions, NADAC, FDA parser, MAC lists, FDB adapter, REMS, drug shortage, biosimilar modeled; compound ingredient support, unit conversion factors, drug image references, multi-source generic indicator service implementations missing |
| member-management | 75/100 | 75% | Members, groups, coverage, accumulators, COB, enrollment (834+CSV), eligibility, merge, retroactive, dependent aging-out, 270/271, Part D LEP calculation present; consent management, address validation service, COBRA table/tracking, disenrollment reason coding service missing |
| pharmacy-directory | 70/100 | 70% | Lookup, networks, credentialing, PSAO, network adequacy, performance snapshots, geocoding, NCPDP/NPPES parsers, credential monitor present; contract rate history, accreditation tracking, LDD designation, pharmacy closure handling, chain bulk credentialing, DAW rate tracking service all missing |
| prescriber-directory | 65/100 | 65% | NPPES pipeline, validation, taxonomy, credential monitoring, state prescribing rules, prescriber-pharmacy relationships present; supervisory relationships service, panel size tracking, communication preferences, staleness detection service, opt-out tracking service (field only) missing |
| edi-compliance | 75/100 | 75% | X12 generators (835/837P/I/D/270/271/276/277/278/999), parsers (835/271/277/278/834/999), validators, SFTP+AS2 transport, clearinghouse, scrubbing, denial scoring, FHIR bridge, NCPDP batch, SLA monitoring, cert lifecycle, trading partners + BAA, companion guide reference present; X12 275 clinical attachments generator/parser missing, EDI-specific RBAC missing, real-time transaction monitoring dashboard endpoint minimal |
| medical-claims | 78/100 | 78% | Claim ingestion, drug identification, pricing, site-of-care, administration method, 340B detection, medical-pharmacy crosswalk, denial management, accumulator integration all present; NLP auto-coding integration (stub client only), waste analysis endpoint partial, ASP refresh job present but ASP pricing service shallow |

---

## Per-Module Detail

---

### core-platform (score 72/100)

**PRD scope summary:** Tenants, users, RBAC, MFA (TOTP + FIDO2), audit log (hash chain), notifications, jobs, files, government exclusion screening, feature flags, webhooks, bank holiday calendar, security headers, rate limiting, DLQ, SSO/SAML/OIDC, circuit breaker, break-glass procedure, incident response.

**Implemented:**
- Tenant CRUD with isolation (TenantScopedMixin) ✅
- Users + RBAC (roles, permissions, role assignment) ✅
- TOTP MFA enrollment + verification ✅
- FIDO2 credentials table (migration 0004) + schema field ✅ — but route handler explicitly defers FIDO2: `# Future: fido2 verification. For now reject unknown methods.` ⚠️
- Audit log with SHA-256 hash chain, tamper detection ✅
- Sessions (model + service, migration 0006) ✅
- API keys (SHA-256 hashed) ✅
- Government exclusion screening (OIG/SAM ingestion + matching + job) ✅
- Bank holiday calendar (API + seed) ✅
- Jobs API + scheduler + runner ✅
- Files API + storage ✅
- Health check ✅
- DLQ router mounted in `create_app()` ✅
- SecurityHeadersMiddleware + RateLimitMiddleware mounted ✅
- Notifications service + delivery + preferences ✅ (router exists but NOT mounted in main.py / api.py — AUDIT FINDING re-confirmed)

**Missing:**
- Webhooks (no `WebhookService`, no webhook model, no webhook router) ❌
- Feature flags (no `FeatureFlag` model or service) ❌
- SSO / SAML / OIDC integration ❌
- Break-glass emergency access procedure ❌
- Circuit breaker pattern ❌
- CORS configuration endpoint ❌
- API versioning strategy implementation ❌
- Monitoring & alerting framework (Prometheus/Azure Monitor hooks) ❌

**Partial:**
- FIDO2: DB table exists, schema has `method: "fido2"`, but route handler explicitly rejects it ⚠️
- Auth router (`auth_api_router`), audit router, notifications router, bank_holidays router all exist but are NOT included in `api.py` or `main.py` — they are unreachable in production ⚠️ (AUDIT FINDING from CLAUDE.md reproduced here)
- Incident response / breach notification: no implementation, only PRD text ⚠️

---

### billing (score 70/100)

**PRD scope summary:** Claims ingestion + routing, AP payment cycle, AR invoicing, financial journal (hash chain), 835 generator, NACHA generator, fee engine (8 types), funding models (3 types), program monitoring, 50-state prompt pay compliance, escheatment, DIR fees, spread pricing, accounting adapters (6), void/correction workflows, period close, 1099, positive pay.

**Implemented:**
- Claims ingestion (file upload + API + internal) ✅
- Routing rules engine with priority + pay-to waterfall ✅
- AP records + payment batches + payments ✅
- Payment void workflow ✅
- AR records + invoices + line items ✅
- Invoice void ✅
- Fee engine (8 calculation types in `ar.py`) ✅
- Financial journal (append-only, tag-based) ✅
- Program budget monitoring (burn rate, projections, 6 alert types) ✅
- NACHA generator (fully compliant fixed-width) ✅
- 835 remittance generator ✅
- Routing service + funding config ✅
- Period close report endpoint ✅
- 1099 data endpoint ✅
- Events (publishers + consumers) ✅
- Accounting config model + export endpoint ✅
- SFTP config model ✅

**Missing:**
- 50-state prompt pay deadline table (constant defined but no table/service) ❌
- 50-state escheatment rules table/service ❌
- 50-state clawback limitation rules table/service ❌
- DIR fee service/model (only a journal constant `JOURNAL_DIR_FEE_ASSESSED`) ❌
- Spread pricing tracking model/service ❌
- Rebate pass-through tracking ❌
- Accounting system adapters (QuickBooks Desktop, QB Online, NetSuite, Sage, Xero) — config model only, no format adapters ❌
- Positive pay file generation service (referenced in payment-processing but not billing) ❌
- Payment notification to payee service ❌
- Multi-entity billing service ❌
- Invoice PDF generator ❌

**Partial:**
- `AccountingConfig` model exists with `export_format` field but no actual adapter code ⚠️
- Void/correction: AP void implemented (`void_batch`), AR void (`void_invoice`) implemented; offsetting journal entries need verification ⚠️
- Carryover: model field + service function present ⚠️

---

### payment-processing (score 85/100)

**PRD scope summary:** Vendor adapters (NACHA/Direct ACH, Echo Health, Zelis, check issuance), ACH return handling (80+ codes), settlement tracking, retry logic, OFAC screening, business day calendar, positive pay, reconciliation, payee enrollment, vendor health monitoring, payment file encryption, vendor failover, NACHA 2026 fraud monitoring.

**Implemented:**
- Vendor adapter framework + NACHA, Echo, Zelis, check issuance adapters ✅
- ACH return code library (80+ codes with retryability + default action) ✅
- Settlement tracking (mark_settled) ✅
- Retry service ✅
- OFAC screening service ✅
- Business day calendar service ✅
- Positive pay file generation service ✅
- Reconciliation service ✅
- Payee enrollment (model + API endpoints) ✅
- Vendor health log (model) ✅
- Payment file encryption service ✅
- Submission service with idempotency ✅
- Payment hold (apply + release) ✅
- Full router with dashboard + reconciliation endpoints ✅

**Missing:**
- Vendor failover logic in submission service (adapter failover chain) ❌
- NACHA 2026 fraud monitoring compliance (PRD §3.18 — job exists but fraud monitoring fields not in model) ❌

**Partial:**
- Vendor health monitoring: model table for health log present but no active health-check scheduler job ⚠️

---

### reclaimrx (score 80/100)

**PRD scope summary:** FWA detection rules (50+ pre-built), ML scoring (XGBoost + Isolation Forest), investigation lifecycle, recovery tracking, letter generation, graph analysis, payment holds, anonymous tipline, regulatory reporting, corrective action plans, statute of limitations, watchlist, state audit law compliance, accumulator/maximizer detection, cross-tenant intelligence, predictive risk, bias monitoring.

**Implemented:**
- Detection rules framework + TenantRuleConfig ✅
- XGBoost claim risk scoring + Isolation Forest pharmacy anomaly ✅
- Investigation lifecycle (create, update, assign, timeline, activity) ✅
- Recovery tracking ✅
- Letter service ✅
- Payment holds (apply, list, release) ✅
- Graph analysis service ✅
- Accumulator detection ✅
- Tipline (TipRecord model + POST/GET endpoints) ✅
- Regulatory report model ✅
- State audit rules model ✅
- Statute of limitations model ✅
- Corrective action plan + items model ✅
- Watchlist entry model ✅
- Network risk registry model ✅
- False positive rate job ✅
- Litigation hold fields on Investigation ✅

**Missing:**
- Cross-tenant intelligence service (PRD §10.7) ❌
- Predictive risk / early warning service (PRD §10.8) ❌
- Bias monitoring service (PRD §10.17) ❌
- Adversarial adaptation monitoring service (PRD §10.19) ❌
- Regulatory/law enforcement reporting endpoints not in router ❌
- Watchlist endpoints not in router ❌
- Network intelligence endpoints not in router ❌
- Corrective action plan endpoints not in router ❌

**Partial:**
- Statute of limitations: model exists, no service or API endpoint ⚠️
- Regulatory report: model exists but endpoint missing from router ⚠️
- State audit rules: model + seeder exist, no API endpoint ⚠️

---

### reporting (score 72/100)

**PRD scope summary:** Pre-built report library (50+ reports), custom report builder, dashboards, scheduled delivery, client reporting API, actuarial modeling, Star Ratings / PDC, CAA 2026 transparency, PHI controls (watermarking, masking), regulatory submissions, alert-triggered reports, comparison/trend mode, webhook delivery, concurrent execution queue.

**Implemented:**
- Report library (50+ definitions in `report_library.py`) ✅
- Report builder (data source discovery, field listing, preview) ✅
- Dashboards (CRUD + user customization + filter presets) ✅
- Report run engine ✅
- Client reporting API (claims, billing, program performance, FWA summary) ✅
- Actuarial service (reprice + scenario modeling) ✅
- Star Ratings / PDC (`quality_service.py`, PDC adherence) ✅
- CAA 2026 transparency reporting (`generate_caa_transparency_report`) ✅
- PHI controls (masking, watermarking, access logging) ✅
- Regulatory submissions (CRUD + deadlines) ✅
- Financial reporting service ✅
- Quality gaps + projections ✅
- Events (publishers + consumers) ✅
- Scheduled report model (`ReportSchedule` table exists) ✅

**Missing:**
- Scheduled delivery route handlers (no `@router.` for schedules despite model existing) ❌
- Webhook delivery for scheduled reports (constant defined but no delivery service) ❌
- Concurrent report execution queue service ❌
- Report output size management (streaming / chunking) ❌
- Comparison / trend mode API endpoint ❌
- Alert-triggered report service ❌

**Partial:**
- Scheduler service (`scheduler.py`) calculates next_run but delivery is not wired to route or job ⚠️

---

### ai-nlp (score 48/100)

**PRD scope summary:** Document intelligence (extraction), text classification + NER, content generation, conversational AI (RAG chatbot), intelligent document routing, anomaly narrative generation, LLM provider fallback, human feedback loop, batch document processing, model version pinning, response caching, FHIR PA support (CMS-0057-F), denial prediction, clinical criteria matching, NLP auto-coding, multi-document fax bundle splitting, per-field consensus scoring, adaptive confidence thresholds, cross-field dependency validation, agentic correction layer, self-correction loops, field-level correction audit trail, page-level source citations, paper EOB→835 conversion, extracted-data-to-EDI auto-mapping.

**Implemented:**
- Document extraction service (OpenAI-based) ✅
- RAG chatbot service ✅
- Text classify + entity extraction endpoints ✅
- Content generation (with templates/Jinja2 prompts) ✅
- Guardrails (PHI leak, toxicity, topic restriction) ✅
- Usage logging ✅
- Anomaly narrative (event-driven via consumers + Jinja2 template) ✅
- Source citations in RAG (`_extract_sources`) ✅

**Missing:**
- Denial prediction service ❌
- Clinical criteria matching service ❌
- NLP auto-coding for medical claims ❌
- FHIR PA support (CMS-0057-F) ❌
- Intelligent document routing service ❌
- Human feedback loop service ❌
- Batch document processing service ❌
- Multi-document fax bundle splitting ❌
- Per-field consensus scoring algorithm ❌
- Adaptive confidence thresholds per document type ❌
- Cross-field dependency validation ❌
- Agentic correction layer ❌
- Self-correction validation loops ❌
- Field-level correction audit trail ❌
- Paper EOB → 835 conversion pipeline ❌
- Extracted-data-to-EDI auto-mapping ❌
- Model management endpoints (version pinning, governance) ❌
- LLM provider fallback logic ❌
- Response caching (model exists, service missing) ❌
- Model version pinning service ❌

**Partial:**
- Document routing: table `ModelRoutingRule` not confirmed; no routing service ⚠️
- Jobs directory exists but is empty ⚠️

---

### dataiq (score 62/100)

**PRD scope summary:** Real-time KPI engine, drug trend analytics, network analytics, member analytics, financial analytics, SPC, data quality scoring, benchmarking, what-if scenario engine, claims repricing engine, forecast modeling, natural language query, prescriber profiling, geographic analytics, embedded analytics, data export API, MTM targeting, annotation system, contract guarantee monitoring, underwriting analytics.

**Implemented:**
- KPI counter service (Redis-backed, tenant-scoped) ✅
- Drug trend decomposition service ✅
- SPC (statistical process control) service ✅
- Repricing engine service ✅
- Geo analytics service ✅
- Data quality scoring endpoint ✅
- Benchmarking (model + CRUD endpoints) ✅
- Insight alerts (list + acknowledge) ✅
- Drug trend endpoints (decomposition, top drugs, spend, GLP-1, biosimilar, new drugs, price inflation) ✅
- Network analytics endpoints (adequacy, scorecard, leakage, cost variation) ✅
- Member analytics endpoints (adherence, high-cost, polypharmacy, therapy gaps, opioid) ✅
- Financial analytics endpoints (cost drivers, PMPM, spread, profitability) ✅
- Forecast model table in DB ✅
- Events (publishers + consumers) ✅

**Missing:**
- What-if scenario engine (API endpoints + service) ❌
- Natural language query service ❌
- Forecast API endpoints (model exists, no route) ❌
- Prescriber profiling service/endpoints ❌
- Annotation system (model + service + endpoints) ❌
- Embedded analytics (iframe token generation) ❌
- MTM targeting service/endpoints ❌
- Data export API ❌
- Data catalog / field dictionary API ❌
- Underwriting analytics service ❌
- Contract guarantee monitoring service ❌
- Self-service exploration endpoint ❌

**Partial:**
- Forecast model table defined, no service or API endpoint ⚠️
- Benchmark comparison to baseline (model exists, trend comparison missing) ⚠️

---

### drug-database (score 82/100)

**PRD scope summary:** NDC lookup, drug pricing (AWP/WAC/NADAC/MAC), drug interactions, therapeutic equivalence, drug search, price change alerting, tenant pricing overrides, REMS tracking, drug shortage tracking, compound ingredient support, unit conversion factors, multi-source generic indicator, biosimilar interchangeability, NDC-to-therapeutic-class crosswalk, drug image references, data source priority rules.

**Implemented:**
- NDC lookup service ✅
- Drug pricing service (AWP/WAC/NADAC) ✅
- Drug interactions service ✅
- NADAC parser ✅
- FDA NDC parser ✅
- FDB adapter ✅
- MAC list service ✅
- REMS program table + API endpoint ✅
- Drug shortage table + API endpoint ✅
- Biosimilar flag on drug model ✅
- NDC utility validation ✅
- Therapeutic equivalence (via FDB adapter) ✅
- Price change detection (implied by publisher events) ✅
- Tenant pricing overrides ✅ (router endpoint at `/tenant-overrides`)
- Drug search ✅
- Security headers + rate limiter mounted ✅

**Missing:**
- Compound ingredient support (no model or service) ❌
- Unit conversion factors table/service ❌
- Drug image reference model/service ❌
- Multi-source generic indicator service (field may exist but no service logic) ❌

**Partial:**
- Biosimilar interchangeability: `is_biosimilar` flag exists but no interchangeability interchange service ⚠️
- Drug shortage: table + endpoint exist but no FDA shortage feed ingestion job ⚠️
- REMS: table + endpoint exist but no FDA REMS ingestion job ⚠️

---

### member-management (score 75/100)

**PRD scope summary:** Enrollment file processing (834 + CSV), real-time eligibility check, accumulator management, COB, member search, 270/271 support, member merge, retroactive eligibility, dependent aging-out, enrollment period management, member address validation, Part D LEP, consent management, disenrollment reason coding, COBRA continuation tracking.

**Implemented:**
- 834 EDI parser + CSV parser ✅
- Member CRUD + search ✅
- Groups CRUD ✅
- Coverage periods ✅
- Eligibility service (real-time check, COBRA status handling) ✅
- Accumulator service (deductible, OOP, benefit phase) ✅
- Accumulator DB persistence ✅
- COB service ✅
- 270/271 eligibility transaction service ✅
- Member merge service ✅
- Retroactive enrollment job ✅
- Dependent aging-out job ✅
- Benefit year reset job ✅
- Part D LEP calculation (`calculate_lep` in `accumulator.py`) ✅
- Events (publishers + consumers) ✅
- Security headers + rate limiter ✅
- ID card endpoint ✅

**Missing:**
- Consent management model/service ❌
- Address validation service (USPS/SmartyStreets integration) ❌
- COBRA continuation tracking model (COBRA status handled in eligibility logic only) ❌
- Disenrollment reason coding service ❌

**Partial:**
- Part D LEP: calculation function exists in accumulator service; no dedicated endpoint or model field ⚠️
- COBRA: status enumerated in eligibility service but no `CobraRecord` model or tracking ⚠️

---

### pharmacy-directory (score 70/100)

**PRD scope summary:** Pharmacy lookup (NPI/NABP), network management, credentialing workflow, network adequacy analysis, pharmacy performance metrics, accreditation tracking, LDD designation, contract rate history, pharmacy closure handling, chain bulk credentialing, pharmacy taxonomy auto-classification, DAW rate tracking, NCPDP/NPPES parsing, geocoding, PSAO management.

**Implemented:**
- Pharmacy lookup (NPI + NABP + search + nearby) ✅
- Network CRUD + bulk-add ✅
- Network adequacy analysis endpoint ✅
- Credentialing workflow (apply, approve, deny) ✅
- Credential monitoring (alerts) ✅
- PSAO model + CRUD + pharmacy membership ✅
- Pharmacy performance snapshot model ✅
- Payment info model ✅
- NCPDP parser ✅
- NPPES parser ✅
- Geocoding service ✅
- Credential monitor job ✅
- Cache service (Redis) ✅
- Network service ✅
- DAW rate field on PharmacyPaymentInfo ✅
- Events (publishers + consumers) ✅
- Security headers + API middleware ✅

**Missing:**
- Accreditation tracking model/service (URAC, ACHC, PCAB) ❌
- LDD (Limited Distribution Drug) designation model/service ❌
- Contract rate history model/service ❌
- Pharmacy closure handling service ❌
- Chain bulk credentialing service ❌
- Pharmacy taxonomy auto-classification service (taxonomy util exists, classification missing) ❌

**Partial:**
- Performance metrics: `PharmacyPerformanceSnapshot` model exists but `performance.py` service is shallow ⚠️
- DAW rate: field exists on `PharmacyPaymentInfo` but no DAW rate tracking/reporting service ⚠️

---

### prescriber-directory (score 65/100)

**PRD scope summary:** NPPES data pipeline, prescriber validation (real-time with Luhn NPI check), prescriber search, DEA/controlled substance authority check, credential monitoring, prescriber-pharmacy relationship data, mid-level supervisory relationships, state-specific prescribing authority rules, prescriber panel size, prescriber communication preferences, prescriber opt-out tracking, NPPES staleness detection.

**Implemented:**
- NPPES parser + upsert service ✅
- Prescriber CRUD + search ✅
- Taxonomy code table + service ✅
- Practice affiliations model ✅
- Credential monitoring service + alerts model ✅
- Data refresh log model ✅
- Prescriber-pharmacy relationship model ✅
- State prescribing rules model + service ✅
- Medicare opt-out flag on model ✅
- NPI Luhn validation ✅
- Security headers + rate limiter ✅
- Events (publisher + consumer) ✅

**Missing:**
- Mid-level supervisory relationships model/service ❌
- Panel size tracking model/service ❌
- Communication preferences model/service ❌
- NPPES staleness detection service ❌
- Prescriber opt-out tracking service (field only, no opt-out workflow or endpoint) ❌
- DEA controlled substance authority check service ❌

**Partial:**
- Medicare opt-out: field exists on `Prescriber` model, no opt-out tracking workflow or history table ⚠️
- Credential monitoring: alert model exists, no scheduled job to push DEA expiry checks ⚠️

---

### edi-compliance (score 75/100)

**PRD scope summary:** X12 generators (835/837P/837I/837D/270/271/276/277/278/999), X12 parsers (835/271/277/278/834/999), 4-level validation engine, SFTP + AS2 transport, clearinghouse integration, companion guide management, pre-adjudication claim scrubbing, predictive denial scoring, 835 auto-posting, X12 275 clinical attachments, FHIR-to-X12 bridge, code set version management, ISA fixed-width handling, AS2 cert lifecycle, trading partner BAA tracking, EDI-specific RBAC, inbound response SLA monitoring, real-time transaction monitoring dashboard, NCPDP Batch 1.2.

**Implemented:**
- X12 generators: 835, 837P, 837I, 837D, 270, 271, 276, 277, 278, 999/TA1 ✅
- X12 parsers: 835, 271, 277, 278, 834, 999 ✅
- 4-level validation engine ✅
- SFTP transport ✅
- AS2 transport + cert lifecycle service ✅
- Clearinghouse integration service ✅
- Companion guide reference (field on TradingPartner + PayerCompanionRule model) ✅
- Claim scrubbing service ✅
- Denial scoring service ✅
- 835 auto-posting service ✅
- FHIR bridge service ✅
- Code set version management service ✅
- Trading partner model + BAA/agreement model ✅
- SLA monitoring service ✅
- NCPDP Batch 1.2 service ✅
- Compliance dashboard endpoint ✅
- Control number management ✅
- ISA envelope + delimiter handling ✅

**Missing:**
- X12 275 clinical attachments generator + parser ❌
- EDI-specific RBAC (no `EDIRole` model or middleware) ❌

**Partial:**
- Real-time transaction monitoring dashboard: `get_compliance_dashboard` endpoint exists but is minimal (single GET with no streaming or real-time update) ⚠️
- Companion guide management: field reference + `PayerCompanionRule` model exist; no dedicated companion guide CRUD API ⚠️

---

### medical-claims (score 78/100)

**PRD scope summary:** Claim ingestion pipeline (CMS-1500/837P from EDI), drug identification (J-code + NDC), medical claim pricing (ASP, WAC, AWP), site-of-care analysis, administration method tracking, 340B detection, medical-pharmacy crossover view, denial management, accumulator integration.

**Implemented:**
- Claim CRUD + ingestion (incl. EDI payload ingestion) ✅
- Drug identification service (mapping service) ✅
- Pricing service (ASP, WAC, AWP) ✅
- Site-of-care classification (place_of_service → site category) ✅
- Administration method field + schema ✅
- 340B detection service (JG/TB modifier detection + provider NPI check) ✅
- Medical-pharmacy crosswalk (crosswalk routes + schemas) ✅
- Denial service + appeal management ✅
- Accumulator service ✅
- Unified spend service ✅
- Analytics routes ✅
- ASP refresh job ✅
- Module clients (drug database, member management, pharmacy directory) ✅
- Events (publishers + consumers) ✅
- Security headers + rate limiter ✅

**Missing:**
- NLP auto-coding service integration (pharmacy directory client is a stub with TODO note) ❌
- Waste analysis service (waste fields on model but no dedicated analysis endpoint) ❌

**Partial:**
- Pharmacy directory client: implemented as in-memory stub with explicit `# TODO: implement real HTTP GET` ⚠️
- ASP pricing: service exists but relies on stub data loading rather than real ASP feed ingestion ⚠️
- Waste detection: `has_jw_waste_modifier` + waste fields present, no `/waste` endpoint ⚠️

---

## Overall PRD Compliance: 73/100 (weighted average)

Weighted by PRD size (line count as proxy for feature scope):

| Module | PRD Lines | Score | Weighted |
|---|---|---|---|
| core-platform | 1383 | 72 | 99,576 |
| billing | 1380 | 70 | 96,600 |
| payment-processing | 570 | 85 | 48,450 |
| reclaimrx | 1295 | 80 | 103,600 |
| reporting | 684 | 72 | 49,248 |
| ai-nlp | 908 | 48 | 43,584 |
| dataiq | 690 | 62 | 42,780 |
| drug-database | 652 | 82 | 53,464 |
| member-management | 675 | 75 | 50,625 |
| pharmacy-directory | 622 | 70 | 43,540 |
| prescriber-directory | 499 | 65 | 32,435 |
| edi-compliance | 712 | 75 | 53,400 |
| medical-claims | 529 | 78 | 41,262 |
| **Totals** | **10,599** | — | **758,564** |

**Weighted average: 758,564 / 10,599 = 71.6 → rounded to 72/100**

### Top Gaps by Risk

1. **core-platform**: Auth, audit, notification routers not mounted in `main.py`/`api.py` — these subsystems are unreachable in production. Webhooks + feature flags completely absent.
2. **ai-nlp**: Only ~48% of PRD implemented; most advanced features (denial prediction, clinical criteria, paper EOB→835, fax splitting, consensus scoring, FHIR PA, auto-coding) are entirely missing.
3. **billing**: 50-state compliance tables, accounting adapters, DIR fee/spread pricing services absent despite being listed as "ships complete" in PRD.
4. **dataiq**: What-if scenarios, NL query, forecast endpoints, MTM targeting, annotations all missing from router despite being core PRD capabilities.
5. **reclaimrx competitive gaps**: Cross-tenant intelligence, predictive risk, bias monitoring, adversarial adaptation — models partially exist but no service or API endpoint.
