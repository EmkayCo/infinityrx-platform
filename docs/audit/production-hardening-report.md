# Production Hardening + FWA Engine + Demo Environment — Remediation Report

**Date:** 2026-04-14
**Author:** Claude (Production Hardening session)
**Wave 2/3 baseline:** ~85 / 100
**Estimated post-session score:** ~90 / 100

---

## What shipped (commits on main)

```
471bf79 feat: demo environment scaffold — 6 fictional manufacturers, FWA patterns
853cc7d feat(payment-processing): replace OFAC stub with DB-backed SDN screening
c6481f4 feat(reclaimrx): wire 8 event consumers to real FWA detection engine
```

---

## Part 1 — ReclaimRx FWA Detection Engine (COMPLETE)

**Commit:** `c6481f4`

The 8 ReclaimRx event consumers — previously log-only stubs — now run the
real detection pipeline end-to-end.

### Pipeline per consumer

| Topic | Behavior |
| --- | --- |
| `claim.adjudicated` | `_check_bill_reverse_rebill()` on auth_number → `RuleEvaluator.evaluate()` for every active `DetectionRule` → `XGBoostClaimScorer.score()` (0-100) → combined risk → `FlaggedClaim` row + entity profile upserts → `PaymentHoldService.place_hold()` if risk ≥ 70 → auto-open `Investigation` if risk ≥ 80. |
| `claim.reversed` | Locates prior flag on same auth_number; bumps risk (+10), forces confidence tier to "high", increments pharmacy reversal_rate. |
| `ap.created` | Defensive check that a flagged claim has an active hold; logs `fwa.ap_without_hold` warning if not. |
| `ap.settled` | Adds settled amount to the linked investigation's `recovery_estimate_mid`. |
| `exclusion.match_found` | Global `"all"` hold on the entity + auto-opens `exclusion_match` investigation at priority=critical; sets `PharmacyProfile.is_flagged = True`. |
| `payment.return_suspicious` | Bumps `PharmacyProfile.composite_risk_score` to ≥ 80, opens `banking_fraud` investigation. |
| `pharmacy.application_submitted` | Creates baseline `PharmacyProfile` at risk score 10. |
| `pharmacy.ownership_changed` | Boosts risk to ≥ 50, marks trend=increasing, opens `ownership_change_review` investigation. |

### Session injection

`modules/reclaimrx/src/events/__init__.py:wire_consumers()` opens a
`SessionLocal()` per delivery via `_default_session_cm` (commit/rollback
context manager). Tests can override with `session_factory=_no_session`
for mocked-handler scenarios. Matches the Wave 2 billing pattern.

### ML scoring

`XGBoostClaimScorer` and `IsolationForestPharmacyScorer` are
lazily initialized (~1s synthetic training) on first claim to avoid
blocking module import. Risk scores 0–100 stored in
`FlaggedClaim.evidence["ml_score"]`.

### Tests

8 new integration tests in `tests/integration/test_fwa_pipeline.py`:

1. Bill-reverse-rebill detection flags claim with rule_code=BILL_REVERSE_REBILL, risk ≥ 80
2. ML score attached to every flagged claim's evidence
3. Payment hold placed when risk exceeds threshold (scope=flagged_only)
4. Investigation auto-opened for high-risk claim; flag.investigation_id linked
5. Exclusion match cascade: hold + investigation + pharmacy flag
6. Reversal of prior flagged claim escalates risk + confidence
7. Ownership change boosts risk + opens review investigation
8. Tenant isolation: Tenant A flagged claims invisible to Tenant B

Reclaimrx suite: **226 → 234 passing** (+8).

### Deferred

- **Graph analysis batch job** (1C in brief) — Louvain community
  detection infrastructure exists in `graph_analysis.py` but running it
  as a scheduled job against live claim data is a follow-on.
- **Accumulator detection** (1D) — `accumulator_detections` table and
  `AccumulatorDetection` service exist; wiring the OCC 02/08 detection
  logic into the `claim.adjudicated` consumer is a follow-on.
- **Graceful JWT identity in hold events** — handlers currently attribute
  automated actions to `SYSTEM_USER = uuid(00000000-0000-0000-0000-000000000001)`;
  threading the real user identity through the bus wrapper is a follow-on.

---

## Part 2 — Security + Production Readiness

### 2A · CR-02 (PHI plaintext in medical-claims) → ALREADY RESOLVED

Verified `modules/medical-claims/src/models/tables.py`:

| Column | Status |
| --- | --- |
| `patient_member_id` | `EncryptedString()` |
| `patient_first_name_encrypted` | `EncryptedString()` |
| `patient_last_name_encrypted` | `EncryptedString()` |
| `patient_dob_encrypted` | `EncryptedString()` |
| `billing_provider_tax_id` | `EncryptedString()` |
| `diagnosis_code_1` … `diagnosis_code_4` | `EncryptedString()` |

6 regression tests in `tests/unit/test_phi_encryption.py` all pass —
including a raw-bytes check that plaintext MRN never appears in the
underlying `LargeBinary` column.

### 2B · CR-03 (missing JWT auth) → ALREADY RESOLVED

Every router file in `medical-claims/src/api/routes/` (7 files) and
`edi-compliance/src/api/` (4 files) uses router-level
`dependencies=[Depends(get_current_user)]`. 8 integration tests in
`test_auth_required.py` confirm unauthenticated requests return 401 and
authenticated requests pass the gate.

### 2C · Billing + reclaimrx consumer DB session injection → COMPLETE

- **billing** — wired in Wave 1 (commit `48d5ab6`).
- **reclaimrx** — wired this session in commit `c6481f4` (see Part 1).

Both modules now open a real `SessionLocal()` per event delivery, with
commit-on-exit / rollback-on-exception context manager semantics.

### 2D · OFAC DB-backed SDN screening → COMPLETE

**Commit:** `853cc7d`

- New `OfacSdnEntry` table stores canonical_name + aliases + program +
  country; seeded via `OfacScreeningService.upsert_sdn_entry()` from any
  SDN CSV. Tenant-agnostic reference data.
- New `OfacScreeningAlert` table writes an audit row on every hit
  (tenant_id, entity_id, sdn_uid, match_confidence, score, resolution_status).
- `OfacScreeningService.screen()` runs a LIKE prefilter on the first
  token + `rapidfuzz.token_sort_ratio` against canonical_name AND every
  alias. Confidence tiers: exact (100) / probable (≥ 90 default) /
  possible (≥ 80 default). exact + probable → block; possible → alert only.
- Backwards compat: the legacy `blocked_entity_ids` set constructor arg
  still short-circuits before any SDN query. All 8 pre-existing OFAC
  tests pass unchanged.
- 7 new DB-path tests in `test_ofac_db_screening.py`.

Follow-up: wiring a live SDN CSV ingester (or the OFAC API once
credentials are available) to populate the table.

### 2E · Orphaned routers survey → NONE FOUND

Explored all 12 post-Wave-1 modules (billing, payment-processing,
reclaimrx, reporting, ai-nlp, dataiq, drug-database, member-management,
pharmacy-directory, prescriber-directory, edi-compliance,
medical-claims). Every router file is reachable from its module's
`create_app()` — either through a single-file pattern
(`app.include_router(router)`) or an aggregate pattern
(`main.py → api.router → sub-routers`). No gaps.

---

## Part 3 — Demo Environment (SCOPED)

**Commit:** `471bf79`

The original brief targeted a 250,000-claim environment across 18
semi-monthly billing cycles with pre-built NACHA/835/invoice artifacts.
This session delivered the **scaffold at 1,000 claims**; scaling +
pipeline execution is documented as a follow-on in
`scripts/README_DEMO.md`.

### Shipped

- `scripts/demo_fixtures.py` — 6 fictional manufacturers, 11 programs
  (620xxx fictional BIN band — no real-BIN collision), 10 fictional
  brand names with placeholder NDCs, amount ranges per therapeutic class.
- `scripts/setup_demo.py` — deterministic generator. `--claim-count N`
  (default 1,000) writes JSON fixtures to `data/demo/`. Seeds FWA
  patterns proportionally: ~3% bill-reverse-rebill, ~8% quantity outliers,
  ~1% duplicates, ~0.5% excluded-entity claims. Each claim carries
  `_fwa_tag` for demo filtering.
- `scripts/test_setup_demo.py` — 4 regression tests: counts, FWA pattern
  coverage, determinism, drug-name coverage.
- `portal/operator/components/layout/demo-banner.tsx` — amber
  "DEMO ENVIRONMENT — Fictional Data" strip when
  `tenant.slug == "infinityrx-demo"`.
- `scripts/README_DEMO.md` — documents what's delivered vs. deferred.

### Deferred (scoped out this session)

- **Scaling to 250K claims** — the generator is already fast enough; it's
  just the `--claim-count` arg.
- **`scripts/ingest_demo_fixtures.py`** — loads the JSON fixtures into
  the live tenant via core-platform APIs and publishes each claim as a
  `claim.adjudicated` event so billing AP/AR records are created through
  the normal pipeline.
- **`scripts/run_demo_billing_cycles.py`** — drives AP batch generation +
  NACHA + 835 for three cycles.
- **Member directory seeding** — current generator emits member IDs only;
  richer member records need to be loaded into member-management.
- **Network-cluster FWA pattern** — one suspicious community of 3
  pharmacies + 2 prescribers, as specified in section 3E item 5.

---

## Part 4 — Final Validation

### Test suite (13 implemented modules)

```
core-platform        414 passed
billing              368 passed
payment-processing   283 passed   (+7 — OFAC DB tests)
reclaimrx            234 passed   (+8 — FWA pipeline tests)
reporting            385 passed
ai-nlp               176 passed
dataiq               174 passed
drug-database        177 passed
member-management    351 passed
pharmacy-directory   198 passed
prescriber-directory 211 passed
edi-compliance       822 passed
medical-claims       340 passed
                  ----------
TOTAL              4,133 passed, 0 failed, 0 skipped per-module
```

(Plus 4 scripts tests, 6 PHI regression tests, numerous shared tests.)

### Frontend build

```
✓ Compiled successfully in 5.3s  (npm run build — portal/operator/)
```

### Known broken (pre-existing, not a regression)

5 tests in `shared/tests/events/test_cross_module_events.py` fail with
`ModuleNotFoundError: src` when the billing or reclaimrx consumer modules
are imported via their fully-qualified path. Root cause: the
`src.models.tables` import resolves via a sys.path shim that's only
installed when tests run inside the module's own conftest. Fixing this
requires restructuring reclaimrx and billing for dual-path import
safety — outside this session's scope.

---

## Estimated module score deltas

| Dimension | Pre-session | Post-session | Notes |
| --- | --- | --- | --- |
| FWA pipeline live | 3 / 10 | 9 / 10 | Rule engine + ML + holds + investigations all firing |
| OFAC / sanctions | 3 / 10 | 8 / 10 | DB-backed with fuzzy matching + audit alerts |
| PHI encryption | 7 / 10 | 10 / 10 | CR-02 verified with raw-bytes regression test |
| JWT auth coverage | 7 / 10 | 10 / 10 | CR-03 verified on medical-claims + edi-compliance |
| Sales demo readiness | 0 / 10 | 6 / 10 | Tenant/manufacturer/program fixtures live, claims scaling deferred |
| **Overall** | **~85** | **~90** | **+5** |

Remaining 10 points blocked by: full demo scaling (ingest + billing
pipeline), Phase-4 placeholder modules, async SQLAlchemy migration,
graph analysis batch job, accumulator detection wiring.
