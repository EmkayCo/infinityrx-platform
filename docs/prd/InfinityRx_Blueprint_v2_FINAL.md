# InfinityRx Platform — Master Blueprint v2.0

**FINAL — Approved for Build**  
**Date:** April 12, 2026  
**Scale:** 100M+ claims/year, tens of billions of dollars, zero error tolerance  

---

## GOVERNING RULES

**1. ZERO REFERENCE** to RxLogic or any third-party vendor anywhere in code, docs, comments, variable names, test data, or artifacts.

**2. STANDARD, NOT SPECIFIC.** Every module is built to the industry standard — the full capability for any client type (manufacturer, health plan, TPA, 340B, workers comp, PBM service company). No module is built for one client's configuration. Client-specific setups (IFX's current business, future clients) are tenant configurations within the system, not code. The PRD describes the engine. The client's business is the fuel.

**3. BUILD PHILOSOPHY.** Mike's WHAT = the real goal. Mike's HOW = best guess, not gospel. Research the right approach, identify ALL gaps, suggest the smarter path. Build on standards (full NCPDP D.0, full FDB, full EDI specs), build for extensibility. Claude is the technical expert ensuring nothing is missing and everything is future-proof.

**4. CONFIGURATION OVER CODE.** Every business rule, every fee calculation, every detection rule, every billing cycle, every payment routing, every SFTP destination, every report template — all configurable per tenant through the UI or config upload. If adding a new client requires changing code, the architecture is wrong.

**5. EXISTING SPECS ARE REFERENCE, NOT ARCHITECTURE.** The existing PaySync V1/V2 spec and ReclaimRx spec describe IFX's current tenant configuration. They move to `docs/reference/` as examples of how one tenant is configured. They do NOT define the module architecture. Module PRDs are written fresh to the standard.

---

## TECH STACK

```
Backend:       Python 3.13 + FastAPI 0.135.x
Frontend:      Next.js 16.2 + React 19.2 + TypeScript 5.8 + Tailwind CSS + shadcn/ui
Database:      PostgreSQL 17 + Redis 7.4
Runtime:       Node.js 22 LTS
Events:        RabbitMQ 4.x (local) / Azure Service Bus (prod)
AI/NLP:        Azure OpenAI Service (GPT-4.1)
ML:            scikit-learn + XGBoost
OCR Primary:   Azure Document Intelligence
OCR Secondary: Mistral Document AI 2512 (dual-model consensus)
Infra:         Docker, Terraform, AKS (Azure)
Drug Data:     First DataBank (licensed)
Provider Data: NCPDP Data Queue (licensed) + NPI Registry (public)
```

---

## 25 MODULES

### Module 1 — Core Platform
Multi-tenant infrastructure that every other module plugs into. Tenant provisioning and isolation. Authentication (Azure AD B2C, JWT). Role-based access control configurable per tenant. API gateway with per-tenant rate limiting. Event bus (publish/subscribe) for inter-module communication. Audit logging (who/what/when/where/before/after on every action, queryable, exportable, SOC 2-ready). Job scheduler. File management. Notification/alerting engine (configurable events and channels per tenant). White-label configuration (branding, colors, logos, domain per tenant). Government exclusion screening (OIG/SAM.gov — all entities, all tenants, recurring). Help desk unified view (cross-module claim/member/pharmacy lookup for support operators). Docker Compose local dev stack (PostgreSQL 17, Redis 7.4, RabbitMQ 4). Shared test fixtures. CI/CD pipeline. Health check endpoints. Pre-flight validator script.

### Module 2 — Drug Database
First DataBank data ingestion with configurable refresh schedule. NDC/GPI/DDID lookup API. Drug pricing API (AWP, WAC, NADAC — all pricing benchmarks, not just one). Drug-drug interaction checking. Therapeutic equivalence engine. Compound ingredient database. Generic/brand classification. Repackaged drug identification. Discontinued drug tracking. MAC (Maximum Allowable Cost) management — create custom MAC lists per tenant, monitor market pricing changes, pharmacy MAC appeal workflow, configurable MAC update frequency. Drug search by name, NDC, GPI, generic name, therapeutic class.

### Module 3 — Pharmacy Directory
NCPDP provider data queue ingestion with configurable refresh. Pharmacy search/lookup API. Network management — create unlimited networks per tenant, assign pharmacies to networks with configurable terms (discount rates, dispensing fees, admin fees). Pharmacy contracts — contract terms, effective/termination dates, auto-renewal, amendment tracking. Pharmacy credentials management. Payment center management — routing numbers, account numbers, payment type (ACH/check/EFT), reporting method, EDI FTP connections. Pharmacy affiliates and chain code management. Provider agreement management — generate agreements from configurable templates, send as PDF (sign-only) or Word (redline), track signature status, countersign, activate upon execution. Pay-to waterfall logic — configurable per tenant: PSAO → chain → pharmacy NPI (or any custom hierarchy). PSAO management — master agreements, pharmacy affiliations, PSAO-level reporting, PSAO fee schedules. Reconciliation vendor management. Mail order pharmacy support — pharmacy type flag, mail order workflow (90-day supply, auto-refill), mail order pricing tier separate from retail. Specialty pharmacy network tier.

### Module 4 — Medical/Prescriber Directory
NPI Registry data ingestion with configurable refresh. Medical provider search API. Prescriber lookup (NPI/DEA). Prescriber validation API for adjudication (NPI valid? DEA active? In-network for this plan?). Provider credentialing workflow. Taxonomy code management. Provider network management. Prescriber-level restrictions (prescriber-specific PA requirements, prescriber tier assignments).

### Module 5 — Member Management
Cardholder/member CRUD with configurable fields per tenant. Eligibility engine — real-time eligibility determination based on enrollment dates, plan assignment, and benefit status. Enrollment workflows (configurable per tenant — some tenants self-enroll members, some bulk-upload, some receive eligibility feeds). Group/plan assignment with effective/termination dates. Accumulator/maximizer tracking — running OOP ledger per member per benefit year, resets on configurable benefit year boundary, supports both manufacturer-side (defense: detect accumulator plans, calculate impact) and health-plan-side (implementation: configure accumulator/maximizer programs). Debit card member linking. Member search API. Member requirement management (configurable eligibility requirements per program — age, diagnosis, prior therapy, insurance type). Member communication preferences.

### Module 6 — Plan Design & Configuration
Configurable hierarchy: Organization → Carrier → Group → Plan → SubGroup (depth configurable per tenant). Benefit configuration — copays (flat/percentage/tiered by drug type), deductibles, OOP maximums, coinsurance, benefit phases (configurable — not just Part D phases). Formulary management — create unlimited formularies per tenant, drug tier assignment, therapeutic class management. Formulary optimization tools — impact analysis (model cost impact of tier changes), therapeutic class review reports, P&T committee support materials, formulary change notification engine (push to pharmacies and prescribers). Network assignment per plan. Plan cloning/templating. Program types — fully configurable, not hardcoded: copay assistance, voucher/eVoucher, bridge/free goods, debit card, specialty, statement account, workers compensation, commercial, Medicare, Medicaid, or any custom type. DUR rules configurable per plan. Location rules. Step therapy configurable per formulary. Fill rules.

### Module 7 — Rules Engine
Configurable rule library — every rule type is a template that can be instantiated with parameters per tenant/plan/program. Rule types: age, cost calculation (configurable tiers: standard/preferred/maintenance with custom labels), copay (flat/percentage/tiered/step — any structure), MAC pricing, dispense fee, dispense limit, refill (early refill threshold configurable), restriction, process, DAW, prior authorization triggers, quantity limits, compound pricing, under-reimbursement/POS adjustment (configurable benchmark: WAC, manufacturer-defined target, sales data, or custom formula), coupon/voucher, accumulator/maximizer (dual-sided), workers comp (state-specific rule sets), 340B split billing, and custom rule types definable by tenant. Visual drag-and-drop rule builder — pipeline canvas showing adjudication flow, drag rules from library, reorder priority, configure parameters inline. Natural language rule creation — describe a rule in plain English, AI creates the rule definition, user confirms. BRD config file upload — parse completed business rules document, validate, preview, apply. Rule versioning — every change creates a new version, rollback capability, audit trail. Rule testing — test a rule against sample claims before activating.

### Module 8 — Claims Adjudication Engine
NCPDP D.0 full-standard transaction parser — all transaction types (B1, B2, B3, E1, etc.), all segments, all fields. Built to the NCPDP standard, not to any specific file format. Real-time adjudication pipeline — sub-1-second processing target, 100M+ claims/year capacity, architect for 300M+. Rules engine execution orchestration — configurable rule execution order per plan. DUR processing — all DUR professional service codes, reason codes, result codes. COB coordination — primary/secondary/tertiary, configurable COB rules per plan. Prior authorization checking — real-time PA status lookup. Claim history lookup — sub-millisecond Redis-cached access to member's claim history for refill checks, quantity accumulation, duplicate detection. Response builder — NCPDP D.0 response format with all required fields. POS adjustment / under-reimbursement — calculated per tenant's configured rules, communicated via configurable channel (note/remark field, separate response segment, or custom channel). Transaction logging — every claim request and response stored with full audit trail. Claim reprocessing / retroactive adjustments — detect retroactive changes (eligibility, pricing, rules), identify affected claims, re-adjudicate, calculate delta, generate adjustment transactions. Claim restacking — automatic re-adjudication when eligibility changes retroactively. Compound claim handling per NCPDP Compound Segment.

### Module 9 — Switch Connectivity
Configurable switch integrations — add new switches without code changes. RelayHealth, Change Healthcare, RedSail/PowerLine as initial integrations. NCPDP D.0 telecommunications protocol handling. BIN/PCN routing table — configurable per tenant, maps incoming BIN/PCN to the correct plan/program. Connection health monitoring. Automatic failover between switches. Response timeout handling (configurable timeout per switch — industry standard 30 seconds, internal adjudication target sub-1-second). Switch certification testing support. Message framing and socket-level connectivity. Transaction routing audit trail.

### Module 10 — Prior Authorization
PA request intake from multiple channels (pharmacy claim reject, prescriber ePA, manual entry, phone). Clinical review criteria engine — configurable criteria sets per drug/therapeutic class/plan. Approval/denial workflow — configurable review steps, configurable reviewers per criteria type. Multi-level appeal management. PA letter generation — configurable branded templates per tenant. CoverMyMeds integration. SureScripts ePA integration. PA status API for adjudication engine (real-time lookup). PA duration management (configurable validity periods, renewal workflows, expiration notifications). PA reporting (approval rates, turnaround times, appeal outcomes).

### Module 11 — Billing & Financial
Configurable billing cycles — any frequency (semi-monthly, monthly, weekly, custom), configurable cycle dates per tenant. Payables engine — calculate what's owed to each pay-to entity based on adjudicated claims, configurable payment terms, configurable payment methods per pay-to entity. Receivables engine — calculate what's owed by each client, configurable invoice line items, configurable fee structures. Invoice generation — in-system branded PDF with configurable templates per tenant, email delivery, downloadable. Fee schedule management — configurable fee types (claims processing, admin, transaction, dispensing, custom), configurable calculation methods (flat, per-claim, percentage, tiered), configurable split logic. Payment file generation — NACHA/ACH with configurable bank accounts, configurable entry class codes. 835 remittance generation — per pay-to entity, configurable content. SaaSant Excel / QuickBooks integration. Bank reconciliation — upload bank payment file, match to generated payments, flag discrepancies. Statement account support — configurable per pharmacy per program: report-only (no payment), separate billing for statement vs non-statement claims. PSAO/reconciliation vendor 835 distribution — configurable SFTP destinations per vendor, automated file grouping and delivery. Prefund balance tracking — running ledger per client, configurable alert thresholds, burn rate projection, replenishment tracking. POS adjustment payment tracking — separate from standard 835, configurable reporting format. Carryover management. ACH return processing — configurable handling rules per return code. AR aging reports — configurable aging buckets. Government exclusion screening integration.

### Module 12 — Payment Processing
Configurable payment integrations — add new payment vendors without code changes. Echo integration (pharmacy payment distribution). ACH processing. Check issuance integration. Debit card program payments. Payment tracking and settlement. Payment file generation and validation. Payment reversal handling. Configurable payment batching (immediate, daily, per-cycle). Payment audit trail.

### Module 13 — EDI & Compliance
HIPAA 835 (005010X221A1). HIPAA 837P (005010X222A1). HIPAA 837I (005010X223A2). 270/271 eligibility verification. NCPDP SCRIPT/eRx (NewRx, RefReq/RefRes, CancelRx, RxChangeRequest). SureScripts integration. PHI masking — architectural enforcement layer (strips PHI before API response based on user type, not a UI toggle). Data retention policies — configurable per tenant. SOC 2 audit trail. HIPAA technical safeguard compliance. Configurable EDI trading partner management. EDI file validation before transmission.

### Module 14 — Medical Claims Engine
Manual claim submission via configurable web forms (CMS-1500, CMS-1450/UB-04 — form fields configurable per claim type). Dual-OCR document parsing — Azure Document Intelligence + Mistral Document AI consensus model. Low-confidence fields flagged for manual review, never silently accepted. Medical rules engine — configurable rules per plan (diagnosis validation, procedure validation, place of service, medical fee schedules). Medical claims adjudication — configurable adjudication logic per plan type. EDI 837P/837I ingestion and processing. Clearinghouse integration (Change Healthcare as initial, configurable for additional clearinghouses). Medical COB coordination. Medical payment processing. ICD-10, CPT/HCPCS code validation with configurable code set updates.

### Module 15 — Reporting & Analytics
Configurable report builder — dimensions, filters, date ranges, groupings, all selectable by user. Pre-built report templates for common report types (billing, claims, utilization, financial reconciliation, regulatory). Scheduled report delivery — configurable schedule, configurable recipients, configurable format (Excel/PDF/CSV), configurable delivery method (email/SFTP/portal). Client reporting API — documented, authenticated, rate-limited REST endpoints per tenant. Dashboard analytics with configurable widgets and layouts. PBM transparency reporting — 2026 CAA mandated semiannual reports (net drug spending, rebates, spread pricing), auto-generated per the HHS/DOL/Treasury standard format. Report templates branded per tenant. Export engine. Ad-hoc query capability.

### Module 16 — ReclaimRx (FWA & Recovery)
**Detection rule engine** — configurable detection rule library, not hardcoded to any client type. Detection rule templates organized by client type:
- **Manufacturer programs:** NQ inflation, bill-reverse-rebill, contracted rate deviation, volume spikes, days supply manipulation, duplicate claims, eVoucher abuse, accumulator/maximizer impact
- **Health plan:** network leakage (out-of-network utilization), formulary non-compliance, inappropriate utilization (therapeutic duplication, drug-disease contraindication), high-cost claimant analysis, prescriber outlier patterns, pharmacy audit triggers
- **TPA:** claims validation, duplicate detection, eligibility verification failures, billing code accuracy
- **340B:** duplicate discount detection, contract pharmacy compliance, covered entity verification, split billing accuracy
- **Workers comp:** state formulary compliance, treatment guideline adherence, overbilling patterns

Custom detection rules definable per tenant. **ML anomaly detection** — configurable models per tenant/client type. XGBoost classifier with configurable feature sets. Models trained per tenant on their confirmed outcomes. Configurable risk scoring thresholds. Model performance monitoring and retraining triggers. **Pharmacy profiling** — behavioral baseline per pharmacy, deviation detection, cross-pharmacy comparison within networks. **Recovery estimation** — conservative/mid/aggressive projections with configurable methodology per tenant. Confidence tiers (High/Medium/Low). Every estimate carries methodology tag. **Collections/correction workflow** — configurable workflow steps per tenant (letter → response period → escalation → recoupment). **Audit management** — desk audits and on-site audits, configurable audit letter templates, response tracking, recoupment management. **External verification integration** — BPG PatientLens, Complete BI, configurable for additional verification vendors. **340B compliance auditing.** **Accumulator/maximizer detection** for manufacturer clients. **Configurable alert routing** per tenant.

### Module 17 — Program Configuration & Onboarding
BRD template engine — generate business rules document templates configurable per program type. Config file upload → program setup: parse, validate, preview, apply. Program launch wizard — guided UI, configurable steps per program type. NDC/GPI assignment per program. BIN/PCN/Group configuration. Contract management — configurable contract templates, terms, SLAs, fee schedules, effective/termination dates, amendment tracking, auto-renewal. Client onboarding workflow — configurable steps from signed contract through go-live. Onboarding status dashboard.

### Module 18 — Claims Testing Simulator
NCPDP D.0 test harness — simulates pharmacy claims to the adjudication engine without real pharmacy systems. Configurable test scenarios (any combination of eligibility, copay, DUR, COB, PA, compound, reversal, under-reimbursement). Medical claim test harness. Scenario builder — create from BRD requirements, save, share, reuse across tenants. Response validation — expected vs actual, field-by-field diff. Regression suite — run saved scenarios after any rule change. Test data generation — create synthetic but realistic test claims based on program parameters.

### Module 19 — EBV/EBI & RTBC
Electronic benefit verification — BPG PatientLens, Complete BI, configurable for additional vendors. Real-time eligibility/benefit checking. Price checking / cost transparency. Coverage determination. Real-Time Benefits Check (RTBC) — SureScripts RTBC transaction support (BENREQ/BENRES), patient-specific cost and coverage at point of prescribing. Configurable verification vendor routing per plan/program. Usage tracking and cost management for paid verification services.

### Module 20 — Portals
**20a — Client Portal:** configurable dashboards per tenant (claims volume, payment status, program performance). Claims analytics. Financial summaries. ML-powered insights. Report access. Dispute management. Document management. User management (client-side). All data tenant-scoped. PHI architecturally masked for non-provider users.

**20b — Pharmacy Portal:** manual claim submission. 835/payment history. Claim status. Credential management. POS adjustment reporting. Secure messaging. Banking update workflow. All data scoped to pharmacy's own claims.

**20c — Medical Provider Portal:** CMS form upload. Claim status/history. EOB access. Payment history. Credential management. All data scoped to provider's own claims.

**20d — Member/Patient Portal:** coverage checker. Copay lookup. Prescription history. Participating pharmacy finder. Deductible/OOP status. Program enrollment. Refill reminders. Cost transparency tools. Configurable per tenant (some tenants may not expose all features).

### Module 21 — AI/NLP Layer
Azure OpenAI integration. Natural language query across all modules — scoped to user's permission level and tenant. Conversational program setup. Intelligent search. Anomaly alerting in plain English. Report generation via conversation. Natural language rule creation. All responses tenant-isolated. Configurable AI features per tenant (some tenants may not want AI enabled).

### Module 22 — Rebate Management
Configurable rebate contract terms (per drug, per formulary tier, per volume band, or custom structure). Formulary placement tracking. Utilization reporting for rebate calculations. Rebate invoicing. Reconciliation (actual vs estimated). Contract amendment tracking. Supports manufacturer-to-PBM, manufacturer-to-health-plan, and custom rebate flows.

### Module 23 — DataIQ
Cross-module data integrity checks. Data validation engine — configurable validation rules. Trend analysis. Program performance metrics. Data pipeline monitoring (FDB refresh, NCPDP refresh, job health). Configurable quality alerts. Data quality scoring per module.

### Module 24 — Medicare Part D / PDE Management (Future — Architecture Ready)
PDE submission to CMS. TrOOP tracking. Benefit phase management (configurable phases). LIS/LICS processing. SPAP coordination. CMS HPMS connectivity. PDE correction/deletion. Coverage year transitions. DIR reporting. Data model and API contracts defined during Phase 1.

### Module 25 — MTM / Clinical Programs (Future — Architecture Ready)
CMR workflow. Targeted medication review. Adherence monitoring. Medication synchronization. Disease management programs. Clinical outreach campaigns. Star Ratings optimization. Configurable clinical program templates. Data model and API contracts defined during Phase 1.

---

## PROJECT STRUCTURE

```
infinityrx-platform/
├── CLAUDE.md                          # 60 lines, universal principles
├── docker-compose.yml                 # PostgreSQL 17, Redis 7.4, RabbitMQ 4
├── .env.example                       # All secret placeholders
├── .gitignore
├── .claude/
│   ├── settings.json
│   ├── agents/                        # 41 team member skill files
│   │   ├── tier1-core/               # 12 files
│   │   ├── tier2-specialists/        # 15 files
│   │   ├── tier3-situational/        # 7 files
│   │   └── build-agents/            # 7 files
│   ├── commands/
│   └── rules/                        # financial, phi, claims-domain, testing, ui
├── docs/
│   ├── glossary.md
│   ├── negative-constraints.md
│   ├── api-contracts/                # Inter-module API contracts
│   ├── prd/                          # Module PRDs (standard-based, not client-specific)
│   ├── reference/                    # Client-specific reference docs
│   │   ├── ifx-paysync-v1-config.md     # IFX's current billing setup
│   │   ├── ifx-paysync-v2-spec.md       # IFX's planned billing features
│   │   └── ifx-reclaimrx-config.md      # IFX's current FWA detection rules
│   ├── sops/
│   └── templates/
├── infrastructure/
│   ├── terraform/
│   ├── docker/
│   └── k8s/
├── shared/
│   ├── CLAUDE.md
│   ├── auth/ | db/ | events/ | models/ | utils/
├── modules/
│   ├── core-platform/
│   │   ├── CLAUDE.md                 # 50-80 lines, module-specific
│   │   ├── src/ | tests/ | migrations/ | Dockerfile
│   │   └── tasks/ (todo.md + lessons.md)
│   ├── billing/                      # NOT "paysync" — generic name
│   ├── reclaimrx/                    # Brand name is fine — it's a product
│   ├── drug-database/
│   ├── pharmacy-directory/
│   ├── medical-prescriber-directory/
│   ├── member-management/
│   ├── plan-design/
│   ├── rules-engine/
│   ├── adjudication-engine/
│   ├── switch-connectivity/
│   ├── prior-authorization/
│   ├── payment-processing/
│   ├── edi-compliance/
│   ├── medical-claims/
│   ├── reporting/
│   ├── program-config/
│   ├── testing-simulator/
│   ├── ebv-ebi-rtbc/
│   ├── ai-nlp/
│   ├── rebate-management/
│   ├── dataiq/
│   ├── part-d-pde/ (placeholder)
│   └── mtm-clinical/ (placeholder)
├── portals/
│   ├── shared/ (component library)
│   ├── client-portal/
│   ├── pharmacy-portal/
│   ├── medical-portal/
│   └── member-portal/
└── tests/
    ├── fixtures/ | integration/ | contract/
```

**Note:** Module 11 folder is now `billing/` not `paysync/`. PaySync is IFX's product name for their billing. The module itself is the generic billing engine. IFX's config is in `docs/reference/`.

---

## PRD APPROACH

**Every PRD answers these questions:**

1. What does this module do for ANY client type?
2. What are ALL the use cases across manufacturers, health plans, TPAs, 340B, workers comp?
3. What is configurable per tenant?
4. What are the data models (schemas)?
5. What are the API endpoints?
6. What is the business logic (rules, calculations, workflows)?
7. What are the UI screens and wizard flows?
8. What events does it emit/listen to on the event bus?
9. What are the test scenarios (known-good, known-bad, edge cases)?

**PRDs are written just-in-time, one phase ahead:**
- Before Phase 1 → write PRD for Core Platform
- During Phase 1 → write PRDs for Phase 2 modules
- During Phase 2 → write PRDs for Phase 3 modules
- And so on

**PRDs are 200-400 lines each.** Business logic and data models only. No build process instructions (those are in CLAUDE.md and agent skill files).

**Existing IFX specs move to `docs/reference/`** — they inform what IFX's tenant configuration looks like. They're examples, not standards.

---

## BUILD PHASES

### Phase 1 — Core Platform (Module 1)
**4 sessions, 1-2 weeks**
| Session | Scope |
|---------|-------|
| 1 | Infrastructure (Terraform Azure defs, Docker Compose, DB framework, schema namespacing) |
| 2 | Auth (Azure AD B2C, JWT, RBAC, multi-tenant user model, tenant provisioning) |
| 3 | Event bus, audit logging, notification engine, government exclusion screening |
| 4 | Job scheduler, file manager, test fixtures, CI/CD, health checks, pre-flight validator |

### Phase 2 — Tools You Need Now (Modules 11, 12, 15, 16, 21, 23)
**4 sessions, 4-6 weeks, 2 batches**
Batch A: Billing (11), Payment Processing (12), ReclaimRx (16), Reporting (15)
Batch B: AI/NLP (21), DataIQ (23), cross-module integration

### Phase 3 — Reference Data (Modules 2, 3, 4, 5)
**4 sessions, 3-4 weeks**
Drug Database (2), Pharmacy Directory (3), Medical/Prescriber (4), Member Management (5)

### Phase 4 — Medical & Compliance (Modules 13, 14)
**4 sessions, 4-5 weeks**
EDI & Compliance (13), Medical Claims (14), integration testing, portal prep

### Portals (Modules 20a-d, after Phase 4)
**4 sessions, 3-4 weeks**
Shared components → Client Portal, Pharmacy Portal, Medical Provider Portal, Member Portal

### Phase 5 — Adjudication Rebuild (Modules 6-10, 17-19, 22)
**4 sessions, 8-10 weeks, 4 waves**
Wave A: Plan Design (6), Program Config (17), Rebate (22), EBV/EBI/RTBC (19)
Wave B: Rules Engine (7), Prior Auth (10)
Wave C: Adjudication Engine (8), Testing Simulator (18)
Wave D: Switch Connectivity (9), end-to-end testing, shadow mode

---

## TEAM: 41 MEMBERS

12 Core (every module) + 15 Specialists (when relevant) + 7 Situational + 7 Build Agents

Full roster in separate Team Roster document. Updated to include #41 Medicare Part D Specialist (dormant until Module 24).

---

## LAUNCH — WHAT TO DO RIGHT NOW

### Day 1
1. Upgrade to Claude Max 20x at claude.ai ($200/month)
2. Enable "Extra usage" in Settings → Usage (cap at $300/month)
3. Install Node.js 22 LTS from nodejs.org on MacBook
4. Open Terminal: `npm install -g @anthropic-ai/claude-code`
5. Run `claude` — log in with Anthropic account
6. Install Superpowers: `/plugin marketplace add obra/superpowers-marketplace` then `/plugin install superpowers@superpowers-marketplace`
7. Create GitHub private repo `infinityrx-platform` (empty, no files)

### Day 1-2: Initialize Monorepo
```bash
mkdir ~/infinityrx-platform
cd ~/infinityrx-platform
git init
claude
```

Tell Claude Code:
```
Set up the InfinityRx platform monorepo with the complete folder structure 
from the blueprint. Create all directories, all CLAUDE.md files, docker-compose.yml,
.env.example, .gitignore, and placeholder agent skill files. Follow the structure 
exactly as specified in the blueprint.
```

Then:
```
git add -A
git commit -m "Initial monorepo structure"
git remote add origin https://github.com/YOUR_USERNAME/infinityrx-platform.git
git push -u origin main
```

### Day 2-3: Populate Skill Files and Rules
Tell Claude Code to populate each of the 41 agent skill files and 5 rules files using the Team Roster and Blueprint as source material.

### Day 3: Move Existing Code to Reference
```
Copy PaySync V1 spec → docs/reference/ifx-paysync-v1-config.md
Copy PaySync V2 spec → docs/reference/ifx-paysync-v2-spec.md
Copy ReclaimRx spec → docs/reference/ifx-reclaimrx-config.md
Copy existing PaySync code → modules/billing/src/legacy/ (for assessment)
Copy existing ReclaimRx code → modules/reclaimrx/src/legacy/ (for assessment)
```

### Day 3-4: Write First PRD
In this Claude chat or a dedicated project, we write `docs/prd/prd-core-platform.md` together. This is the first thing the build agents use.

### Day 4: Start Phase 1
Open 4 Terminal tabs. Each runs Claude Code with `--worktree`:
```
Tab 1: claude --worktree session-1   → "Build Core Platform: infrastructure + DB framework"
Tab 2: claude --worktree session-2   → "Build Core Platform: auth + API gateway"
Tab 3: claude --worktree session-3   → "Build Core Platform: event bus + audit + notifications"
Tab 4: claude --worktree session-4   → "Build Core Platform: job scheduler + file manager + CI/CD"
```

### During Phase 1: Write Phase 2 PRDs
While Phase 1 builds, we write PRDs for:
- `prd-billing.md` (the generic billing engine — NOT PaySync-specific)
- `prd-payment-processing.md`
- `prd-reclaimrx.md` (generic FWA for all client types)
- `prd-reporting.md`
- `prd-ai-nlp.md`
- `prd-dataiq.md`

### Phase 1 Complete → Move to Dell
1. Dell: PowerShell Admin → `wsl --install`
2. Ubuntu tab → tell Claude Code to set up build server (tmux, Docker, Tailscale, Python, Node)
3. Clone repo from GitHub
4. Install Tailscale on MacBook too
5. SSH from MacBook to Dell via Tailscale
6. Continue build on Dell

### Phase 2 and Beyond
Launch 4 sessions per phase. PRDs written one phase ahead. Gates auto-pass at 100%. You intervene only on failures.

---

## WHAT SUCCESS LOOKS LIKE

When this platform is complete:
- A new manufacturer client onboards by filling out a BRD → uploading config → testing → go live. No code changes.
- A health plan client onboards by configuring their plan hierarchy, formulary, network, and rules. Same platform, different configuration.
- A TPA client plugs in via API. Same adjudication engine, their data isolated by tenant.
- ConnectiveRx becomes a client — their brand on the portals, InfinityRx invisible, everything white-labeled.
- 340B auditing is a detection profile, not a separate product.
- Adding a new rule type is dragging it into the visual builder, not writing code.
- Asking "how many claims did Pharmacy X submit for NDC Y last quarter?" is typing that question in plain English.
- Everything is documented, SOPs on every screen, API specs auto-generated, configurable, scalable to 300M+ claims/year.
