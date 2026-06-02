# Claims/Adjudication Cluster — Depth Re-Audit
**Date:** 2026-05-21  
**Scope:** portal/operator surfaces for claims, adjudication-engine, medical-claims, prior-authorization, rules-engine, program-config, switch-connectivity  
**Method:** Read-only — PRD designed surfaces mapped against portal/operator/app/** files and nav-config.ts  

---

## Navigation Confirmation

`nav-config.ts` is the authoritative sidebar source. Confirmed wired sections in cluster:

| Sidebar Entry | Route Prefix | Wired? |
|---|---|---|
| Claims | /claims | Yes |
| Programs | /programs | Yes |
| Medical Claims | /medical-claims | Yes (via page links, not sidebar — no sidebar entry) |
| Adjudication | — | NO (no sidebar entry, no portal directory) |
| Prior Auth | — | NO (no sidebar entry, no portal directory) |
| Rules Engine | — | NO (no sidebar entry, no portal directory) |
| Switch | — | NO (no sidebar entry, no portal directory) |

Note: Medical Claims has portal pages but is NOT in nav-config.ts; it is linked only via button navigation within the medical-claims landing page itself.

---

## Surface Classification Table

### MODULE: Claims (portal /claims — adjudication-engine BFF)

| Surface | Designed? | Build State | Effort | Note |
|---|---|---|---|---|
| Claims Explorer (list, filters, KPIs) | Yes — PRD §4.2 Phase 5 + adjudication §18 | BUILT_WIRED | — | Full TanStack table, 35 columns, 6 KPI cards, FilterPanel, wired to /billing/v1/claims |
| Claim Detail page (patient/provider/financial info cards, tabs) | Yes — adjudication §18 GET /claims/{id} | BUILT_WIRED | — | Rich InfoCard layout with Reversal, Related, Investigation, Attachments tabs; wired to /billing/v1/claims/{id} |
| Manual Claim Entry (CMS-1500/UB-04 form) | Yes — adjudication §18 POST /claims/manual | SCAFFOLD | M | 4-section form (patient/provider/claim/financial) with attachment upload; no wizard steps, no CMS-1500/UB-04 form layout, no adjudication trace, no draft/resume — flat form only |
| Claim Lookup (by ID/Auth#/Rx#) | Yes — adjudication §18 | BUILT_WIRED | — | Single-record search by 3 field types; wired to /billing/v1/claims/{id} |
| PA Override queue (approve/deny with notes) | Yes — adjudication §6 Override Management UI | SCAFFOLD | L | Table + approve/deny modal exists; missing: multi-level approval workflow, supervisor queue, duration/scope config, override history per member, override rate monitoring, bulk revoke, expiry alerts |
| Claim Trace Viewer (step-by-step adjudication trace) | Yes — adjudication §5 Full Claim Trace | NOT_BUILT | L | No trace viewer component. Detail page has no trace tab. Backend stores claim_trace JSONB but portal has no surface to display it |
| Override Management Dashboard (active overrides, expiry alerts) | Yes — adjudication §6 Override Management UI | NOT_BUILT | M | No /claims/overrides or /admin/overrides page. Only the PA Override queue page exists (different concept) |
| Claim Reprocess trigger | Yes — adjudication §18 POST /claims/reprocess | NOT_BUILT | S | No UI surface |

---

### MODULE: Medical Claims (portal /medical-claims)

| Surface | Designed? | Build State | Effort | Note |
|---|---|---|---|---|
| Medical drug claim browser (HCPCS filter, provider, member, status) | Yes — PRD §20 Phase 5 | BUILT_WIRED | — | Full DataTable wired to medical-claims BFF; status/search filters; row-click to detail |
| Medical claim detail page | Yes — PRD §20 Phase 5 | BUILT_WIRED | — | Full detail with drug mapping, ASP pricing, waste, 340B flag, POS labels, mapping source badge |
| HCPCS→NDC crosswalk viewer | Yes — PRD §20 Phase 5 | BUILT_WIRED | — | Search + upload mutation, confidence score bar, mapping source badge; wired to medical-claims BFF |
| Unified drug spend (pharmacy + medical side-by-side) | Yes — PRD §20 Phase 5 | BUILT_WIRED | — | Member search + bar chart + split spend table; wired to /api/v1/unified-spend |
| Site-of-care analysis | Yes — PRD §20 Phase 5 | BUILT_WIRED | — | POS breakdown bar chart + DataTable; wired to medical-claims BFF |
| 340B summary | Yes — PRD §20 Phase 5 | BUILT_WIRED | — | Server component; KPI cards + interactive claims table; wired to /api/v1/340b/summary |
| Medical Claims sidebar entry | Yes — should be in nav-config | BUILT_UNWIRED | S | Pages exist and work but /medical-claims is absent from nav-config.ts — only reachable via direct URL or button links from within the section |

---

### MODULE: Program Config (portal /programs — program-config backend)

| Surface | Designed? | Build State | Effort | Note |
|---|---|---|---|---|
| Program Overview list (enrollments, spend, GTN, budget) | Yes — PRD §3 Program Launch Wizard | BUILT_WIRED | — | ConfigurableDataTable wired to /api/v1/programs; 11 columns including GTN ratio, budget remaining |
| Program Detail page (enrollment/claims/leakage/budget/configuration tabs) | Yes — PRD §3 | BUILT_WIRED | — | 5 tabs; enrollment table, bar chart; wired to /api/v1/programs/{id}/enrollments |
| Program Budget & Forecast | Yes — PRD §3 step 7 (reporting) | BUILT_WIRED | — | Budget summary table + bar/line charts; wired to /api/v1/programs/budget/summary |
| Program Enrollment dashboard | Yes — PRD §3 | BUILT_WIRED | — | Enrollment analytics + by-program breakdown bar chart; wired |
| Program Config (create new program) | Yes — PRD §3 8-step wizard | SCAFFOLD | L | Flat single-page form (basic info, copay card, financial config, covered drugs). Missing: wizard steps 3-8 (BIN/PCN, pricing rules, eligibility criteria, pharmacy network, reporting, review+activate), draft/resume, non-linear navigation, simulator test step |
| 8-Step Program Launch Wizard | Yes — PRD §3 full wizard | NOT_BUILT | L | /programs/config is a flat form, not a wizard. Steps 3-8 not implemented at all |
| BRD Template Builder (drag-and-drop form builder) | Yes — PRD §2 Template Builder | NOT_BUILT | L | No portal surface. No /programs/brd or similar route |
| BRD Client Portal (client-facing submission flow) | Yes — PRD §2 Client-Facing BRD Portal | NOT_BUILT | L | No portal surface |
| IFX BRD Review Workflow queue | Yes — PRD §2 IFX Review Workflow | NOT_BUILT | M | No portal surface |
| Manufacturer Self-Service Program Builder (10-step) | Yes — PRD §4 | NOT_BUILT | L | No portal surface |
| Contract Management (CRUD, SLAs, amendments, renewal alerts) | Yes — PRD §5 | NOT_BUILT | M | No portal surface |
| Client Onboarding Dashboard (12-step workflow, SLA tracking) | Yes — PRD §6 | NOT_BUILT | M | No portal surface |
| Auto-Configuration Diff View + Promote | Yes — PRD §2 Auto-Configuration | NOT_BUILT | M | No portal surface |

---

### MODULE: Prior Authorization (portal — none)

| Surface | Designed? | Build State | Effort | Note |
|---|---|---|---|---|
| PA Reviewer Queue (prioritized, urgent flag) | Yes — PRD §5 reviewer queue | NOT_BUILT | L | Zero portal directory. Backend module built. No portal route exists |
| PA Detail page (criteria, decision, letter) | Yes — PRD §5 | NOT_BUILT | M | No portal surface |
| Multi-Level Appeal Wizard | Yes — PRD §5 Appeals multi-level | NOT_BUILT | L | No portal surface. This is one of the highest-complexity designed workflows |
| PA Criteria CRUD (per drug/class/plan, versioned) | Yes — PRD §3 Clinical Criteria Engine | NOT_BUILT | M | No portal surface |
| Letter Template Management | Yes — PRD §5 Letters | NOT_BUILT | M | No portal surface |
| ePA Status Monitor (CoverMyMeds, SureScripts, FHIR) | Yes — PRD §4 | NOT_BUILT | M | No portal surface |
| FRM Digital Tools (office dashboard, one-click PA) | Yes — PRD §6 | NOT_BUILT | L | No portal surface |
| GLP-1 Criteria template editor | Yes — PRD §3 | NOT_BUILT | M | No portal surface |
| Note: PA Override queue at /claims/pa-override | Partial overlap | SCAFFOLD | — | Covers inline claim-level approvals only; not a full PA reviewer workflow |

---

### MODULE: Rules Engine (portal — none)

| Surface | Designed? | Build State | Effort | Note |
|---|---|---|---|---|
| Visual Drag-and-Drop Pipeline Builder | Yes — PRD §4 Visual Pipeline Builder | NOT_BUILT | L | Zero portal directory. The highest-complexity UI in the entire cluster |
| Rule Library browser (list rule instances by plan) | Yes — PRD §4 | NOT_BUILT | M | No portal surface |
| Rule instance CRUD (configure parameters) | Yes — PRD §4 | NOT_BUILT | M | No portal surface |
| Pipeline branching + live preview | Yes — PRD §4 | NOT_BUILT | L | No portal surface |
| Version compare (side-by-side diff) | Yes — PRD §5 | NOT_BUILT | M | No portal surface |
| Natural Language Rule Creation | Yes — PRD §4 NL method | NOT_BUILT | M | No portal surface |
| BRD Config File Upload + preview | Yes — PRD §4 BRD method | NOT_BUILT | M | No portal surface |
| Rule Test (sample claim against rule/pipeline) | Yes — PRD §5 | NOT_BUILT | M | No portal surface |
| State Regulatory Compliance viewer | Yes — PRD §5 | NOT_BUILT | M | No portal surface |

---

### MODULE: Adjudication Engine (portal — none; surfaces via /claims BFF only)

| Surface | Designed? | Build State | Effort | Note |
|---|---|---|---|---|
| Claim Trace Viewer | Yes — PRD §5 Full Claim Trace | NOT_BUILT | L | See Claims section above — designed as core adjudication surface |
| Override Rule panel (slide-out from claim trace) | Yes — PRD §6 | NOT_BUILT | M | Requires Claim Trace Viewer first |
| Active Overrides Dashboard | Yes — PRD §6 Override Management UI | NOT_BUILT | M | See Claims section above |
| Real-time throughput/latency metrics dashboard | Yes — PRD §18 GET /claims/stats | NOT_BUILT | M | No admin or ops surface for this |
| Accumulator/Maximizer detection report | Yes — PRD §7 | NOT_BUILT | M | No portal surface |
| Copay fraud flags viewer | Yes — PRD §9 | NOT_BUILT | M | No portal surface (distinct from ReclaimRx investigations) |
| Drug waste alerts dashboard | Yes — PRD §12 | NOT_BUILT | M | No portal surface |
| Pharmacy reimbursement transparency page | Yes — PRD §14 | NOT_BUILT | M | No portal surface |

---

### MODULE: Switch Connectivity (portal — none)

| Surface | Designed? | Build State | Effort | Note |
|---|---|---|---|---|
| Switch configuration CRUD (adapters, connection pool) | Yes — PRD §3 + §9 | NOT_BUILT | M | Zero portal directory |
| BIN/PCN routing table (CRUD, wildcard, priority) | Yes — PRD §5 | NOT_BUILT | M | No portal surface |
| Switch health monitor (latency, throughput, failover status) | Yes — PRD §6 | NOT_BUILT | M | No portal surface |
| Connection metrics dashboard | Yes — PRD §6 | NOT_BUILT | M | No portal surface |
| Certification runner (import scripts, run suite, evidence export) | Yes — PRD §7 | NOT_BUILT | L | No portal surface |
| SCRIPT version config per switch/pharmacy | Yes — PRD §4 | NOT_BUILT | S | No portal surface |

---

## Summary

### Wired surfaces (BUILT_WIRED): 14
Claims Explorer, Claim Detail, Claim Lookup, Medical Claim Browser, Medical Claim Detail, HCPCS→NDC Crosswalk, Unified Drug Spend, Site-of-Care Analysis, 340B Summary, Program Overview List, Program Detail (5-tab), Program Budget & Forecast, Program Enrollment Dashboard  
*(Medical Claims nav entry counted separately as BUILT_UNWIRED)*

### Scaffold surfaces (SCAFFOLD): 3
Manual Claim Entry (flat form, not CMS-1500/UB-04 wizard), PA Override Queue (list+modal, no multi-level workflow), Program Config (flat form, not 8-step wizard)

### Built but unwired (BUILT_UNWIRED): 1
Medical Claims sidebar nav entry missing from nav-config.ts

### Not built (NOT_BUILT): 40
All adjudication-engine portal-specific surfaces (trace viewer, override dashboard, metrics, accumulator report, fraud flags, waste alerts, reimbursement transparency), all prior-authorization surfaces (reviewer queue, appeal wizard, criteria CRUD, letters, ePA monitor, FRM tools), all rules-engine surfaces (pipeline builder, rule CRUD, NL creation, BRD upload, test harness, state compliance), all switch-connectivity surfaces (switch config, BIN/PCN routing, health monitor, certification runner), plus program-config advanced surfaces (BRD builder, manufacturer self-service, contract management, onboarding dashboard, diff+promote)

---

COUNTS: NOT_BUILT=40, SCAFFOLD=3, BUILT_UNWIRED=1, BUILT_WIRED=14 (of 58)  
EFFORT_TOTAL: ~110–130 person-days  
KEY_GAPS:  
1. Rules Engine visual drag-and-drop pipeline builder with branching + live preview (NOT_BUILT, L — largest single UI in cluster, blocks adjudication configuration entirely)  
2. Prior Authorization reviewer queue + multi-level appeal wizard (NOT_BUILT, L+L — full lifecycle portal absent)  
3. Program Config 8-step launch wizard (SCAFFOLD — only steps 1-2 exist as a flat form; steps 3-8 unbuilt)  
4. Adjudication Claim Trace Viewer + Override Rule panel (NOT_BUILT, L+M — core ops surface for help desk)  
5. Switch Connectivity portal entirely absent (NOT_BUILT — 6 surfaces, ~15pd)  
6. BRD Template Builder + Manufacturer Self-Service Program Builder (NOT_BUILT, L+L)  
7. Medical Claims missing from sidebar nav-config (BUILT_UNWIRED, S — quick fix)  
REPORT_PATH: docs/audit/depth-reaudit-claims-2026-05-21.md
