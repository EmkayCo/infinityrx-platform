# InfinityRx ICP Operator Portal — Unified Redesign Specification
## Version 1.0 — April 15, 2026

---

## 1. Overview

This document is the single source of truth for the complete redesign of the InfinityRx ICP (InfinityRx Claims Processor) Operator Portal. It covers brand identity, layout architecture, navigation, every page's functional requirements, analytics, ReclaimRx GTN protection, and the AI assistant — all unified into one specification.

### What This Portal Is

The ICP Operator Portal is the internal tool used by the InfinityRx operations team to manage manufacturer copay assistance programs. Operators use it to process claims, manage billing cycles, investigate leakage, monitor pharmacy networks, and serve their manufacturer clients.

### Who Uses It

- **IFX Operators** — process claims, run billing cycles, manage payments (full read-write)
- **IFX Analysts** — investigate leakage, monitor analytics, generate reports (read + investigate)
- **IFX Admins** — configure clients, manage users, system settings (full admin)
- **IFX Viewers** — read-only access to dashboards and reports

The manufacturer's own portal (where the manufacturer logs in to see their program data) is a separate future build. However, operators should be able to "view as manufacturer" — launching a read-only view of what the manufacturer would see on their portal, for support purposes (Appfolio pattern).

### Design Principles

1. **Manufacturer-first** — every dashboard, metric, and workflow is oriented around managing pharmaceutical manufacturer copay programs
2. **Everything drills down** — every stat card, chart element, table row, and KPI is clickable and leads to the underlying records
3. **Configuration over code** — adding a client, changing a fee structure, or modifying a threshold never requires a developer
4. **Operator efficiency** — the most common tasks (claim lookup, investigation triage, billing review) are reachable in 2 clicks or fewer from any page
5. **Data completeness** — detail pages show every field an operator needs, organized in cards and tables, not hidden behind tabs

---

## 2. Brand & Visual Identity

### Colors

Source: InfinityRx 2024 Brand Book

| Token | Hex | Usage |
|-------|-----|-------|
| `--ifx-navy` | `#19286B` | Primary brand color. Sidebar background, headers, primary buttons |
| `--ifx-navy-dark` | `#0D0936` | Deep accents, active states, hover states |
| `--ifx-blue` | `#324AB2` | Secondary buttons, links, interactive elements |
| `--ifx-pink` | `#FF77FF` | Accent highlights, badges, alerts, notification dots, active indicators |
| `--ifx-lavender` | `#EDF0FF` | Light background surfaces, card backgrounds, table alternating rows |
| `--ifx-white` | `#FFFFFF` | Main content background, card surfaces |
| `--ifx-gray-50` | `#F8F9FC` | Page background (very light, not pure white) |
| `--ifx-gray-100` | `#E8EAF0` | Borders, dividers |
| `--ifx-gray-300` | `#9BA3B5` | Secondary text, placeholder text |
| `--ifx-gray-700` | `#374151` | Primary body text |
| `--ifx-gray-900` | `#111827` | Headings, emphasis |
| `--ifx-success` | `#10B981` | Positive values, enabled states, healthy indicators |
| `--ifx-warning` | `#F59E0B` | Caution states, degraded indicators |
| `--ifx-error` | `#EF4444` | Errors, critical alerts, leakage flags |
| `--ifx-info` | `#3B82F6` | Informational badges, tooltips |

**Application rule:** Light background for the main content area (clean, professional work tool). Dark navy for the sidebar. Pink as the accent that draws the eye to important elements (notifications, active nav items, alert badges, new items).

### Typography

| Usage | Font | Weight | Size |
|-------|------|--------|------|
| Headings (H1-H3) | Lato | Bold (700) | 24/20/16px |
| Body text | Lato | Regular (400) | 14px |
| Table headers | Lato | SemiBold (600) | 13px |
| Table data | Lato | Regular (400) | 13px |
| Mono/data (NPIs, NDCs, claim IDs) | IBM Plex Sans Mono | Regular (400) | 13px |
| KPI card values | Lato | Bold (700) | 28px |
| Sidebar nav items | Lato | Medium (500) | 14px |
| Small labels, captions | Lato | Regular (400) | 12px |

Lato is available on Google Fonts (next/font/google). IBM Plex Sans Mono TTFs are in the brand assets folder (self-host via next/font/local).

### Logo

- **Sidebar (collapsed):** IFX infinity mark only (no text), white on navy, 32px
- **Sidebar (expanded):** Full "InfinityRx" logo with infinity mark, white on navy
- **Login page:** Full logo, blue on white, centered above login form
- **Favicon:** Infinity mark, navy on transparent

Logo files: `infinityrx-white.png` (sidebar), `infinityrx-blue.png` (login), `icp.png` (ICP sub-brand for browser tab title)

### Visual Motifs

- Subtle wave line pattern from the brand book `patterns/lines.svg` used as a very faint background on the login page and empty states
- No photographic imagery in the portal UI — this is a work tool, not a marketing site
- Rounded corners: 8px for cards, 6px for buttons, 4px for inputs
- Shadows: Minimal — `0 1px 3px rgba(0,0,0,0.08)` for cards, no heavy drop shadows

---

## 3. Layout Architecture

### Three-Column Layout (Appfolio Pattern)

```
┌──────────┬──────────────────────────────────────────────────┬──────┐
│          │  Top Bar (search, user menu, notifications)       │      │
│          ├──────────────────────────────────────────────────┤      │
│          │  Section Tabs (mirrors sidebar sub-items)         │      │
│  Left    ├──────────────────────────────────────────────────┤ Right│
│ Sidebar  │                                                  │ Strip│
│  (nav)   │              Main Content Area                   │      │
│          │                                                  │      │
│          │  (Filter panel + KPI cards + charts + tables)     │      │
│          │                                                  │      │
│          │                                                  │      │
│          │                                                  │      │
└──────────┴──────────────────────────────────────────────────┴──────┘
```

### Left Sidebar (220px expanded, 60px collapsed)

- Dark navy background (`--ifx-navy`)
- IFX logo at top
- Collapsible module categories with chevrons (▶ collapsed, ▼ expanded)
- Active module highlighted with `--ifx-pink` left border accent + lighter navy background
- Active sub-item highlighted with `--ifx-pink` text
- Icons for each module (lucide-react icon set)
- "Minimize" toggle at bottom to collapse to icon-only mode (60px)
- Scrollable if content exceeds viewport height
- Tenant name at bottom (e.g., "InfinityRx" or "EmkayCo")

### Top Bar (56px height)

- **Left:** Breadcrumb trail (Dashboard > ReclaimRx > Investigations > INV-2024-0012)
- **Center:** Global search bar with ⌘K shortcut — searches entities (claims, pharmacies, prescribers, members, investigations, invoices) not just pages
- **Right:** Notification bell (with pink badge count), user avatar/name, dropdown with profile/settings/logout

### Section Tabs (below top bar, 40px height)

When a sidebar module is selected, its sub-items appear as horizontal tabs across the top of the content area. This mirrors the sidebar sub-items — user can navigate from either place.

Example: Click "Accounting" in sidebar → top tabs show: `Billing Cycles | Invoices | Payments & Batches | NACHA | Journal Entries`

If a sub-item has its own sub-sections (e.g., Claims Explorer has filter tabs), those appear as a second row of smaller tabs below.

### Right Action Strip (48px width)

Thin vertical strip on the far right with icon-only buttons:

- **🤖 Assistant** — opens the AI chat/help panel (sliding overlay)
- **⭐ Tasks** — opens contextual task list (actions relevant to current page)
- **🔔 Notifications** — opens notification panel
- **❓ Support** — opens help documentation

Clicking any icon slides open a panel (400px wide) from the right edge, overlaying the main content. Panel has a close (X) button.

### Main Content Area

- Light gray background (`--ifx-gray-50`)
- Content cards on white backgrounds with subtle shadows
- Maximum content width: none (full width minus sidebar and right strip)
- Responsive: below 1024px, sidebar collapses to icon-only; below 768px, sidebar becomes a hamburger overlay

---

## 4. Navigation Structure

### Complete Sidebar Hierarchy

```
🏠 Dashboard

💊 Programs
   ├── Program Overview
   ├── Enrollment
   ├── Budget & Forecast
   └── Program Configuration

📋 Claims
   ├── Claims Explorer
   ├── Claim Lookup
   ├── Manual Claims
   └── PA Override

💰 Accounting
   ├── Billing Cycles
   ├── Invoices
   ├── Payments & Batches
   ├── NACHA
   └── Journal Entries

🔍 ReclaimRx
   ├── GTN Dashboard
   ├── Leakage Monitor
   ├── Investigations
   ├── Pharmacy Risk Scores
   ├── Recovery Tracking
   └── Case Wizard

📊 Analytics
   ├── Claim Summary
   ├── Fill Performance
   ├── Adherence
   ├── Pharmacy Insights
   ├── Geographic Analysis
   └── Trend Analysis

🏥 Directories
   ├── Pharmacies
   ├── Prescribers
   ├── Drugs / Formulary
   └── Members

👥 Client Management
   ├── Companies
   ├── Client Programs
   ├── Fee Configuration
   ├── Preferred Networks
   ├── Exceptions
   ├── Cardholder IDs
   ├── State Rules
   └── Portal Access

📡 EDI
   ├── Monitor
   ├── Transactions
   ├── Partners
   └── Certificates

🗺️ Network
   ├── Pharmacy Locator
   └── Credentialing

📄 Reporting
   ├── Report Library
   ├── Report Builder
   └── Scheduled Reports

⚙️ Admin
   ├── Users & Roles
   ├── Tenant Settings
   ├── System Health
   ├── Configuration
   ├── Audit Log
   └── Encryption Tools
```

Every top-level item collapses to a single line. Clicking the module name expands/collapses its children. Clicking a child navigates to that page and shows section tabs at the top.

---

## 5. Global Components

These components are used across every page in the portal. Build them once, use everywhere.

### 5.1 Configurable Data Table

The most-used component in the portal. Every list view uses it.

**Features:**
- **Column selector** — gear icon opens a panel listing all available columns with checkboxes. User can show/hide any column. Default columns are pre-selected per table. User preferences persist per table (saved to user profile in the database).
- **Column reordering** — drag column headers to rearrange
- **Column resizing** — drag column borders to resize
- **Sorting** — click any column header to sort asc/desc. Sort indicator visible.
- **Sticky header** — header row stays fixed when scrolling vertically
- **Pinned columns** — first 1-2 columns (typically name/ID) are pinned left when scrolling horizontally
- **Row click** — clicking a row navigates to the detail page for that entity
- **Row hover** — subtle highlight on hover
- **Row selection** — checkbox column for multi-select. "Select all" in header. Bulk action bar appears when rows are selected.
- **Search** — text input above the table that filters across all visible columns
- **Filters** — dropdown filters for key columns (status, type, date range, etc.) — configurable per table
- **Pagination** — "Displaying 1-25 of 1,234" with page size selector (25, 50, 100). For very large datasets (>10K rows), use virtual scrolling instead.
- **Export** — button that exports current view (with active filters) to CSV or Excel
- **Empty state** — "No [entities] found" with contextual message and suggested action
- **Loading state** — skeleton rows while data loads
- **Dollar formatting** — all monetary columns formatted as $X,XXX.XX
- **Date formatting** — consistent MM/DD/YYYY or relative ("2 days ago")
- **NPI/NDC formatting** — monospace font, 10-digit NPI, 11-digit NDC
- **Status badges** — colored pills for status columns (Active/Inactive, Paid/Reversed, Open/Closed)

### 5.2 Detail Page Layout

Every entity (pharmacy, prescriber, drug, member, claim, investigation, invoice, cycle, batch) has a detail page following the same pattern:

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│ ← Back to [list]           Entity Name / ID        [Actions]│
├─────────────────────────────────────────────────────────────┤
│ Summary Cards (3-4 key stats about this entity)             │
├────────────────────┬────────────────────────────────────────┤
│                    │                                        │
│  Info Card 1       │  Info Card 2                          │
│  (Identity/Core)   │  (Financial/Operational)              │
│                    │                                        │
├────────────────────┴────────────────────────────────────────┤
│ Tabbed Sections                                             │
│ [Claims] [Investigations] [History] [Documents] [Config]    │
│                                                             │
│ (Active tab content — usually a Configurable Data Table)    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

- **Back link** — returns to the list view, preserving search/filter/page state
- **Summary cards** — 3-4 key metrics about this entity (e.g., for a pharmacy: total claims, total paid, reversal rate, risk score)
- **Info cards** — organized sections of fields displayed as label: value pairs in a 2-column grid. All fields visible (no "show more" — if there are many fields, use multiple cards)
- **Tabbed sections** — for related data (claims for this pharmacy, investigations involving this prescriber, etc.) — each tab contains a Configurable Data Table
- **Action buttons** — top-right. Context-specific (Edit, Flag for Review, Generate Report, View as Manufacturer, etc.)

### 5.3 Filter Panel

Used on analytics pages and the Claims Explorer. Based on the Power BI filter panel layout.

**Position:** Left side of the main content area, collapsible (can be hidden to give more space to charts/tables)

**Standard filters (available on every analytics page):**
- Date range (date pickers: from/to)
- Period toggle (Monthly / Weekly / Daily / Invoice Cycle)
- Company Name (multi-select dropdown)
- Group ID (multi-select dropdown)
- NCPDP Provider ID (text input)
- NPI Number (text input)
- OCC (multi-select dropdown)
- Network ID (multi-select dropdown)
- Statement Account (multi-select dropdown)
- NDC (text input)
- Drug Name (searchable dropdown)
- Prescriber ID (text input)
- Chain Code (multi-select dropdown)
- Status (multi-select: Paid, Reversed, Pending)
- "Clear all filters" button
- "Save this view" button — saves current filter combination as a named preset

### 5.4 KPI Card Row

Horizontal row of stat cards across the top of dashboard and analytics pages.

**Each card:**
- Label (e.g., "Net Claim Count")
- Value (large, bold, formatted — e.g., "1,710,564" or "$552.58M")
- Trend indicator (↑ 12% or ↓ 5% vs. prior period, color coded green/red)
- **Clickable** — clicking the card navigates to a filtered view showing the underlying records
- Subtle colored top border (using brand colors or semantic colors)

Cards are scrollable horizontally on smaller screens.

### 5.5 Drill-Down Charts

Every chart in the portal follows this pattern:

- **Hover** → tooltip with data point details
- **Click a data point** (bar, slice, line point) → navigates to a filtered table view showing the records behind that data point
- **Legend click** → toggles series visibility
- **Export** → download chart data as CSV
- **Full screen** → expand chart to full viewport

Charts use the IFX brand color palette. Primary series: `--ifx-navy`. Secondary: `--ifx-blue`. Accent: `--ifx-pink`. Additional series use the semantic colors.

---

## 6. Page-by-Page Specifications

### 6.1 Dashboard (`/`)

The operator's home base. Shows a high-level view of program health and recent activity.

**Layout:**
- KPI card row: Active Programs, Total Claims (this period), Total Copay Spend, GTN Ratio, Active Investigations, Pending Payments
- Every KPI card is clickable → navigates to the relevant module
- **Program Health cards** — one card per active manufacturer program showing: program name, claims this period, spend this period, GTN %, active alerts. Click → program detail.
- **Recent Activity feed** — timeline of recent events (new investigations, completed billing cycles, payment batches settled, claims flagged). Each item is clickable → navigates to the event.
- **Alerts & Actions** — items requiring operator attention: billing cycles awaiting approval, investigations needing review, payment batches pending. Click → navigate to the item.
- **Quick Actions** — buttons for common tasks: Look Up Claim, Start Billing Cycle, Create Investigation, Generate Report

**Dashboard is customizable** — operators can rearrange sections via drag-and-drop. Layout preference persists per user.

### 6.2 Programs

#### 6.2.1 Program Overview (`/programs`)

List of all manufacturer copay programs.

**Table columns (default):** Program Name, Manufacturer, Drug(s), Status (Active/Paused/Ended), Active Enrollments, Total Claims (YTD), Total Spend (YTD), GTN Ratio, Budget Remaining
**Click row →** Program detail page

#### 6.2.2 Program Detail (`/programs/[id]`)

**Summary cards:** Total Enrollments, Active Patients, Total Claims, Total Copay Spend, GTN Ratio, Budget Utilization %

**Info cards:**
- Program Configuration: Program name, manufacturer, covered drugs (NDCs), copay card BIN/PCN/Group, max benefit per patient, max fills per patient, annual budget, effective date, term date
- Financial Summary: Total budget, spend to date, remaining, projected annual spend, cost per fill, cost per patient

**Tabs:**
- **Enrollment** — table of enrolled patients (member ID, enrollment date, fills to date, spend to date, status)
- **Claims** — all claims for this program (standard claims table)
- **Leakage** — ReclaimRx investigations and flags specific to this program
- **Budget** — budget vs. actual chart (monthly), burn rate trending, forecast line
- **Configuration** — editable program settings (all fields from info card, editable in-place)

#### 6.2.3 Enrollment (`/programs/enrollment`)

Enrollment analytics across all programs.

**Charts:** New enrollments by period, active patients trending, enrollment by source/channel
**Table:** Recent enrollments with patient ID, program, enrollment date, first fill date, status

#### 6.2.4 Budget & Forecast (`/programs/budget`)

**Charts:** Budget vs. actual (all programs, stacked), burn rate trending, forecast
**Table:** Per-program budget summary: Program, Annual Budget, Spend to Date, Remaining, Projected Year-End, Variance

#### 6.2.5 Program Configuration (`/programs/config`)

Admin page for creating/editing programs. Form-based with all program fields. This is a configuration page, not analytics — operators can create new programs, modify budgets, update covered NDCs, change eligibility rules, all from the UI. No backend developer needed.

---

### 6.3 Claims

#### 6.3.1 Claims Explorer (`/claims`)

The primary claims view. Replaces the current portal's "Claims Lookup" and the new portal's `/billing/claims`.

**Filter panel** (left side, collapsible) — full filter set from Section 5.3

**KPI card row:** Total Claims, Net Claims, Total Benefit Spend, Average Benefit, Reversal Rate, Abandonment Rate

**Period toggle:** Monthly / Weekly / Daily / Invoice Cycle

**Table:** Configurable Data Table with all claim fields available as columns.

**Default columns:** Date, Type (Claim/Reversal), Pharmacy Name, NPI, Rx#, Fill#, Drug Name, NDC, Patient Name, Auth#, OCC, Status, Paid Amount, Copay Amount

**Available columns (user can add):** Patient DOB, Card Holder ID, Group ID, Control ID, Coverage Code, BIN, Network, Prescriber ID, Prescriber Name, Days Supply, Quantity, Ingredient Cost, Dispensing Fee, Sales Tax, Patient Paid Amount, Transaction Fee, Debit Card Amount, POS Adjustment, Incentive Fee, Chain Code, Statement Account, Reject Code, Date of Service, Place of Service, Diagnosis Code, GPI, Therapeutic Class

**Click row →** Claim detail page

#### 6.3.2 Claim Detail (`/claims/[id]`)

**THIS PAGE DOES NOT EXIST TODAY. It is the single highest-ROI fix from the UX audit.**

**Summary cards:** Total Paid, Patient Responsibility, Copay Assistance, Claim Status

**Info cards:**
- **Patient Information:** Cardholder ID, First Name, Last Name, DOB, Sex, Address, Phone, Email, MRN, Claim ID (fields from current portal's manual claims form)
- **Provider Information:** Billing Provider NPI, Federal Tax ID, Billing Provider Name, Address, Phone, Fax, Email, Service Provider NPI, Service Provider Name, Address
- **Claim Information:** Rx Number, Claim Type, Claim Disposition, Status, Date Added, Other Coverage Code, IFX Group ID, BIN/Other Payer ID, Insurance Type, Insured's ID, Policy Group, Plan Name, Fill Number, Reject Reason, Date of Service From/To, Place of Service, Emergency Indicator, NDC, Drug Name, CPT/HCPS, JCode Modifier, Diagnosis Codes, Units, Days Supply, Quantity
- **Financial:** Ingredient Cost, Dispensing Fee, Sales Tax, Copay Amount, Patient Paid, Plan Paid, Total Paid, POS Adjustment, Debit Card Amount, Transaction Fee, Incentive Fee
- **Copay Program:** Program Name, Card BIN/PCN/Group, Copay Assistance Amount, Remaining Benefit, Enrollment Date

**Tabs:**
- **Reversal History** — if this claim has been reversed, show the reversal chain (original → reversal → resubmission)
- **Related Claims** — other claims for the same patient, same drug, or same pharmacy
- **Investigation** — if this claim is part of a ReclaimRx investigation, link to it
- **Attachments** — any uploaded documents (PDFs from the current portal's manual claims)

**Actions:** Flag for Review, Create Investigation, View in Batch, View Invoice

#### 6.3.3 Manual Claims (`/claims/manual`)

Matches the current portal's Manual Claims Management page. Full claim entry form with all fields from the current portal (Patient Information, Provider Information, Claim Information, Financial Information sections). Attachments upload. Submit/Close buttons.

#### 6.3.4 PA Override (`/claims/pa-override`)

Prior authorization override management. Table of PA override requests with status, approval/denial actions.

---

### 6.4 Accounting

#### 6.4.1 Billing Cycles (`/accounting/cycles`)

**Table:** Cycle ID, Dates (from-to), Status (Draft/Approved/Settled), Total Claims, Total Paid, Fee Total, Created By, Created Date
**Click row →** Cycle detail page

**Cycle Detail (`/accounting/cycles/[id]`):**
- Summary cards: Total Claims, Total Paid, Total Fees, Net Amount
- Info card: Cycle dates, status, approval workflow (who approved, when), settlement date
- Tabs:
  - **Claims** — all claims in this cycle (configurable table)
  - **AR Entries** — accounts receivable entries generated
  - **AP Entries** — accounts payable entries generated
  - **Journal Entries** — virtual transfer journal entries
  - **SaaSant Preview** — preview of what the SaaSant Excel workbook will contain (tabs, totals)
  - **835 Preview** — list of 835 files that would be generated, with pharmacy/NPI/chain grouping
  - **NACHA Preview** — ACH transactions that would be generated
- Actions: Approve Cycle, Reject Cycle, Generate Outputs, Settle

#### 6.4.2 Invoices (`/accounting/invoices`)

**Table:** Invoice Number, Client, Period, Total Amount, Status (Draft/Sent/Paid), Due Date, Paid Date
**Click row →** Invoice detail with line items, PDF download, mark as paid

#### 6.4.3 Payments & Batches (`/accounting/payments`)

**Table:** Batch ID, Type (Check/ACH), Status, Total Amount, Claims Count, Created Date, Settled Date
**Click row →** Batch detail with individual payments, claim assignments

#### 6.4.4 NACHA (`/accounting/nacha`)

NACHA file generation and history. Table of generated files with download links, settlement status.

#### 6.4.5 Journal Entries (`/accounting/journal-entries`)

Virtual transfer journal entries. Table with date, type (AP/AR/Transfer), accounts, amounts, QB class assignments.

---

### 6.5 ReclaimRx — GTN Protection Engine

**This is the core value proposition of the platform for manufacturer clients.**

#### 6.5.1 GTN Dashboard (`/reclaimrx`)

The landing page for ReclaimRx. Shows the gross-to-net health of all manufacturer programs.

**KPI card row:**
- Total Copay Spend (YTD)
- Identified Leakage (YTD, $ amount)
- GTN Ratio (with trend arrow)
- Active Investigations
- Recovered (YTD, $ amount)
- Recovery Rate (% of identified leakage recovered)

**Every card is clickable → drills to the relevant view**

**Charts:**
- **GTN Trend** — line chart showing GTN ratio over time (monthly). Click a month → filtered claims for that period.
- **Leakage by Category** — pie/donut chart breaking leakage into: Pharmacy Misuse, Accumulator Programs, Maximizer Programs, 340B Overlap, Other. Click a slice → filtered investigation list for that category.
- **Leakage by Program** — horizontal bar chart showing leakage $ per manufacturer program. Click a bar → program-specific leakage detail.
- **Top Flagged Pharmacies** — table of pharmacies with highest leakage, with risk score, total leakage $, investigation status. Click row → pharmacy detail.

**Recent Alerts** — list of new flags and investigations needing attention.

#### 6.5.2 Leakage Monitor (`/reclaimrx/leakage`)

Detailed leakage analysis with the full filter panel.

**Leakage categorization:**
- **Pharmacy Misuse** — duplicate claims, override abuse, fake patients, copay exceeding drug cost
- **Accumulator Programs** — payer plans excluding copay from deductible
- **Maximizer Programs** — payer plans reclassifying drug as non-essential
- **340B Overlap** — claims where 340B pricing and copay assistance both applied
- **Alternative Funding** — patients redirected to charity foundations
- **Prescriber Anomaly** — prescribers with outlier patterns
- **Patient Anomaly** — patients with suspicious enrollment or fill patterns

**Table:** All flagged claims/patterns with: Flag ID, Category, Pharmacy/Prescriber/Patient, Estimated Leakage $, Status (New/Under Investigation/Confirmed/Dismissed), Date Flagged
**Click row →** Investigation detail

#### 6.5.3 Investigations (`/reclaimrx/investigations`)

**Dual view:** Toggle between Kanban board and Table view

**Kanban columns:** New → Under Review → Escalated → Confirmed → Recovery → Closed

**Card content:** Investigation ID, subject (pharmacy/prescriber name), leakage category badge, estimated $ impact (prominently displayed), assigned analyst, days open, severity badge

**Click card →** Investigation detail

**Table view alternative:** Same data as Kanban but in the Configurable Data Table format for bulk triage.

**Filters:** Category, Severity, Assigned To, Date Range, Status, Program

#### 6.5.4 Investigation Detail (`/reclaimrx/investigations/[id]`)

**Summary cards:** Estimated Leakage, Confirmed Leakage, Recovered Amount, Days Open

**Info card:** Investigation ID, Category (from leakage types), Subject Entity (pharmacy NPI + name or prescriber NPI + name), Program(s) affected, Severity, Status, Assigned Analyst, Date Opened, Last Activity

**Tabs:**
- **Evidence** — checklist of evidence items, toggleable, with ability to add new items
- **Flagged Claims** — table of all claims tied to this investigation (full claim fields, clickable to claim detail)
- **Related Entities** — other pharmacies, prescribers, or patients connected to this pattern
- **Activity Timeline** — chronological log of all actions, notes, status changes
- **Documents** — uploaded evidence files, generated letters
- **Recovery** — recovery status, amounts, method (offset, demand letter, legal)

**Actions:** Escalate, Assign, Add Note, Generate Recovery Letter, Close Investigation, Dismiss

#### 6.5.5 Pharmacy Risk Scores (`/reclaimrx/risk`)

**Table:** All pharmacies in the network with their risk score (0-100), risk factors, leakage history, total claims, total copay paid, reversal rate, active investigations.

**Scoring factors visible per pharmacy:**
- Claim volume anomaly (vs. peer pharmacies)
- Rejection rate on payer claims
- Override usage frequency
- Fill frequency per patient
- Copay-to-total ratio
- Known investigation history
- Chain vs. independent classification

**Click row →** Pharmacy detail page (in Directories) with risk tab highlighted

#### 6.5.6 Recovery Tracking (`/reclaimrx/recovery`)

**KPI cards:** Total Identified, Total Recovered, Recovery Rate, Pending Recovery, Average Time to Recover

**Table:** Recovery ID, Investigation ID, Pharmacy/Entity, Estimated Amount, Actual Recovered, Method (Offset/Demand/Legal), Status (Pending/In Progress/Recovered/Written Off), Date Initiated, Date Closed

**Click row →** Recovery detail with full history

#### 6.5.7 Case Wizard (`/reclaimrx/wizard`)

Guided workflow for creating a new investigation. Steps:
1. Select category (leakage type)
2. Identify subject entity (pharmacy, prescriber, or patient — searchable)
3. Select flagged claims (from pre-flagged or manual selection)
4. Estimate leakage amount
5. Assign analyst
6. Add initial notes
7. Review & create

---

### 6.6 Analytics

All analytics pages are built for operators analyzing manufacturer copay program performance. Every page has the Filter Panel (Section 5.3) on the left, KPI cards at the top, drill-down charts in the center, and exportable tables below.

#### 6.6.1 Claim Summary (`/analytics/claims`)

Replaces Power BI Claim Summary page.

**KPI card row:** Claim Count, Ingredient Cost, Sales Tax, Patient Paid, Dispensing Fee, Paid Claim, Copay Assistance Total, Transaction Fee
**Period toggle:** Monthly / Weekly / Daily / Invoice Cycle
**Charts:**
- Net Claim Count by Period (bar chart — click bar → filtered claims)
- New Enrollment by Period (bar chart)
- Claim Count by Status (Paid vs. Reversed — stacked bar)
- Claims by OCC (horizontal bar)

**Table:** Period breakdown with Net Claim Count, Total Benefit Spend, Average Benefit, Abandonment Rate, Total Pharmacies, Copay Spend

#### 6.6.2 Fill Performance (`/analytics/fills`)

Manufacturer-specific fill analytics.

**KPI cards:** Total Fills, New Starts (NBRx), Refills, Avg Fills per Patient, Avg Days Supply
**Charts:**
- Fills by period (new vs. refill stacked bar)
- Fills by pharmacy type (retail/mail/specialty pie)
- Fills by chain (top 10 horizontal bar)
- Days supply distribution (30/60/90 bar)

**Table:** Drug-level fill detail — Drug Name, NDC, Company Name, Net Fills, New Starts, Refills, Avg Quantity, Avg Days Supply, Total Spend

#### 6.6.3 Adherence (`/analytics/adherence`)

**KPI cards:** Overall PDC, Persistence at 6 months, Persistence at 12 months, Avg Fills per Patient
**Charts:**
- PDC distribution (histogram — what % of patients are at each PDC level)
- Persistence curve (Kaplan-Meier style — % still filling at 1, 2, 3... 12 months)
- Adherence by pharmacy (top/bottom 10)
- Adherence with copay card vs. without (side-by-side comparison — the ROI proof)

**Table:** Patient-level adherence — Patient ID, Drug, PDC, Fills, First Fill, Last Fill, Status (Adherent/Non-Adherent/Discontinued)

#### 6.6.4 Pharmacy Insights (`/analytics/pharmacies`)

Replaces Power BI Pharmacy Insights page.

**KPI cards:** Total Pharmacies, Avg Claims per Pharmacy, Avg Benefit per Pharmacy, Total Spend
**Charts:**
- Claims by Pharmacy State (geographic heat map)
- Top 20 pharmacies by claim volume (horizontal bar)
- Pharmacy type distribution (retail/mail/specialty/340B)

**Table:** Pharmacy Name, NPI, NCPDP, State, Net Claims, % Covered, Total Spend, Avg Benefit, Abandonment Rate, Risk Score
**Click row →** Pharmacy detail

#### 6.6.5 Geographic Analysis (`/analytics/geography`)

**Map view:** Interactive state-level heat map (claim volume or spend) — click state → filtered view
**Table:** State-level breakdown with claim count, spend, pharmacy count, avg benefit

#### 6.6.6 Trend Analysis (`/analytics/trends`)

**Trend decomposition** — answers "why did spend change?"

**Charts:**
- Total spend trending (line, YoY comparison)
- Trend decomposition: utilization change + unit cost change + mix change = total change (waterfall chart)
- Top movers (drugs/pharmacies with biggest cost increases and decreases)

**Table:** Period-over-period comparison with $ change and % change for each metric

---

### 6.7 Directories

Every directory page uses the Configurable Data Table. Every row clicks through to a comprehensive detail page.

#### 6.7.1 Pharmacies (`/directories/pharmacies`)

**Default columns:** Pharmacy Name, NPI, NCPDP, Chain Code, State, City, Phone, Status, Risk Score
**Click row →** Pharmacy detail

**Pharmacy Detail (`/directories/pharmacies/[npi]`):**

**Summary cards:** Total Claims, Total Paid, Reversal Rate, Risk Score

**Info cards (ALL of these fields displayed):**
- **Identity:** Pharmacy Name, NPI, NCPDP ID, DEA Number, Store Number, Tax ID
- **Chain & Network:** Chain Code, Pay-To Provider Name, Pay-To Provider ID, Reconciliation Vendor, Network Participation (list of networks), Contract Effective/Term Dates
- **Classification:** Dispensing Class (Retail/Mail/Specialty/LTC/340B), Billing Taxonomy, 340B Status, Specialty Designations
- **Contact:** Full Address, Phone, Fax, Email, Contact Person Name
- **Operational:** State License Numbers, Accreditations, Hours of Operation

**Tabs:**
- **Claims** — all claims for this pharmacy (configurable table, filterable)
- **Prescribers** — prescribers who send scripts to this pharmacy
- **Investigations** — ReclaimRx investigations involving this pharmacy
- **DataQ** — data quality metrics: claim rejection rate by reason, field completeness scores, common reject codes, response times, SLA compliance
- **Risk Analysis** — risk score breakdown, anomaly factors, historical risk trending
- **Financial** — payment history, average paid per claim, copay amounts, fee breakdown

#### 6.7.2 Prescribers (`/directories/prescribers`)

**Default columns:** Prescriber Name, NPI, Specialty, DEA, State, Total Claims, Top Drug
**Click row →** Prescriber detail

**Prescriber Detail:**
- Identity: NPI, Name, Specialty, DEA, State License, Address
- Prescribing Patterns: Total Claims, Top Drugs (table), Avg Claims per Month, Claim Volume Trend
- Tabs: Claims, Affiliated Pharmacies, Investigations

#### 6.7.3 Drugs / Formulary (`/directories/drugs`)

**Default columns:** Drug Name, NDC, Generic Name, Manufacturer, Strength, Dosage Form, GPI, Therapeutic Class
**Click row →** Drug detail

**Drug Detail:**
- Identity: NDC, Drug Name, Generic Name, Manufacturer, Strength, Dosage Form, Route
- Classification: GPI, Therapeutic Class, Brand/Generic, Specialty Flag, REMS Status
- Pricing: AWP, WAC, MAC (if available)
- Tabs: Claims (all claims for this NDC), Prescribers (who prescribes it), Pharmacies (who dispenses it)

#### 6.7.4 Members (`/directories/members`)

**Default columns:** Member ID, Name, DOB, Group, Plan, Status, Total Claims
**Click row →** Member detail

**Member Detail:**
- Identity: Member ID, Name, DOB, Group Number, Plan Name, Effective/Term Dates, Coverage Type
- Copay Program: Enrolled programs, card status, remaining benefit
- Tabs: Claims, Prescriptions, Adherence, Eligibility History

---

### 6.8 Client Management

#### 6.8.1 Companies (`/clients`)

Replaces current portal's Client Management page.

**Table:** Company Name, BIN, Federal ID, City, State, Status (Enabled/Disabled), Programs Count
**Actions per row:** View, Edit, Payment Setup, Delete (with confirmation)
**Click row →** Company detail

**Company Detail (`/clients/[id]`):**

**Tabs (matching current portal):**
- **Client Details** — company name, address, BIN, Federal ID, contact info, all editable
- **Client Profile** — fee configuration: Account Setup (IBL Setup Fee, ICP Setup Fee, Pharmacy Trans Fee, Claim Processing Fee, Pharmacy Disp Fee, Minimum Balance, Opening Balance), Monthly Recurring Payments (ICP Service Fee, IBL Service Fee with start/end dates) — ALL editable
- **Client Programs** — copay programs for this manufacturer, linked to Programs module
- **Statement Providers** — provider configurations
- **Blocked Providers** — blocked pharmacy list

#### 6.8.2 Client Programs (`/clients/programs`)

Cross-client view of all programs. Same as Programs module but organized by client.

#### 6.8.3 Fee Configuration (`/clients/fees`)

Master fee schedule management. Table of all fee types with current rates, effective dates. All editable from the UI.

#### 6.8.4 Preferred Networks, Exceptions, Cardholder IDs, State Rules

Each is a configuration table with full CRUD from the UI. Matches the current portal's Client Support sub-pages but in the new layout.

#### 6.8.5 Portal Access (`/clients/portal-access`)

"View as Manufacturer" — select a client → launches a read-only view showing what that manufacturer would see on their portal. Operator can click around, see the same dashboards and data, but cannot make changes. Used for support calls (Appfolio pattern).

---

### 6.9 EDI

#### 6.9.1 Monitor (`/edi/monitor`) — Connection health with status indicators, click for detail
#### 6.9.2 Transactions (`/edi/transactions`) — Transaction list, click for raw EDI content
#### 6.9.3 Partners (`/edi/partners`) — Partner config, endpoints, certificates
#### 6.9.4 Certificates (`/edi/certs`) — Certificate management

---

### 6.10 Network

#### 6.10.1 Pharmacy Locator (`/network/locator`)

Google Maps integration with search by address, distance, specialty filters, network filters. Matches current portal's Pharmacy Map but modernized.

#### 6.10.2 Credentialing (`/network/credentialing`)

Pharmacy credentialing status tracking. Table with pharmacy name, NPI, credentialing status, documents, expiration dates.

---

### 6.11 Reporting

#### 6.11.1 Report Library — Pre-built report templates
#### 6.11.2 Report Builder — Drag-and-drop custom report builder with data source selection, field picker, filter configuration, preview
#### 6.11.3 Scheduled Reports — Automated report generation on schedule, email delivery

---

### 6.12 Admin

#### 6.12.1 Users & Roles (`/admin/users`)

User management with CRUD. Role assignment (Admin, Operator, Analyst, Viewer). Permission matrix visible and editable.

#### 6.12.2 Tenant Settings (`/admin/tenants`)

Tenant configuration: MFA requirements, max concurrent sessions, feature flags (toggleable from UI).

#### 6.12.3 System Health (`/admin/system-health`)

Real-time status indicators for all system components. Auto-refreshing. Click degraded/unhealthy → detail view.

#### 6.12.4 Configuration (`/admin/config`)

**This must be a real configuration page, not fake.** System-wide settings organized in sections:
- **Billing:** Default fee structures, billing cycle rules, SaaSant template settings
- **Payments:** NACHA settings, bank account configurations, payment routing rules
- **Claims:** Adjudication thresholds, reject code mappings, override rules
- **ReclaimRx:** Detection thresholds, risk scoring weights, alert rules
- **EDI:** Endpoint configurations, partner settings, retry policies
- **Notifications:** Email settings, alert thresholds, escalation rules

Every setting is editable from the UI. Changes are logged in the audit trail.

#### 6.12.5 Audit Log (`/admin/audit-log`)

Searchable log of all system actions: who did what, when, on which entity. Filterable by user, action type, entity type, date range.

#### 6.12.6 Encryption Tools (`/admin/encryption`)

Matches current portal's Encryption Tool.

---

## 7. AI Assistant / Help Panel

Accessible from the right action strip (🤖 icon). Opens as a sliding panel from the right.

### 7.1 Panel Layout

```
┌──────────────────────────────┐
│  IFX Assistant          [X]  │
├──────────────────────────────┤
│ ┌──────────────────────────┐ │
│ │  [Ask a Question]       │ │
│ │  [Search Documentation] │ │
│ │  [Data Insights]        │ │
│ │  [How-To Guides]        │ │
│ └──────────────────────────┘ │
│                              │
│  Chat history / results      │
│                              │
│                              │
│                              │
├──────────────────────────────┤
│  [Type your question...]     │
│                     [Send]   │
└──────────────────────────────┘
```

### 7.2 Capabilities

- **Ask a Question** — natural language query about the system, data, or processes. Uses the AI Query Tool pattern from the current portal (SQL Assistant) but upgraded.
- **Search Documentation** — searches all IFX documentation, user manuals, process guides. Returns relevant sections with links.
- **Data Insights** — context-aware data queries. "How many claims did Axsome have last month?" → queries the data and returns the answer with a chart.
- **How-To Guides** — step-by-step walkthroughs for common tasks. "How do I start a billing cycle?" → guided tutorial.

### 7.3 Context Awareness

The assistant knows which page the operator is on and can provide context-specific help. If the operator is on the pharmacy detail page and asks "what's the risk score for this pharmacy?", the assistant already knows which pharmacy is being viewed.

---

## 8. Data Requirements

### 8.1 New Data Entities Needed (not in current data model)

1. **Programs** — copay program configuration (name, manufacturer, NDCs, BIN/PCN/Group, budget, dates)
2. **Enrollments** — patient enrollment in copay programs (patient ID, program ID, enrollment date, card status, benefit remaining)
3. **Leakage Flags** — categorized leakage detections (flag ID, category, entity, claims, estimated $, status)
4. **Risk Scores** — pharmacy risk scores (NPI, score, factors, last calculated)
5. **User Preferences** — per-user table column configurations, dashboard layouts, saved filter presets
6. **Budget Tracking** — program budgets with actual spend tracking
7. **Recovery Records** — recovery cases with estimated/actual/method/status (extends current ReclaimRx)

### 8.2 Fields Needed on Existing Entities

**Pharmacy (add to directory):** Chain Code, Pay-To Provider Name/ID, Reconciliation Vendor, Dispensing Class, 340B Status, Network Participation, Contract Dates — these exist in the claim stream but need to be joined/materialized on the pharmacy entity.

**Claim (add to detail):** Program ID (which copay program), Copay Assistance Amount (manufacturer's copay contribution), Leakage Category (if flagged), Investigation ID (if part of an investigation)

**Investigation (add):** Leakage Category, Estimated Dollar Impact, Confirmed Dollar Impact, Program(s) Affected, Recovery Status, Recovery Amount

---

## 9. Build Sequence & Agent Team Strategy

### Agent Team Overview

Claude Code supports up to 7 parallel agents, each in its own git worktree. For this project, we use a phased approach: single-agent for foundation work (shared components), then 4-5 parallel agents for module builds.

**Hardware requirements (MacBook Pro):**
- 32GB RAM → safe for 3-4 concurrent agents
- 64GB RAM → safe for 5-6 concurrent agents
- Claude Max 20x subscription handles the token throughput for 5 parallel agents

**Key constraint:** Agents must work on different file paths. Two agents editing the same file = merge conflicts. The architecture is designed so each module lives in its own route directory (`app/reclaimrx/`, `app/claims/`, etc.) and its own component directory — natural worktree boundaries.

**Enable agent teams:**
```json
// settings.json
{ "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }
```

---

### Phase 1A — Foundation (Single Agent, Sessions 1-2)

**Why single agent:** This phase builds the shared components that every module depends on. Parallel agents would collide on the same files.

**One agent builds:**

1. **Brand theme swap**
   - Replace Inter → Lato (next/font/google)
   - Replace JetBrains Mono → IBM Plex Sans Mono (next/font/local from brand assets)
   - Replace color palette in `app/globals.css` @theme block with IFX brand colors (#19286B, #FF77FF, #EDF0FF, #324AB2, #0D0936)
   - Add IFX logo to sidebar and login page
   - Update favicon to IFX infinity mark

2. **Layout architecture**
   - Rebuild `components/layout/app-shell.tsx` as three-column layout (sidebar + main + right strip)
   - Build collapsible sidebar component with the full hierarchy from Section 4
   - Build section tabs component (mirrors sidebar sub-items across top of content area)
   - Build right action strip (Assistant, Tasks, Notifications, Support icons + sliding panel skeleton)
   - Build top bar with breadcrumbs, global search bar, user menu

3. **Shared components** (consumed by all modules)
   - `components/ui/configurable-data-table.tsx` — the reusable table with column selector, sorting, pinning, export, bulk actions, user preference persistence
   - `components/ui/detail-page-layout.tsx` — the standard detail page template (back link, summary cards, info cards, tabbed sections, action buttons)
   - `components/ui/filter-panel.tsx` — the collapsible filter panel matching Power BI depth
   - `components/ui/kpi-card.tsx` — clickable stat card with value, trend indicator, drill-down link
   - `components/ui/drill-down-chart.tsx` — chart wrapper that handles hover tooltips, click-to-filter, legend toggle, export
   - `components/ui/status-badge.tsx` — colored pills for status columns
   - `components/ui/column-selector.tsx` — the show/hide column panel with user persistence

4. **Claim Detail page** (`app/claims/[id]/page.tsx`)
   - Highest-ROI missing page from the UX audit
   - Uses the detail page layout template
   - All fields from Section 6.3.2

5. **Global search upgrade**
   - Replace 7-entry page-nav command palette with entity search
   - Searches: claims (by ID, auth#), pharmacies (by name, NPI), prescribers (by name, NPI), members (by name, ID), investigations (by ID), invoices (by number)
   - Results link to detail pages

6. **Test infrastructure update**
   - Update existing 96 tests for new layout/theme
   - Add component tests for new shared components
   - `npm run qa` must pass before moving to Phase 1B

**Deliverable:** Merge to main. All existing pages work with the new layout, theme, and shared components. The portal looks like IFX and navigates like Appfolio. `npm run qa` green.

---

### Phase 1B — Core Modules (4-5 Parallel Agents, Sessions 3-4)

**Why parallel:** Each agent works in its own worktree on a separate module. No shared file conflicts. All agents consume the shared components built in Phase 1A but don't modify them.

**Setup:**
```bash
# Agent 1 — ReclaimRx
claude --worktree reclaimrx-rebuild

# Agent 2 — Claims + Accounting  
claude --worktree claims-accounting

# Agent 3 — Directories
claude --worktree directories-detail

# Agent 4 — Dashboard + Programs
claude --worktree dashboard-programs

# Agent 5 (optional) — Analytics foundation
claude --worktree analytics-rebuild
```

**Agent 1: ReclaimRx (worktree: `reclaimrx-rebuild`)**
- Files: `app/reclaimrx/**`, `components/reclaimrx/**`
- Builds:
  - GTN Dashboard (`/reclaimrx`) — KPI cards (Total Spend, Identified Leakage, GTN Ratio, Active Investigations, Recovered, Recovery Rate), GTN trend chart, leakage by category pie, leakage by program bar, top flagged pharmacies table. All clickable.
  - Leakage Monitor (`/reclaimrx/leakage`) — categorized leakage table with filter panel, dollar amounts, drill-down
  - Investigation detail upgrade — add leakage category, estimated/confirmed dollar impact, program(s) affected, recovery tab
  - Pharmacy Risk Scores (`/reclaimrx/risk`) — scoring table with risk factors breakdown
  - Recovery Tracking upgrade — KPI cards, recovery detail with method/status/amounts
  - Investigation Kanban upgrade — cards show dollar amounts prominently, leakage category badges
  - Case Wizard — guided investigation creation flow
- Mock data: Add leakage categories, GTN metrics, risk scores to seed data
- Tests: E2E tests for GTN dashboard drill-down, investigation categorization, recovery workflow

**Agent 2: Claims + Accounting (worktree: `claims-accounting`)**
- Files: `app/claims/**`, `app/accounting/**`, `components/claims/**`, `components/accounting/**`
- Builds:
  - Claims Explorer — rebuild with Configurable Data Table, full filter panel, all available columns from Section 6.3.1
  - Manual Claims — match current portal's form (Patient Info, Provider Info, Claim Info, Financial Info sections)
  - PA Override page
  - Billing Cycles list + detail with SaaSant/835/NACHA preview tabs
  - Invoices list + detail with line items and PDF download
  - Payments & Batches list + detail
  - NACHA file management
  - Journal Entries view
  - All table rows clickable to detail pages
  - All action buttons functional (approve, reject, settle, generate)
- Tests: E2E tests for claims drill-down, billing cycle workflow, invoice detail

**Agent 3: Directories (worktree: `directories-detail`)**
- Files: `app/directories/**`, `components/directories/**`
- Builds:
  - Pharmacy detail page — ALL fields from Section 6.7.1 (identity, chain/network, classification, contact, operational). Tabs: Claims, Prescribers, Investigations, DataQ, Risk Analysis, Financial
  - Prescriber detail page — all fields, tabs for claims/pharmacies/investigations
  - Drug detail page — all fields including pricing, tabs for claims/prescribers/pharmacies
  - Member detail page — all fields, copay program info, tabs for claims/prescriptions/adherence/eligibility
  - All list pages use Configurable Data Table with appropriate default columns
  - Privacy masking on member PHI fields
- Mock data: Enrich pharmacy seeds with chain code, pay-to, recon vendor, dispensing class. Enrich drug seeds with GPI, pricing. Enrich member seeds with copay enrollment.
- Tests: E2E tests for each detail page, drill-through from list to detail

**Agent 4: Dashboard + Programs + Client Management (worktree: `dashboard-programs`)**
- Files: `app/page.tsx` (dashboard), `app/programs/**`, `app/clients/**`, `components/programs/**`, `components/clients/**`
- Builds:
  - Dashboard redesign — KPI cards (all clickable), program health cards, activity feed (with onEventClick), alerts & actions, quick action buttons
  - Program Overview list + detail (Section 6.2)
  - Program Enrollment analytics
  - Budget & Forecast page with budget vs. actual chart
  - Program Configuration (CRUD from UI)
  - Client Management — Companies list + detail matching current portal (Client Details, Client Profile with fee config, Client Programs, Statement Providers, Blocked Providers tabs). All editable.
  - Fee Configuration master page
  - Preferred Networks, Exceptions, Cardholder IDs, State Rules — configuration tables with CRUD
  - Portal Access — "view as manufacturer" read-only mode
- Tests: E2E tests for dashboard widget click-through, program CRUD, client fee editing

**Agent 5 (optional): Analytics Foundation (worktree: `analytics-rebuild`)**
- Files: `app/analytics/**`, `components/analytics/**`
- Builds:
  - Claim Summary — replicate Power BI page 1 with full filter panel, KPI cards, period toggle, drill-down charts
  - Fill Performance — NBRx, fills by type/chain/geography, days supply distribution
  - Adherence — PDC, persistence curve, adherence by pharmacy, copay impact comparison
  - Pharmacy Insights — replicate Power BI page 3 with state heat map
  - Geographic Analysis — interactive state map
  - Trend Analysis — YoY trending with decomposition (utilization vs. unit cost vs. mix)
  - All charts drill down to underlying records
  - Export on every chart and table
- Tests: E2E tests for filter panel, chart drill-down, export

**Merge strategy:** Each agent works on its own branch. When an agent completes its module:
1. Agent runs `npm run qa` in its worktree
2. Agent merges main into its branch (pick up any changes from other agents that already merged)
3. Agent resolves any conflicts (should be rare since modules are isolated)
4. You review the diff and merge to main
5. Other agents pull main to pick up the newly merged module

**Merge order (recommended):** Agent 3 (Directories) → Agent 2 (Claims) → Agent 1 (ReclaimRx) → Agent 4 (Dashboard) → Agent 5 (Analytics). This order works because later agents may link to detail pages built by earlier agents.

---

### Phase 1C — Integration + Analytics Deep Dive (3-4 Parallel Agents, Sessions 5-6)

After Phase 1B merges, all modules exist but may need cross-module wiring. This phase connects everything and builds the remaining pages.

**Agent 1: Cross-Module Drill-Down Wiring (worktree: `drill-down-wiring`)**
- Wire every stat card on every page to its target (e.g., ReclaimRx "Active Investigations" → filtered investigations list)
- Wire every chart click to a filtered table view
- Wire every dashboard widget to its target module
- Ensure breadcrumbs work across all navigation paths
- Test all drill-down chains end-to-end

**Agent 2: Admin + EDI + Network (worktree: `admin-edi-network`)**
- Admin Configuration page — real settings with editable fields, organized by section (Billing, Payments, Claims, ReclaimRx, EDI, Notifications). Save button. Audit trail.
- Users & Roles with full CRUD and permission matrix
- Tenant Settings with toggleable features
- System Health with auto-refresh and click-to-detail
- Audit Log with full search/filter
- EDI Monitor, Transactions (with raw EDI content view), Partners, Certificates
- Network — Pharmacy Locator (Google Maps integration), Credentialing
- Encryption Tools

**Agent 3: Reporting + Export (worktree: `reporting-export`)**
- Report Library with pre-built templates
- Report Builder — drag-and-drop field selection, filter configuration, preview
- Scheduled Reports — schedule configuration, email delivery setup
- Make all 7+ export buttons functional across the portal (CSV + Excel)
- Ensure every Configurable Data Table's export respects active filters

**Agent 4: Test Suite Expansion (worktree: `test-expansion`)**
- Add E2E tests for every new page from Phase 1B
- Add regression tests for all drill-down chains
- Add component tests for Configurable Data Table (column selector, persistence, export)
- Add tests for client configuration CRUD
- Add tests for program management CRUD
- Update `npm run qa` to cover new modules
- Target: 200+ total tests (up from current 96)

---

### Phase 1D — AI Assistant + Polish (2-3 Agents, Session 7)

**Agent 1: AI Assistant (worktree: `ai-assistant`)**
- Build the sliding panel UI (Section 7)
- Integrate with Claude API for natural language queries
- Documentation search — index all IFX docs, user manuals, process guides
- Data insights — context-aware queries ("How many claims did Axsome have last month?")
- How-to guides — step-by-step walkthroughs for common tasks
- Context awareness — assistant knows which page operator is viewing

**Agent 2: Tasks Panel + Notifications (worktree: `tasks-notifications`)**
- Tasks panel — contextual action links per module (e.g., on Accounting page: "Create Billing Cycle", "Generate NACHA", "Reconcile Payments")
- Notification system — bell icon with badge count, notification panel, notification preferences
- Email notification triggers (new investigation, payment settled, billing cycle awaiting approval)

**Agent 3: Final QA + Polish (worktree: `final-polish`)**
- Full adversarial browser QA (re-run the comprehensive QA from earlier, updated for redesign)
- Fix any visual inconsistencies, broken layouts, missing interactions
- Responsive layout testing (desktop, laptop, tablet, mobile)
- Dark mode implementation (using brand's dark palette: #0D0936 background, adjusted text/surface colors)
- Performance profiling — ensure no page exceeds 3s to interactive
- Final `npm run qa` — all tests green, all routes clean

---

### Session Summary

| Session | Phase | Agents | Work | Est. Time |
|---------|-------|--------|------|-----------|
| 1-2 | 1A Foundation | 1 (single) | Theme, layout, shared components, claim detail, search | 4-6 hrs |
| 3-4 | 1B Core Modules | 4-5 (parallel) | ReclaimRx, Claims/Accounting, Directories, Dashboard/Programs, Analytics | 6-10 hrs |
| 5-6 | 1C Integration | 3-4 (parallel) | Drill-down wiring, Admin/EDI/Network, Reporting/Export, Test expansion | 4-6 hrs |
| 7 | 1D Polish | 2-3 (parallel) | AI Assistant, Tasks/Notifications, Final QA | 3-4 hrs |
| **Total** | | | | **~17-26 hrs** |

**Token budget estimate:** At 5 agents running concurrently, expect ~2-3x the token consumption of serial development. Claude Max 20x should handle this comfortably, but monitor usage during Phase 1B. If rate limits hit, drop to 3 agents.

---

## 10. Success Criteria

The redesign is complete when:

1. **Brand:** Portal looks and feels like InfinityRx — navy sidebar, Lato typography, IFX logo, pink accents on light background
2. **Navigation:** Every module collapses/expands in the sidebar, section tabs mirror sidebar sub-items, operator can reach any page in ≤ 3 clicks
3. **Drill-down:** Every number, stat card, chart element, and table row is clickable and leads to underlying data — zero dead ends
4. **Data completeness:** Every detail page (pharmacy, prescriber, drug, member, claim, investigation) shows ALL fields an operator needs, including chain code, pay-to, reconciliation vendor, dispensing class, DataQ specs
5. **Configurable tables:** Users can show/hide any column on any table, preferences persist per user across sessions
6. **GTN visibility:** ReclaimRx shows gross-to-net ratio, leakage categorized by type (pharmacy misuse, accumulator, maximizer, 340B, alternative funding) with dollar amounts, and drill-down to individual claims
7. **Configuration:** All client setup, fee structures, program settings, billing rules, payment routing, detection thresholds, and system configuration is editable from the UI — no backend developer needed
8. **Analytics parity:** Portal analytics cover at minimum everything in the current Power BI dashboards (Claim Summary, NDC Utilization, Pharmacy Insights, Average Benefit Spend) with the same filter depth plus manufacturer-specific additions (fill performance, adherence, trend decomposition)
9. **Search:** Global search (⌘K) finds any entity (claim by ID/auth#, pharmacy by name/NPI, prescriber by name/NPI, member by name/ID, investigation by ID, invoice by number) and navigates to the detail page
10. **Actions work:** All action buttons (approve, reject, escalate, assign, export, flag, create, edit, delete) do what they say — zero stub buttons
11. **AI Assistant:** Help panel answers questions about system usage, searches documentation, and provides context-aware data insights
12. **Export:** Every table and chart in the portal can be exported to CSV or Excel, respecting active filters
13. **QA gate:** `npm run qa` passes with 200+ tests (unit + E2E) covering all modules, drill-down chains, and regression scenarios
14. **Performance:** No page exceeds 3 seconds to fully interactive. Virtual scroll handles 100K+ row datasets smoothly.
