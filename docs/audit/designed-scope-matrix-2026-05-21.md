# Designed Portal Scope Matrix — 2026-05-21

**Purpose:** Extraction of operator-portal-facing scope from PRDs, per module.  
**Sources:** `docs/prd/prd-operator-portal.md`, `InfinityRx_Blueprint_v2_FINAL.md`, all per-module PRDs, and four `packages/modules/*/module.config.ts` files.  
**Method:** READ-ONLY audit. No code was modified. This is the "designed" column for a gap matrix; a separate agent inventories what is actually wired.

---

## 0. Operator Portal — Top-Level Shell (prd-operator-portal.md)

Designed portal capabilities that span all modules:

- **Sidebar navigation** with role-based visibility (hidden, not grayed, for unauthorized sections)
- **Four dashboard presets:** Billing Operations, FWA Investigation, Executive Overview, System Admin
- **Customizable widget grid:** drag-and-drop reorder, resize, add/remove, save per user, reset to preset (§6.2)
- **Activity feed** — real-time SSE timeline of all operator actions, filterable by module/severity/user/time (§6.3)
- **Command palette** (`Cmd+K`) — search across pages, actions, record IDs, client/pharmacy/drug names (§11)
- **Notification center** — in-app bell, per-user preferences for in-app / email / SMS per event type (§10)
- **Two-person approval flows** for operations exceeding configurable dollar thresholds (§8.1)
- **30-second undo/rollback** timed toast on billing cycle approval, claim status change, bulk actions (§8.2)
- **Dollar amount confirmation** — amounts shown in large font with verbal description on every financial operation (§8.3)
- **Audit trail viewer** on every financial/PHI page: version diff, who/when/what, export to PDF (§19)
- **Universal wizard framework** — step sidebar, auto-save on every step, draft persistence, back navigation (§7.1)
- **TanStack data tables** — virtual scroll 100K+ rows, per-column filter, bulk-select, density toggle, fixed columns (§9.1)
- **Bulk actions floating bar** — approve/reject/export selected rows, partial failure reporting (§9.2)
- **Export menu** on every table — CSV, Excel, PDF (IFX letterhead), clipboard, 24-hour share link (§9.3)
- **Mobile-responsive approval flows** with WebAuthn biometric re-auth (§15)
- **First-login onboarding checklist** — MFA setup, dashboard layout choice, billing tutorial, test cycle (§13.1)
- **Contextual `ⓘ` tooltips** on every complex field with example values and documentation link (§13.2)
- **"Coming Soon" cards** for Phase 5 modules: Plan Design, Adjudication, Prior Auth, Switch, Rebate (§4.2)
- **Concurrent editing conflict resolution** — optimistic locking, side-by-side diff, pessimistic lock on critical records (§14)
- **Keyboard shortcuts** — full overlay (`?` key), `G+D/B/R/P` navigation, `Cmd+A/E`, `↑↓ Enter Space` table navigation (§12)
- **WCAG 2.2 AA accessibility** — full keyboard nav, ARIA, reduced motion mode (§16)
- **Dark mode** — first-class, toggled in user settings, system preference auto-detected (§3)

**Module.config.ts registered surface kinds:** `["server", "client"]` (paysync, prescriber-directory); reclaimrx and directories registered as `as const` without explicit surfaceKinds (defaults to SD-4 shell manifest tooling).

---

## 1. Billing (Module 11) — `prd-billing.md`

### Operator Portal Screens / Capabilities

- **Billing cycle wizard** (6-step): Upload → Map → Validate → Preview → Approve → Generate & Transmit (§7.2 of portal PRD; §5.1–5.2 of billing PRD)
  - **[UPLOAD]** Step 1: drag-and-drop zone + file picker; accepts CSV, Excel, pipe-delimited; configurable per client (portal PRD §7.2)
  - Step 2: field mapping UI — drag source column to target, auto-map with fuzzy match, save mapping template, skip if template exists
  - Step 3: validation results — row-by-row error list, "Fix and re-validate" or "Proceed with valid records only"; **download error records as CSV**
  - Step 4: preview — total claims/dollars, comparison to last cycle, anomaly flags (>25% deviation), sample 20 claims, financial preview (AP/AR/fees/journal entries)
  - Step 5: approval — second-person approval gate if amount > threshold; "Confirm and Generate" button
  - Step 6: generate & transmit — progress per output (SaaSant, 835, NACHA), download links, "Transmit to [bank]" with final confirmation
- **Claims review table** — TanStack, virtual scroll, filters (client, program, route, status, DOS), bulk actions (approve/reject/flag), export
- **Invoice management** — list, detail, download PDF, status tracking (draft → approved → sent → paid/overdue)
- **AP records list** — filterable by entity/status; AP detail view; summary by entity/status
- **Payment batch list** — generate, validate, approve, submit to vendor, void; payments in batch drill-down
- **835 remittance viewer** — inline viewer per pay-to per batch
- **NACHA file management** — generate, preview, transmit, track acknowledgment; positive pay file download
- **AR aging report** — configurable aging buckets; open dispute workflow; write-off workflow (admin)
- **Settlement screen** — **[UPLOAD]** upload bank settlement file, auto-match, unmatched flagged for manual resolution (billing PRD §5.3)
- **Journal query** — filter by date/client/program/category; period summary; accounting export trigger
- **Program financial monitoring dashboard** — budget remaining gauge, daily spend trend (90 days), burn rate vs 30-day avg, projected depletion date, alert acknowledgment (billing PRD §5.7)
- **Period close workflow** — verify settled batches/invoices, export journal, close flag (billing PRD §5.12)
- **Void/correction workflows** — void payment batch (pre-settlement), void invoice (pre-payment), correct invoice (post-payment credit memo) (billing PRD §5.11)
- **Routing rules management** — list, create, update, test against sample claims (API: `POST /routing-rules/test`)
- **Fee configuration** — list fee configs, create/update (8 calculation types)
- **Funding/prefund** — view ledger, record deposit, view burn rate projection (API: `/funding/{id}/projection`)
- **Vendor/bank/SFTP/accounting config screens** — CRUD payment vendors, bank accounts, accounting integration, SFTP configs, test connection
- **AP/AR two-person approval flow** — preparer → approver notification, MFA re-verification for high-value (portal PRD §8.1)
- **Carryover management** — view open carryovers; inbox card: `carryover_open`

**paysync module.config.ts routes (registered):**
`/admin/paysync`, `/admin/paysync/uploads`, `/admin/paysync/cycles`, `/admin/paysync/batches`, `/admin/paysync/carryovers`, `/admin/paysync/invoices`, `/admin/paysync/payment-runs`, `/admin/paysync/files`, `/admin/paysync/settlements`, `/admin/paysync/reconcile`, `/admin/paysync/journal`, `/admin/paysync/reports`, `/admin/paysync/setup`

**Inbox item kinds registered in paysync module.config.ts:**
`upload_pending_review`, `upload_validated_awaiting_batching`, `cycle_pending_close`, `cycle_close_review`, `batch_drafted`, `ar_invoice_draft`, `ap_payment_run_held`, `banking_discrepancy`, `reconciliation_pending`, `carryover_open`, `journal_periodic_review`

---

## 2. Payment Processing (Module 12) — `prd-payment-processing.md`

### Operator Portal Screens / Capabilities

- **Vendor adapter management** — list vendors, create/update adapter, test connection, health history (API: `/vendors/{id}/test`, `/vendors/{id}/health`)
- **Submission list** — filterable; submission detail with vendor response; retry failed submission button
- **Settlement tracking** — pending settlements list; **[UPLOAD]** upload bank settlement file (file-based settlement method); manual settlement button per individual payment (API: `POST /settlements/upload`)
- **ACH returns list** — browse returns by code; manual return entry; ACH return code reference lookup
- **Payee enrollment status** — list enrollments per vendor; initiate enrollment with vendor; unenrolled pharmacies report (conversion opportunity)
- **Payment reconciliation dashboard** — matched / discrepancies / unmatched view, drill-down to batch details, age tracking for outstanding payments, export to Excel (billing PRD §3.11)
- **Vendor health dashboard** — real-time status (healthy/degraded/down), response time tracking, error rate, failover chain status
- **Payment processing dashboard** — volumes, settlement rates, vendor health comparison (API: `/dashboard/vendor-comparison`)

---

## 3. ReclaimRx (Module 16) — `prd-reclaimrx.md`

### Operator Portal Screens / Capabilities

- **FWA flags dashboard** — severity breakdown (critical/high/medium/low), trend chart, top flagged pharmacies/prescribers (portal PRD §8 Build Phase 3)
- **Investigation queue** — kanban board: new → assigned → evidence → demand → resolved (portal PRD §7.5; reclaimrx PRD §7.1)
- **Investigation detail page** — flag evidence, AI-generated anomaly narrative, activity timeline, assigned investigator
- **Investigation wizard** (5-step guided workflow):
  1. Review flag details (what detected, why unusual, evidence)
  2. Assign to investigator
  3. Evidence collection checklist (prescription copies, signature logs, inventory)
  4. Demand letter generation (AI/NLP drafts, human reviews)
  5. Resolution (recovery amount, corrective action plan, case closure)
- **Recovery tracking table** — amounts by status (estimated / demanded / agreed / collected / written-off) with confidence tiers and methodology tags
- **Entity profiles** — pharmacy profile detail (risk score, behavioral metrics, NDC concentration, peer group comparison); prescriber profile; member profile
- **Pharmacy/prescriber risk-ranked list** — sortable by composite risk score, flag count, confirmed fraud count
- **Accumulator detection list** — member-level accumulator/maximizer detection results, financial impact summary (API: `/accumulator/impact`)
- **Known accumulator/maximizer plan database** view
- **Payment holds** — place/release hold on entity, list active holds (API: `/holds`)
- **Tipline** — submit and review anonymous tips; dismiss or convert to investigation (API: `/tips`)
- **Detection rules management** — list system + tenant rules, enable/disable, override parameters; create custom rules; assign detection profiles to tenant
- **ML model management** — list models, performance metrics, trigger retraining, view recent predictions
- **Graph/network intelligence** — list suspicious communities, entity relationship map, visual graph for investigation UI (API: `/graph/communities`, `/graph/visualization/{id}`)
- **Regulatory reports** — generate from investigation, list submitted reports, track deadlines
- **FWA summary reports** — pharmacy scorecard, recovery report, accumulator impact, 340B compliance, trend analysis, rule effectiveness
- **Watchlist** — list watchlisted entities, acknowledge entries, predictive risk scores

**reclaimrx module.config.ts routes (registered):**
`/reclaimrx`, `/reclaimrx/dashboard`, `/reclaimrx/investigations`, `/reclaimrx/investigations/[id]`, `/reclaimrx/holds`, `/reclaimrx/fraud-rings`, `/reclaimrx/fraud-rings/[id]`, `/reclaimrx/graph-runs`, `/reclaimrx/thresholds`, `/reclaimrx/accumulator-anomalies`

---

## 4. Member Management (Module 5) — `prd-member-management.md`

### Operator Portal Screens / Capabilities

- **Member search** — by member ID (exact), name + DOB (fuzzy), SSN (encrypted, PHI-gated), BIN/PCN/Group (portal PRD §8 Build Phase 4)
- **Member detail page** — demographics (PHI-masked per role), coverage periods, accumulator balances, COB records, claims history
- **Enrollment file upload wizard** (portal PRD §8 Build Phase 4):
  - **[UPLOAD]** Upload enrollment file — 834 EDI, CSV, or Excel (member-management PRD §3.1, API: `POST /enrollment/upload`)
  - Preview: first 20 records + validation summary before processing
  - Process with operator confirmation
  - Results: added/updated/terminated/errors summary; **download error records as file with error descriptions**
- **Enrollment file history** — list all processed files, processing status, result counts
- **Manual member creation** — create individual member via form
- **Member demographics edit** — update fields with audit trail
- **Member termination** — terminate with reason code (standardized set)
- **Accumulator viewer** — current balances per accumulator type; accumulator transaction ledger (full history); manual adjustment (admin-only)
- **Benefit year reset trigger** (admin/scheduled)
- **COB management** — add/update/remove coordination-of-benefits records per member
- **Coverage periods** — current + historical, add/update coverage period
- **Eligibility check tool** — query eligibility by member ID + BIN/PCN/Group + DOS; view eligibility check log
- **Member merge workflow** — select primary + duplicate, side-by-side comparison, confirm direction
- **Group management** — list groups, create/update, view members in group
- **ID card data view** — BIN, PCN, Group, Member ID per member
- **Enrollment statistics** — active member count by group and plan

---

## 5. Reporting (Module 15) — `prd-reporting.md`

### Operator Portal Screens / Capabilities

- **Report library** — browse by category (claims, billing AP/AR, financial, FWA, utilization, member, pharmacy, prescriber, program, regulatory, actuarial, quality), search, favorites
- **Report generation wizard** — select template → set parameters → preview → schedule/deliver
- **Report builder (drag-and-drop)** — select data source, dimensions, measures, filters; save for reuse (power users)
- **Scheduled report management** — create, edit, pause/resume, view history, configure delivery (email/SFTP/portal/webhook)
- **Report viewer** — inline PDF/HTML preview + download; branded template with IFX letterhead
- **Dashboard management** — pre-built role dashboards, user-customized layouts, widget add/remove
- **Saved filter presets** — create, share across tenant
- **Report run history** — execution log, row count, output file download, delivery status
- **Client Reporting API access** — documented REST endpoints for clients to pull reports programmatically
- **Pre-built regulatory reports** — 2026 CAA semiannual transparency reports (net drug spending, rebates, spread pricing) in HHS/DOL/Treasury standard format (blueprint §15)

---

## 6. Drug Database (Module 2) — `prd-drug-database.md`

### Operator Portal Screens / Capabilities

- **NDC lookup** — search by NDC, drug name, GPI, generic name, therapeutic class; detail page with full drug information (portal PRD §8 Build Phase 4)
- **Drug detail page** — pricing (AWP/WAC/NADAC with effective dates), drug interactions (severity levels), therapeutic equivalents/generic equivalents, REMS flag, formulary classification
- **Drug search** — brand name, generic name, NDC, GPI, therapeutic class
- **Price change alerts** — alert when AWP/WAC pricing updates on a tracked drug (portal PRD §8 Build Phase 4)
- **HCPCS-to-NDC crosswalk viewer** — map HCPCS J-codes/Q-codes to NDCs (used by Medical Claims; listed in portal PRD §8 Build Phase 5)
- **MAC management** — create/manage MAC lists per tenant, monitor market pricing changes, pharmacy MAC appeal workflow (blueprint §2)
- **Drug pricing history** — effective-dated pricing per price type (AWP, WAC, NADAC, FUL, MAC)

**directories module.config.ts routes (registered):**
`/directories`, `/directories/drugs`, `/directories/drugs/[ndc]`, `/directories/pricing`, `/directories/ingestion`, `/directories/audit`

---

## 7. Pharmacy Directory (Module 3) — `prd-pharmacy-directory.md`

### Operator Portal Screens / Capabilities

- **Pharmacy search** — by NPI, NABP, name, location, pharmacy type, network (portal PRD §8 Build Phase 4)
- **Pharmacy detail page** — demographics, hours, capabilities, ownership, network memberships, contract terms, credentialing status, performance metrics
- **Network management** — create networks, add/remove pharmacies, set network membership status, configure contract terms per pharmacy per network
- **Credentialing queue** — applications under review; verification checklist (NPI, state license, DEA, OIG/SAM, liability insurance); approve/deny with notes; document receipt tracking
  - **[UPLOAD]** Credentialing applications include document uploads (state license, DEA certificate, liability insurance, W9, accreditation certificate) attached to application (pharmacy-directory PRD §data model: `credentialing_documents`)
- **Network adequacy map** — geographic coverage analysis, gap identification, member-to-pharmacy distance compliance (portal PRD §8 Build Phase 4; pharmacy-dir PRD network adequacy section)
- **Provider agreement management** — generate agreements from templates, send PDF (sign-only), track signature status, countersign, activate on execution (blueprint §3)
- **PSAO management** — master agreements, pharmacy affiliations, PSAO-level reporting, PSAO fee schedules (blueprint §3)
- **Pharmacy performance metrics** — cost, quality, adherence, volume per pharmacy; peer comparison

**directories module.config.ts routes (registered):**
`/directories/pharmacies`, `/directories/pharmacies/[npi]`

---

## 8. Prescriber Directory (Module 4) — `prd-prescriber-directory.md`

### Operator Portal Screens / Capabilities

- **Prescriber search** — by NPI, DEA number, name, specialty, location (portal PRD §8 Build Phase 4)
- **Prescriber detail page** — credentials (DEA status, state license, Medicare/PECOS status), taxonomy/specialty, practice locations, telehealth states
- **Credential monitoring dashboard** — DEA expiry alerts, license status changes, OIG/SAM exclusion flags (portal PRD §8 Build Phase 4)
- **DEA status alerts** — prescribers with expired or revoked DEA numbers (portal PRD §8 Build Phase 4)
- **Organization/group practice directory** — Type 2 NPI lookup (blueprint §4)
- **Prescriber-level restrictions** — view/manage prescriber-specific PA requirements and tier assignments (blueprint §4)

**prescriber-directory module.config.ts routes (registered):**
`/prescribers`, `/prescribers/:npi`, `/prescribers/search`

**directories module.config.ts routes (registered):**
`/directories/prescribers`, `/directories/prescribers/[npi]`

*(Note: two separate module configs exist for prescriber lookups — the older standalone `prescriber-directory` config and the consolidated `directories` config.)*

---

## 9. EDI & Compliance (Module 13) — `prd-edi-compliance.md`

### Operator Portal Screens / Capabilities

- **Trading partner management** — CRUD trading partners, configure transport (AS2/SFTP/direct/API), set test/production mode, supported transaction list (portal PRD §8 Build Phase 5)
- **Transaction file browser** — filter by type (835/837/270/271/834/278/NCPDP Batch), direction (inbound/outbound), status (pending/transmitted/acknowledged/rejected/failed) (portal PRD §8 Build Phase 5)
- **Transaction detail page** — validation results (syntax, segment, code set), transmission status, acknowledgment tracking, processing errors (portal PRD §8 Build Phase 5)
- **Acknowledgment tracking** — TA1 / 999 / 277CA per trading partner
- **Transmission queue** — queued outbound files, pending acknowledgment (portal PRD §8 Build Phase 5)
- **Real-time transaction monitor dashboard** — live transaction volume, error rate, per-partner health (portal PRD §8 Build Phase 5)
- **Certificate expiry alerts** — AS2 certificate expiration warnings (portal PRD §8 Build Phase 5)
- **Control number sequence management** — ISA/GS/ST sequences per trading partner
- **NCPDP Batch** — inbound/outbound pharmacy claim batch browser

---

## 10. Medical Claims (Module 14) — `prd-medical-claims.md`

### Operator Portal Screens / Capabilities

- **Medical drug claim browser** — filter by HCPCS code, provider NPI, member ID, status, DOS (portal PRD §8 Build Phase 5)
- **Claim detail page** — drug mapping (HCPCS → NDC), ASP/WAC pricing, waste/overfill amounts, 340B flag, site-of-care classification, COB (portal PRD §8 Build Phase 5)
- **HCPCS-to-NDC crosswalk viewer** — map procedure codes to drug identity (portal PRD §8 Build Phase 5)
- **Unified drug spend view** — pharmacy benefit + medical benefit side-by-side for same drug/member (portal PRD §8 Build Phase 5)
- **Site-of-care analysis** — distribution across office infusion/hospital outpatient/home infusion/specialty pharmacy (portal PRD §8 Build Phase 5)
- **340B summary** — 340B-flagged medical claims with covered entity detail (portal PRD §8 Build Phase 5)
- **Manual claim entry** — configurable web forms (CMS-1500, UB-04) (blueprint §14)
  - **[UPLOAD]** Dual-OCR document upload — upload paper/PDF claim forms; Azure Document Intelligence + Mistral Document AI parse and extract fields; low-confidence fields flagged for manual review (blueprint §14; medical-claims PRD purpose section)
- **Claim adjudication status** — received → validated → priced → adjudicated → paid/denied/appealed
- **Appeal management** — track appealed claims, documentation attachment

---

## 11. AI/NLP (Module 21) — `prd-ai-nlp.md`

### Operator Portal Screens / Capabilities

- **Document processing monitor** — recent extractions list, confidence scores per field, human review queue for low-confidence outputs (portal PRD §8 Build Phase 5)
- **Prompt template management** — list/edit versioned prompt templates per service type; configure temperature, max tokens, confidence threshold, guardrail patterns (portal PRD §8 Build Phase 5)
- **Chatbot conversation viewer** — review conversational AI interactions per tenant/user (portal PRD §8 Build Phase 5)
- **Model performance dashboard** — accuracy metrics per service type, human review rate, acceptance/modification/rejection rates (portal PRD §8 Build Phase 5)
- **Cost tracking by service type** — input/output tokens, estimated cost per module requesting AI services (portal PRD §8 Build Phase 5)
- **Human review queue** — flagged AI outputs (confidence < threshold) requiring operator review/acceptance/modification/rejection
- **Anomaly narrative viewer** — AI-generated plain English explanations for ReclaimRx flags; human can accept or override
- **Translation service config** — language support configuration per tenant (blueprint §21)

---

## 12. DataIQ (Module 23) — `prd-dataiq.md`

### Operator Portal Screens / Capabilities

- **Real-time metrics dashboard** — live claim volume counter (per minute/hour), live financial tracker (AP/AR dollars), live FWA tracker (portal PRD §8 Build Phase 6)
- **Drug trend dashboards** — spend trending, brand/generic ratio, GLP-1 tracking, specialty spend, biosimilar adoption, price inflation, rebate optimization, top drugs by spend/volume (dataiq PRD §2.2)
- **Network analytics** — pharmacy performance scorecard, network adequacy coverage map, network leakage analysis, cost variation across pharmacies, mail order conversion opportunity (dataiq PRD §2.3)
- **Member analytics** — adherence dashboard (PDC by drug class), high-cost claimant analysis, polypharmacy risk, opioid utilization, new-to-therapy tracking (dataiq PRD §2.4)
- **Financial analytics** — cost driver decomposition, PMPM trending, spread analysis, client profitability, 12-month forecast model (dataiq PRD §2.5)
- **Data quality score dashboard** — 0-100 daily score per tenant, component breakdowns, trend, benchmark status (green/yellow/red) (portal PRD §8 Build Phase 6; dataiq PRD §2.6)
- **Anomaly detection alerts** — SPC-triggered alerts when metrics deviate >2σ from moving average (dataiq PRD §2.1)
- **Benchmarking** — internal/historical/target/industry comparisons; green/yellow/red visual status per metric (dataiq PRD §2.7)
- **Natural language query interface** — type question in English, receive analytics response (portal PRD §8 Build Phase 6)
- **Pivot table explorer** — self-service dimension/measure selection, cohort analysis, saved explorations (portal PRD §8 Build Phase 6; dataiq PRD §2.8)
- **What-if scenario modeling** — model impact of formulary/network/benefit changes on costs (dataiq PRD §2.5)

---

## 13. Plan Design (Module 6) — `prd-plan-design.md` — Phase 5 (Coming Soon)

### Operator Portal Screens / Capabilities

- **Plan hierarchy configuration** — Organization → Group → Plan → SubGroup, effective-dated, inheritable
- **Benefit configuration wizard** — copay structure, deductible, OOP max, coinsurance, benefit phases, day supply rules, annual/lifetime maximums
- **Formulary management** — create formularies, tier assignment per NDC/GPI, PA/ST/QL flags, specialty designation, versioning, rollback
- **Formulary optimization tools** — model cost impact of tier changes, P&T committee support (agenda, monographs, impact analyses, vote tracking), formulary change notifications
- **Network assignment** — assign networks to plans, tiered networks, specialty pharmacy tiers
- **Pricing model selection** — AWP discount / MAC / cost-plus / NADAC / net-cost / etc. per plan/network tier
- **Biosimilar formulary tools** — reference product → biosimilar mapping, auto-substitution config, state substitution law tracking
- **GLP-1 indication-based coverage configuration**
- **Network adequacy analysis** — coverage by county/ZIP, gap identification, network change impact modeling
- **Plan cloning/templating** — clone with all settings, pre-configured templates per program type
- **[UPLOAD]** Bulk plan import/export — upload CSV/Excel to create/update hundreds of plans (plan-design PRD §8)
- **Benefit design what-if simulator** — model financial impact on plan costs and member OOP before committing; save/compare scenarios; export for P&T or client review
- **IRA negotiated drug tracking** — flag drugs with CMS Maximum Fair Prices, apply MFP for Part D members

---

## 14. Program Configuration (Module 17) — `prd-program-config.md` — Phase 5 (Coming Soon)

### Operator Portal Screens / Capabilities

- **BRD template builder** — drag-and-drop form builder, pre-built templates per program type, conditional logic, versioned (program-config PRD §2)
- **BRD review queue** — submitted BRDs, AI-highlighted potential issues, approve/reject/request-changes per section; client notification (program-config PRD §2)
- **Auto-configuration diff view** — before promoting BRD config, operator sees exactly what will change (new plans, rules, formulary entries); one-click promote or item-by-item approval; rollback (program-config PRD §2)
- **Program launch wizard** (8-step) — program basics, drug config, BIN/PCN assignment, pricing rules, eligibility criteria, pharmacy network, reporting, review & activate; save/resume draft (program-config PRD §3)
  - **[UPLOAD]** Step 2 drug configuration includes bulk NDC/GPI import (program-config PRD §3 "bulk import")
- **Manufacturer self-service program builder** — guided wizard with AI recommendations for copay offer design and accumulator strategy; submit for IFX review (program-config PRD §4)
- **Contract management** — CRUD contracts, SLA tracking, BFSF documentation, spend cap config, amendments with effective dates, renewal alerts (program-config PRD §5)
- **Client onboarding dashboard** — all programs in onboarding with status per step (12 configurable steps), SLA tracking, bottleneck identification (program-config PRD §6)
- **Onboarding workflow status** — per-program step tracker from signed contract through go-live (program-config PRD §6)
- **[UPLOAD]** BRD submission: client attaches supporting documents (formulary, contract, drug lists) during BRD portal completion (program-config PRD §2 "Client-Facing BRD Portal")

---

## 15. Rebate Management (Module 22) — `prd-rebate-management.md` — Phase 5 (Coming Soon)

### Operator Portal Screens / Capabilities

- **Rebate contract management** — lifecycle: draft → negotiation → active → amendment → renewal → termination; NDC-11 level terms; side-by-side contract comparison (rebate PRD §3)
- **Rebate calculation engine results** — view calculated rebates per period per contract; net vs expected reconciliation
- **Rebate invoicing** — generate invoices to manufacturers, track payment against invoice
- **Reconciliation** — expected vs received vs passed-through to plan; dollar-for-dollar audit trail
- **Guaranteed spend cap tracking** — real-time actual vs ceiling, refund owed vs savings retained, trending alert (rebate PRD §5)
- **Manufacturer GTN waterfall dashboard** — gross-to-net per drug per program with drill-down (WAC → net price) (rebate PRD §6)
- **Program performance benchmarking** — enrollment rate, first fill, PDC, abandonment, avg copay, GTN ratio vs industry avg (rebate PRD §7)
- **Copay program analytics** — program design analytics, fraud control results, accumulator/maximizer impact, executive optimization modeling (rebate PRD §8)
- **Fiduciary compliance dashboard** — rebates received vs passed-through, spread pricing transparency, affiliated pharmacy utilization, BFSF documentation completeness, CAA 2026 reporting status (rebate PRD §9)
- **CAA 2026 transparency reports** — semiannual reports for large employers (rebate PRD §2)
- **One-click audit data export** — all rebate contract terms, payments, pass-throughs, BFSF invoices for external auditors (rebate PRD §2)

---

## 16. Prior Authorization (Module 10) — `prd-prior-authorization.md` — Phase 5 (Coming Soon)

### Operator Portal Screens / Capabilities

- **Reviewer queue** — PA requests prioritized by urgency (24-hour fills at top), filterable by drug type/workload (PA PRD §5)
- **PA detail view** — clinical criteria evaluation results, auto-approve status, member/drug/plan info
- **PA decision workflow** — approve / deny / pend / request more info; configurable duration; quantity limits; grandfathering config
- **Multi-level appeal management** — clinical reviewer → medical director → external review; regulatory deadline tracking per state and plan type; expedited (24-72 hr) appeal; documentation upload
  - **[UPLOAD]** Appeal documentation submission — upload supporting clinical documentation (PA PRD §5 "appeal documentation submission")
- **Letter generation** — branded PDF: approval, denial with reason/criteria/appeal rights, appeal decision, request for info (PA PRD §5)
- **PA criteria management** — CRUD configurable criteria sets per drug/class/plan; GLP-1 PA templates; versioned and effective-dated (PA PRD §3)
- **PA reporting** — approval rates, turnaround times, appeal outcomes (blueprint §10)
- **FRM digital tools dashboard** — office-level pending PAs, BVs, copay enrollment opportunities per practice; one-click PA initiation; FRM activity logging (PA PRD §6)
- **REMS compliance tracking** — FDA REMS requirements per drug, certifications, monitoring (PA PRD §6)

---

## 17. Adjudication Engine (Module 8) — `prd-adjudication-engine.md` — Phase 5 (Coming Soon)

### Operator Portal Screens / Capabilities

- **Claim rule override dashboard** — active overrides across all members; filter by rule type/operator/date/expiration; expiring-soon alerts; one-click revoke; bulk revoke (adjudication PRD §6)
- **Override creation panel** — triggered when operator reviews a rejected claim; select reason, duration, scope; supervisor approval flow for high-risk rules (adjudication PRD §6)
- **Override history per member** — every override with status (active/expired/revoked), linked to original rejected claim and subsequent paid claims
- **Override reporting** — volume by rule type, by operator, override-to-paid conversion rate, financial impact; flags if a rule gets overridden >X% of the time (adjudication PRD §6)
- **Claim trace viewer** — step-by-step visual trace of every rule that fired (input values, output values, execution time per rule); "Reasons for Adjudication" plain-English explainer (adjudication PRD §5)
- **ML training API** — operator-facing controls for adjudication ML model training (from CLAUDE.md status: "ML training API")

---

## 18. Rules Engine (Module 7) — `prd-rules-engine.md` — Phase 5 (Coming Soon)

### Operator Portal Screens / Capabilities

- **Visual drag-and-drop pipeline builder** — canvas with rules as connected nodes, branching logic, rule groups, live preview (sample claim runs through in real-time), version comparison (side-by-side diff), copy pipeline between plans (rules PRD §4)
- **Rule library browser** — all 19+ rule types organized by category (pricing, coverage, authorization, specialty)
- **Rule detail/configuration** — configure parameters inline on canvas
- **Natural language rule creation** — describe rule in English, AI parses to definition, user confirms (rules PRD §4)
- **[UPLOAD]** BRD config file upload — upload completed Business Rules Document, validate against system rules, preview what will be created, apply bulk in one operation (rules PRD §4)
- **Rule versioning** — every change creates version with effective date; rollback to any version; audit trail; approval workflow for material changes (rules PRD §5)
- **Rule testing** — test any rule against sample claims before activating (rules PRD §5)
- **MAC appeal workflow** — pharmacy MAC appeal management per drug (blueprint §7)

---

## 19. Switch Connectivity (Module 9) — `prd-switch-connectivity.md` — Phase 5 (Coming Soon)

### Operator Portal Screens / Capabilities

- **Switch management** — CRUD switch adapters (RelayHealth, Change Healthcare, RedSail), test connection, configure heartbeat interval and timeout
- **Switch health dashboard** — real-time status (latency, throughput, error rate, uptime) per switch; failover chain status
- **BIN/PCN routing table** — configure per tenant: BIN/PCN → plan/program mapping; wildcard support; priority ordering; pass-through routing
- **Switch certification** — import switch certification test scripts, run certification suite in test mode, generate evidence package (request/response pairs, pass/fail), re-certification scheduling and tracking (switch PRD §7)
- **Transaction log** — encrypted transaction log viewer (switch PRD §data models: `switch_transaction_log`)
- **NCPDP SCRIPT version config** — configure per switch/pharmacy which SCRIPT version to use (2017071 vs 2023011) (switch PRD §4)

---

## 20. Core Platform (Module 1) — `prd-core-platform.md`

### Operator Portal Screens / Capabilities (Admin Section)

- **User management** — CRUD users, role assignment, MFA enrollment status, session viewer; lock/unlock accounts (portal PRD §8 Build Phase 6)
- **Tenant settings** — configuration, feature flags, white-label branding, security settings (MFA required, IP allowlist, session timeout) (portal PRD §8 Build Phase 6)
- **Audit log viewer** — searchable, filterable (user, date, action, module), exportable, hash chain verification display (portal PRD §8 Build Phase 6; core PRD HIPAA)
- **System health dashboard** — all services green/yellow/red, DLQ depth, event bus health (RabbitMQ), Redis health, database health (portal PRD §8 Build Phase 6; portal PRD §6.1 "System Admin" preset)
- **API key management** — create/revoke service and client API keys, view usage, set permissions and IP restrictions
- **Role management** — view/configure RBAC roles and permissions per tenant
- **Government exclusion screening** — OIG/SAM results viewer, alert acknowledgment; screening schedule config (blueprint §1; core PRD)
- **Client onboarding wizard** (7-step): client details → programs → banking → fees → outputs → test → activate (portal PRD §7.4)
- **Notification preferences** — per-user per-notification-type configuration (portal PRD §10.2)
- **Session management** — view active sessions per user; force logout; concurrent session limit enforcement
- **Help desk unified view** — cross-module claim/member/pharmacy lookup for support operators (blueprint §1)
- **DLQ management** — dead letter queue depth viewer, message inspection, requeue/discard (security rules: "Mount DLQ router on production app")

---

## 21. Part D / PDE Compliance (Module 24) — `prd-part-d-pde.md` — Phase 5 Future

### Operator Portal Screens / Capabilities

- **PDE validation dashboard** — count of PDEs pending/validated/submitted/accepted/rejected; drill-down to rejections by error code with resolution guidance (part-d PRD §3)
- **PDE submission tracking** — batch-level tracking; CMS acceptance/rejection per individual PDE; resubmit corrected PDEs
- **IRA negotiated drug tracking dashboard** — all negotiated drugs with effective dates, savings per drug per period; pipeline for future negotiation rounds (part-d PRD §5)
- **Annual reconciliation** — compare InfinityRx claims data against CMS records; resolve discrepancies (part-d PRD §9)
- **DIR reporting** — generate DIR report, submit via HPMS, POS DIR amounts per claim (part-d PRD §8)
- **Coverage gap discount tracking** — manufacturer discount percentages per phase per year (part-d PRD §4)
- **LIS/SPAP eligibility management** — LIS level tracking, SPAP coordination (part-d PRD §7)
- **Audit readiness viewer** — PDE source claim linkage, coverage determination records, formulary administration records (part-d PRD §10)

---

## 22. EBV/EBI/RTBC (Module 19) — `prd-ebv-ebi-rtbc.md` — Phase 5 Future

### Operator Portal Screens / Capabilities

- **EBV verification log** — eligibility check history with response details (EBV PRD §2)
- **Hub services integration config** — inbound/outbound API configuration for external hub partners (ConnectiveRx, Mercalis, etc.) (EBV PRD §6)
- **RTPB (Real-Time Prescription Benefit Check) config** — configure Surescripts RTPB network integration, formulary publishing (EBV PRD §4)
- **Usage tracking and cost management** — paid verification service inquiry counts and costs (blueprint §19)
- **Verification vendor routing config** — configure which BV/BI vendor routes per plan/program (blueprint §19)

---

## 23. MTM / Clinical Programs (Module 25) — `prd-mtm-clinical.md` — Phase 5 Future

### Operator Portal Screens / Capabilities

- **Pharmacist workbench** — members flagged for intervention prioritized by risk score/ROI; member context (claims history, adherence, lab data, social determinants); intervention workflow with prescriber approval tracking; templates for common interventions (MTM PRD §4)
- **CMR tracking dashboard** — eligible members, scheduled CMRs, completion rates vs CMS benchmarks, compensation queue (MTM PRD §2)
- **Risk stratification view** — member risk scores, intervention targeting by ROI, cohort analysis (MTM PRD §3)
- **Adherence dashboard** — PDC by drug class across population, CMS star rating drug class tracking (MTM PRD §5)
- **Peer-to-peer prescriber collaboration** — structured communication tracking, acceptance/rejection rates per prescriber (MTM PRD §4)
- **Guaranteed savings tracking** — intervention outcomes against savings guarantees (MTM PRD §3)

---

## 24. Directories Module (Consolidated) — `packages/modules/directories/module.config.ts`

The `directories` module.config.ts consolidates pharmacy, prescriber, drug, HCPCS/ICD-10 codes, pricing, exclusions, and data ingestion into a single portal surface. Specific routes beyond what pharmacy/prescriber/drug individual PRDs describe:

- `/directories/codes/hcpcs` — HCPCS code browser (supports Medical Claims crosswalk)
- `/directories/codes/icd10` — ICD-10 code browser
- `/directories/exclusions` — OIG/SAM exclusion list viewer (cross-directory, all entity types)
- `/directories/ingestion` — **[UPLOAD]** data ingestion status and trigger UI for NCPDP, NPPES, FDA NDC, CMS NADAC feeds; likely includes manual data import for reference datasets (module.config.ts `integrations: ["shared-ingestion-api"]`)
- `/directories/audit` — audit trail for all directory data changes

---

## UPLOAD_FLOWS_DESIGNED

The following modules' PRDs specify a data-upload or file-ingest UI in the operator portal:

- **Billing (Module 11):** Claims file upload (drag-and-drop, CSV/Excel/pipe-delimited, configurable per client) — portal PRD §7.2 Billing Cycle Wizard Step 1; bank settlement file upload for AP settlement matching — billing PRD §5.3 (`POST /settlement/upload`)
- **Payment Processing (Module 12):** Bank settlement file upload (file-based settlement method for matching individual payments) — payment PRD §3.2 (`POST /settlements/upload`)
- **Member Management (Module 5):** Enrollment file upload wizard — 834 EDI, CSV, or Excel; preview before processing; error record download — member PRD §3.1, API `POST /enrollment/upload`
- **Medical Claims (Module 14):** Paper/PDF claim form upload for dual-OCR parsing (Azure Document Intelligence + Mistral) — blueprint §14; medical-claims PRD purpose section
- **Plan Design (Module 6):** Bulk plan import via CSV/Excel to create/update hundreds of plans at once — plan-design PRD §8 ("Bulk import/export")
- **Program Configuration (Module 17):** BRD submission includes client document attachments (formulary, contract, drug lists) — program-config PRD §2; bulk NDC/GPI import in Program Launch Wizard Step 2; Rules Engine BRD config file upload — rules PRD §4
- **Prior Authorization (Module 10):** Appeal documentation upload (supporting clinical documentation) — PA PRD §5
- **Directories (module.config.ts):** Data ingestion UI (`/directories/ingestion`) for reference data feeds (NCPDP, NPPES, FDA NDC, NADAC); `integrations: ["shared-ingestion-api"]` declared in module.config.ts
- **Pharmacy Directory (Module 3):** Credentialing document uploads (state license, DEA certificate, liability insurance, W9, accreditation certificate) attached to credentialing applications — pharmacy-dir PRD data model `credentialing_documents`

---

## PAYSYNC_VS_BILLING_VS_ACCOUNTING

The Blueprint (§ Note under Module 11 folder name, and §GOVERNING RULES #5) explicitly defines the boundary: **PaySync is IFX's internal product name** for their tenant configuration of the generic Billing module — it is NOT a separate module. The codebase folder is `modules/billing/`, not `modules/paysync/`. The PaySync V1/V2 spec lives in `docs/reference/` as a client-specific example. The **Billing module (Module 11)** is the generic engine containing AP, AR, claims ingestion, the financial journal, and program financial monitoring for any client type.

**Payment Processing (Module 12)** is a distinct module strictly responsible for vendor-adapter execution — it takes payment instructions from Billing, formats them for Echo/Zelis/NACHA/check, submits, and reports settlement back. It holds no billing logic, no invoicing, and no journal. Billing decides who gets paid; Payment Processing does the paying.

**Accounting** is not a separate module — it is a subsystem of Billing (Module 11). The financial journal (`billing.journal_entries`) is the source of truth, and accounting-system exports (QuickBooks, NetSuite, Xero, Sage, generic GL) are generated from journal entries via `billing.accounting_configs`. The `paysync` module.config.ts surface in the portal (registered routes `/admin/paysync/*`) is the operator-facing UI layer that bridges both Billing and Payment Processing backends (`requires.backends: ["billing", "payment-processing"]`) under the PaySync brand name. There is no separate "accounting" portal surface — accounting is accessed via the Journal and Reports screens within the PaySync/Billing surface.

---

## REPORT_PATH

`docs/audit/designed-scope-matrix-2026-05-21.md`
