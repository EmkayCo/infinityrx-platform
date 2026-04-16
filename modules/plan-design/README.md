# Plan Design & Configuration Module

Benefit plan hierarchy, formulary management, network design, pricing calculators,
NCPDP F&B v60 publication, P&T committee tools, and market access intelligence.

## Key features

- Organization → Group → Plan → SubGroup hierarchy with inheritance resolution
- Formulary management with effective-dated versioning and rollback
- Biosimilar mapping and GLP-1 indication-based coverage
- IRA MFP (Maximum Fair Price) flags per drug
- NCPDP Formulary & Benefit Version 60 XML generation
- P&T committee packet and meeting management
- 8 pricing calculators behind `PricingCalculator` ABC: AWP Discount, MAC, Cost-Plus,
  NADAC-Based, Net-Cost, Cost-Plus Specialty, Direct Manufacturer, Cash Discount
- Cash-pay comparison (returns lower of insurance vs cash price)
- Pharmacy network assignment with tier, specialty accreditation, site-of-care, bagging
- CMS network adequacy (haversine distance) calculator
- Any Willing Pharmacy (AWP) application queue (CAA 2026)
- Benefit design what-if simulation with financial impact analysis
- Market access intelligence: coverage landscape, competitive positioning, payer mix,
  accumulator exposure
- Draft → Sandbox → Test → Promote → Rollback plan state machine
- Bulk CSV import for plans

## API

Base path: `/api/v1/plan-design`

Routes are grouped under:
- `/hierarchy` — organizations, groups, plans, subgroups, program types
- `/formularies` — drug tiers, versions, biosimilars, F&B v60, impact analysis
- `/pt-meetings` — P&T committee meetings
- `/networks` — pharmacy assignment, adequacy, AWP applications
- `/market-access` — coverage landscape, competitive, payer mix, accumulator exposure,
  what-if simulation

All routes require JWT bearer authentication (`Authorization: Bearer <token>`) and
`X-Tenant-Id` header.

## Module structure

```
src/
  api/
    routes/        hierarchy.py, formulary.py, network.py, market_access.py
    schemas/       hierarchy.py, formulary.py, network.py, market_access.py
    dependencies.py
    router.py
  db/
    session.py
  events/
    publisher.py
    consumers.py
  infrastructure/
    security_headers.py
    rate_limiter.py
  models/
    tables.py
  services/
    hierarchy.py
    formulary.py
    network.py
    pricing.py
    market_access.py
  main.py
tests/
  conftest.py
  unit/
  integration/
```

## Running tests

```bash
cd modules/plan-design
pytest tests/ --cov=src --cov-report=term-missing
```
