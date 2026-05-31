# ReclaimRx Detection v2 — Recalibration, Reference Data, Engine Rework, Portal Wiring

**Date:** 2026-05-31
**Status:** Draft → pending codex spec-lock (L1)
**Supersedes:** `2026-05-29-reclaimrx-csv-detection-design.md` (v1) for everything past ingest.
**Module:** `modules/reclaimrx` + `portal/operator/app/reclaimrx`

---

## 1. Why v2 (what the v1 dry-run proved)

v1 shipped: durable fast ingest (execute_values, RLS-safe, ~5 min for 2.6M rows), the World-A schema/ORM, the 47-rule catalog, and precise grouping rules. The full-file dry-run then exposed that **the broad/statistical rules are mis-calibrated for this dataset**: a manufacturer copay-assistance file (client "32" = 81%, BIN 025706 = 99%) where the program pays full ingredient cost. Absolute thresholds (esp. MFR-001 `nq_to_wac > 1.10`) flagged **~793K of 2.6M claims (~30%)** — noise, not FWA. The write path (savepoint-per-anomaly + per-fire eval-log + per-rule full scans) also could not finish in a day.

v2 fixes calibration + the engine, adds reference-data-backed rules, and surfaces results in the **existing** portal Leakage Monitor for human calibration.

## 2. Carried-forward (still in force from v1)

Ingest path (COPY-rejected→`execute_values`, RLS via `SET LOCAL app.current_tenant_id`, durable, full-coverage gate, idempotency lock), World-A ORM + migrations (`0005`/`0008_ml_detector_seed` restored, two-head fork documented as tech-debt, feature index `0009`), Decimal money, single-tenant attribution, `resolved_client_id` NULL + raw in `row_data`. **The 2.6M rows are already ingested** (run-only re-detection is possible).

## 3. Locked decisions (v2)

| # | Decision |
|---|---|
| V1 | **Rule set = A + recalibrated B + new-C** (below). Target total flag rate **< ~1%** of claims. |
| V2 | **Calibration pattern** for all statistical/threshold rules: flag only **top outliers** — percentile (e.g. ≥ p99 within peer group) or z-score (\|z\| ≥ 3) — gated by **minimum sample size** AND a **dollar floor**. No absolute ratio thresholds. |
| V3 | **MFR-001 reframed**: NOT `nq/WAC`. Compare a claim's NQ to **the same patient's prior NQ for the same drug** (longitudinal per-patient baseline). Calibrated via the portal (V8), not a guessed threshold. |
| V4 | **Reject-resubmit** = only **reject `75` (PA required) → rebill with reject `70` (not covered)** for the same prescription, within **≤12h** and **12–24h** buckets (too fast for a real PA = the signal). Measured size: **72 within 12h**, ~0 in 12–24h. Group key TBD-in-plan: `rx_number_hash` (same-claim rebill) vs patient+ndc+pharmacy — decide via portal review. |
| V5 | **New-C via reference data (read grant on `reference.*`):** ALL-002 Phantom/Excluded Pharmacy, ALL-003 Phantom/Excluded Prescriber, + **FDB pricing enrichment** for NQ rules. DEA / formulary / 340B / WC / telehealth / copay-accumulator stay LATER (no data). |
| V6 | **Reference access** = grant the reclaimrx app role `SELECT` on the specific `reference.*` tables (or read-only views). Direct read; reference is shared read-only by design. (Architecture note: documented exception to module-isolation for shared reference data.) |
| V7 | **Engine rework:** (a) batched `execute_values` anomaly inserts (no savepoint-per-row); (b) **single streaming scan** evaluating all per-row rules together (not one full scan per rule); (c) **flag-rate guardrail** — abort/alert if a rule or the run exceeds a configurable cap (default 5%); (d) eval-log writes `finding_raised`+`error` only, `no_finding` aggregated. |
| V8 | **Calibration UI = existing Leakage Monitor** (`/reclaimrx/leakage`) — wire it to World-A anomalies (new API + adapter). No new screens. The filtered table is the calibrate-by-eyeball surface. |
| V9 | **API surface:** new `GET /api/v1/reclaimrx/anomalies` (filter/paginate over `Anomaly`) + `GET /api/v1/reclaimrx/detection-runs` (over `DetectionRun`). |

## 4. Rule set (v2)

**A — precise, run as-is (with engine rework):**
- ALL-001 Duplicate Claim (B1/Paid, ≥2 distinct auth, exclude reversal/duplicate-lifecycle)
- MFR-002 Bill-Reverse-Rebill (B1→B2→B1 ≤14d, higher-NQ rebill)
- **Reject-75→70 fast-rebill** (V4) — buckets ≤12h / 12–24h

**B — recalibrated to outlier (V2):**
- MFR-003 Contracted Rate Deviation → own-prior-period z-score, min 30 prior fills, \|z\|≥3 + $ floor (now with **real FDB WAC** per NDC, not just CSV `extended_wac`)
- MFR-004 Volume Spike → peer z-score, min peer count, top ~0.5%
- HP-005 Prescriber Outlier → peer std-dev, min 20 peers + volume floor
- HP-008 High-Cost Claimant → true population percentile + $ floor
- ALL-006 Weekend/Holiday Spike → min weekday-volume floor, top outliers only
- ALL-005 Early Refill → per-patient prior-fill gap, clear cases + repeat offenders

**MFR-001 (reframed, V3):** per-patient prior-NQ deviation for the same drug; threshold set after portal review.

**New-C (V5):**
- ALL-002 Phantom/Excluded Pharmacy: `pharmacy_npi` not in `reference.dataq_master` (82,643) OR deactivated OR present in `reference.oig_leie_exclusions`/`sam_exclusions` (join) OR flagged in `reference.ncpdp_pharmacy_fwa_actions` (383,862)
- ALL-003 Phantom/Excluded Prescriber: `prescriber_npi` not in `reference.prescribers` (9.49M) OR `status='deactivated'` OR OIG/SAM exclusion join. (No DEA leg — `dea_registrations` empty.)
- **FDB pricing enrichment:** join NDC → `reference.fdb_ndc_price_history` for current WAC (price_type 09) / NADAC (24/25) / SWP-as-AWP (07; confirm with team), feeding MFR-001/003 with authoritative pricing instead of only the CSV's embedded values.

**LATER (unchanged, no data):** ALL-007/008/009/010, MFR-005/006/007/008, HP-001/002/003/004/006/007/009/010, TPA-*, 340B-*, WC-*, TH-001/003/004. (TH-002/005 optional — keep deferred unless wanted.)

## 5. Reference-data integration

- Migration: `GRANT SELECT` to the reclaimrx app role on `reference.dataq_master`, `reference.ncpdp_pharmacy_fwa_actions`, `reference.prescribers`, `reference.oig_leie_exclusions`, `reference.sam_exclusions`, `reference.fdb_ndc_price_history`, `reference.fdb_price_type_desc`, `reference.drugs` (or read-only views over them). Document as the shared-reference-read exception.
- Lookups done **set-based** during the single scan / as pre-joined CTEs (NOT per-row N+1): e.g. left-join the distinct `pharmacy_npi` set against `dataq_master`+exclusions once; build an in-memory valid-NPI set or a temp table.
- NPI→entity_name for the portal adapter: from `dataq_master` (pharmacy) / `prescribers` (prescriber).
- **AWP caveat:** FDB has no true AWP price type; type 07 (SWP) is the proxy. Confirm with team before using for any rate rule.

## 6. Engine rework (V7) — detail

- **Single scan:** one `yield_per` stream over `csv_upload_rows` per run; for each row, evaluate all applicable per-row rules (MFR-001, ALL-002/003, pricing); accumulate anomalies in a buffer; flush via `execute_values` every N (e.g. 5,000). Grouping/statistical rules stay set-based SQL (one query each), not per-row.
- **No savepoint-per-anomaly:** batch insert; sanitize snapshot fields up front (NPI→NULL-if-not-10, keep raw in `finding_details`) so inserts don't violate CHECKs.
- **Flag-rate guardrail:** track per-rule + total fire counts; if total fires > `flag_rate_cap × record_count` (default 5%), mark the run `completed_with_warnings` (or abort per config), record the offending rule(s) in `resolution_stats`, and do NOT silently persist a 30% flood.
- **Eval-log:** `finding_raised` + `error` rows only; `no_finding` as aggregate counts on the run.
- **Statement timeout:** stays 0 for the batch session.

## 7. API + portal wiring (V8/V9)

- **Backend:** `GET /api/v1/reclaimrx/anomalies?run_id&finding_code&severity&entity_type&status&page` → paginated `AnomalyRead` (RLS-scoped, MFA per existing pattern). `GET /api/v1/reclaimrx/detection-runs` → run list (`source_filename`, `record_count`, `anomaly_count`, `status`, `started_at`, `resolution_stats`).
- **Adapter (Anomaly → Leakage row):** `finding_code`→category (mapping table), entity_type from which NPI is set, `entity_name` via reference lookup, `amount_paid`→estimated_leakage, status map (`open→new`, `under_review→under_investigation`, …), `case_id`→investigation_id.
- **Frontend:** repoint `/reclaimrx/leakage` queryFn to `/anomalies` + swap/extend the `LeakageFlag` type; add `finding_code` + `severity` filters to the existing FilterPanel. Wire the `graph-runs` stub → `/detection-runs` as a runs list (ConfigurableDataTable). No new components.

## 8. Calibration workflow (the deliverable loop)

1. Run detection (re-detect on the already-ingested 2.6M rows).
2. Open Leakage Monitor → filter by `finding_code` → eyeball what each rule flagged + the metric in `finding_details`.
3. Adjust the rule's percentile/z/min-sample/$-floor params (tenant `detection_rule_instance.parameters`).
4. Re-run detection-only; repeat until flag rate + precision look right (target <1%).
MFR-001 + reject-75→70 group-key choice are calibrated this way.

## 9. Out of scope (v2)

DEA validation, formulary/PA, therapeutic-class, 340B, workers-comp, telehealth-flag rules, copay-accumulator; the GTN dashboard / risk-scores / recovery portal endpoints (separate World-B/GTN workstream); recoup-case workflow; ML scoring/training; graph analysis.

## 10. Testing

- Recalibration unit tests: percentile/z-score/min-sample/$-floor helpers; each recalibrated rule fires on planted outliers, NOT on the bulk (assert flag rate on a synthetic distribution < cap).
- Reject-75→70: planted 75→70 sequences at 6h/18h/30h → assert ≤12h and 12–24h buckets correct, >24h excluded; group-key behavior.
- New-C: planted invalid/deactivated/excluded NPIs → ALL-002/003 fire; valid NPIs don't. Reference joins set-based (query-count test, no N+1).
- Engine: flag-rate guardrail trips on a synthetic 30%-fire rule; batched insert correctness; single-scan produces same anomalies as multi-scan on the fixture.
- API: `/anomalies` + `/detection-runs` RLS-scoped (cross-tenant test as `ifx_dev_app`), pagination, filters.
- Adapter: Anomaly→Leakage mapping unit tests (finding_code→category, NPI→entity, status map).
- Full-file acceptance: re-detect 2.6M → flag rate <1%, completes in reasonable time, results visible + filterable in Leakage Monitor.

## 11. Risks

| Risk | Mitigation |
|---|---|
| Recalibration still over/under-fires | Flag-rate guardrail + portal eyeball loop before locking thresholds |
| Reference cross-schema read vs module isolation | Explicit grant/views + documented shared-reference exception |
| AWP proxy (SWP) wrong basis | Confirm with team before any AWP-based rule; WAC is solid |
| Single-scan refactor regresses rule results | Parity test vs current per-rule results on the fixture |
| Portal type swap breaks Leakage Monitor | Adapter + type test; keep World-B Investigation screens untouched |
| Detection still slow at 2.6M | Single-scan + batched writes + set-based grouping; measure in acceptance run |

---

## 12. Codex L1 hardening (supersedes looser language above)

### H1 — Guardrail safe + schema-valid (was V7)
- **Stage then promote.** Detection writes anomalies to a **run-scoped staging path**: either (a) count fires per rule in-pass and insert only after the run passes the cap, or (b) insert into `reclaimrx.anomalies` inside ONE transaction and **roll back the whole run** if the cap trips (no partial flood ever visible). Default = (b) hard atomic.
- **No new status value.** `detection_runs.status` stays in the existing CHECK (`in_progress/completed/failed/cancelled`). Over-cap → `status='failed'` + `resolution_stats.guardrail = {tripped:true, rule, fire_rate, cap}`. Persist NO anomalies for a failed run.
- **Hard-fail, not warn.** Full-file detection over the cap is a `failed` run, not a warning with persisted rows.
- **Cap default = 1%** total run fire rate (aligned to target), plus a per-rule cap (default 0.5%). Configurable in run params.

### H2 — Calibration parameter table (exact, per rule) — was V2
Each `detection_rule_instance.parameters` MUST carry these explicit keys (no implicit defaults):
`cohort_key` (exact columns), `eligible_statuses` (e.g. ['Paid'] B1 only), `lookback_window_days` + `current_window`, `statistic` (`percentile_cont` value e.g. 0.99 OR z-score with `z_threshold`), `tie_handling`, `min_group_size`, `min_entity_count`, `dollar_floor` (Decimal), `rule_fire_rate_cap`. Percentiles computed **within the named cohort**, not global, unless stated. Reversals/rejects excluded unless the rule targets them. **Acceptance = run FAILS if total flag rate > 1%** (not a 5% warn). The plan must enumerate these values per recalibrated rule (MFR-003/004, HP-005/008, ALL-006, ALL-005).

### H3 — MFR-001 coverage-gated (was V3)
- **Disabled by default** until a coverage report runs: count patients with ≥`min_prior_fills` paid B1 fills of the same drug (`ndc`) within `lookback_window_days`. Exact defs: patient key=`patient_unique_hash`, drug key=`ndc` (GPI as alt if NDC too sparse), paid B1-only, `min_prior_fills` (default 3), `min_elapsed_days`, prior statistic = **median** prior NQ (robust to outliers).
- If coverage < a threshold (e.g. <20% of claims have enough history) → **fall back** to the per-NDC top-percentile approach (catalog doc) OR keep MFR-001 disabled. The plan includes the coverage-measurement task as a hard gate before enabling.

### H4 — Anomalies API is server-side filtered/paginated (was V8/V9)
- `GET /anomalies` contract: server-side `finding_code`, `severity`, `entity_type`, `status`, `run_id` filters + sort + `page`/`page_size` + `total_count`. NOT client-side fetch-all.
- **`entity_name` enrichment is set-based per page**: collect the distinct NPIs in the page, one batched join to `reference.dataq_master`/`reference.prescribers`, map back. No per-anomaly lookup.
- Leakage Monitor frontend MUST send filters/page to the backend (replace the client-side `useMemo` fetch-all). This is a real change to the page, not just a queryFn repoint.

### H5 — ALL-002/003 operate only on valid NPIs (was V5)
- Reference rules evaluate ONLY normalized **10-digit** NPIs. Missing/invalid/non-NPI identifiers are **NOT** flagged as phantom — they increment a `data_quality` counter in `resolution_stats` (or an optional separate low-severity `data_quality` finding), OUTSIDE the <1% FWA target.
- Phantom = valid 10-digit NPI with **no** match in `reference.dataq_master`/`reference.prescribers`. Excluded = exact NPI match in `reference.oig_leie_exclusions`/`sam_exclusions`. Both require exact identifier match + source provenance (table, exclusion date) in `finding_details`.

### H6 (was MEDIUM) — locked
- **Reject 75→70 group key:** HARD GATE — pick `rx_number_hash` (same-claim rebill) as primary; document collision/split behavior with reviewed examples before production enablement.
- **`finding_code → LeakageCategory` mapping:** defined in the plan as an explicit table; **anomaly API uses its OWN DTO** (`AnomalyRead`), adapted to the portal row shape only at the page boundary — World-B `Investigation`/`LeakageFlag` types are NOT mutated (no shared-type breakage).
- **AWP/SWP gate in rule config:** WAC-based rules may run; any SWP-as-AWP rule stays `disabled` until the pricing basis is signed off by the team.
