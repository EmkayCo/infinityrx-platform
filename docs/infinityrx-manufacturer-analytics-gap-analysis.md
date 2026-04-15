# InfinityRx — Manufacturer Copay Program Analytics
## Gap Analysis & Best Practices (Phase 1 Focus)

---

## The Business Context

Pharmaceutical manufacturers are IFX's core clients. They fund copay assistance programs to help patients afford branded medications. IFX processes the claims, manages the payments, and should be detecting leakage.

The industry scale: pharma companies collectively spend $12B+/year on copay programs. Estimated annual revenue leakage from these programs is $90B — driven by accumulators, maximizers, alternative funding programs, and pharmacy-level misuse. Gross-to-net (GTN) performance is now a board-level priority at every major manufacturer.

This means IFX's value proposition isn't "we process your copay claims." It's "we protect your copay dollars from leaking." ReclaimRx isn't a nice-to-have module — it's the core of the sale.

---

## What a Manufacturer Client Wants to See

When a pharma manufacturer logs into their portal (or when an IFX operator pulls up a client view), these are the questions they're asking, in priority order:

### 1. GROSS-TO-NET (GTN) — "How much of my copay spend is actually reaching patients?"

**KPIs they need:**
- **Total copay program spend** (YTD, MTD, by period)
- **Copay dollars paid to pharmacies** (the money that went out)
- **Copay dollars reaching patients** vs. **copay dollars lost to leakage**
- **GTN ratio** (net revenue / gross revenue — trending over time)
- **GTN impact by leakage type:**
  - Accumulator programs (payer excluded copay from patient's deductible)
  - Maximizer programs (payer reclassified drug as "non-essential")
  - Alternative funding programs (patient routed away from commercial benefit)
  - Pharmacy-level misuse (duplicate claims, override abuse, fake patients)
  - 340B duplicate discounts
- **GTN variance vs. budget** (manufacturer sets a GTN target — are we beating or missing it?)
- **GTN trend** (is it getting better or worse month over month?)

**What you have today:** Total benefit spend, paid claims, ingredient cost, transaction fees in Power BI. No GTN calculation. No leakage categorization. No accumulator/maximizer detection dashboard.

**Gap: CRITICAL.** This is the #1 metric manufacturers care about. Every competitor (ConnectiveRx, RIS Rx, ZS) builds their entire platform around GTN protection. IFX needs this front and center.

### 2. LEAKAGE DETECTION — "Where are my copay dollars going that they shouldn't?"

**What the manufacturer wants to see:**

**Pharmacy-Level Leakage:**
- Pharmacies with anomalous claim patterns (high volume, unusual fill frequency)
- Pharmacies with high rejection rates on payer claims but high copay card usage
- Pharmacies submitting claims for patients who don't exist or aren't eligible
- Override code abuse (same override code used repeatedly)
- Duplicate claims across pharmacies for the same patient
- Claims where the copay amount exceeds the drug cost
- Pharmacies where copay-to-total-cost ratio is abnormally high

**Prescriber-Level Leakage:**
- Prescribers with abnormally high copay card utilization per patient
- Prescribers associated with multiple pharmacies flagged for misuse
- Prescriber volume outliers (writing far more scripts than peers in same specialty)
- Prescribers with high rates of new-to-therapy starts that drop off quickly (possible "script farming")

**Payer-Level Leakage:**
- Payer plans using accumulator programs (copay dollars not counting toward patient deductible)
- Payer plans using maximizer programs (reclassifying drug to extract copay value)
- Alternative funding program redirection (patients moved to charity foundations)
- Payer masking behaviors (hiding accumulator/maximizer status to avoid detection)

**Patient-Level Leakage:**
- Patients enrolled in multiple copay programs simultaneously
- Patients with fills at multiple pharmacies (pharmacy shopping)
- Patients with no payer claim on file (copay card used without legitimate insurance)
- Patients who abandon therapy quickly after initial fills (possible card harvesting)

**What you have today:** ReclaimRx has an investigations module and recovery tracking. The UX audit found stat cards, a Kanban board, and a recovery table — but no drill-down from stats to underlying claims, and no categorized leakage dashboard. The mock data has 20 recovery records and 10 investigation cards.

**Gap: HIGH.** The structure exists (ReclaimRx) but the analytics layer is shallow. Manufacturers need leakage categorized by type with dollar amounts, trending, and drill-down to the specific claims and pharmacies. This is where ZS charges consulting fees — IFX should build it into the platform.

### 3. ADHERENCE — "Are patients staying on therapy?"

**KPIs they need:**
- **Proportion of Days Covered (PDC)** for their specific drug(s)
- **Persistence rate** (% of patients still filling after 3, 6, 9, 12 months)
- **Average fills per patient** (trending)
- **Time to first fill** (from enrollment to first claim)
- **Time between fills** (are patients filling on schedule?)
- **Therapy discontinuation rate** (and at what point patients stop)
- **Reasons for discontinuation** (cost, side effects, therapy complete, lost to follow-up)
- **Adherence by pharmacy** (which pharmacies have the best/worst adherent patients)
- **Adherence by geography** (regional patterns)
- **Impact of copay assistance on adherence** (patients with copay card vs. without — what's the adherence delta?)

**What you have today:** PDC adherence chart on the member analytics page. Abandonment rate in Power BI (30% average). No persistence tracking. No fill-by-fill patient journey. No copay-vs-no-copay comparison.

**Gap: HIGH.** Manufacturers fund copay programs specifically to improve adherence. They need to prove the ROI — "patients with our copay card had 85% PDC vs. 62% without." If IFX can show this, it's a powerful retention argument for keeping the manufacturer as a client.

### 4. FILL ANALYTICS — "How is my drug being dispensed?"

**KPIs they need:**
- **Total fills** (new starts, refills, renewals — broken out)
- **New-to-brand (NBRx)** starts per period
- **Total prescriptions (TRx)** per period
- **Fills by pharmacy type** (retail, mail, specialty, 340B)
- **Fills by pharmacy chain** (CVS, Walgreens, independent, specialty)
- **Fills by geography** (state, region, zip code)
- **Fills by payer type** (commercial, Medicare, Medicaid, cash)
- **Fills by prescriber specialty**
- **Days supply distribution** (30 vs. 60 vs. 90 day)
- **Average quantity per fill**
- **Average copay amount per fill** (what patients are actually paying)
- **Average manufacturer copay assistance per fill** (what IFX is paying on their behalf)
- **Fill-to-reversal ratio** (how many fills end up reversed)
- **Reversal reasons** (reject codes, patient issues, pharmacy issues)

**What you have today:** Net claim count, prescription count, fill number in the claims data. Some of this is in Power BI but not broken out by new vs. refill, not by pharmacy type, not by payer type. No NBRx tracking.

**Gap: MEDIUM-HIGH.** The data is in the claims stream — it just needs to be computed and displayed. NBRx is particularly important because manufacturers track it as a leading indicator of market share.

### 5. PROGRAM PERFORMANCE — "Is my copay program working?"

**KPIs they need:**
- **Program enrollment** (active cards, new enrollments, reactivations)
- **Card utilization rate** (% of enrolled patients who actually use the card)
- **Average copay assistance per patient per year**
- **Total program cost** (copay dollars paid + admin fees + processing fees)
- **Cost per incremental fill** (how much copay spend per additional fill driven by the program)
- **ROI calculation** (incremental revenue from increased fills vs. total program cost)
- **Accumulator/maximizer impact** (how many patients hit the copay wall, what happens to adherence after)
- **Program budget burn rate** (are we on track to stay within annual copay budget?)
- **Budget forecast** (projected total program spend based on current utilization)

**What you have today:** Basic spend tracking. No enrollment analytics. No utilization rate. No ROI calculation. No budget tracking or forecasting.

**Gap: HIGH.** Manufacturers budget their copay programs annually. They need to know if they're going to run out of money in October. IFX should track budget vs. actual and forecast.

### 6. COMPETITIVE INTELLIGENCE — "How does my drug compare?"

**KPIs they need (where data is available):**
- **Market share within therapeutic class** (their drug vs. competitors)
- **Formulary position** (which payers have them preferred, non-preferred, excluded)
- **Copay card lift** (incremental market share attributable to the copay program)
- **Switch patterns** (patients switching from competitor drugs to theirs, and vice versa)

**What you have today:** Nothing. This requires external data (IQVIA, Symphony Health) that IFX may not have.

**Gap: STRATEGIC.** This is a "future state" capability. Flag it but don't build it in Phase 1. If IFX ever integrates with external data sources, this becomes extremely valuable.

---

## What the Manufacturer Portal Should Show

When a manufacturer client logs into their own portal view, this is the hierarchy:

```
📊 Program Dashboard (their landing page)
   ├── GTN Overview (the single most important view)
   │   ├── GTN ratio trending
   │   ├── Leakage by category (pie chart + table)
   │   ├── Budget vs. actual
   │   └── Click any number → drill to claims
   │
   ├── Fill Performance
   │   ├── Total fills (new + refill breakdown)
   │   ├── NBRx trending
   │   ├── Fills by pharmacy, geography, payer
   │   └── Days supply distribution
   │
   ├── Adherence
   │   ├── PDC for their drug
   │   ├── Persistence curve (% still filling at 3/6/9/12 months)
   │   ├── Adherence by pharmacy
   │   └── Copay impact (with card vs. without)
   │
   ├── Leakage Alerts
   │   ├── Flagged pharmacies (with severity)
   │   ├── Flagged prescribers
   │   ├── Accumulator/maximizer detected
   │   └── Recovery status
   │
   ├── Financial Summary
   │   ├── Total program spend
   │   ├── Claims processed
   │   ├── Payments made
   │   ├── Invoices
   │   └── Fee breakdown
   │
   └── Reports
       ├── Monthly program report (downloadable)
       ├── Quarterly business review deck
       └── Ad-hoc report builder
```

**This is view-only for the manufacturer** — they can see their data, run reports, and view alerts, but they can't modify claims, approve payments, or change configurations. The operator portal (IFX team) has full read-write access with all the action buttons.

The Appfolio pattern applies here: if a manufacturer calls and has a question, the IFX operator can launch the manufacturer's portal view on their screen and see exactly what the manufacturer sees — same data, same layout — to guide them through it.

---

## ReclaimRx: What "Incredible" Looks Like

Based on the research, here's what the best leakage detection platforms (RIS Rx, ZS, ConnectiveRx) offer that ReclaimRx should match or exceed:

### Detection Capabilities
1. **Real-time claim validation** — flag suspicious claims BEFORE payment, not after (pre-claim identification is best-in-class per ConnectiveRx)
2. **ML-based anomaly detection** — unsupervised learning on claim patterns to find fraud that rules can't catch (ZS's approach)
3. **Multi-dimensional pattern analysis** — correlate across patient, pharmacy, prescriber, and payer dimensions simultaneously
4. **Accumulator/maximizer detection** — identify payer plans using cost-shifting programs, including masked programs
5. **Alternative funding program detection** — spot when patients are redirected to charity foundations
6. **340B overlap detection** — flag claims where 340B pricing and copay assistance are both applied (duplicate discount)
7. **Pharmacy network scoring** — continuous risk scoring of every pharmacy in the network

### Recovery Capabilities
8. **Automated recovery workflows** — once leakage is confirmed, generate recovery letters, offset future payments, or flag for legal
9. **Recovery tracking** — estimated vs. actual recovery, by pharmacy, by case
10. **Recovery ROI** — total dollars recovered vs. cost of the detection program

### What ReclaimRx Has Today
- Investigation Kanban board (Open → In Review → Escalated → Resolved → Closed)
- Recovery table (20 records with estimated/actual amounts)
- Severity badges on investigations
- Evidence checklist per investigation
- Activity timeline

### What ReclaimRx Is Missing
- No GTN impact quantification per investigation
- No leakage categorization (accumulator, maximizer, pharmacy misuse, etc.)
- No pharmacy risk scoring
- No prescriber outlier detection dashboard
- No real-time claim validation (everything is retrospective)
- No ML-based anomaly detection (investigations are manually created)
- No accumulator/maximizer detection
- No 340B overlap detection
- No automated recovery workflow
- No recovery ROI tracking
- The stat cards on the dashboard don't drill down to anything

**The opportunity:** RIS Rx reported protecting $1B in revenue for their clients in 2025 alone. If IFX can build even a fraction of this capability into ReclaimRx, it becomes the primary reason manufacturers choose IFX over competitors.

---

## Phase 1 Recommendations (Manufacturer-First)

### Build Now (Portal Redesign Phase 1)

1. **GTN Dashboard** — the manufacturer's #1 view. Total spend, leakage by category, GTN ratio, budget tracking. Drill-down everywhere.

2. **Leakage categorization in ReclaimRx** — every investigation should have a leakage type (pharmacy misuse, accumulator, maximizer, 340B overlap, etc.) and an estimated dollar impact. The Kanban cards should show dollar amounts prominently.

3. **Fill analytics** — total fills, new vs. refill, by pharmacy, by geography, by payer. This replaces the Power BI NDC Utilization and Pharmacy Insights pages but focused on the manufacturer's specific drugs.

4. **Adherence dashboard** — PDC for their drug, persistence curve, adherence by pharmacy. Include the copay impact comparison.

5. **Program budget tracking** — budget vs. actual, burn rate, forecast. Manufacturers budget copay programs annually — give them real-time visibility.

6. **Manufacturer portal view** — the view-only dashboard their team can log into. Same data the operator sees, without action buttons.

### Build Next (Phase 2)

7. **Pharmacy risk scoring** — continuous ML-based scoring of every pharmacy
8. **Accumulator/maximizer detection** — identify payer plans using cost-shifting
9. **Real-time claim flags** — pre-payment detection rules
10. **Automated recovery workflows** — recovery letters, payment offsets
11. **Quarterly business review generator** — auto-generate the QBR deck from portal data

### Build Later (Phase 3+)

12. **340B overlap detection** (requires 340B entity data integration)
13. **Alternative funding program detection**
14. **Competitive intelligence** (requires external data)
15. **Predictive leakage modeling** (ML on historical patterns to predict future leakage)

---

## Impact on the Portal Sidebar

With the manufacturer focus, the sidebar should be reorganized:

```
🏠 Dashboard (manufacturer program overview)

💊 Programs (manufacturer copay programs)
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

🔍 ReclaimRx (leakage detection — the crown jewel)
   ├── GTN Dashboard
   ├── Leakage Monitor
   ├── Investigations
   ├── Pharmacy Risk Scores
   ├── Recovery Tracking
   └── Case Wizard

📊 Analytics
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
   ├── Programs
   ├── Fee Configuration
   └── Portal Access (view manufacturer portal)

📡 EDI
   ├── Monitor
   ├── Transactions
   └── Partners

📄 Reporting
   ├── Report Library
   ├── Report Builder
   └── Scheduled Reports

⚙️ Admin
   ├── Users & Roles
   ├── System Config
   ├── System Health
   └── Audit Log
```

The key change: **Programs** and **ReclaimRx GTN** move up to the top of the hierarchy because they're the core of the manufacturer relationship. Claims and Accounting are supporting functions. Analytics is focused on what manufacturers care about (fills, adherence, pharmacy performance) not what health plans care about (network adequacy, formulary compliance, Star Ratings).
