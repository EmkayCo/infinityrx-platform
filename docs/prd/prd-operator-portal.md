# PRD — Module 20a: Operator Portal — FINAL

**Module:** Operator Portal (Internal IFX Operations)  
**Folder:** `portal/operator/`  
**Priority:** Phase 4B (start immediately — progressive shell)  
**Dependencies:** Core Platform (1), Billing (11), Payment (12), ReclaimRx (16), Reporting (15)  

---

## 1. Purpose

The Operator Portal is the internal command center for InfinityRx operations. It replaces the legacy accounting portal and is the primary interface for the 41-member team to run billing cycles, manage payments, investigate fraud, generate reports, configure clients, and monitor the entire platform.

**Design philosophy: dummy-proof.** Every action has guardrails. Every multi-step process is a wizard. Every financial operation requires confirmation. Every destructive action is reversible. The interface should be so intuitive that a new operator can run their first billing cycle on day one with zero training — guided entirely by the UI.

**Progressive shell approach:** build the portal framework now, connect modules as they complete. Sections for unbuilt modules show "Coming Soon" cards. Operators can start testing billing, payment, ReclaimRx, and reporting workflows immediately.

---

## 2. Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Framework | Next.js 15+ (App Router) + TypeScript 5 | SSR capability, file-based routing, best AI builder compatibility |
| UI Components | shadcn/ui + Radix UI primitives | Copy-paste ownership, accessible by default, fastest-growing 2026 |
| Styling | Tailwind CSS v4 | Utility-first, purges unused CSS, IFX brand tokens |
| Data Grid | TanStack Table v8 | Virtual scrolling, sorting, filtering, column resizing, bulk selection |
| Charts | Recharts 3 | Financial dashboards, trend lines, composable React components |
| Forms | React Hook Form + Zod | Type-safe validation matching backend Pydantic schemas |
| Server State | TanStack Query v5 | Caching, background refresh, optimistic updates, retry |
| Client State | Zustand | Lightweight, no boilerplate, devtools support |
| Command Palette | cmdk (by Vercel) | Cmd+K search across all actions and records |
| Drag & Drop | @dnd-kit/core | Dashboard widget reordering, kanban boards |
| Auth | NextAuth.js | JWT + MFA challenge flow wired to Core Platform |
| Real-time | Server-Sent Events (SSE) | Activity feed, notification stream, live dashboard updates |
| Deploy | Azure Static Web Apps | Frontend hosting, integrated with Azure AD |

---

## 3. IFX Brand Design System

Derived from infinityrx.com:

```css
:root {
  /* Primary palette */
  --ifx-navy-900: #0B1D3A;        /* deep navy — primary backgrounds, sidebar */
  --ifx-navy-700: #1B3A5C;        /* medium navy — cards, panels */
  --ifx-navy-500: #2D5F8A;        /* lighter navy — hover states */
  
  /* Accent */
  --ifx-teal-500: #00B4D8;        /* teal/cyan — primary accent, CTAs, links */
  --ifx-teal-400: #22D3EE;        /* lighter teal — hover accent */
  --ifx-teal-600: #0891B2;        /* darker teal — pressed state */
  
  /* Semantic */
  --ifx-success: #10B981;
  --ifx-warning: #F59E0B;
  --ifx-error: #EF4444;
  --ifx-info: #3B82F6;
  
  /* Surfaces */
  --ifx-bg-light: #F8FAFC;
  --ifx-bg-dark: #0F172A;
  --ifx-surface-light: #FFFFFF;
  --ifx-surface-dark: #1E293B;
  --ifx-border-light: #E2E8F0;
  --ifx-border-dark: #334155;
  
  /* Text */
  --ifx-text-primary-light: #1E293B;
  --ifx-text-primary-dark: #F1F5F9;
  --ifx-text-secondary-light: #64748B;
  --ifx-text-secondary-dark: #94A3B8;
  
  /* Typography */
  --ifx-font-display: 'Inter', system-ui, sans-serif;
  --ifx-font-body: 'Inter', system-ui, sans-serif;
  --ifx-font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  
  /* Spacing & Radius */
  --ifx-radius: 8px;
  --ifx-radius-lg: 12px;
  --ifx-shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --ifx-shadow-md: 0 4px 6px rgba(0,0,0,0.07);
}
```

Dark mode is a first-class citizen — operators working late-night billing cycles need it. Toggle in user settings, persisted per user. System preference auto-detection on first visit.

---

## 4. Portal Architecture

### 4.1 Progressive Shell

```
┌─────────────────────────────────────────────────────────────┐
│ TOP BAR                                                      │
│ [☰] InfinityRx Logo    [🔍 Cmd+K]  [🔔 3]  [👤 Mike K ▾]  │
├──────────┬──────────────────────────────────────────────────┤
│ SIDEBAR  │ MAIN CONTENT                                      │
│          │                                                    │
│ Dashboard│ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│ ────────│ │ Widget 1 │ │ Widget 2 │ │ Widget 3 │          │
│ Billing  │ └──────────┘ └──────────┘ └──────────┘          │
│ Payments │                                                    │
│ ReclaimRx│ ┌──────────┐ ┌──────────────────────┐          │
│ Reporting│ │ Widget 4 │ │ Activity Feed         │          │
│ ────────│ └──────────┘ └──────────────────────┘          │
│ Directory│                                                    │
│  ↳ Pharm │                                                    │
│  ↳ Prescr│                                                    │
│  ↳ Drugs │                                                    │
│  ↳ Member│                                                    │
│ ────────│                                                    │
│ EDI Ops  │                                                    │
│ Analytics│                                                    │
│ ────────│                                                    │
│ Admin    │                                                    │
│  ↳ Users │                                                    │
│  ↳ Tenants                                                   │
│  ↳ Config│                                                    │
│  ↳ Audit │                                                    │
└──────────┴──────────────────────────────────────────────────┘
```

### 4.2 Navigation States

| Section | Backend Module | Status | Sidebar State |
|---|---|---|---|
| Dashboard | Core Platform | ✅ Ready | Active — always visible |
| Billing | Billing (11) | ✅ Ready | Active — full wizard workflows |
| Payments | Payment Processing (12) | ✅ Ready | Active — full workflows |
| ReclaimRx | ReclaimRx (16) | ✅ Ready | Active — investigation queue |
| Reporting | Reporting (15) | ✅ Ready | Active — report library |
| Pharmacy Directory | Pharmacy Dir (3) | ✅ Ready | Active — network management, credentialing |
| Prescriber Directory | Prescriber Dir (4) | ✅ Ready | Active — NPI lookup, credential monitoring |
| Drug Database | Drug DB (2) | ✅ Ready | Active — NDC lookup, pricing, interactions |
| Member Management | Member Mgmt (5) | ✅ Ready | Active — enrollment, eligibility, accumulators |
| EDI Operations | EDI (13) | ✅ Ready | Active — trading partners, transaction monitor |
| Medical Claims | Medical Claims (14) | ✅ Ready | Active — HCPCS claims, 340B, unified spend |
| AI/NLP | AI/NLP (21) | ✅ Ready | Active — document processing, chatbot config |
| Analytics | DataIQ (23) | ✅ Ready | Active — real-time metrics, drug trend, forecasting |
| ───────── | ───────── | ──── | ───────── |
| Plan Design | Plan Design (6) | ❌ Phase 5 | Visible — "Coming Soon" |
| Adjudication | Adjudication (8) | ❌ Phase 5 | Visible — "Coming Soon" |
| Prior Auth | Prior Auth (10) | ❌ Phase 5 | Visible — "Coming Soon" |
| Switch | Switch (9) | ❌ Phase 5 | Visible — "Coming Soon" |
| Rebate Mgmt | Rebate (22) | ❌ Phase 5 | Visible — "Coming Soon" |
| Admin | Core Platform | ✅ Ready | Active — user/tenant/config/audit |

"Coming Soon" cards show: module name, expected availability, a brief description of what it will do. When the backend module completes and its API is reachable, the card auto-transitions to the live page. No portal code change needed — just a feature flag flip.

---

## 5. Role-Based Access

| Role | Dashboard | Billing | Payments | ReclaimRx | Reporting | Directories | EDI | Analytics | Admin |
|---|---|---|---|---|---|---|---|---|---|
| **Admin** | Full | Full | Full | Full | Full | Full | Full | Full | Full |
| **Billing Operator** | Billing widgets | Full | View | View | Generate | View | View | View | — |
| **FWA Investigator** | FWA widgets | View | View | Full | Generate | View | — | View | — |
| **Client Manager** | Client widgets | View | View | View | Full | Full | View | Full | — |
| **Viewer** | View-only | View | View | View | View | View | View | View | — |

Each role sees a customized sidebar — sections they can't access are hidden (not grayed out — hidden). Admin sees everything.

---

## 6. Dashboard

### 6.1 Dashboard Presets

Four pre-built layouts — operator chooses on first login or switches anytime:

**Billing Operations:**
- Active billing cycles (status, amounts, next action needed)
- Payment batches pending approval
- AP/AR summary (today, this cycle, this month)
- Prefund account balances with burn rate
- Recent billing activity feed

**FWA Investigation:**
- New flags (today, this week) with severity breakdown
- Active investigations by stage
- Recovery pipeline (estimated, demanded, collected)
- Top flagged pharmacies / prescribers
- FWA activity feed

**Executive Overview:**
- Total claims processed (today, MTD, YTD)
- Revenue summary (fees collected, outstanding)
- System health (all modules green/yellow/red)
- Client count and active programs
- Key metrics trending (PMPM, generic rate, denial rate)

**System Admin:**
- System health (services, database, Redis, RabbitMQ)
- Active users / sessions
- API request volume and error rate
- Audit log (recent entries)
- DLQ depth and event bus health

### 6.2 Customizable Widget Grid

After choosing a preset, operators can customize:
- **Drag-and-drop** widgets to reorder
- **Resize** widgets (1x1, 2x1, 1x2, 2x2 grid units)
- **Add/remove** widgets from a widget catalog
- **Save** as personal layout (persisted per user)
- **Reset** to preset default with one click

Widget catalog includes 25+ widgets across all modules. Each widget:
- Has a skeleton loading state (not spinner)
- Has an error boundary (crash doesn't kill dashboard)
- Has a refresh button (manual) + configurable auto-refresh interval
- Shows "last updated" timestamp
- Is exportable (screenshot to clipboard, data to CSV)

### 6.3 Activity Feed

Real-time operation timeline via SSE:

```
🔵 2:34 PM — Mike K approved Billing Cycle #2024-SM-15 ($13.2M)
🟢 2:33 PM — System generated 835 remittance for Echo batch #4521
🟡 2:30 PM — ReclaimRx flagged 12 new claims (3 high severity)
🔵 2:28 PM — Sarah L uploaded enrollment file (2,340 members)
🔴 2:25 PM — Payment batch #789 rejected by bank (NSF on prefund 1018)
🟢 2:20 PM — NACHA file transmitted to Webster Bank
```

Filterable by: module, severity, user, time range. Clickable — each entry links to the relevant record.

---

## 7. Wizard Workflows

Every multi-step operation is a guided wizard. All wizards share these patterns:

### 7.1 Universal Wizard Framework

```
┌─────────────────────────────────────────────────┐
│ WIZARD TITLE                           [X Close] │
├──────────┬──────────────────────────────────────┤
│ STEPS    │ STEP CONTENT                          │
│          │                                        │
│ ● Upload │ [Current step's form/content]          │
│ ○ Map    │                                        │
│ ○ Validate                                       │
│ ○ Preview│                                        │
│ ○ Confirm│                                        │
│          │                                        │
│          │                                        │
│          ├──────────────────────────────────────┤
│          │ [← Back]  [Save Draft]  [Next →]      │
└──────────┴──────────────────────────────────────┘
```

**Universal wizard behaviors:**
1. **Step sidebar** shows progress — completed steps get ✅, current step highlighted, future steps grayed
2. **Auto-save** on every step transition — if session expires, resume from last saved step
3. **Drafts** — incomplete wizards saved in "My Drafts" section. Visible on dashboard.
4. **Back navigation** — always available. Going back preserves data entered in later steps.
5. **Validation** — real-time inline validation on every field. "Next" button disabled until current step is valid.
6. **Skip** — optional steps show "Skip" link. Required steps don't.
7. **Review step** — every wizard ends with a full summary of all entered data before final confirmation
8. **Confirmation** — final step shows dollar totals (if applicable) with explicit "Confirm and Execute" button. High-value operations require second-person approval.

### 7.2 Billing Cycle Wizard

**Step 1 — Upload Claims File**
- Drag-and-drop zone + file picker
- Accepts: CSV, Excel, pipe-delimited (configurable per client)
- Shows: file name, size, estimated record count
- Validation: correct file extension, not empty, not duplicate of recent upload

**Step 2 — Map Fields (if new format)**
- Two-column layout: left = uploaded file columns, right = system fields
- Auto-map: system guesses mappings based on column headers (fuzzy match)
- Manual override: drag source column to target field
- Save mapping template: "Save as [Client Name] Standard Format" for reuse
- Skip if using a previously saved mapping template

**Step 3 — Validate**
- Progress bar as validation runs
- Results: ✅ X records valid, ⚠️ Y records with warnings, ❌ Z records with errors
- Expandable error list: row number, field, error message, original value
- Option: "Fix errors and re-validate" or "Proceed with valid records only"
- Download error records as CSV for offline correction

**Step 4 — Preview**
- Summary: total claims, total dollar amount, breakdown by client/program
- Comparison to last cycle: +/- claims, +/- dollars, percentage change
- Flag anomalies: "This cycle is 25% higher than average — review before approving"
- Sample: show first 20 claims in data table (sortable, filterable)
- Financial preview: AP amounts, AR amounts, fee amounts, journal entries

**Step 5 — Approve**
- Full summary with dollar amounts prominently displayed
- If amount > approval threshold: "This cycle requires second-person approval. Submitting for review by [authorized approvers]."
- If amount ≤ threshold: "Confirm and Generate" button
- On confirm: system generates all outputs (SaaSant Excel, 835, NACHA, reports)

**Step 6 — Generate & Transmit**
- Progress: generating SaaSant file... ✅, generating 835 files... ✅, generating NACHA... ✅
- Download links for all generated files
- Transmit NACHA: "Transmit to [bank]" button with final confirmation
- Status: transmitted, pending acknowledgment, settled

### 7.3 Payment Batch Wizard

Similar structure for payment processing:
1. Select claims for payment (filter by client, date range, status)
2. Review payment amounts and vendor routing (Echo, CheckIssuing, NACHA)
3. Generate payment files with preview
4. Two-person approval for batches > threshold
5. Transmit and track acknowledgment

### 7.4 Client Onboarding Wizard

Replaces the manual process (currently requires code changes):
1. Client details (name, contacts, billing address, tax ID)
2. Program configuration (drug programs, fee structure, billing rules)
3. Banking setup (prefund accounts, payment routing)
4. Fee rules (claims processing fee, admin fee, split rules)
5. Output configuration (835 format, SaaSant tabs, report templates)
6. Test: run a sample billing cycle with test data
7. Activate: flip client to production

### 7.5 Investigation Wizard (ReclaimRx)

Guided FWA investigation workflow:
1. Review flag details (what was detected, why it's unusual, evidence)
2. Assign to investigator
3. Evidence collection checklist (prescription copies, signature logs, inventory)
4. Demand letter generation (AI/NLP drafts, human reviews)
5. Resolution (recovery amount, corrective action plan, case closure)

---

## 8. Financial Safety Guardrails

### 8.1 Two-Person Approval

For operations exceeding configurable thresholds:

| Operation | Default Threshold | Approval Flow |
|---|---|---|
| Billing cycle approval | $1,000,000 | Preparer → Approver |
| NACHA file transmission | $500,000 | Preparer → Approver |
| Payment batch execution | $500,000 | Preparer → Approver |
| Client fee configuration change | Any change | Preparer → Approver |
| Tenant configuration change | Any change | Preparer → Admin |
| User role elevation | Any change | Requester → Admin |

Approval flow:
1. Preparer completes the wizard and clicks "Submit for Approval"
2. System creates an approval request with full details
3. Approver receives notification (in-app + email)
4. Approver reviews details (full read-only view of what was prepared)
5. Approver clicks "Approve" (with MFA re-verification for high-value) or "Reject" with reason
6. On approval: system executes the operation
7. On rejection: preparer notified with rejection reason, can modify and resubmit

### 8.2 Undo / Rollback

| Operation | Undo Window | Undo Method |
|---|---|---|
| Billing cycle approval | 30 seconds (soft commit) | Toast: "Approved — Undo" |
| After undo window closes | Requires supervisor | Formal reversal workflow |
| NACHA transmission | Not undoable after transmission | Pre-transmission confirmation only |
| Claim status change | 5 minutes | Toast undo |
| Bulk action | 30 seconds | Toast: "X items updated — Undo" |
| Configuration change | Versioned — rollback to any version | Config version history |

All configuration changes are versioned. Every change creates a new version with diff. Rollback to any previous version with one click.

### 8.3 Dollar Amount Formatting & Confirmation

Every dollar amount displayed in the portal:
- Formatted with commas and 2 decimal places: $1,234,567.89
- Large amounts highlighted with color scale: <$100K normal, $100K-$1M bold, >$1M bold + background highlight
- Confirmation dialogs for financial operations show the amount in LARGE FONT with verbal description: "$13,247,891.23 (thirteen million two hundred forty-seven thousand eight hundred ninety-one dollars and twenty-three cents)"
- Amount mismatches flagged with warning icon and explanation

---

## 9. Data Tables

Every data table in the portal follows this specification:

### 9.1 TanStack Table Standard

- **Virtual scrolling**: handles 100,000+ rows without pagination (scroll loads more)
- **Column resizing**: drag column borders to resize
- **Column reordering**: drag column headers to reorder
- **Column visibility**: toggle columns on/off from column settings dropdown
- **Sorting**: click header to sort (asc → desc → none). Multi-column sort with Shift+click.
- **Filtering**: per-column filter dropdowns (text search, date range, number range, multi-select for enums)
- **Global search**: search across all visible columns
- **Row selection**: checkbox column for bulk actions. Select all / deselect all.
- **Fixed columns**: first 1-2 identifying columns fixed during horizontal scroll
- **Row actions**: hover reveals action icons (view, edit, flag). Click row to open detail panel.
- **Density toggle**: compact / comfortable / spacious row height

### 9.2 Bulk Actions

When rows are selected, a floating action bar appears above the table:

```
┌─────────────────────────────────────────────────────┐
│ ✓ 47 of 1,234 selected  │ Approve │ Reject │ Export │ ⋮ More │
└─────────────────────────────────────────────────────┘
```

- Shows count and dollar total of selected items
- Available actions depend on context (claim table: approve/reject/flag; investigation table: assign/close)
- Destructive actions require confirmation dialog with count and summary
- After execution: toast with undo option + result summary ("42 approved, 5 failed — View failures")
- Partial failure: show which items failed and why in expandable error list

### 9.3 Export

Every table has an export menu:
- **CSV**: all rows (filtered) or selected rows only
- **Excel**: with formatting, column headers, sheet name
- **PDF**: printable format with IFX letterhead and timestamp
- **Clipboard**: copy selected rows as tab-separated (paste into Excel)
- **Share link**: generate a timestamped snapshot URL (read-only, expires in 24 hours)

---

## 10. Notifications & Communication

### 10.1 Notification Center

Bell icon in top bar shows unread count. Click opens panel:

```
┌─────────────────────────────────────┐
│ Notifications                [Mark all read] │
├─────────────────────────────────────┤
│ 🔴 Payment batch #789 rejected      2m ago │
│ 🟡 Billing cycle ready for approval  15m ago │
│ 🔵 Report "Q1 Summary" generated    1h ago │
│ 🟢 NACHA file acknowledged          2h ago │
└─────────────────────────────────────┘
```

### 10.2 Notification Preferences

Per-user, per-notification-type configuration:

| Notification Type | In-App | Email | SMS | Mutable? |
|---|---|---|---|---|
| System down / critical error | ✅ Always | ✅ Always | ✅ Always | No |
| Financial discrepancy detected | ✅ Always | ✅ Default | Optional | Partially |
| Approval request pending | ✅ Always | ✅ Default | Optional | Partially |
| Billing cycle completed | ✅ Default | Optional | — | Yes |
| Report generated | ✅ Default | Optional | — | Yes |
| FWA flag (high severity) | ✅ Always | ✅ Default | Optional | Partially |
| FWA flag (medium/low) | ✅ Default | Optional | — | Yes |
| Data refresh completed | Optional | — | — | Yes |

---

## 11. Command Palette (Cmd+K)

Global search and action launcher. Press `Cmd+K` (Mac) or `Ctrl+K` (Windows) from anywhere:

```
┌─────────────────────────────────────────┐
│ 🔍 Search actions, records, pages...     │
├─────────────────────────────────────────┤
│ ACTIONS                                  │
│   Start billing cycle                    │
│   Generate report                        │
│   Upload enrollment file                 │
│ RECENT                                   │
│   Billing Cycle #2024-SM-15             │
│   Investigation INV-0042                 │
│ PAGES                                    │
│   Billing → Claims Review                │
│   ReclaimRx → Investigation Queue        │
└─────────────────────────────────────────┘
```

Searchable: page names, action names, record IDs (claim numbers, batch IDs, investigation numbers), client names, pharmacy names, drug names. Results ranked by relevance and recency.

---

## 12. Keyboard Shortcuts

`?` key opens shortcuts overlay from any page:

| Shortcut | Action |
|---|---|
| `Cmd+K` | Open command palette |
| `?` | Show shortcuts reference |
| `Cmd+S` | Save current form / draft |
| `Cmd+Enter` | Submit / approve current wizard step |
| `Esc` | Close modal / cancel current action |
| `G then D` | Go to Dashboard |
| `G then B` | Go to Billing |
| `G then R` | Go to ReclaimRx |
| `G then P` | Go to Payments |
| `↑↓` | Navigate table rows |
| `Enter` | Open selected row detail |
| `Space` | Toggle row selection |
| `Shift+Click` | Multi-select range |
| `Cmd+A` | Select all visible rows |
| `Cmd+E` | Export selected |
| `N` | New / Create (context-dependent) |
| `F` | Focus filter/search |

---

## 13. Onboarding & Contextual Help

### 13.1 First-Login Checklist

New operators see a checklist overlay on first login:

```
Welcome to InfinityRx! Complete these steps to get started:

□ Set up MFA (required) ──────────────────── [Start →]
□ Choose your dashboard layout ─────────────── [Choose →]
□ Review the billing workflow tutorial ────── [Watch →]
□ Run your first test billing cycle ─────── [Try →]
□ Explore the command palette (Cmd+K) ────── [Try →]

[Dismiss — I'll figure it out myself]
```

Each step links directly to the relevant wizard or tutorial. Checklist reappears on dashboard until all steps are completed or explicitly dismissed.

### 13.2 Contextual Tooltips

Every complex field has an `ⓘ` icon that shows a tooltip on hover:
- **Short explanation** of what the field means
- **Example value** for the expected format
- **Why it matters** (one sentence)
- **Link** to full documentation (opens in new tab)

### 13.3 Empty States

When a section has no data, show a helpful empty state instead of a blank table:

```
┌─────────────────────────────────────────────┐
│                                              │
│     📋 No billing cycles yet                 │
│                                              │
│     Start your first billing cycle to see    │
│     claims, payments, and invoices here.     │
│                                              │
│     [Start Billing Cycle →]                  │
│                                              │
└─────────────────────────────────────────────┘
```

---

## 14. Concurrent Editing & Conflict Resolution

When two operators edit the same record simultaneously:

1. **Optimistic locking**: each record has a `version` field. On save, check `version` matches.
2. **Conflict detection**: if versions don't match, show diff dialog:
   - "This record was modified by [Sarah L] at [2:34 PM]. Review their changes?"
   - Side-by-side diff of fields that changed
   - Options: "Keep my changes", "Accept their changes", "Merge manually"
3. **Critical records** (client configuration, fee rules): pessimistic locking. When operator opens for editing, show "[Mike K] is currently editing this record — view-only mode" to other users. Lock auto-releases after 5 minutes of inactivity.

---

## 15. Mobile Responsive

Not a full mobile app — but critical flows work on mobile:

| Feature | Mobile Support |
|---|---|
| Dashboard (read-only) | ✅ Responsive widgets stack vertically |
| Approval flows | ✅ Review summary + approve/reject with biometric |
| Notifications | ✅ Full notification center |
| Activity feed | ✅ Scrollable timeline |
| Billing wizard | ❌ Desktop only (too complex for mobile) |
| Data tables | ⚠️ Horizontal scroll, limited columns |
| Reports | ✅ View + download (not build) |

Approval on mobile includes biometric re-authentication (FaceID/TouchID via WebAuthn) before approving financial operations.

---

## 16. Accessibility (WCAG 2.2 AA)

Non-negotiable for enterprise healthcare:

- Full keyboard navigation on every page
- ARIA labels on all interactive elements
- Screen reader optimization (semantic HTML, live regions for notifications)
- Color contrast ratio ≥ 4.5:1 for text, ≥ 3:1 for large text
- Focus indicators visible on all focusable elements
- No information conveyed by color alone (icons + text labels)
- Skip navigation link on every page
- Reduced motion mode for users with vestibular sensitivity

---

## 17. Performance

- **First Contentful Paint**: <1.5 seconds
- **Time to Interactive**: <3 seconds
- **Dashboard widget load**: <500ms each (parallel loading with skeleton states)
- **Table render (10,000 rows)**: <1 second (virtual scrolling)
- **Command palette search**: <200ms response
- **Page navigation**: <300ms (client-side routing, prefetching)

### 17.1 Loading States

Every component has three states:
1. **Skeleton**: grey animated placeholders in the shape of expected content (shown during initial load)
2. **Loaded**: actual data displayed
3. **Error**: error boundary with "Failed to load — Retry" message + auto-retry after 30 seconds

No blank screens. No raw spinners. Skeleton everywhere.

---

## 18. Error Handling

### 18.1 Error Boundaries

Each widget, each table, each form section has its own error boundary. A crashed chart widget does NOT take down the dashboard. The crashed widget shows: error description (user-friendly), "Retry" button, and "Report Issue" link.

### 18.2 Form Errors

- **Inline validation**: as user types, show ✅ or ❌ with message below the field
- **On submit**: scroll to first error, focus the field, shake animation
- **Server errors**: toast notification with error message + link to affected field
- **Network errors**: "Connection lost — changes saved locally. Retrying..." with auto-retry

### 18.3 API Failure

When a backend API is unreachable:
- Dashboard widgets show "Service temporarily unavailable" with last-known data and timestamp
- Sidebar section shows a yellow warning dot
- System health widget turns the affected module yellow/red
- Cached data displayed where available (stale-while-revalidate pattern via TanStack Query)

---

## 19. Audit Trail Visibility

Every page that shows financial or PHI data includes an audit trail viewer:

- Click "View History" on any record to see: who created it, every modification (who, when, what changed), who approved it
- Diff view: side-by-side comparison of any two versions
- Filter by user, date range, field changed
- Export audit trail as PDF (for compliance/audit responses)
- PHI access: every time an operator views member PHI, it's logged and visible in the audit trail

---

## 20. Session Decomposition

### Build Phase 1 — Shell + Auth + Dashboard (Week 1-2)
- Next.js project setup with TypeScript, Tailwind, shadcn/ui
- IFX brand design system tokens (navy/teal palette, Inter font, dark mode)
- Auth flow (login → MFA challenge → dashboard) wired to Core Platform
- Layout: collapsible sidebar, top bar, main content area
- Role-based navigation (sidebar shows/hides based on role)
- Command palette (Cmd+K) with page navigation + record search
- Notification center (bell icon + panel + SSE real-time stream)
- User settings (dark mode toggle, notification preferences, dashboard layout)
- Dashboard widget grid framework (drag-and-drop reorder via @dnd-kit)
- 4 dashboard presets (Billing, FWA, Executive, Admin)
- Activity feed widget (real-time SSE)
- Skeleton loading states on all widgets
- Error boundaries per widget
- "Coming Soon" cards for Phase 5 modules
- First-login onboarding checklist
- Keyboard shortcuts (`?` overlay, `Cmd+K`, `G+D/B/R/P`)

### Build Phase 2 — Billing + Payments (Week 2-3)
- Billing cycle wizard (6-step: upload → map → validate → preview → approve → generate)
- Field mapping UI with drag-and-drop + auto-map + save template
- Claims review table (TanStack Table — virtual scroll, filters, bulk actions, export)
- Invoice management (list, detail, download, status tracking)
- Payment batch wizard (select → review → generate → approve → transmit)
- NACHA file management (generate, preview, transmit, track acknowledgment)
- 835 remittance viewer
- AP/AR dashboard widgets with cycle comparison
- Two-person approval flow for operations above threshold
- Undo/rollback with 30-second timed toast
- Dollar confirmation with verbal amount description

### Build Phase 3 — ReclaimRx + Reporting (Week 3-4)
- FWA flags dashboard (severity breakdown, trend chart, top flagged entities)
- Investigation queue as kanban board (new → assigned → evidence → demand → resolved)
- Investigation detail page (flag evidence, anomaly narrative from AI/NLP, timeline)
- Investigation wizard (5-step guided workflow)
- Recovery tracking table with amounts (estimated, demanded, collected)
- Report library (browse by category, search, favorites)
- Report generation wizard (template → parameters → preview → schedule/deliver)
- Scheduled report management (create, edit, pause, view history)
- Report viewer (inline PDF/HTML preview + download)
- Report builder (for power users — select metrics, filters, output format)

### Build Phase 4 — Directories + Members (Week 4-5)
- Pharmacy Directory: search (NPI, name, location, type), detail page, network management, credentialing queue, network adequacy map
- Prescriber Directory: search (NPI, name, specialty, location), detail page, credential monitoring dashboard, DEA status alerts
- Drug Database: NDC lookup with pricing (AWP, WAC, NADAC), drug detail page (interactions, equivalents, REMS), drug search, price change alerts
- Member Management: member search (ID, name, DOB), member detail (demographics, coverage, accumulators, claims history), enrollment file upload wizard, eligibility check, accumulator viewer with ledger

### Build Phase 5 — EDI + Medical Claims + AI/NLP (Week 5-6)
- EDI Operations: trading partner management (CRUD, test mode toggle), transaction file browser (filter by type, direction, status), transaction detail with validation results, acknowledgment tracking, transmission queue, real-time transaction monitor dashboard, certificate expiry alerts
- Medical Claims: medical drug claim browser (filter by HCPCS, provider, member, status), claim detail (drug mapping, ASP pricing, waste, 340B flag), HCPCS-to-NDC crosswalk viewer, unified drug spend view (pharmacy + medical side by side), site-of-care analysis, 340B summary
- AI/NLP Config: document processing monitor (recent extractions, confidence scores, human review queue), prompt template management, chatbot conversation viewer, model performance dashboard, cost tracking by service type

### Build Phase 6 — Analytics + Admin + Polish (Week 6-7)
- DataIQ Analytics: real-time metrics dashboard (live claim volume, financial counters), drug trend dashboards (spend trending, brand/generic, GLP-1, biosimilar), network analytics (pharmacy scorecard, adequacy map), member analytics (adherence, high-cost), financial analytics (cost drivers, PMPM, spread), data quality score dashboard, benchmark status (green/yellow/red), natural language query interface, pivot table explorer
- Admin: user management (CRUD, role assignment, MFA status, session viewer), tenant settings (configuration, feature flags), audit log viewer (searchable, filterable, exportable, hash chain verification), system health dashboard (all services green/yellow/red, DLQ depth, event bus health)
- Client onboarding wizard (7-step: details → programs → banking → fees → outputs → test → activate)
- Accessibility audit and WCAG 2.2 AA fixes
- Performance optimization (prefetching, caching, code splitting)
- Mobile responsive for approval flows + dashboard viewing

### Build Phase 7 — Phase 5 Module Integration (Ongoing)
- As Phase 5 modules complete: wire Plan Design, Adjudication, Prior Auth, Switch, Rebate Management pages
- Each integration: create page(s) → connect API → test → flip feature flag → section lights up
