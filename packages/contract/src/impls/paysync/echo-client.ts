// packages/contract/src/impls/paysync/echo-client.ts
// EchoClient -- Wave 41 M6 Echo Spec 400 contract.
// Wraps listEchoRuns, getEchoRun, listEchoIngestions, runEchoCandor
// from the operator portal's paysync-api.ts (portal/shared/lib/paysync-api.ts).
//
// Base URL note: the existing portal paysync-api.ts routes through the billing
// backend at /api/v1/billing/echo (not /admin/paysync/echo -- that is the UI
// route). Confirm PAYSYNC_BASE in paysync-api.ts before wiring RealImpl.
//
// Plan E Step 6.0b -- stub interface + cache policies only.
// RealImpl + MockImpl deferred to the Plan F / Echo surface implementation phase.

import type { CachePolicy } from "../../cache-policy.js";

// -- Types ------------------------------------------------------------------

export type EchoRunStatus =
  | "pending_submission"
  | "submitted"
  | "status_received"
  | "reconciled"
  | "failed";

export type EchoSpec400Run = {
  readonly id: string;
  readonly run_date: string; // YYYY-MM-DD
  // null until the NACHA file is generated and stored
  readonly file_path: string | null;
  // SHA-256 hex of the generated file for integrity verification
  readonly file_sha256: string | null;
  readonly record_count: number;
  // Decimal as string per financial-precision.md -- never a float
  readonly total_amount: string;
  readonly submitted_at: string | null; // ISO 8601
  readonly submitted_by: string | null; // user_id
  readonly status_file_received_at: string | null;
  readonly status_file_processed_at: string | null;
  readonly manual_ap_record_ids: string[];
  readonly status: EchoRunStatus;
  readonly created_at: string; // ISO 8601
};

export type EchoIngestion = {
  readonly id: string;
  readonly echo_run_id: string;
  readonly ingested_at: string; // ISO 8601
  readonly record_count: number;
  readonly status: "success" | "partial" | "failed";
  readonly error_summary: string | null;
};

export type EchoRunListResponse = {
  readonly items: EchoSpec400Run[];
  readonly total: number;
  readonly next_cursor: string | null;
};

export type EchoIngestionListResponse = {
  readonly items: EchoIngestion[];
  readonly total: number;
};

// -- Cache Policies ---------------------------------------------------------

export const PAYSYNC_ECHO_CACHE_POLICIES: Record<string, CachePolicy> = {
  listEchoRuns: {
    ttl_seconds: 30,
    key: ["paysync", "echo", "{tenant_id}", "runs"],
    invalidation_tags: ["paysync:echo"],
    backend_down: "stale-ok",
  },
  getEchoRun: {
    ttl_seconds: 60,
    key: ["paysync", "echo", "{tenant_id}", "runs", "{run_id}"],
    invalidation_tags: ["paysync:echo"],
    backend_down: "stale-ok",
  },
  runEchoCandor: {
    // Mutation -- no caching; triggers invalidation of all echo tags
    ttl_seconds: 0,
    key: ["paysync", "echo", "{tenant_id}", "candor"],
    invalidation_tags: ["paysync:echo"],
    backend_down: "fail-fast",
  },
  listEchoIngestions: {
    ttl_seconds: 30,
    key: ["paysync", "echo", "{tenant_id}", "runs", "{run_id}", "ingestions"],
    invalidation_tags: ["paysync:echo"],
    backend_down: "stale-ok",
  },
};
