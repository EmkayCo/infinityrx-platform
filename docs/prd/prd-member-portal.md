# PRD — Module 20e: Member Portal — FINAL

**Module:** Member Portal (Patient / Member Facing)  
**Folder:** `portal/member/`  
**Priority:** Phase 4B (after Operator Portal stabilizes)  
**Dependencies:** Core Platform (1), Member Mgmt (5), Drug DB (2), Pharmacy Dir (3), Billing (11), AI/NLP (21)  

---

## 1. Purpose

The Member Portal is the patient-facing interface. Members enrolled in InfinityRx-administered programs use it to understand their benefits, check drug costs, find pharmacies, manage prescriptions, access copay assistance, and communicate with support. This portal serves the people whose health depends on getting their medications — the UX must be accessible to ALL literacy levels, ALL age groups, ALL abilities.

**Design philosophy:** the member is NOT a healthcare professional. No jargon. No codes. No abbreviations. Plain English (and multilingual). Large text. Simple flows. Every screen answers one question: "Can I get my medication, and what will it cost me?"

**Regulatory context:** the 2026 Consolidated Appropriations Act requires PBMs to pass through 100% of rebates and provide transparency. This portal is how InfinityRx demonstrates transparency to members.

---

## 2. Tech Stack

Shared with Operator Portal: Next.js 15 + TypeScript + shadcn/ui + Tailwind CSS v4. Deployed as `members.infinityrx.com`. PWA-enabled for mobile home screen installation.

Additional:
- **i18n**: next-intl for multi-language support (English, Spanish minimum; configurable per program)
- **Large text mode**: accessibility toggle for 150% base font size
- **High contrast mode**: separate from dark mode — specifically for low-vision users

---

## 3. Authentication

- Login via Core Platform auth
- Member identified by member ID + DOB verification (no complex passwords for elderly members)
- Passwordless option: magic link sent to email or SMS verification code
- Caregiver access: authorized caregivers (parent for dependent, adult child for elderly parent) can access member's portal with delegated permissions
- Session timeout: 15 minutes HIPAA standard, with 2-minute warning modal
- Auto-save: all in-progress forms saved before timeout

---

## 4. Pages & Features

### 4.1 Home Dashboard
- **Welcome message**: "Hello [first name]" with today's date
- **My medications**: list of active prescriptions with next refill date, days supply remaining, visual indicator (green = on track, yellow = refill soon, red = overdue)
- **My costs this year**: simple deductible/OOP progress bar — "You've paid $1,200 of your $3,000 deductible" with visual fill
- **Action items**: refill reminders, documents to review, messages from support
- **Quick actions**: large tap-friendly buttons — "Check Drug Cost", "Find a Pharmacy", "Get Help"

### 4.2 My Medications
- **Active medications list**: drug name (brand + generic), dose, frequency, prescriber name, pharmacy, days supply, next refill date
- **Medication detail**: what this medication is for (plain English), how to take it, common side effects, drug interactions warning, manufacturer information
- **Refill status**: last fill date, days remaining, auto-refill status (if applicable)
- **Cost history**: what member paid at each fill (copay, coinsurance), what plan paid, what manufacturer assistance covered (if any)
- **Switch to generic**: if member is on a brand with a generic available, show: "A generic version ([name]) is available and could save you $[X] per fill. Talk to your doctor about switching."

### 4.3 Drug Cost Lookup
- **Search**: type drug name → auto-complete with brand and generic options
- **Cost display**: for the searched drug, show:
  - Tier and formulary status (covered / not covered / PA required)
  - Estimated cost to member (copay or coinsurance) based on current benefit phase
  - Cost comparison: brand vs generic vs therapeutic alternatives
  - Cost at different pharmacies: retail vs mail order vs specialty (when available)
- **Savings opportunities**: copay assistance programs, manufacturer coupons, patient assistance programs that apply to this drug
- **Prior auth required?**: plain-English explanation if PA is needed, with "Your doctor can request this" message
- **NOT on formulary?**: show alternatives with "These similar medications ARE covered and cost less"

### 4.4 Find a Pharmacy
- **Map view**: pharmacies in member's network within configurable radius, with map pins
- **List view**: sorted by distance, showing name, address, phone, hours, services (mail order, specialty, 24-hour)
- **Filter**: by type (retail, mail order, specialty), by chain, by hours (open now), by services
- **Pharmacy detail**: contact info, hours, directions link (opens Google/Apple Maps), network status, services offered
- **Preferred pharmacy**: member can set a preferred pharmacy (saved to profile)

### 4.5 My Benefits
- **Benefit summary**: plan name, effective dates, deductible (individual/family), OOP maximum, copay structure by tier
- **Accumulator dashboard**: visual progress bars for:
  - Deductible: $X spent of $Y
  - Out-of-pocket maximum: $X spent of $Y
  - For Part D: current benefit phase (deductible → initial coverage → coverage gap → catastrophic) with explanation of what each phase means
- **Copay assistance tracking**: if enrolled in copay programs, show how much manufacturer assistance has been applied vs accumulator rules
- **ID card**: digital ID card with BIN, PCN, Group, Member ID — downloadable/printable, add to Apple Wallet / Google Wallet
- **Plan documents**: EOB viewer, plan description (SPD), formulary PDF

### 4.6 EOB Viewer
- **Explanation of Benefits**: humanized view (NOT raw 835)
  - Claim date, drug name, pharmacy
  - What was billed, what plan paid, what member owes
  - Adjustment explanations in plain English
- **Historical EOBs**: browse by date range
- **Download**: PDF for each EOB period

### 4.7 Copay Assistance & Savings
- **Enrolled programs**: list of copay assistance programs member is enrolled in with status
- **Savings tracker**: total saved through copay assistance YTD, per-fill savings history
- **Available programs**: programs member MAY qualify for based on their medications (with enrollment link/phone number)
- **Accumulator status**: clear explanation of how copay assistance interacts with deductible/OOP — critical for members subject to accumulator adjustment programs. "Your copay assistance counts / does not count toward your deductible."

### 4.8 Secure Messaging
- **Message center**: threaded conversations with InfinityRx member support
- **Categories**: benefit question, coverage question, pharmacy issue, copay assistance, general
- **Response time**: "We typically respond within 24 hours"
- **No PHI in subject lines**: system enforces — subject line is category only, detail inside the thread

### 4.9 AI-Powered Help
- **"Ask a Question" chatbot**: conversational AI powered by AI/NLP module
  - "What's my copay for Humira?" → pulls member's benefit and drug data, returns exact copay
  - "Where can I fill my prescription near 10017?" → pharmacy search with map
  - "Why was my claim denied?" → pulls claim status, explains denial in plain English
  - "How much have I spent toward my deductible?" → accumulator lookup
- **Escalation**: if chatbot can't answer, creates a secure message to support team
- **Multilingual**: chatbot responds in member's preferred language

### 4.10 Settings & Profile
- **Personal info**: name, address, phone, email (view, request changes)
- **Communication preferences**: email, SMS, mail for different communication types
- **Language preference**: English, Spanish (more configurable per program)
- **Accessibility**: large text mode, high contrast mode, screen reader optimization
- **Caregiver access**: manage authorized caregivers
- **Notification preferences**: refill reminders (on/off, timing), EOB notifications, plan change alerts

---

## 5. Accessibility (BEYOND WCAG 2.2 AA)

This portal serves elderly members, members with disabilities, and members with low health literacy. Accessibility is not a checkbox — it's the core design principle.

- **WCAG 2.2 AA minimum**, aspire to AAA where feasible
- **Large text mode**: 150% base font, toggle in header AND in settings
- **High contrast mode**: separate from dark mode — black backgrounds with high-contrast text and borders
- **Screen reader optimized**: semantic HTML, ARIA landmarks, live regions for dynamic content
- **Keyboard navigation**: full keyboard access on every feature
- **Reading level**: all content written at 6th grade reading level or below
- **No jargon**: no abbreviations without explanation. "NDC" → never used. "Prior authorization" → "Your doctor needs to get approval first"
- **Visual indicators**: never rely on color alone — always icons + text + color
- **Touch targets**: minimum 44x44px on all interactive elements (mobile)
- **Slow connection support**: works on 3G connections (no heavy JavaScript bundles)
- **Print-friendly**: ID card, EOB, benefit summary all print cleanly

---

## 6. Mobile Experience

Members primarily access on phones. The portal is mobile-first:

- **PWA**: installable to home screen, offline access to cached ID card and benefit summary
- **Bottom navigation**: Home, Medications, Cost Lookup, Pharmacy Finder, More
- **Thumb-zone design**: primary actions in bottom 2/3 of screen
- **Apple Wallet / Google Wallet**: add digital ID card
- **Push notifications** (opt-in): refill reminders, claim processed, EOB available, message from support
- **Camera access**: scan prescription label barcode to look up drug cost (future)

---

## 7. Multilingual

- **English and Spanish at launch** (largest PBM member language groups)
- **Language detection**: browser language preference → suggest portal language on first visit
- **Per-member setting**: language preference saved to profile, persists across sessions
- **AI chatbot**: responds in member's preferred language
- **Content translation**: all static content professionally translated (not machine-only). Dynamic content (drug names, claim data) displayed as-is with surrounding translated context.
- **Extensible**: additional languages configurable per program (Mandarin, Vietnamese, Korean for specific populations)

---

## 8. Session Decomposition

1. **Shell + auth + home + medications**: Next.js PWA setup, member auth (member ID + DOB + magic link option), home dashboard with medication list and accumulator bars, medication detail pages, refill status tracker, digital ID card with wallet integration
2. **Cost + pharmacy + benefits**: drug cost lookup with formulary/tier/copay display and savings suggestions, pharmacy finder with map and filtering, benefit summary with accumulator progress bars, EOB viewer (humanized), plan document library
3. **Copay assistance + messaging + chatbot + settings**: copay assistance enrollment and savings tracker, accumulator interaction explanation, secure messaging center, AI chatbot integration (multilingual), member profile management, caregiver access, notification preferences, language settings, accessibility toggles
