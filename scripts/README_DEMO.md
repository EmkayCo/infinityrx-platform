# InfinityRx Sales Demo Environment

Tools for setting up the `infinityrx-demo` tenant with fictional but
realistic data for sales demonstrations.

## What this session delivered

1. **`scripts/demo_fixtures.py`** — pure fixtures:
   - 6 fictional manufacturers (Zenara, Meridian, Crestview, Helios,
     Pinnacle, Orion)
   - 11 fictional programs across those manufacturers, using the 620xxx
     fictional BIN band that avoids real BIN collisions
   - 10 fictional brand names mapped to placeholder NDCs that match the
     therapeutic class of real NDCs in the drug database
   - Amount ranges per therapeutic class driving realistic claim
     distributions

2. **`scripts/setup_demo.py`** — deterministic fixture generator:
   - `--claim-count N` (default 1,000): emits a sterilized claim stream
     as `data/demo/claims.json`
   - `--reset`: drops existing fixtures before regenerating
   - Seeds FWA patterns proportionally to claim count: ~3%
     bill-reverse-rebill, ~8% quantity outliers, ~1% duplicate
     submissions, ~0.5% excluded-entity claims
   - All claims tagged with `_fwa_tag` so QA and portal demo tools can
     filter for the pattern being demonstrated

3. **`scripts/test_setup_demo.py`** — regression tests: fixture counts,
   FWA pattern coverage, determinism, and every drug name appearing.

4. **`portal/operator/components/layout/demo-banner.tsx`** — visual
   marker ("DEMO ENVIRONMENT — Fictional Data") shown when the active
   tenant's slug is `infinityrx-demo`.

## What's deferred

The original brief targeted 250,000 claims across 18 semi-monthly billing
cycles with pre-built NACHA/835/invoice artifacts for 3 completed cycles.
This session delivered the scaffold at 1,000 claims; the scaling work
requires:

- **`scripts/ingest_demo_fixtures.py`** — loads the JSON fixtures into
  the live tenant via the core-platform Tenant + User APIs and
  publishes each claim as a `claim.adjudicated` event so billing AP/AR
  records are created through the normal pipeline.
- **`scripts/run_demo_billing_cycles.py`** — drives `AP.generate_batch`
  + NACHA builder + 835 generator for three cycles, writing artifacts
  to `data/demo/billing/{cycle_id}/`.
- **Member directory seeding** — 45k fictional members with realistic
  address distribution (the current generator emits member IDs only;
  names/DOBs/addresses come from the manifold lists inside
  `_generate_members()`).
- **Network cluster seeding** — the "one suspicious community" pattern
  requires an explicit graph edge layout rather than the flat-random
  `normal_npis`/`fraud_npis` split.

The 1,000-claim scaffold is sufficient to demonstrate:
- ReclaimRx FWA detection firing on live fictional data
- Portal browsing tenant-isolated to demo
- Drug/pharmacy/prescriber lookups returning real reference data for
  the mapped NDCs

## Usage

```bash
# Generate the JSON fixture pack (idempotent)
uv run python scripts/setup_demo.py

# Regenerate from scratch
uv run python scripts/setup_demo.py --reset

# Scale up (up to ~100k claims finishes in < 30 seconds on modern hardware)
uv run python scripts/setup_demo.py --claim-count 10000
```

Output lands in `data/demo/`:
- `tenant.json` — tenant slug + admin user payload
- `manufacturers.json` — 11 program seed records
- `drugs.json` — 10 drug → NDC mappings
- `claims.json` — the generated claim stream
- `summary.json` — counts + provenance

## Demo integrity guardrails

- All pharmacy/prescriber NPIs are in the `1xxxxxxxxx` / `7xxxxxxxxx`
  bands to avoid collision with real NPPES NPIs that might overlap
  with exclusion-list entries during testing.
- All BINs are in the 620xxx fictional band.
- The portal banner fires on `tenant.slug == "infinityrx-demo"` — no
  ambiguity between demo and production at the UI layer.
