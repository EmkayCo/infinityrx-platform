# PRD — Module 18: Claims Testing Simulator (FINAL)

**Module:** Claims Testing Simulator
**Folder:** `modules/testing-simulator/`
**Phase:** 5, Wave 4 (after Adjudication Engine)
**Dependencies:** Core Platform (1), Claims Adjudication Engine (8), Rules Engine (7)

---

## 1. Purpose

The Testing Simulator lets operators submit test claims without a real pharmacy system. It validates plan configuration, rules, formulary, and pricing before go-live — and after any change to verify nothing broke. It is a first-class experience that's always accessible, not a hidden tool.

---

## 2. Test Modes

### Interactive Testing
- Operator fills claim form (member, pharmacy, prescriber, NDC, qty, day supply)
- Submits to adjudication in test mode (no financial impact, no history update)
- Response with full detail: pricing breakdown, rules fired, DUR results, PA status, claim trace

### Scenario-Based Testing
- Named test scenarios with predefined inputs and expected outputs
- Save per program or per tenant
- Field-by-field diff: highlight where actual differs from expected

### Regression Testing
- After any rule/formulary/plan change: run all saved scenarios for affected programs
- Red/green report: which pass, which broke, what changed
- Block go-live if critical scenarios fail (configurable severity)
- Scheduled regression: nightly or on-demand
- **Regression dashboard always visible:** green/yellow/red status showing scenario health. Yellow if untested after recent changes.

### Bulk Test Data Generation
- Generate synthetic realistic test claims based on program parameters
- Configurable: N claims across M pharmacies with realistic NDC distribution
- Stress test mode: thousands of test claims for throughput validation

---

## 3. "Test This" Buttons (Integrated Experience)

- **On every rule:** click "Test This" to run a sample claim against just that rule
- **On every plan:** click "Test This Plan" to open simulator pre-filled with that plan's details
- **On every pipeline:** click "Test Pipeline" to run sample claim through full pipeline with trace
- **A/B test mode:** run same claims through two different rule pipelines, compare results side-by-side

---

## 4. Sandbox Environment

- Every tenant gets a sandbox that mirrors production config
- Changes made in sandbox first, tested, then promoted to production
- Sandbox has its own database state — tests don't affect production
- Regression suite runs against sandbox automatically after changes
- One-click promote: sandbox → production with audit trail
- One-click rollback: production → previous version

---

## 5. Scenario Builder

Create test cases from BRD requirements. Pre-built scenario types: standard claim, eligibility (active/terminated/wrong group/future), copay (generic/brand/specialty/non-formulary), DUR (interaction/early refill/duplication/excessive qty), COB (all OC types), PA (approved/denied/expired/not found), compound (multi-ingredient), reversal, under-reimbursement, accumulator detection, copay fraud flag, therapeutic alternative, indication-based coverage.

Each scenario: input fields, expected response (or expected reject code), description, severity (critical/major/minor), tags, associated program.

---

## 6. Medical Claim Test Harness

Same concept for medical claims (EDI 837): build test CMS-1500 or UB-04 in UI, submit to medical claims engine in test mode, validate response against expected EOB/payment.

---

## 7. Switch Certification Support

Import switch-specific certification scripts, map to simulator format, run against adjudication engine in test mode, generate evidence package, store results for re-certification tracking.

---

## 8. Data Models

```
test_scenarios (with severity, tags, claim_input, expected_output), test_scenario_suites, test_runs (with actual_output, diff, result), test_run_summaries, certification_runs, sandbox_environments
```

---

## 9. API, Events, Tests, Session Decomposition

**API:** submit test claim, CRUD scenarios/suites, run suite, run regression, generate synthetic data, run certification, test results with diffs.

**Events:** `testing.scenario_failed`, `testing.suite_completed`, `testing.regression_passed/failed`, `testing.certification_completed`

**Subscribes to:** `rule.updated`, `formulary.updated`, `plan.updated` (trigger regression if auto-run enabled)

**Session decomposition:** (1) test engine: test mode adjudication, result comparison, diff generation; (2) scenario management: CRUD, builder UI, import/export; (3) sandbox & regression: sandbox environments, scheduled runs, dashboard, A/B testing; (4) certification & data gen: switch certification, synthetic claim generator
