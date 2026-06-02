# Depth Re-Audit: Analytics / Admin / AI Cluster
**Date:** 2026-05-21  
**Scope:** portal/operator — /analytics/**, /admin/** (excl. paysync), plus cross-cutting shell features and designed surfaces for ai-nlp, part-d-pde, ebv-ebi-rtbc, mtm-clinical  
**Designed sources:** prd-operator-portal.md §6/§8/§10/§11/§19, prd-dataiq.md, prd-reporting.md, prd-ai-nlp.md, prd-part-d-pde.md, prd-ebv-ebi-rtbc.md, prd-mtm-clinical.md  
**Built sources:** portal/operator/app/{analytics,admin}/**, portal/shared/components/**, portal/operator/components/**

---

## Classification Key
- **NOT_BUILT** — no component exists anywhere
- **SCAFFOLD** — basic display only; missing designed interactive depth
- **BUILT_UNWIRED** — full component exists, not reachable/connected to live data
- **BUILT_WIRED** — exists, reachable via route, matches design intent

**Effort:** S = <0.5 pd, M = 0.5–2 pd, L = 2–5 pd, XL = >5 pd

---

## A. Cross-Cutting Portal Shell Features

| Surface | Designed? | Build State | Effort to Complete | Note |
|---|---|---|---|---|
| Command palette (Cmd+K) — page nav + record search | §11 | BUILT_WIRED | — | portal/shared/components/command-palette uses cmdk; wired in AppShell; entity-search.ts plugged in |
| Notification center — bell icon, unread count, panel | §10.1 | BUILT_WIRED | — | portal/shared/components/notification-center uses SSE stream from core-platform |
| Notification preferences per type | §10.2 | SCAFFOLD | M | settings/notifications page exists but no per-type toggle UI confirmed; needs verification |
| Dashboard 4 preset tabs (Billing Ops, FWA, Executive, System Admin) | §6.1 | BUILT_WIRED | — | page.tsx has PRESETS const with 4 IDs, localStorage persistence, tab switcher rendered |
| Customizable widget grid — drag-drop reorder + resize | §6.2 | BUILT_WIRED | — | portal/shared/components/widget-grid uses @dnd-kit, WidgetSize 1x1/2x1/1x2/2x2, localStorage persist |
| Widget grid — add/remove from catalog (25+ widgets) | §6.2 | SCAFFOLD | L | DnD + resize exists; no add/remove catalog UI; only preset-defined widgets rendered |
| Widget auto-refresh + "last updated" timestamp | §6.2 | SCAFFOLD | M | refetchInterval used on most queries; no per-widget refresh button or last-updated display |
| Widget export (screenshot to clipboard, CSV) | §6.2 | NOT_BUILT | M | No widget-level export found in widget-grid component |
| Activity feed — real-time SSE, filterable, clickable | §6.3 | BUILT_WIRED | — | ActivityFeedSection on dashboard page queries /api/v1/dashboard/activity; links per event |
| Activity feed — filter by module/severity/user/time | §6.3 | NOT_BUILT | S | ActivityFeedSection has no filter controls |
| Wizard framework — universal step sidebar + auto-save + drafts | §7.1 | BUILT_WIRED | — | portal/shared/components/wizard/wizard-container.tsx + wizard-container; billing/payment/investigation/report wizards all built |
| Wizard — "My Drafts" section on dashboard | §7.1 | NOT_BUILT | M | No drafts surface on dashboard or any visible route |
| Keyboard shortcuts overlay (? key) | §12 | BUILT_WIRED | — | ShortcutsOverlay in AppShell, ? shortcut registered |
| All G+x navigation shortcuts | §12 | BUILT_WIRED | — | useKeyboardShortcut for g+d, g+c, g+r, g+a registered in AppShell |
| First-login onboarding checklist | §13.1 | BUILT_WIRED | — | OnboardingChecklist component on dashboard page, localStorage flag |
| Audit trail viewer — per-record "View History" | §19 | NOT_BUILT | L | Audit log page is a platform-wide log; no per-record history panel/diff viewer on any detail page |
| Audit trail — diff view (side-by-side version compare) | §19 | NOT_BUILT | L | No diff component found anywhere |
| Audit trail — export as PDF | §19 | SCAFFOLD | M | ExportMenu on audit-log page does CSV/Excel; no PDF export |
| Two-person approval flow | §8.1 | BUILT_WIRED | — | portal/shared/components/approval-flow/index.tsx exists; used in billing/payment wizards |
| Undo/rollback toast (30-sec window) | §8.2 | SCAFFOLD | M | Toast used via sonner throughout; no timed undo pattern found in wizard steps |
| Dollar verbal confirmation in financial ops | §8.3 | SCAFFOLD | M | DollarDisplay component formats amounts; no verbal word-out confirmation dialog found |
| Session timeout modal | §§ | BUILT_WIRED | — | portal/operator/components/layout/session-timeout-modal.tsx in AppShell |
| Role-based sidebar (hide inaccessible sections) | §5 | BUILT_WIRED | — | nav-config.ts + sidebar with role-gated sections |
| Coming Soon cards for Phase 5 modules | §4.2 | BUILT_WIRED | — | portal/shared/components/coming-soon-card exists; used for unbuilt module routes |

---

## B. Analytics / DataIQ (/analytics/**)

| Surface | Designed? | Build State | Effort to Complete | Note |
|---|---|---|---|---|
| Analytics dashboard — live metrics (claims/hr, dollars flowing, flags/day) with SSE | §8 Phase 6 | BUILT_WIRED | — | analytics/page.tsx uses SSE + animated counters; 3 live KPI cards |
| Drug Trend dashboards — spend trend, brand/generic, GLP-1, biosimilar, top by spend | §8 Phase 6 | BUILT_WIRED | — | analytics/drug-trend fully tabbed with 5 tabs, Recharts charts, real API calls |
| Network analytics — pharmacy scorecard table, adequacy summary, reject rate/MAC ratio charts | §8 Phase 6 | BUILT_WIRED | — | analytics/network full page; DataTable + 2 charts + 4 adequacy KPI cards |
| Member analytics — PDC adherence, high-cost claimants | §8 Phase 6 | BUILT_WIRED | — | analytics/member full page; adherence bar + high-cost DataTable |
| Financial analytics — PMPM trend, spread analysis, cost driver decomposition | §8 Phase 6 | BUILT_WIRED | — | analytics/financial full page; 3 KPI cards + PMPM line + spread + cost driver bar |
| Data quality score dashboard — overall score, 4 components, 90-day trend, active issues | §8 Phase 6 | BUILT_WIRED | — | analytics/data-quality full page; radial gauge + component bars + trend line |
| Claim summary analytics — 8 KPIs, claims bar, status stacked bar, OCC, reject codes, monthly table | PRD DataIQ | BUILT_WIRED | — | analytics/claims full Power-BI-parity page with FilterPanel + ConfigurableDataTable + 4 charts |
| Fill performance — NBRx, refills, pharmacy type, chain fills, days supply, drug-level table | PRD DataIQ | BUILT_WIRED | — | analytics/fills full page with 5 charts + drug-level table + export |
| Trend analysis — YoY spend, trend decomposition waterfall, top movers | PRD DataIQ | BUILT_WIRED | — | analytics/trends waterfall chart + YoY line + top movers tables |
| Geography analytics — state choropleth map, per-state table | PRD DataIQ | BUILT_WIRED | — | analytics/geography choropleth + state DataTable |
| Pharmacy analytics (separate page) | PRD DataIQ | BUILT_WIRED | — | analytics/pharmacies page with choropleth + top pharmacies bar + filter panel |
| Adherence deep-dive — PDC histogram, persistence curve, copay impact, by-pharmacy bar | PRD DataIQ | BUILT_WIRED | — | analytics/adherence full page with 4 charts + KPI row |
| Natural language query interface | §8 Phase 6, PRD DataIQ §644 | NOT_BUILT | XL | No NL query page or component found anywhere in portal |
| Pivot table explorer (self-service) | PRD DataIQ §128/601 | NOT_BUILT | XL | No pivot table component; no /analytics/pivot route |
| What-if scenario engine / forecast UI | PRD DataIQ §689 | NOT_BUILT | XL | No what-if or forecast page found |
| Benchmark status dashboard (green/yellow/red per metric) | PRD DataIQ §111-123 | NOT_BUILT | L | No benchmark page; no /analytics/benchmarks route |
| Real-time metrics widget (benchmark breach alerts) | PRD DataIQ §434 | NOT_BUILT | M | Insight alert delivery designed; not surfaced in portal |

---

## C. Reporting (/reporting/**)

| Surface | Designed? | Build State | Effort to Complete | Note |
|---|---|---|---|---|
| Report library (browse by category, search, favorites) | §8 Phase 3 | BUILT_WIRED | — | reporting/library/page.tsx exists + [templateId] detail page |
| Report generation wizard (template → params → preview → schedule/deliver) | §8 Phase 3 | BUILT_WIRED | — | components/report-wizard/index.tsx; reporting/generate/page.tsx |
| Scheduled report management (create, edit, pause, history) | §8 Phase 3 | BUILT_WIRED | — | reporting/scheduled/page.tsx with DataTable + pause/play/delete mutations |
| Report viewer (inline preview + download) | §8 Phase 3 | BUILT_WIRED | — | reporting/viewer/[reportId]/page.tsx |
| Report builder (power users — pick metrics/filters/format) | §8 Phase 3 | SCAFFOLD | L | reporting/builder/page.tsx exists with metric/dimension/filter UI; no live preview or save-to-library wired |

---

## D. Admin — Users, Tenants, Audit Log, System Health, Config

| Surface | Designed? | Build State | Effort to Complete | Note |
|---|---|---|---|---|
| User management — CRUD, role assignment, MFA status | §8 Phase 6 | BUILT_WIRED | — | admin/users full page; Create modal wired to POST /api/v1/users; lock + toggle-active mutations; Edit button shows toast "not implemented" |
| User management — edit existing user (role change, name) | §8 Phase 6 | SCAFFOLD | M | Edit icon fires toast "use API directly" — mutation not built |
| User management — session viewer (active sessions per user) | §8 Phase 6 | NOT_BUILT | M | No session list per user; lock terminates all sessions but no viewer |
| Tenant settings — MFA toggle, max sessions, feature flags | §8 Phase 6 | BUILT_WIRED | — | admin/tenants full page; inline edit with PATCH mutation |
| Tenant settings — client onboarding wizard (7-step) | §8 Phase 6 | BUILT_WIRED | — | components/client-onboarding-wizard/index.tsx exists |
| Audit log viewer — searchable, filterable, paginated, exportable | §19, §8 Phase 6 | BUILT_WIRED | — | admin/audit-log full page; search + date + action filters; pagination; ExportMenu CSV/Excel |
| Audit log — hash chain verification UI | §19 | NOT_BUILT | M | Hash column shown (truncated) but no verify-chain button or integrity check UI |
| System health dashboard — all services, DLQ depth, DB/Redis/event bus | §8 Phase 6 | BUILT_WIRED | — | admin/system-health full page; 30s auto-refresh; overall status banner; per-service latency table |
| Config — feature flags display, system settings display, change-set workflow | §8 Phase 6 | BUILT_WIRED | — | admin/config full page; feature flags + system settings read-only; link to change-sets |
| Config — feature flags are editable (toggle in UI) | §8 Phase 6 | SCAFFOLD | M | Flags shown with ToggleRight/ToggleLeft icons but no onClick mutation — display only |
| Config — system settings are editable | §8 Phase 6 | NOT_BUILT | M | Values shown as static strings; no edit/save |
| Encryption tools (key rotation, column verification) | §8 Phase 6 | NOT_BUILT | S | admin/encryption shows ComingSoonPage |
| Admin network — pay-to-entities, chain-membership, banking discrepancies, ACH origination | §8 Phase 6 | BUILT_WIRED | — | All 4 sub-routes exist with real components (paysync-api backed) |

---

## E. AI/NLP Operator Portal Surfaces

| Surface | Designed? | Build State | Effort to Complete | Note |
|---|---|---|---|---|
| Document processing monitor (extractions, confidence scores, review queue) | §8 Phase 5, PRD ai-nlp | NOT_BUILT | L | No /ai-nlp or /documents route in operator portal |
| Prompt template management | PRD ai-nlp | NOT_BUILT | L | No route found |
| Chatbot conversation viewer | PRD ai-nlp | NOT_BUILT | L | No route found |
| Model performance dashboard | PRD ai-nlp | NOT_BUILT | L | No route found |
| Cost tracking by service type | PRD ai-nlp | NOT_BUILT | M | No route found |

---

## F. Part-D PDE, EBV/EBI/RTBC, MTM-Clinical Operator Portal Surfaces

| Surface | Designed? | Build State | Effort to Complete | Note |
|---|---|---|---|---|
| Part-D PDE validation dashboard (pending/validated/submitted/rejected, drill-down by error) | PRD prd-part-d-pde | NOT_BUILT | L | No /part-d route in operator portal |
| EBV/EBI — eligibility verification results viewer | PRD prd-ebv-ebi-rtbc | NOT_BUILT | L | No /ebv or /eligibility route in operator portal |
| MTM Clinical — pharmacist workbench / intervention workflow | PRD prd-mtm-clinical | NOT_BUILT | XL | No /mtm route; module itself is scaffold-only on backend |

---

## Summary Counts

| Category | NOT_BUILT | SCAFFOLD | BUILT_UNWIRED | BUILT_WIRED | Total |
|---|---|---|---|---|---|
| Shell features | 8 | 6 | 0 | 11 | 25 |
| Analytics/DataIQ | 5 | 0 | 0 | 12 | 17 |
| Reporting | 0 | 1 | 0 | 4 | 5 |
| Admin | 4 | 4 | 0 | 6 | 14 |
| AI/NLP portal | 5 | 0 | 0 | 0 | 5 |
| Part-D/EBV/MTM portal | 3 | 0 | 0 | 0 | 3 |
| **TOTAL** | **25** | **11** | **0** | **33** | **69** |

---

## Effort Estimate

| Bucket | Items | Rough Person-Days |
|---|---|---|
| NOT_BUILT XL (NL query, pivot, what-if, MTM workbench) | 4 | 24–32 pd |
| NOT_BUILT L (benchmark, audit-diff, ai-nlp 4 surfaces, Part-D, EBV, per-record audit, user session viewer, encryption) | 12 | 24–36 pd |
| NOT_BUILT M (widget catalog, activity filter, drafts, hash verify, config edits, widget export, verbal confirm, undo pattern) | 9 | 9–18 pd |
| NOT_BUILT S (encryption coming-soon → real) | 1 | 0.5 pd |
| SCAFFOLD → complete (report builder wiring, feature flag edits, user edit, notif prefs, widget refresh, undo toast) | 11 | 11–22 pd |
| **TOTAL** | **37** | **~68–108 pd** |

---

## Shell Feature State (rebuild-vs-patch signal)

| Shell Feature | State |
|---|---|
| Command palette (Cmd+K, cmdk) | BUILT_WIRED — fully functional |
| Notification center (SSE, unread count, panel, filter) | BUILT_WIRED — SSE wired, panel rendered |
| Dashboard presets (4 tabs, localStorage persistence) | BUILT_WIRED — all 4 presets, chooser on dashboard |
| Widget grid (drag-drop reorder, resize 4 sizes, persist) | BUILT_WIRED — @dnd-kit full implementation |
| Widget catalog (add/remove) | NOT_BUILT — only preset-defined widgets, no catalog |
| Wizard framework (step sidebar, auto-save, validation) | BUILT_WIRED — shared wizard-container used by 4 wizards |
| Audit trail viewer (per-record diff, PDF export) | NOT_BUILT — platform log only; no per-record history |

**Verdict:** The four foundational shell features (command palette, notification center, dashboard presets, widget grid drag-drop) are BUILT_WIRED. The shell does NOT require rebuild — it requires targeted gap-fills. The analytics sub-pages are the strongest area (12/17 BUILT_WIRED). The NOT_BUILT gap is concentrated in: NL-query/pivot/what-if (XL effort each), all AI/NLP portal surfaces, Part-D/EBV/MTM portal surfaces, and per-record audit diff. These are additive features, not blockers to existing wired surfaces.
