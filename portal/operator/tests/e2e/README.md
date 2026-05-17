# Operator Portal — Playwright E2E Tests

## Overview

End-to-end tests that run the Playwright browser against a live dev server
and (for full integration tests) the full docker-compose backend stack.

Tests fall into two tiers:

| Tier | Gate | Backend required |
|---|---|---|
| Smoke / mock | Always-on | No — API is mocked at network layer |
| Round-trip (SP-1) | `E2E_STACK_READY=true` | Yes — full docker-compose stack |

## Running smoke tests (no backend needed)

```bash
cd portal/operator
npx playwright test --project chromium
```

Smoke tests mock every backend API call via `page.route()`. They verify
UI shell, route loading, and operator flow state machines.

## Running the SP-1 round-trip spec

### Prerequisites

1. Full docker-compose stack running:

```bash
# From repo root
docker-compose up -d postgres redis rabbitmq core-platform billing
```

2. Dev server running (or let Playwright start it):

```bash
cd portal/operator
npm run dev
```

3. Playwright installed:

```bash
npx playwright install chromium
```

### Run command

```bash
cd portal/operator
E2E_STACK_READY=true PW_REUSE_SERVER=true npx playwright test sp1-paysync-round-trip
```

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `E2E_STACK_READY` | `false` | Set to `"true"` to lift the skip guard on round-trip tests |
| `CORE_BASE_URL` | `http://localhost:8000` | Base URL for core-platform backend |
| `BILLING_BASE_URL` | `http://localhost:8001` | Base URL for billing backend |
| `PORTAL_BASE_URL` | `http://localhost:3000` | Base URL for the Next.js portal |
| `PW_REUSE_SERVER` | `false` | Set to `"true"` to reuse an already-running dev server |

## SP-1 round-trip spec (`sp1-paysync-round-trip.spec.ts`)

Full 25-step scenario covering the Operator -> Approver -> Auditor workflow:

**Operator (alice_operator):**
1. Navigate to PaySync Inbox
2. Upload `upload-001-healthy.csv` via the Uploads page
3. Assert upload status transitions `parsing` -> `validated`
4. Assert Inbox shows `upload_validated_awaiting_batching`
5. Open UploadDetailPage, assert 20 claims visible
6. Create draft batch from upload
7. Assert ProvenanceBreadcrumb shows upload reference

**Approver (bob_approver):**
8. Open Inbox, see `batch_drafted` item
9. Close the current cycle
10. Send the draft invoice (assert MoneyDisplay + explicit confirm step)
11. Release the held payment run
12. Generate NACHA file (assert artifact + download link)
13. Generate 835 file (assert ProvenanceTrace shows Upload -> Cycle -> Batch -> File)
14. Download NACHA file, assert non-empty response body
15. Finalize reconciliation

**Auditor (carol_auditor):**
16. Open Inbox, see `journal_periodic_review` item
17. Navigate to Journal, assert entries visible
18. Trigger HashChainVerifierPanel verify
19. Assert green badge "Chain intact — N entries verified"
20. Assert generate button disabled with "Approver role required" tooltip
21. Navigate to Files, assert all artifacts visible and download works
22. Navigate to Reports, assert all pages render without errors

**Final assertions:**
23. ProvenanceBreadcrumb present on UploadDetailPage
24. RoleSwitcherChip absent from page source
25. All Inbox items in terminal state

## Role switching

Roles are switched by closing the current browser context and opening a new one
authenticated as the next fixture user. Authentication uses the test-auth
shortcut endpoint (`POST /api/v1/core/test-auth/token`) which issues a real
HS256 JWT for the fixture user.

**The test-auth endpoint is blocked in production** (`INFINITYRX_ENV=production`
returns 403). It is only available in `development` and `mock` environments.

## Fixture data

Seed data lives in `packages/modules/paysync/fixtures/seeds/*.json`.
The spec calls `POST /api/v1/billing/seed` in `beforeAll` to populate the DB
and `DELETE /api/v1/billing/seed` in `afterAll` to clean up.

The upload CSV is `packages/modules/paysync/fixtures/uploads/upload-001-healthy.csv`
(20 healthy claims, zero validation failures).

## CI integration

Add to `.github/workflows/sp1-paysync.yml`:

```yaml
- name: Start docker-compose stack
  run: docker-compose up -d postgres redis rabbitmq core-platform billing

- name: Wait for backends
  run: |
    until curl -sf http://localhost:8000/health && curl -sf http://localhost:8001/health; do
      sleep 2
    done

- name: Run SP-1 E2E round-trip
  env:
    E2E_STACK_READY: "true"
    CORE_BASE_URL: http://localhost:8000
    BILLING_BASE_URL: http://localhost:8001
  run: |
    cd portal/operator
    npx playwright install --with-deps chromium
    npx playwright test sp1-paysync-round-trip --reporter=list
```
