# TODO

Linked-task tracker for in-code TODO/FIXME markers and deferred follow-ups
(per CLAUDE.md: "No TODO/FIXME without a linked task in tasks/todo.md").

---

## TODO-4c-001 — MFR-003 / HP-008 per-row evaluators never fire (no baseline cache)

**Module:** reclaimrx — `src/detection/mfr003_evaluator.py`, `src/detection/batch_engine.py`
**Severity:** HIGH (latent — rules silently produce zero anomalies; no crash)
**Found by:** codex L3 pre-ship review, 2026-06-01. Pre-existing gap (identical at HEAD),
not a regression from the Task 4c crash-recovery fix.

**Problem:** `evaluate_mfr003_row` and `evaluate_hp008_row` call
`_derive_statistical_metric(..., baseline=None, ...)`. Both MFR-003 (z-score vs
pharmacy_own_rate_history) and HP-008 (member_cost percentile) short-circuit to `{}`
when `baseline is None`, so `result["_fired"]` is never truthy and the adapters always
return `None`. Task 4c wired the per-row streaming dispatch (`_PER_ROW_STAT_CODES` branch
in `_dispatch_statistical_rules`) but never wired the baseline cache the evaluators need.

**Fix (scoped):**
1. Pre-load a baseline cache per per-row rule using `_BASELINE_KIND_MAP`
   (MFR-003 → `pharmacy_own_rate_history`, HP-008 → `member_cost`) before the stream.
2. Compute the per-row scope key (MFR-003 → pharmacy_npi+ndc; HP-008 → patient_unique_hash)
   and pass the matching baseline into `evaluate_mfr003_row` / `evaluate_hp008_row`.
3. Add `run_detection` regression tests proving seeded baselines yield MFR-003 / HP-008
   anomalies (Decimal-only, ROUND_HALF_UP for any money math).
4. Re-run codex L3 until no HIGH.

**Status:** OPEN — deferred follow-up (decision 2026-06-01: land crash fix first).
