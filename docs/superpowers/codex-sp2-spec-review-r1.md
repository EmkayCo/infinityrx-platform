# Codex SP-2 Spec Review — All Rounds

**Spec:** `docs/superpowers/specs/2026-05-16-sp2-directories-portal-design.md`
**Date:** 2026-05-16
**Rounds run:** 3 (budget was 2; r2 verdict required r3)
**Final verdict:** GO-WITH-CHANGES (r3 addressed; spec is ready for plan-writing)

---

## Round 1

**Verdict: NO-GO**

**BLOCK §5.5, §6.4, §6.7 — Wrong ingestion API paths.**
Spec claimed BFF calls `POST /data-ingestion/{source}/trigger` and `GET /data-ingestion/status`.
Actual prefix in `shared/data_ingestion/api/routes.py` docstring is `/api/v1/data-ingestion`.
All ingestion API path references corrected to `/api/v1/data-ingestion/*`.

**BLOCK §5.4, §6.7 — False auth claim on backend router.**
Spec said the backend "already requires JWT auth." Actual `shared/data_ingestion/api/routes.py`
has no `Depends(get_current_user)` on any route — it carries no auth dependency.
Corrected: spec now states BFF is the auth boundary; backend has no auth.

**BLOCK §5.1 — Manifest filename wrong.**
Spec referenced `infrastructure/manifests/operator.yml`. Actual file is
`infrastructure/manifests/operator-dev.yml`. Corrected throughout.

**BLOCK §5.1 — Composition scripts claim.**
Spec implied `scripts/generate-composition.ts` and `scripts/audit-composition.ts` exist.
They do not exist yet — they are built as part of SP-0 execution.
Corrected: spec now states SP-2 depends on SP-0 having shipped them first.

**CONCERN §9.6 — Pharmacy stats cross-tenant test incomplete.**
`GET /api/v1/pharmacies/stats` has mandatory `x-tenant-id` query parameter.
BFF must extract `tid` from JWT and pass it. Added mandatory note + per-endpoint
cross-tenant isolation test requirement.

---

## Round 2

**Verdict: NO-GO**

**BLOCK §1, §2, §4 D3 — Dataset count inconsistency.**
§1 said "~15-16 static reference datasets"; §2 said "all 19 source datasets (6 browse clusters)."
Corrected: spec now says "18 inventoried reference directories (15 with confirmed batch
loaders → 6 browse clusters)."

**BLOCK §4 D3 / §5.2 — Hyphenated source keys.**
Spec used `fda-ndc`, `cms-opt-out` (directory-name form). Actual `_SOURCE_NAME` constants
use underscores: `fda_ndc`, `cms_opt_out`. All source keys corrected to underscore form.

**BLOCK §4 D3 — False claim about "distinct loader files."**
Spec claimed each of the 15 datasets has a distinct loader file. `relay-health`, `fdb`, and
`bpg` have no `_SOURCE_NAME` in `shared/data_ingestion/sources/`. Corrected: spec explicitly
marks these 3 as "no loader" with reasons (reference files only / B9-blocked / live API).

**CONCERN §5.5 — Contradictory mount language.**
Spec said ingestion router "is mounted by each module's `create_app()`" then immediately said
"mount is unconfirmed." Partially fixed in r2; fully resolved in r3.

**CONCERN §9.6 — Pharmacy stats x-tenant-id mandatory.**
BFF must pass `?x-tenant-id={tid}` (mandatory, not optional — 422 without it).
Added explicit BFF pass-through requirement and per-endpoint test.

---

## Round 3

**Verdict: NO-GO**

**BLOCK §1 — "All 15 loaders run on cron schedules" is false.**
`ncpdp` has `DEFAULT_SCHEDULES["ncpdp"] = None` (manual-only).
Corrected: §1 now says "batch loaders run on varying schedules (or manually, as with NCPDP)."

**BLOCK §4 D3, §5.2 — `_SOURCE_NAME` not universal across all loader files.**
`nppes.py` uses `_SOURCE = "nppes"`, `sam_exclusions.py` uses `_SOURCE = "sam_exclusions"`,
`state_medicaid_bins.py` uses `source_name = "state_medicaid_bins"`.
Corrected: D3 notes the three different constant names; §5.2 table annotates each with
its actual constant name; note explains all three are semantically equivalent.

**BLOCK §4 D3 / §5.2 — DEFAULT_SCHEDULES has additional source keys not in D3's 15.**
`DEFAULT_SCHEDULES` in `scheduler.py` contains `nppes_monthly`, `nppes_deactivation`,
`rxnorm`, `oig_leie`, `dea_registrations` — not listed in D3. Confirmed: `rxnorm.py`,
`oig_leie.py`, `dea_registrations.py` DO exist in `shared/data_ingestion/sources/` with
valid source-name constants. These are 3 additional batch loaders.
Corrected: D3 notes these extras; §5.2 adds a DEFAULT_SCHEDULES note; §11 cross-ref
updated; §9.3 fixture note updated. Plan-writer must decide whether to include them
in the ingestion console and which browse cluster (if any) they belong to.

**CONCERN §5.5 — Mount language still contradictory.**
"Mounted by each module's `create_app()`" then "unconfirmed." Fully resolved: removed
the "mounted by" claim; only the "unconfirmed — plan-writer must verify" language remains.

**CONCERN §2/§3 — Unprefixed `POST /{source}/trigger` references.**
Fixed in §3 non-goals and §2 goal #3 to use full `POST /api/v1/data-ingestion/{source}/trigger`.
Also fixed §6.4 component descriptions to use BFF `/api/directories/ingest/*` paths.

**NIT §9.2 — Literal "95%" string.**
Removed; replaced with "insufficient branch coverage percentage."

---

## Autonomous decisions made during drafting

1. **Treated relay-health, fdb, bpg as "no batch loader"** — no `_SOURCE_NAME` found in
   `shared/data_ingestion/sources/`; open questions §10.6 and §10.7 flag them for plan-writer.
2. **Pharmacy stats cross-tenant posture** — reference data is shared/not tenant-scoped;
   pharmacy stats endpoint is the one exception requiring `x-tenant-id` pass-through.
   Ruled as a test requirement, not a spec blocker.
3. **D3 count stayed at 15 primary loaders** despite 3 extra DEFAULT_SCHEDULES sources
   (`rxnorm`, `oig_leie`, `dea_registrations`) — these are surfaced as a plan-writer
   reconciliation item, not added to D3 without product confirmation.
4. **No new events in SP-2** — EventEnvelope rule not triggered (ingestion triggers go
   directly to shared API, no new event types introduced by SP-2 itself).
5. **PHI posture confirmed** — NPPES, FDA, CMS, OFAC, SAM are public reference data.
   No PHIMixin, EncryptedString, or PHI audit required in SP-2.

---

## Spec gaps surfaced (open questions §10)

| # | Gap | Status |
|---|---|---|
| §10.1 | Search index vs BFF fan-out if 300ms budget not achievable | Open — plan-writer decides |
| §10.2 | Plan phasing sequence for Approach A | Open — plan-writer decides |
| §10.3 | Which module mounts shared ingestion router | Open — plan-writer must verify |
| §10.4 | `members/` migration strategy (exclude from SP-2) | Open — plan-writer must confirm |
| §10.5 | Quality alert persistence (session-local vs backend) | Open — plan-writer decides |
| §10.6 | BPG ingestion trigger behavior (live API, no schedule) | Open — plan-writer confirms |
| §10.7 | `relay-health/` vs `RelayHealth/` canonical source | Open — plan-writer determines |
| §10.8 | `medicaid/` BIN coverage maps vs exclusions surface | Open — plan-writer clarifies |
| New | `rxnorm`, `oig_leie`, `dea_registrations` browse cluster assignment | Open — plan-writer reconciles |

---

## Token cost estimate

- Round 1: ~35K tokens (spec read + path verification + review output)
- Round 2: ~40K tokens (re-read + detailed source key verification + review output)
- Round 3: ~30K tokens (targeted re-read + scheduler.py read + review output)
- Total: ~105K tokens across 3 codex rounds
