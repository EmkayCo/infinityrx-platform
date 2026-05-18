// src/bff/quality.ts
// BFF aggregator and dismiss routes for the data-quality dashboard (SP-2 Plan D).
//
// Auth pattern: verifyTokenRaw + AccessClaimsSchema.safeParse — same as Plan C
// (stateless; shell middleware handles revocation checking).
//
// Dismiss state: Redis is NOT available in this Next.js package (no ioredis
// dependency in package.json). Dismiss state is stored in a BFF-local Map keyed
// by "{tid}:{source}" with an expiry timestamp. This is INTENTIONALLY NON-DURABLE:
//   - State is lost on Next.js server restart or redeployment.
//   - State is NOT shared across replicas in multi-pod deployments.
//   - TTL is 24h, matching Plan A §10.5 dir:alert_dismissed:{tid}:{source} semantics.
// This is explicitly accepted as best-effort UX for SP-2 launch. A future wave
// can replace this Map with an ioredis call once Redis is added to the portal deps.

import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import {
  verifyTokenRaw,
  AccessClaimsSchema,
  resolveEnvClaim,
} from "@infinityrx/auth";

const INGESTION_BASE =
  process.env.PRESCRIBER_DIRECTORY_URL ?? "http://prescriber-directory:8010";
const PHARMACY_BASE =
  process.env.PHARMACY_DIRECTORY_URL ?? "http://pharmacy-directory:8009";
const DRUG_BASE =
  process.env.DRUG_DATABASE_URL ?? "http://drug-database:8011";

// ---------------------------------------------------------------------------
// Dismiss store — BFF-local, non-durable, 24h TTL per dismiss action.
// Key: "{tid}:{source}" → expiry timestamp (ms since epoch).
// ---------------------------------------------------------------------------

const DISMISS_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours
const _dismissStore = new Map<string, number>();

function _isDismissed(tid: string, source: string): boolean {
  const key = `${tid}:${source}`;
  const expiry = _dismissStore.get(key);
  if (expiry === undefined) return false;
  if (Date.now() > expiry) {
    _dismissStore.delete(key);
    return false;
  }
  return true;
}

function _setDismissed(tid: string, source: string): void {
  const key = `${tid}:${source}`;
  _dismissStore.set(key, Date.now() + DISMISS_TTL_MS);
}

// ---------------------------------------------------------------------------
// Quality-source allowlist — sources that can appear in the quality dashboard.
// Superset of TRIGGERABLE_SOURCES (adds fdb which is b9_blocked/no_loader).
// bpg and relay-health are excluded: no IngestionSchedule row.
// ---------------------------------------------------------------------------

export const QUALITY_SOURCES: ReadonlySet<string> = new Set([
  "nppes",
  "nppes_monthly",
  "nppes_deactivation",
  "ncpdp",
  "fda_ndc",
  "fda_orange_book",
  "fda_purple_book",
  "fda_drug_shortages",
  "fda_rems",
  "rxnorm",
  "hcpcs",
  "icd10_cm",
  "cms_asp",
  "cms_nadac",
  "state_medicaid_bins",
  "cms_opt_out",
  "ofac_sdn",
  "sam_exclusions",
  "oig_leie",
  "dea_registrations",
  "fdb",
]);

// Sources that can be dismissed. fdb can be dismissed even though it has no
// loader (the alert for b9_blocked is still actionable from an operator POV).
// Codex CONCERN resolved: use quality-source allowlist, not triggerable-source.
export const DISMISSIBLE_SOURCES: ReadonlySet<string> = QUALITY_SOURCES;

// Cluster assignment per source key — verified against Plan A §10.3 and Plan D §D-D3.
const SOURCE_CLUSTER: Record<string, string> = {
  nppes: "prescribers",
  nppes_monthly: "prescribers",
  nppes_deactivation: "prescribers",
  ncpdp: "pharmacies",
  fda_ndc: "drugs",
  fda_orange_book: "drugs",
  fda_purple_book: "drugs",
  fda_drug_shortages: "drugs",
  fda_rems: "drugs",
  rxnorm: "drugs",
  hcpcs: "codes",
  icd10_cm: "codes",
  cms_asp: "pricing",
  cms_nadac: "pricing",
  state_medicaid_bins: "pricing",
  cms_opt_out: "exclusions",
  ofac_sdn: "exclusions",
  sam_exclusions: "exclusions",
  oig_leie: "exclusions",
  dea_registrations: "exclusions",
  fdb: "drugs",
};

// ---------------------------------------------------------------------------
// Auth helper — returns parsed claims or a 401 NextResponse.
// ---------------------------------------------------------------------------

type AuthResult =
  | { ok: true; claims: { sub: string; tid: string } }
  | NextResponse;

async function _verifyAuth(
  req: NextRequest,
  correlationId: string,
): Promise<AuthResult> {
  const authHeader = req.headers.get("authorization") ?? "";
  const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : null;

  if (!token) {
    return NextResponse.json(
      {
        error: {
          code: "UNAUTHORIZED",
          message: "Authentication required",
          correlation_id: correlationId,
        },
      },
      { status: 401 },
    );
  }

  try {
    const env = resolveEnvClaim(process.env.INFINITYRX_ENV ?? "development");
    const secret = process.env.JWT_SECRET ?? "";
    const raw = await verifyTokenRaw(token, secret, env);
    const parsed = AccessClaimsSchema.safeParse(raw);
    if (!parsed.success) {
      return NextResponse.json(
        {
          error: {
            code: "UNAUTHORIZED",
            message: "Invalid token claims",
            correlation_id: correlationId,
          },
        },
        { status: 401 },
      );
    }
    return {
      ok: true,
      claims: { sub: parsed.data.sub, tid: parsed.data.tid },
    };
  } catch {
    return NextResponse.json(
      {
        error: {
          code: "UNAUTHORIZED",
          message: "Invalid token",
          correlation_id: correlationId,
        },
      },
      { status: 401 },
    );
  }
}

// ---------------------------------------------------------------------------
// GET /api/directories/quality
// Aggregates SourceStatus from shared ingestion API + per-module record counts.
// Returns DatasetQuality[] for the quality dashboard sidebar.
// ---------------------------------------------------------------------------

export async function getQuality(req: NextRequest): Promise<NextResponse> {
  const correlationId =
    req.headers.get("x-correlation-id") ?? crypto.randomUUID();

  const authResult = await _verifyAuth(req, correlationId);
  if (authResult instanceof NextResponse) return authResult;
  const { tid } = authResult.claims;

  // Parallel fan-out — 200ms budget per backend via AbortSignal.
  const controller = new AbortController();
  const fanOutTimeout = setTimeout(() => controller.abort(), 200);
  let isPartial = false;

  let sourceStatuses: Array<{
    source: string;
    cron_expression: string | null;
    enabled: boolean;
    last_run: {
      status: string;
      records_inserted: number;
      records_errored: number;
      started_at: string;
    } | null;
    last_success_at: string | null;
    next_run_at: string | null;
  }> = [];

  try {
    const [statusResp, pharmacyResp, drugResp] = await Promise.allSettled([
      fetch(`${INGESTION_BASE}/api/v1/data-ingestion/status`, {
        headers: { "x-correlation-id": correlationId },
        signal: controller.signal,
      }),
      // Pharmacy stats require x-tenant-id as a query param (mandatory per router.py:442).
      // tid is derived from validated JWT claims — not from request input.
      fetch(
        `${PHARMACY_BASE}/api/v1/pharmacies/stats?x-tenant-id=${encodeURIComponent(tid)}`,
        {
          headers: { "x-correlation-id": correlationId },
          signal: controller.signal,
        },
      ),
      fetch(`${DRUG_BASE}/api/v1/drugs/refresh/status`, {
        headers: { "x-correlation-id": correlationId },
        signal: controller.signal,
      }),
    ]);

    clearTimeout(fanOutTimeout);

    if (statusResp.status === "fulfilled" && statusResp.value.ok) {
      sourceStatuses = await statusResp.value.json();
    } else {
      isPartial = true;
    }

    // Pharmacy and drug stats are informational extras — partial is acceptable.
    if (pharmacyResp.status === "rejected" || !pharmacyResp.value?.ok) {
      isPartial = true;
    }
    if (drugResp.status === "rejected" || !drugResp.value?.ok) {
      isPartial = true;
    }
  } catch {
    clearTimeout(fanOutTimeout);
    isPartial = true;
  }

  // Build status lookup by source key.
  const statusBySource = new Map(
    sourceStatuses.map((s) => [s.source, s]),
  );

  // Assemble quality rows for all 21 quality sources.
  const datasets = [];
  for (const source of QUALITY_SOURCES) {
    const status = statusBySource.get(source);
    const cluster = SOURCE_CLUSTER[source] ?? "drugs";
    const isB9Blocked = source === "fdb";
    const noLoader = isB9Blocked;

    datasets.push({
      source,
      cluster,
      last_run_at: status?.last_run?.started_at ?? null,
      last_success_at: status?.last_success_at ?? null,
      last_run_status: status?.last_run?.status ?? null,
      records_inserted: status?.last_run?.records_inserted ?? null,
      records_errored: status?.last_run?.records_errored ?? null,
      cron_expression: status?.cron_expression ?? null,
      next_run_at: status?.next_run_at ?? null,
      // Dismiss state derived from JWT claims (tid from validated token, not request input).
      is_dismissed: _isDismissed(tid, source),
      no_loader: noLoader,
      b9_blocked: isB9Blocked,
    });
  }

  const res = NextResponse.json(
    {
      datasets,
      as_of: new Date().toISOString(),
      is_partial: isPartial,
    },
    { status: 200 },
  );
  res.headers.set("x-correlation-id", correlationId);
  // Quality data is not PHI (reference data only) — cache at proxy layer.
  res.headers.set("Cache-Control", "s-maxage=60, stale-while-revalidate=30");
  return res;
}

// ---------------------------------------------------------------------------
// POST /api/directories/quality/dismiss/{source}
// Marks an alert dismissed in the BFF-local dismiss store (24h TTL).
// Returns 204 on success, 404 for unknown sources.
// Only DISMISSIBLE_SOURCES may be dismissed (all 21 quality sources).
// ---------------------------------------------------------------------------

export async function dismissAlert(
  req: NextRequest,
  source: string,
): Promise<NextResponse> {
  const correlationId =
    req.headers.get("x-correlation-id") ?? crypto.randomUUID();

  const authResult = await _verifyAuth(req, correlationId);
  if (authResult instanceof NextResponse) return authResult;
  const { tid } = authResult.claims;

  if (!DISMISSIBLE_SOURCES.has(source)) {
    const res = NextResponse.json(
      {
        error: {
          code: "SOURCE_NOT_FOUND",
          message: `Source '${source}' is not a recognized quality dashboard source`,
          correlation_id: correlationId,
        },
      },
      { status: 404 },
    );
    res.headers.set("x-correlation-id", correlationId);
    return res;
  }

  _setDismissed(tid, source);

  const res = new NextResponse(null, { status: 204 });
  res.headers.set("x-correlation-id", correlationId);
  return res;
}
