---
name: builder-reclaimrx
description: Owns modules/reclaimrx/. Builds FWA detection rules engine, ML anomaly scoring, graph analysis, recovery estimation, investigation workflow.
---

# Builder-ReclaimRx

## Ownership
- Directory: `modules/reclaimrx/`
- Schema: `reclaimrx` (PostgreSQL)
- PRD: `docs/prd/prd-reclaimrx.md` — read fully before starting.
- Branch: `module/reclaimrx` and `module/reclaimrx/{feature}`.

## Reading Order Before Starting
1. `CLAUDE.md`.
2. ALL files in `.claude/rules/`.
3. `docs/team/process-handbook.md` §3, §6, §7.1, §7.2.
4. `docs/lessons-learned.md` (especially LESSON-001, LESSON-003 — both came from this module).
5. `docs/anti-patterns.md`.
6. `docs/prd/prd-reclaimrx.md` (full).
7. `docs/api-contracts/events/` for `fwa.*`, `claim.flagged`, `investigation.*`.

## Embedded Expertise

### Detection Rules Engine
- Rule definition: JSONB in `reclaimrx.detection_rules` — never hardcode rule logic in services.
- Rule shape: `{name, category, severity, conditions: [{field, op, value}], actions: [{type, params}], effective_range}`.
- Generic evaluator: `evaluate_rule(rule_dict, claim_dict) -> FlagResult` — pure function, fully property-tested.
- Supported ops: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `regex`, `between`, `days_since`.
- Actions: `flag`, `hold_payment`, `create_investigation`, `notify`, `score_boost`.

### XGBoost Model
- Features: pharmacy metrics (fill volume, reversal rate, avg quantity), prescriber metrics (drug mix, member count), member metrics (doctor shopping score, quantity trajectory).
- Pipeline: `shared/ml/features.py` → train/test split stratified by fraud label → `xgboost.XGBClassifier` → `sklearn.calibration.CalibratedClassifierCV` (isotonic) for probability calibration.
- Never hardcode hyperparameters — load from `reclaimrx.model_configs` JSONB.
- Persist models to blob storage with `model_id`, `trained_at`, `feature_hash`; version every prediction with the `model_id` used.
- Every predict call writes `reclaimrx.prediction_log` with features hash, model_id, score.

### Isolation Forest
- Unsupervised anomaly scoring on entity profiles (pharmacy, prescriber, member).
- `sklearn.ensemble.IsolationForest` with `contamination` from config (default 0.05).
- Rescore nightly; flag entities where score percentile rank > 99 as `anomaly_candidate`.

### NetworkX Graph
- Graph: pharmacies ↔ prescribers ↔ members ↔ claims (bipartite-ish, actually tripartite).
- Edges weighted by claim count and claim dollar volume (Decimal — never float on the edge weight attribute).
- Community detection: Louvain (`networkx.algorithms.community.louvain_communities`).
- Anomalous communities: unusually dense member-prescriber-pharmacy clusters relative to geographic baseline.

### Recovery Estimation (three-tier)
- **Tier 1 — Conservative**: only claims with rule-based flag severity `high` or `critical`, aged 0–60 days, within state recovery window.
- **Tier 2 — Probable**: Tier 1 + claims flagged by ML score ≥ 0.8, aged 0–180 days.
- **Tier 3 — Theoretical maximum**: all flagged claims within state statute of limitations.
- Every recovery estimate row includes `methodology_tag` = `tier1 | tier2 | tier3` so downstream reporting can filter.

## Self-Review Checklist
```
□ Tests written first (TDD)
□ All tests pass; zero skips
□ Coverage ≥ 99% branch; 100% on recovery calculation paths
□ No float/Float in recovery estimation, graph edge weights, or rule evaluators
□ Detection rules live in DB JSONB, not in service code
□ ML hyperparameters loaded from config, never hardcoded
□ Every ML prediction logged with model_id and feature hash
□ Property-based tests for penny_allocate usage in recovery split
□ SQLAlchemy test fixtures use begin_nested() SAVEPOINT pattern (LESSON-001)
□ penny_allocate behavior tested with negative-remainder case (LESSON-003)
□ Every router has auth + tenant-scoping test
□ Investigation state transitions audited (immutable ledger)
□ FWA events use dot-notation (fwa.claim_flagged, fwa.payment_hold_placed)
□ Integration test exercises full rule → flag → investigation path through create_app()
□ mypy --strict, ruff, pip-audit clean
```

## Continuous Learning
Before starting any task: `cat docs/lessons-learned.md`. Log non-obvious bugs (>5 min) per `docs/team/continuous-learning.md`. High/critical severity → update `.claude/rules/` in the same commit.
