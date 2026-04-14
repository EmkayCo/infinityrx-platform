# PRD — Module 20b: Client Portal — FINAL

**Module:** Client Portal (Manufacturer / Health Plan / TPA Facing)  
**Folder:** `portal/client/`  
**Priority:** Phase 4B  
**Dependencies:** Core Platform (1), Billing (11), Payment (12), Reporting (15), DataIQ (23), Program Config (17), Member Mgmt (5)  

---

## 1. Purpose

The Client Portal is the external-facing interface for InfinityRx's clients — pharmaceutical manufacturers, health plans, TPAs, and 340B programs. It provides self-service access to program performance, financial data, reports, and configuration without requiring IFX operator assistance.

**Design philosophy:** clean, professional, data-rich but not overwhelming. Clients log in to answer: "How is my program performing? What do I owe? What are my members doing?" Every answer should be reachable in ≤3 clicks.

---

## 2. Tech Stack

Shared with Operator Portal: Next.js 15 + TypeScript + shadcn/ui + Tailwind CSS v4 + TanStack Table + Recharts. Same IFX brand design system. Deployed as a separate Next.js app on a separate subdomain (`clients.infinityrx.com`).

---

## 3. Authentication & Multi-Tenancy

- Login via Core Platform auth (JWT + MFA)
- Each client user belongs to one tenant (client organization)
- Client users can ONLY see data for their own programs — enforced at API level via tenant_id
- Roles: **Client Admin** (full access + user management), **Client Manager** (reports + analytics + program config), **Client Viewer** (reports only, read-only)
- SSO support: SAML 2.0 / OIDC for enterprise clients using their own identity provider

---

## 4. Pages & Features

### 4.1 Dashboard
- **Program overview cards**: each program shows: active members, total claims (MTD/YTD), total spend, utilization rate, program health indicator (green/yellow/red)
- **Financial summary**: total billed, total paid, outstanding balance, next invoice date
- **Key metrics trending**: 3-month sparklines for PMPM, generic rate, adherence, claim volume
- **Recent activity**: last 10 events (invoice generated, report published, enrollment file processed)
- **Announcements**: IFX-published messages (formulary changes, system maintenance, new features)

### 4.2 Program Performance
- **Claims dashboard**: total claims by program, by drug, by pharmacy, by month. Filter by date range, drug, pharmacy type.
- **Drug utilization**: top drugs by spend and volume, brand vs generic ratio, new-to-therapy members, therapeutic class breakdown
- **Member analytics**: active members trending, adherence rates (PDC by drug class), high-cost members (anonymized), benefit phase distribution
- **Pharmacy analytics**: top pharmacies by volume, network utilization (in-network vs out-of-network), mail order conversion rate
- **GLP-1 tracker**: dedicated dashboard for GLP-1/weight loss drug utilization (top client concern 2025-2026)

### 4.3 Financial
- **Invoice history**: all invoices with status (generated, sent, paid, overdue). Download invoice PDF. View line-item detail.
- **Payment history**: all payments received with check/EFT details. Download remittance.
- **Fee summary**: breakdown of fees (claims processing, admin, per-script) by program by period
- **Budget tracking**: spend vs budget by program with forecast. Alert when projected to exceed budget.
- **Rebate summary**: rebate credits applied, pending, by drug by quarter (when Rebate Mgmt module available)

### 4.4 Reports
- **Report library**: all reports published for this client, organized by category (financial, clinical, operational, regulatory)
- **Self-service reports**: configure parameters (date range, program, drug, pharmacy), generate on-demand
- **Scheduled reports**: view and manage scheduled report subscriptions
- **Download center**: all generated reports available for download (PDF, Excel, CSV)
- **Star Ratings dashboard**: CMS Star Rating measures relevant to this client (adherence measures, MTM completion)

### 4.5 Members (if authorized)
- **Member search**: by member ID, name (masked), group
- **Member detail**: coverage status, accumulator balances, claims history (PHI access controlled by role)
- **Enrollment file upload**: wizard for uploading enrollment changes (add/update/terminate members)
- **Eligibility check**: real-time eligibility lookup for a specific member

### 4.6 Program Configuration (Client Admin only)
- **Program settings**: view and request changes to program rules (fee structure, benefit design, pharmacy network)
- **Change request workflow**: client submits change → IFX operator reviews → approves/rejects → change applied
- **Configuration history**: all changes with who requested, who approved, when applied
- **Contact management**: update client contacts, billing address, notification preferences

### 4.7 Documents & Communications
- **Document library**: contracts, SLAs, BAAs, compliance certificates shared by IFX
- **Secure messaging**: threaded messages between client and IFX team (PHI-safe, within portal)
- **Knowledge base**: FAQ, how-to guides, glossary of PBM terms

### 4.8 Embedded Analytics (DataIQ)
- **Embeddable DataIQ widgets**: drug trend charts, cost driver decomposition, PMPM trending — embedded directly in the client portal using DataIQ embed endpoints
- **Natural language query**: client types "Show me top 10 drugs by spend last quarter" → DataIQ generates the answer
- **What-if scenarios**: client models impact of formulary changes, benefit design changes (when available)

---

## 5. UX Patterns (Inherited from Operator Portal)

All Operator Portal UX patterns apply:
- Wizard workflows for enrollment upload, report generation, change requests
- Auto-save drafts on all multi-step flows
- Skeleton loading states (no spinners)
- Error boundaries per widget
- Export everywhere (CSV, Excel, PDF on every table/chart)
- Command palette (Cmd+K) — scoped to client's data
- Dark mode support
- Mobile responsive for dashboards and reports (read-only)
- Contextual tooltips on every metric and field
- WCAG 2.2 AA accessibility

---

## 6. White Labeling

Configurable per tenant:
- **Logo**: client can upload their own logo (displayed in top bar alongside IFX logo or replacing it)
- **Color accent**: primary accent color customizable (default: IFX teal)
- **Portal title**: "InfinityRx Client Portal" or custom title
- **Domain**: optional custom subdomain (e.g., `portal.clientname.com` → proxy to InfinityRx)
- **Report branding**: reports generated for this client use their logo and brand colors

---

## 7. Session Decomposition

1. **Shell + auth + dashboard**: Next.js app, auth with SSO support, dashboard with program cards and financial summary, activity feed, announcements, role-based navigation
2. **Performance + financial**: program performance dashboards (claims, drugs, members, pharmacies), invoice history, payment history, fee summary, budget tracking, GLP-1 tracker
3. **Reports + members + config**: report library with self-service generation, download center, member search (if authorized), enrollment upload wizard, program configuration with change request workflow
4. **Documents + analytics + white label**: document library, secure messaging, knowledge base, embedded DataIQ widgets, natural language query, white label configuration
