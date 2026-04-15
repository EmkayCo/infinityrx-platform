/**
 * Mock endpoint handlers — maps URL patterns to seed data responses.
 * Each entry is a tuple of [pattern, handler].
 * Patterns are matched against the URL pathname (query string stripped).
 *
 * Real-data handlers: endpoints marked with loadAgg() fetch from
 * /data/aggregated/*.json (pre-built static files served from /public).
 */

import {
  BILLING_CYCLES,
  CLAIMS,
  INVOICES,
  MAPPING_TEMPLATES,
  PAYMENT_BATCHES,
  NACHA_FILES,
  VENDORS_LIST,
  SUBMISSIONS,
  ACH_RETURNS,
  FWA_FLAGS,
  INVESTIGATIONS,
  RECOVERY_ROWS,
  FWA_DASHBOARD,
  PHARMACIES,
  PRESCRIBERS,
  DRUGS,
  MEMBERS,
  TRADING_PARTNERS,
  EDI_TRANSACTIONS,
  CERT_ALERTS,
  EDI_MONITOR_STATS,
  REPORT_TEMPLATES,
  GENERATED_REPORTS,
  SCHEDULED_REPORTS,
  BUILDER_METRICS,
  BUILDER_DIMENSIONS,
  DRUG_SPEND_TREND,
  BRAND_GENERIC,
  TOP_BY_SPEND,
  PHARMACY_SCORECARDS,
  NETWORK_ADEQUACY,
  MEMBER_ADHERENCE,
  FINANCIAL_METRICS,
  DATA_QUALITY,
  LIVE_METRICS,
  ACTIVITY_EVENTS,
  SERVICE_HEALTH,
  HIGH_COST_MEMBERS,
  MEDICAL_CLAIMS,
  HCPCS_CROSSWALK,
  UNIFIED_SPEND,
  THREESIXTYFOURTY_SUMMARY,
  SITE_OF_CARE,
  AUDIT_ENTRIES,
  USERS,
  TENANTS,
  CLAIMS_ENRICHED,
  PA_OVERRIDES,
  JOURNAL_ENTRIES,
  makeUUID,
  isoDate,
  money,
  rngInt,
  PRIMARY_TENANT,
} from "./seed";

// ── Real-data helpers ─────────────────────────────────────────────────────────
// Pre-load aggregations from /data/aggregated/*.json on first use.
// These are static files served from the /public directory.

type AggCache = {
  overview?: Record<string, unknown>;
  cycles?: unknown[];
  byClient?: unknown[];
  byNrid?: unknown[];
  topPharmacies?: unknown[];
  topNdcs?: unknown[];
  topClients?: unknown[];
  dailyVolume?: unknown[];
  nridDistribution?: unknown[];
  reversalRate?: Record<string, unknown>;
  activityFeed?: unknown[];
  investigations?: unknown[];
  manifest?: Record<string, unknown>;
};

const _aggCache: AggCache = {};

async function loadAgg<T>(file: string): Promise<T> {
  if (typeof window === "undefined") {
    // Server-side: read from disk directly. Avoids an HTTP self-loop
    // during SSR of pages that use the mock data layer — otherwise a
    // Server Component would fetch() back to the same dev-server process
    // while it's mid-render of the request that triggered the fetch.
    const { readFile } = await import("fs/promises");
    const { join } = await import("path");
    const text = await readFile(
      join(process.cwd(), "public", "data", "aggregated", `${file}.json`),
      "utf-8"
    );
    return JSON.parse(text) as T;
  }
  // Client-side: fetch from the public directory. Cached aggressively so
  // subsequent handler calls within the same session reuse the payload.
  const r = await fetch(`${window.location.origin}/data/aggregated/${file}.json`, {
    cache: "force-cache",
  });
  if (!r.ok) throw new Error(`Failed to load ${file}.json: ${r.status}`);
  return r.json() as Promise<T>;
}

async function getOverview(): Promise<Record<string, unknown>> {
  if (!_aggCache.overview) {
    _aggCache.overview = await loadAgg<Record<string, unknown>>("overview");
  }
  return _aggCache.overview;
}

async function getCycles(): Promise<unknown[]> {
  if (!_aggCache.cycles) {
    _aggCache.cycles = await loadAgg<unknown[]>("cycles");
  }
  return _aggCache.cycles;
}

async function getByClient(): Promise<unknown[]> {
  if (!_aggCache.byClient) {
    _aggCache.byClient = await loadAgg<unknown[]>("by-client");
  }
  return _aggCache.byClient;
}

async function getByNrid(): Promise<unknown[]> {
  if (!_aggCache.byNrid) {
    _aggCache.byNrid = await loadAgg<unknown[]>("by-nrid");
  }
  return _aggCache.byNrid;
}

async function getTopPharmacies(): Promise<unknown[]> {
  if (!_aggCache.topPharmacies) {
    _aggCache.topPharmacies = await loadAgg<unknown[]>("top-pharmacies");
  }
  return _aggCache.topPharmacies;
}

async function getTopNdcs(): Promise<unknown[]> {
  if (!_aggCache.topNdcs) {
    _aggCache.topNdcs = await loadAgg<unknown[]>("top-ndcs");
  }
  return _aggCache.topNdcs;
}

async function getTopClients(): Promise<unknown[]> {
  if (!_aggCache.topClients) {
    _aggCache.topClients = await loadAgg<unknown[]>("top-clients");
  }
  return _aggCache.topClients;
}

async function getDailyVolume(): Promise<unknown[]> {
  if (!_aggCache.dailyVolume) {
    _aggCache.dailyVolume = await loadAgg<unknown[]>("daily-volume");
  }
  return _aggCache.dailyVolume;
}

async function getReversalRate(): Promise<Record<string, unknown>> {
  if (!_aggCache.reversalRate) {
    _aggCache.reversalRate = await loadAgg<Record<string, unknown>>("reversal-rate");
  }
  return _aggCache.reversalRate;
}

async function getActivityFeed(): Promise<unknown[]> {
  if (!_aggCache.activityFeed) {
    _aggCache.activityFeed = await loadAgg<unknown[]>("activity-feed");
  }
  return _aggCache.activityFeed;
}

async function getInvestigations(): Promise<unknown[]> {
  if (!_aggCache.investigations) {
    _aggCache.investigations = await loadAgg<unknown[]>("investigations");
  }
  return _aggCache.investigations;
}

async function getManifest(): Promise<Record<string, unknown>> {
  if (!_aggCache.manifest) {
    _aggCache.manifest = await loadAgg<Record<string, unknown>>("manifest");
  }
  return _aggCache.manifest;
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
type Handler = (match: RegExpMatchArray, body?: unknown) => unknown | Promise<unknown>;

interface RouteEntry {
  pattern: RegExp;
  methods: Method[];
  handler: Handler;
}

/**
 * Build a deterministic sample of synthetic claim records for detail pages
 * (pharmacy, member, prescriber). The `seed` parameter makes rows stable for
 * a given entity — the same pharmacy NPI always gets the same mock claims —
 * so navigating back and forth doesn't shuffle data.
 */
function buildClaimRecordSample(seed: string) {
  let s = 0;
  for (let i = 0; i < seed.length; i++) s = (s * 31 + seed.charCodeAt(i)) >>> 0;
  const rand = () => {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    return s;
  };
  const statuses = ["paid", "paid", "paid", "paid", "reversed"];
  return Array.from({ length: 15 }, (_, i) => {
    const drug = DRUGS[rand() % DRUGS.length];
    const billed = ((rand() % 50000) / 100 + 10).toFixed(2);
    const paid = (parseFloat(billed) * (0.6 + (rand() % 30) / 100)).toFixed(2);
    const daysAgo = i * 3 + (rand() % 3);
    return {
      id: `CLM-${seed.slice(0, 8)}-${String(i).padStart(4, "0")}`,
      date_of_service: new Date(Date.now() - daysAgo * 24 * 60 * 60 * 1000)
        .toISOString()
        .slice(0, 10),
      ndc: drug.ndc,
      drug_name: `${drug.brand_name} ${drug.strength}`,
      billed_amount: billed,
      paid_amount: paid,
      status: statuses[rand() % statuses.length],
    };
  });
}

const ROUTES: RouteEntry[] = [
  // ── Health ──────────────────────────────────────────────────────────────────
  {
    pattern: /\/health\/detailed$/,
    methods: ["GET"],
    handler: () => ({
      status: "healthy",
      services: SERVICE_HEALTH,
      database_healthy: true,
      redis_healthy: true,
      event_bus_healthy: true,
      dlq_depth: 0,
      checked_at: isoDate(0),
      as_of: isoDate(0),
    }),
  },
  {
    pattern: /\/health$/,
    methods: ["GET"],
    handler: () => ({ services: SERVICE_HEALTH }),
  },

  // ── Admin ────────────────────────────────────────────────────────────────────
  {
    pattern: /\/admin\/tenants\/([^/]+)$/,
    methods: ["PATCH"],
    handler: (match, body) => {
      const tenant = TENANTS.find((t) => t.id === match[1]) ?? TENANTS[0];
      return { ...tenant, ...(body as Record<string, unknown>) };
    },
  },
  {
    pattern: /\/admin\/tenants$/,
    methods: ["GET"],
    handler: () => ({ tenants: TENANTS }),
  },
  // ── Users (real backend paths: /api/v1/users*) ──────────────────────────
  // USERS seed is in the legacy portal-side shape (name, role, active,
  // mfa_enrolled, last_login). The backend's `UserResponse` uses
  // display_name, roles[], status, mfa_enabled, last_login_at — so we map
  // on the fly. This keeps the seed file stable while the portal pages
  // consume the canonical backend shape.
  ...((): RouteEntry[] => {
    const toBackendUser = (u: (typeof USERS)[number]) => ({
      id: u.id,
      tenant_id: u.tenant_id,
      email: u.email,
      display_name: u.name,
      status: u.active ? "active" : "inactive",
      last_login_at: u.last_login,
      failed_login_count: 0,
      mfa_enabled: u.mfa_enrolled,
      created_at: u.created_at,
      roles: [u.role],
    });
    return [
      {
        // List. Backend returns a bare array at the top level — no wrapper.
        pattern: /\/api\/v1\/users$/,
        methods: ["GET"],
        handler: () => USERS.map(toBackendUser),
      },
      {
        // Create. Matches `UserCreate`: { email, display_name, password,
        // role_names[] }. Password is discarded; response mirrors the
        // backend's `UserResponse`.
        pattern: /\/api\/v1\/users$/,
        methods: ["POST"],
        handler: (_match: RegExpMatchArray, body: unknown) => {
          const b = (body ?? {}) as {
            email?: string;
            display_name?: string;
            role_names?: string[];
          };
          return {
            id: `mock-${Date.now()}`,
            tenant_id: USERS[0]?.tenant_id ?? "mock-tenant",
            email: b.email ?? "",
            display_name: b.display_name ?? "",
            status: "active",
            last_login_at: null,
            failed_login_count: 0,
            mfa_enabled: false,
            created_at: new Date().toISOString(),
            roles: b.role_names ?? [],
          };
        },
      },
      {
        // Update (display_name and/or status). Returns the updated user.
        pattern: /\/api\/v1\/users\/([^/]+)$/,
        methods: ["PUT"],
        handler: (match: RegExpMatchArray, body: unknown) => {
          const src = USERS.find((u) => u.id === match[1]) ?? USERS[0];
          const patch = (body ?? {}) as { display_name?: string; status?: string };
          const base = toBackendUser(src);
          return {
            ...base,
            display_name: patch.display_name ?? base.display_name,
            status: patch.status ?? base.status,
          };
        },
      },
      {
        // Lock account — bumps status to "locked".
        pattern: /\/api\/v1\/users\/([^/]+)\/lock$/,
        methods: ["POST"],
        handler: (match: RegExpMatchArray) => {
          const src = USERS.find((u) => u.id === match[1]) ?? USERS[0];
          return { ...toBackendUser(src), status: "locked" };
        },
      },
      {
        // Unlock account — resets status to "active" and clears failures.
        pattern: /\/api\/v1\/users\/([^/]+)\/unlock$/,
        methods: ["POST"],
        handler: (match: RegExpMatchArray) => {
          const src = USERS.find((u) => u.id === match[1]) ?? USERS[0];
          return { ...toBackendUser(src), status: "active", failed_login_count: 0 };
        },
      },
    ];
  })(),
  // ── Legacy /admin/users shims (kept for tests / callers not yet
  //    migrated to the /api/v1/users paths above) ─────────────────────────
  {
    pattern: /\/admin\/users\/([^/]+)\/force-logout$/,
    methods: ["POST"],
    handler: () => ({ success: true }),
  },
  {
    pattern: /\/admin\/users\/([^/]+)$/,
    methods: ["PATCH"],
    handler: (match, body) => {
      const user = USERS.find((u) => u.id === match[1]) ?? USERS[0];
      return { ...user, ...(body as Record<string, unknown>) };
    },
  },
  {
    pattern: /\/admin\/users$/,
    methods: ["GET"],
    handler: () => ({ users: USERS }),
  },
  {
    pattern: /\/admin\/sessions\/active$/,
    methods: ["GET"],
    handler: () => ({
      count: 7,
      users: USERS.slice(0, 7).map((u) => u.name),
    }),
  },

  // ── Audit ────────────────────────────────────────────────────────────────────
  {
    pattern: /\/audit\/recent/,
    methods: ["GET"],
    handler: () => ({
      entries: AUDIT_ENTRIES.slice(0, 20).map((e) => ({
        id: e.id,
        action: e.action,
        user: e.user_name,
        created_at: e.created_at,
        details: e.details,
      })),
      total: AUDIT_ENTRIES.length,
      page: 1,
      page_size: 20,
    }),
  },
  {
    pattern: /\/audit\/entries$/,
    methods: ["GET"],
    handler: () => ({
      entries: AUDIT_ENTRIES,
      total: AUDIT_ENTRIES.length,
      page: 1,
      page_size: AUDIT_ENTRIES.length,
    }),
  },

  // ── User profile ─────────────────────────────────────────────────────────────
  {
    pattern: /\/users\/me\/notification-preferences$/,
    methods: ["PATCH"],
    handler: (_, body) => ({ ...(body as Record<string, unknown>), updated: true }),
  },
  {
    pattern: /\/users\/me$/,
    methods: ["PATCH"],
    handler: (_, body) => ({ ...USERS[0], ...(body as Record<string, unknown>) }),
  },

  // ── Onboarding ───────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/onboarding\/test$/,
    methods: ["POST"],
    handler: () => ({ passed: true, message: "Connectivity verified" }),
  },
  {
    pattern: /\/api\/v1\/onboarding\/activate$/,
    methods: ["POST"],
    handler: () => ({ tenant_id: PRIMARY_TENANT, status: "activated" }),
  },

  // ── MFA ──────────────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/auth\/mfa\/verify$/,
    methods: ["POST"],
    handler: () => ({ verified: true }),
  },

  // ── Activity ─────────────────────────────────────────────────────────────────
  {
    pattern: /\/activity\/stream/,
    methods: ["GET"],
    handler: async () => {
      const feed = await getActivityFeed();
      return feed.slice(0, 20);
    },
  },

  // ── Billing Cycles (summary widgets) ────────────────────────────────────────
  {
    pattern: /\/billing-cycles\/active$/,
    methods: ["GET"],
    handler: async () => {
      const cycles = await getCycles();
      const inProgress = (cycles as Array<Record<string, unknown>>).filter(
        (c) => c.status === "in_progress"
      );
      const total = inProgress.reduce(
        (s, c) => s + parseFloat(String(c.total_client_billed ?? 0)),
        0
      );
      return {
        count: inProgress.length,
        total_amount: total.toFixed(2),
        next_action:
          inProgress.length > 0
            ? `Approve ${inProgress.length} cycle${inProgress.length !== 1 ? "s" : ""} awaiting sign-off`
            : "All cycles complete",
      };
    },
  },
  {
    pattern: /\/billing\/v1\/dashboard$|\/api\/v1\/billing\/dashboard$/,
    methods: ["GET"],
    handler: async () => {
      const [ov, cycles] = await Promise.all([getOverview(), getCycles()]);
      const o = ov as Record<string, unknown>;
      const cycs = cycles as Array<Record<string, unknown>>;
      const inProgress = cycs.filter((c) => c.status === "in_progress");
      return {
        active_cycles: cycs.length,
        pending_approval: inProgress.length,
        claims_today: 0,
        claims_mtd: Number(o.total_claims ?? 0),
        claims_ytd: Number(o.total_claims ?? 0),
        ap_mtd: String(o.total_pharmacy_paid ?? "0.00"),
        ar_mtd: String(o.total_client_billed ?? "0.00"),
        fee_mtd: String(
          (
            parseFloat(String(o.total_processing_fees ?? 0)) +
            parseFloat(String(o.total_transaction_fees ?? 0))
          ).toFixed(2)
        ),
      };
    },
  },

  // ── Billing Cycles CRUD ──────────────────────────────────────────────────────
  {
    pattern: /\/billing\/v1\/cycles\/([^/?]+)\/transmit$/,
    methods: ["POST"],
    handler: () => ({ status: "transmitted" }),
  },
  {
    pattern: /\/billing\/v1\/cycles\/([^/?]+)$/,
    methods: ["GET"],
    handler: async (match) => {
      const cycles = (await getCycles()) as Array<Record<string, unknown>>;
      return cycles.find((c) => c.cycle_id === match[1]) ?? cycles[0];
    },
  },
  {
    pattern: /\/billing\/v1\/cycles$/,
    methods: ["GET", "POST"],
    handler: async (_, body) => {
      if (body) {
        const cycles = (await getCycles()) as Array<Record<string, unknown>>;
        return { ...cycles[0], id: makeUUID(999), status: "draft" };
      }
      const cycles = (await getCycles()) as Array<Record<string, unknown>>;
      return {
        items: cycles,
        total: cycles.length,
        page: 1,
        page_size: 25,
      };
    },
  },

  // ── Claims (billing) ─────────────────────────────────────────────────────────
  {
    pattern: /\/billing\/v1\/claims\/summary$/,
    methods: ["GET"],
    handler: async () => {
      const ov = (await getOverview()) as Record<string, unknown>;
      return {
        today: 0,
        mtd: Number(ov.total_claims ?? 0),
        ytd: Number(ov.total_claims ?? 0),
        paid: Number(ov.paid_claims ?? 0),
        reversals: Number(ov.reversal_claims ?? 0),
        total_billed: String(ov.total_client_billed ?? "0.00"),
      };
    },
  },
  {
    pattern: /\/billing\/v1\/claims\/bulk-action$/,
    methods: ["POST"],
    handler: (_, body) => {
      const b = body as { ids?: string[] } | undefined;
      return { success_count: b?.ids?.length ?? 1, failures: [] };
    },
  },
  {
    pattern: /\/billing\/v1\/claims\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) => CLAIMS.find((c) => c.id === match[1]) ?? CLAIMS[0],
  },
  {
    pattern: /\/billing\/v1\/claims$/,
    methods: ["GET"],
    handler: () => ({ items: CLAIMS, total: CLAIMS.length, page: 1, page_size: 25 }),
  },

  // ── Invoices ─────────────────────────────────────────────────────────────────
  {
    pattern: /\/billing\/v1\/invoices\/([^/?]+)\/(approve|send|void)$/,
    methods: ["POST"],
    handler: (match) => {
      const inv = INVOICES.find((i) => i.id === match[1]) ?? INVOICES[0];
      const action = match[2] as string;
      return { ...inv, status: action === "approve" ? "generated" : action === "send" ? "sent" : "voided" };
    },
  },
  {
    pattern: /\/billing\/v1\/invoices\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) => INVOICES.find((i) => i.id === match[1]) ?? INVOICES[0],
  },
  {
    pattern: /\/billing\/v1\/invoices$/,
    methods: ["GET"],
    handler: () => ({ items: INVOICES, total: INVOICES.length, page: 1, page_size: 25 }),
  },

  // ── AP/AR ────────────────────────────────────────────────────────────────────
  {
    // Matches /ar/summary (home widget), /billing/v1/ar/summary, and /api/v1/ar/summary.
    pattern: /(^|\/)ar\/summary$/,
    methods: ["GET"],
    handler: async () => {
      const ov = (await getOverview()) as Record<string, unknown>;
      const ar = String(ov.total_client_billed ?? "0.00");
      const ap = String(ov.total_pharmacy_paid ?? "0.00");
      const net = (parseFloat(ar) - parseFloat(ap)).toFixed(2);
      return { receivable: ar, payable: ap, net };
    },
  },
  {
    pattern: /\/billing\/v1\/ap-records\/summary$/,
    methods: ["GET"],
    handler: async () => {
      const ov = (await getOverview()) as Record<string, unknown>;
      const ar = String(ov.total_client_billed ?? "0.00");
      const ap = String(ov.total_pharmacy_paid ?? "0.00");
      const fees = String(
        (
          parseFloat(String(ov.total_processing_fees ?? 0)) +
          parseFloat(String(ov.total_transaction_fees ?? 0))
        ).toFixed(2)
      );
      const net = (parseFloat(ar) - parseFloat(ap)).toFixed(2);
      return {
        total_ap: ap,
        total_ar: ar,
        net_outstanding: net,
        this_cycle: String(ov.total_client_billed ?? "0.00"),
        this_month: String(ov.total_client_billed ?? "0.00"),
        total_fees: fees,
        last_updated: isoDate(0),
      };
    },
  },

  // ── Mapping templates ─────────────────────────────────────────────────────────
  {
    pattern: /\/billing\/v1\/mapping-templates$/,
    methods: ["GET", "POST"],
    handler: (_, body) => {
      if (body) return { ...MAPPING_TEMPLATES[0], id: makeUUID(998) };
      return MAPPING_TEMPLATES;
    },
  },

  // ── Uploads ──────────────────────────────────────────────────────────────────
  {
    pattern: /\/billing\/v1\/uploads\/([^/?]+)\/financial-preview$/,
    methods: ["GET"],
    handler: async () => {
      const ov = (await getOverview()) as Record<string, unknown>;
      const ar = String(ov.total_client_billed ?? "0.00");
      const ap = String(ov.total_pharmacy_paid ?? "0.00");
      const fees = String(
        (
          parseFloat(String(ov.total_processing_fees ?? 0)) +
          parseFloat(String(ov.total_transaction_fees ?? 0))
        ).toFixed(2)
      );
      return {
        ap_total: ap,
        ar_total: ar,
        fee_total: fees,
        net_settlement: ar,
        journal_entries: [
          { account: "Accounts Payable", debit: ap, credit: "0.00", description: "Pharmacy dispensing claims" },
          { account: "Accounts Receivable", debit: "0.00", credit: ar, description: "Client invoice" },
          { account: "Revenue - Processing Fees", debit: "0.00", credit: fees, description: "Claims processing and transaction fees" },
        ],
      };
    },
  },
  {
    pattern: /\/billing\/v1\/uploads\/([^/?]+)\/validate$/,
    methods: ["POST"],
    handler: async () => {
      const ov = (await getOverview()) as Record<string, unknown>;
      return {
        upload_id: makeUUID(997),
        total_rows: Number(ov.total_claims ?? 89231),
        valid_count: Number(ov.paid_claims ?? 82162),
        warning_count: 0,
        error_count: 0,
        errors: [],
        warnings: [],
        total_billed: String(ov.total_client_billed ?? "0.00"),
        file_name: "InfinityRX_20260401_1618.txt",
        columns_mapped: 63,
        columns_total: 63,
      };
    },
  },

  // ── Payment batches (summary widgets) ────────────────────────────────────────
  {
    pattern: /\/payment-batches\/pending$/,
    methods: ["GET"],
    handler: async () => {
      const nrids = (await getByNrid()) as Array<Record<string, unknown>>;
      const total = nrids.reduce(
        (s, n) => s + parseFloat(String(n.total_client_billed ?? 0)),
        0
      );
      return {
        count: nrids.length,
        total_amount: total.toFixed(2),
      };
    },
  },

  // ── Payment batches CRUD ──────────────────────────────────────────────────────
  {
    pattern: /\/batches\/routing-preview$/,
    methods: ["POST"],
    handler: async () => {
      const nrids = (await getByNrid()) as Array<Record<string, unknown>>;
      return nrids.map((n) => ({
        vendor: String(n.nrid).toLowerCase(),
        vendor_name: String(n.vendor_name),
        client_id: makeUUID(String(n.nrid).charCodeAt(0)),
        client_name: String(n.vendor_name),
        payment_count: Number(n.total_claims),
        total_amount: String(n.total_client_billed),
      }));
    },
  },
  {
    pattern: /\/batches\/([^/?]+)\/(approve|submit|void)$/,
    methods: ["POST"],
    handler: (match, body) => {
      const batch = PAYMENT_BATCHES.find((b) => b.id === match[1]) ?? PAYMENT_BATCHES[0];
      const action = match[2] as string;
      return {
        ...batch,
        status: action === "approve" ? "approved" : action === "submit" ? "transmitted" : "voided",
        approved_at: action === "approve" ? isoDate(0) : batch.approved_at,
      };
    },
  },
  {
    pattern: /\/batches\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) =>
      PAYMENT_BATCHES.find((b) => b.id === match[1]) ?? PAYMENT_BATCHES[0],
  },
  {
    pattern: /\/batches$/,
    methods: ["GET", "POST"],
    handler: async (_, body) => {
      if (body) return { ...PAYMENT_BATCHES[0], id: makeUUID(996), status: "draft" };
      const nrids = (await getByNrid()) as Array<Record<string, unknown>>;
      const batches = nrids.map((n, i) => ({
        id: makeUUID(800 + i),
        vendor_name: String(n.vendor_name),
        nrid: String(n.nrid),
        status: "pending_approval",
        claim_count: Number(n.total_claims),
        total_amount: String(n.total_client_billed),
        created_at: isoDate(-1),
        approved_at: null,
      }));
      return { items: batches, total: batches.length, page: 1, page_size: 25 };
    },
  },

  // ── Eligible claims ───────────────────────────────────────────────────────────
  {
    pattern: /\/eligible-claims$/,
    methods: ["GET"],
    handler: () => ({
      items: CLAIMS.filter((c) => c.status === "approved").slice(0, 20),
      total: CLAIMS.filter((c) => c.status === "approved").length,
      page: 1,
      page_size: 25,
    }),
  },

  // ── NACHA ─────────────────────────────────────────────────────────────────────
  {
    pattern: /\/nacha\/([^/?]+)\/transmit$/,
    methods: ["POST"],
    handler: (match) => {
      const file = NACHA_FILES.find((n) => n.id === match[1]) ?? NACHA_FILES[0];
      return { ...file, transmitted_at: isoDate(0), ack_status: "acknowledged" };
    },
  },
  {
    pattern: /\/nacha\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) => NACHA_FILES.find((n) => n.id === match[1]) ?? NACHA_FILES[0],
  },
  {
    pattern: /\/nacha$/,
    methods: ["GET"],
    handler: () => ({ items: NACHA_FILES, total: NACHA_FILES.length, page: 1, page_size: 25 }),
  },

  // ── Vendors ───────────────────────────────────────────────────────────────────
  {
    pattern: /\/vendors\/([^/?]+)\/health$/,
    methods: ["GET"],
    handler: (match) => VENDORS_LIST.find((v) => v.id === match[1]) ?? VENDORS_LIST[0],
  },
  {
    pattern: /\/vendors$/,
    methods: ["GET"],
    handler: () => VENDORS_LIST,
  },

  // ── Submissions ───────────────────────────────────────────────────────────────
  {
    pattern: /\/submissions\/([^/?]+)\/retry$/,
    methods: ["POST"],
    handler: (match) => SUBMISSIONS.find((s) => s.id === match[1]) ?? SUBMISSIONS[0],
  },
  {
    pattern: /\/submissions$/,
    methods: ["GET"],
    handler: () => SUBMISSIONS,
  },

  // ── ACH Returns ───────────────────────────────────────────────────────────────
  {
    pattern: /\/returns$/,
    methods: ["GET"],
    handler: () => ACH_RETURNS,
  },

  // ── Payments dashboard ────────────────────────────────────────────────────────
  // Pattern must be specific — a bare `/\/dashboard$/` matches every URL
  // ending in /dashboard including /api/v1/fwa/dashboard, shadowing the
  // FWA handler below.
  {
    pattern: /\/api\/v1\/payments\/dashboard$/,
    methods: ["GET"],
    handler: async () => {
      const [ov, nrids] = await Promise.all([getOverview(), getByNrid()]);
      const o = ov as Record<string, unknown>;
      const n = nrids as Array<Record<string, unknown>>;
      return {
        pending_batches: n.length,
        total_pending_amount: String(o.total_client_billed ?? "0.00"),
        settled_today: "0.00",
        returned_today: Number(o.reversal_claims ?? 0),
        vendor_health: VENDORS_LIST,
        total_pharmacy_paid: String(o.total_pharmacy_paid ?? "0.00"),
        total_claims: Number(o.total_claims ?? 0),
      };
    },
  },

  // ── ReclaimRx FWA ─────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/fwa\/dashboard$/,
    methods: ["GET"],
    handler: async () => {
      const [rr, invs] = await Promise.all([getReversalRate(), getInvestigations()]);
      const r = rr as Record<string, unknown>;
      const investigations = invs as Array<Record<string, unknown>>;
      return {
        ...FWA_DASHBOARD,
        overall_reversal_rate: r.overall_rate,
        active_investigations: investigations.filter((i) => i.status !== "resolved").length,
        total_investigations: investigations.length,
        high_severity: investigations.filter((i) => i.flag && (i.flag as Record<string, unknown>).severity === "critical").length,
      };
    },
  },
  {
    pattern: /\/flags\/summary$/,
    methods: ["GET"],
    handler: async () => {
      const invs = (await getInvestigations()) as Array<Record<string, unknown>>;
      return {
        today: invs.filter((i) => i.status === "new").length,
        week: invs.length,
        high_severity: invs.filter((i) => i.flag && (i.flag as Record<string, unknown>).severity === "critical").length,
      };
    },
  },

  // ── Investigations ────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/investigations\/([^/?]+)$/,
    methods: ["GET", "PATCH"],
    handler: async (match, body) => {
      const SENTINEL_UUID = "00000000-0000-0000-0000-000000000000";
      const NOW = new Date().toISOString();
      const invs = (await getInvestigations()) as Array<Record<string, unknown>>;
      const raw = invs.find((i) => String(i.id) === match[1]);
      if (!raw) {
        return {
          error: "not_found",
          message: `Investigation ${match[1]} not found`,
        };
      }
      const flagRaw = (raw.flag ?? {}) as Record<string, unknown>;
      const full = {
        id: String(raw.id),
        tenant_id: SENTINEL_UUID,
        flag_id: `flag-${String(raw.id)}`,
        flag: {
          id: `flag-${String(raw.id)}`,
          tenant_id: SENTINEL_UUID,
          flag_type: String(flagRaw.flag_type ?? "billing_anomaly"),
          severity: String(flagRaw.severity ?? "medium"),
          entity_type: "pharmacy" as const,
          entity_id: String(flagRaw.entity_id ?? SENTINEL_UUID),
          entity_name: String(flagRaw.entity_name ?? "Unknown"),
          estimated_recovery: String(raw.estimated_recovery ?? "0.00"),
          anomaly_narrative: String(raw.notes ?? ""),
          detected_at: NOW,
          claim_count: 0,
        },
        status: String(body ? (body as Record<string, unknown>).status ?? raw.status : raw.status),
        assigned_to_name: raw.assigned_to_name ? String(raw.assigned_to_name) : undefined,
        days_open: Number(raw.days_open ?? 1),
        estimated_recovery: String(raw.estimated_recovery ?? "0.00"),
        notes: String(raw.notes ?? ""),
        evidence_items: [],
        actions: [],
        created_at: NOW,
        updated_at: NOW,
        ...(body ? (body as Record<string, unknown>) : {}),
      };
      return full;
    },
  },
  {
    pattern: /\/api\/v1\/investigations\/summary$/,
    methods: ["GET"],
    handler: async () => {
      const invs = (await getInvestigations()) as Array<Record<string, unknown>>;
      return {
        active: invs.filter((i) => i.status !== "resolved").length,
        by_stage: {
          new: invs.filter((i) => i.status === "new").length,
          assigned: invs.filter((i) => i.status === "assigned").length,
          evidence: invs.filter((i) => i.status === "evidence").length,
          demand: invs.filter((i) => i.status === "demand").length,
          resolved: invs.filter((i) => i.status === "resolved").length,
        },
      };
    },
  },
  {
    pattern: /\/api\/v1\/investigations$/,
    methods: ["GET"],
    handler: async () => {
      const invs = await getInvestigations();
      const SENTINEL_UUID = "00000000-0000-0000-0000-000000000000";
      const NOW = new Date().toISOString();
      // Transform to full Investigation shape expected by the kanban page
      return (invs as Array<Record<string, unknown>>).map((inv) => {
        const flagRaw = (inv.flag ?? {}) as Record<string, unknown>;
        return {
          id: String(inv.id),
          tenant_id: SENTINEL_UUID,
          flag_id: `flag-${String(inv.id)}`,
          flag: {
            id: `flag-${String(inv.id)}`,
            tenant_id: SENTINEL_UUID,
            flag_type: String(flagRaw.flag_type ?? "billing_anomaly"),
            severity: String(flagRaw.severity ?? "medium"),
            entity_type: "pharmacy" as const,
            entity_id: String(flagRaw.entity_id ?? SENTINEL_UUID),
            entity_name: String(flagRaw.entity_name ?? "Unknown"),
            estimated_recovery: String(inv.estimated_recovery ?? "0.00"),
            anomaly_narrative: String(inv.notes ?? ""),
            detected_at: NOW,
            claim_count: 0,
          },
          status: String(inv.status ?? "new"),
          assigned_to: undefined,
          assigned_to_name: inv.assigned_to_name ? String(inv.assigned_to_name) : undefined,
          days_open: Number(inv.days_open ?? 1),
          estimated_recovery: String(inv.estimated_recovery ?? "0.00"),
          evidence_items: [],
          actions: [],
          created_at: NOW,
          updated_at: NOW,
        };
      });
    },
  },

  // ── Recovery ──────────────────────────────────────────────────────────────────
  {
    pattern: /\/recovery\/pipeline$/,
    methods: ["GET"],
    handler: async () => {
      const invs = (await getInvestigations()) as Array<Record<string, unknown>>;
      const estimated = invs.reduce((s, r) => s + parseFloat(String(r.estimated_recovery ?? 0)), 0);
      const demanded = invs
        .filter((i) => i.status === "demand" || i.status === "resolved")
        .reduce((s, r) => s + parseFloat(String(r.estimated_recovery ?? 0)), 0);
      const collected = invs
        .filter((i) => i.status === "resolved")
        .reduce((s, r) => s + parseFloat(String(r.estimated_recovery ?? 0)) * 0.7, 0);
      return {
        estimated: money(estimated),
        demanded: money(demanded),
        collected: money(collected),
      };
    },
  },
  {
    pattern: /\/recovery\/rows$/,
    methods: ["GET"],
    handler: async () => {
      const invs = (await getInvestigations()) as Array<Record<string, unknown>>;
      return invs.map((inv) => ({
        id: inv.id,
        entity_name: (inv.flag as Record<string, unknown>)?.entity_name ?? inv.id,
        client_name: inv.client_name,
        status: inv.status,
        estimated: inv.estimated_recovery,
        demanded: inv.status === "demand" || inv.status === "resolved" ? inv.estimated_recovery : "0.00",
        collected: inv.status === "resolved" ? money(parseFloat(String(inv.estimated_recovery ?? 0)) * 0.7) : "0.00",
      }));
    },
  },
  {
    pattern: /\/api\/v1\/recovery$/,
    methods: ["GET"],
    handler: () => RECOVERY_ROWS,
  },

  // ── Investigation sub-resources ───────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/investigations\/([^/?]+)\/audit-access$/,
    methods: ["POST"],
    handler: (match) => ({
      logged: true,
      investigation_id: match[1],
      accessed_at: new Date().toISOString(),
    }),
  },
  {
    pattern: /\/api\/v1\/investigations\/([^/?]+)\/claims$/,
    methods: ["GET"],
    handler: () => [],
  },
  {
    pattern: /\/api\/v1\/investigations\/([^/?]+)\/activity$/,
    methods: ["GET"],
    handler: () => [],
  },
  {
    pattern: /\/api\/v1\/investigations\/([^/?]+)\/evidence\/([^/?]+)\/toggle$/,
    methods: ["PATCH"],
    handler: (match) => ({
      id: match[2],
      completed: true,
      updated_at: new Date().toISOString(),
    }),
  },

  // ── Demand letter ─────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/investigations\/([^/?]+)\/demand-letter$/,
    methods: ["POST"],
    handler: () => ({
      letter: "VIA CERTIFIED MAIL\n\nDate: April 14, 2026\n\nDEMAND FOR REPAYMENT\n\nThis letter constitutes formal notice of overpayment pursuant to 42 CFR §1001...",
    }),
  },

  // ── Reporting ─────────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/reports\/templates\/([^/?]+)\/favorite$/,
    methods: ["POST"],
    handler: (match) => {
      const tmpl = REPORT_TEMPLATES.find((t) => t.id === match[1]) ?? REPORT_TEMPLATES[0];
      return { ...tmpl, is_favorite: !tmpl.is_favorite };
    },
  },
  {
    pattern: /\/api\/v1\/templates\/([^/?]+)\/favorite$/,
    methods: ["POST"],
    handler: (match) => {
      const tmpl = REPORT_TEMPLATES.find((t) => t.id === match[1]) ?? REPORT_TEMPLATES[0];
      return { ...tmpl, is_favorite: !tmpl.is_favorite };
    },
  },
  {
    pattern: /\/api\/v1\/reports\/templates\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) => REPORT_TEMPLATES.find((t) => t.id === match[1]) ?? REPORT_TEMPLATES[0],
  },
  {
    pattern: /\/api\/v1\/templates\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) => REPORT_TEMPLATES.find((t) => t.id === match[1]) ?? REPORT_TEMPLATES[0],
  },
  {
    pattern: /\/api\/v1\/reports\/templates$/,
    methods: ["GET", "POST"],
    handler: (_, body) => {
      if (body) return { ...REPORT_TEMPLATES[0], id: makeUUID(995) };
      return REPORT_TEMPLATES;
    },
  },
  {
    pattern: /\/api\/v1\/reports\/scheduled$/,
    methods: ["GET", "POST"],
    handler: (_, body) => {
      if (body) return { ...SCHEDULED_REPORTS[0], id: makeUUID(994) };
      return SCHEDULED_REPORTS;
    },
  },
  {
    pattern: /\/api\/v1\/reports\/scheduled\/([^/?]+)$/,
    methods: ["PATCH", "DELETE"],
    handler: (match, body) => {
      const sched = SCHEDULED_REPORTS.find((s) => s.id === match[1]) ?? SCHEDULED_REPORTS[0];
      return body ? { ...sched, ...(body as Record<string, unknown>) } : { success: true };
    },
  },
  {
    pattern: /\/api\/v1\/reports\/builder\/metrics$/,
    methods: ["GET"],
    handler: () => BUILDER_METRICS,
  },
  {
    pattern: /\/builder\/dimensions$/,
    methods: ["GET"],
    handler: () => BUILDER_DIMENSIONS,
  },
  {
    pattern: /\/api\/v1\/reports\/builder\/dimensions$/,
    methods: ["GET"],
    handler: () => BUILDER_DIMENSIONS,
  },
  {
    pattern: /\/api\/v1\/reports\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) => GENERATED_REPORTS.find((r) => r.id === match[1]) ?? GENERATED_REPORTS[0],
  },
  {
    pattern: /\/reports\/recent$/,
    methods: ["GET"],
    handler: async () => {
      const [cycles, clients] = await Promise.all([getCycles(), getTopClients()]);
      const cycs = cycles as Array<Record<string, unknown>>;
      const tops = (clients as Array<Record<string, unknown>>).slice(0, 2);
      const reports = [
        ...cycs.map((c, i) => ({
          id: makeUUID(900 + i),
          name: `Claims Report — Cycle ${String(c.cycle_id)}`,
          generated_at: isoDate(-i),
          total_claims: c.total_claims,
          total_billed: c.total_client_billed,
        })),
        ...tops.map((t, i) => ({
          id: makeUUID(905 + i),
          name: `Client Statement — ${String(t.client_name)}`,
          generated_at: isoDate(-i - 1),
          total_claims: t.total_claims,
          total_billed: t.total_client_billed,
        })),
      ].slice(0, 5);
      return { reports };
    },
  },
  {
    pattern: /\/api\/v1\/reports$/,
    methods: ["GET", "POST"],
    handler: (_, body) => {
      if (body) {
        return {
          report_id: makeUUID(993),
          status: "generating",
          message: "Report queued — you will be notified when ready",
        };
      }
      return GENERATED_REPORTS;
    },
  },
  {
    pattern: /\/api\/v1\/templates\/([^/?]+)\/favorite$/,
    methods: ["POST"],
    handler: () => ({ success: true }),
  },

  // ── Pharmacy directory ────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/pharmacies\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) => {
      const found = PHARMACIES.find((p) => p.npi === match[1]);
      if (!found) return { error: "not_found", message: `Pharmacy ${match[1]} not found` };
      return found;
    },
  },
  {
    // Synthetic claims list for pharmacy detail page — drawn from DRUGS seed.
    pattern: /\/api\/v1\/pharmacies\/([^/?]+)\/claims$/,
    methods: ["GET"],
    handler: (match) => buildClaimRecordSample(`pharm-${match[1]}`),
  },
  {
    pattern: /\/api\/v1\/pharmacies$/,
    methods: ["GET"],
    handler: () => PHARMACIES,
  },

  // ── Prescriber directory ──────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/prescribers\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) => PRESCRIBERS.find((p) => p.npi === match[1]) ?? PRESCRIBERS[0],
  },
  {
    pattern: /\/api\/v1\/prescribers$/,
    methods: ["GET"],
    handler: () => PRESCRIBERS,
  },

  // ── Drug database ─────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/drugs\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) => {
      const found = DRUGS.find((d) => d.ndc === match[1]);
      if (!found) return { error: "not_found", message: `Drug ${match[1]} not found` };
      return found;
    },
  },
  {
    pattern: /\/api\/v1\/drugs$/,
    methods: ["GET"],
    handler: () => DRUGS,
  },

  // ── Member management ─────────────────────────────────────────────────────────
  {
    // Synthetic claims list for member detail page — drawn from DRUGS seed.
    pattern: /\/api\/v1\/members\/([^/?]+)\/claims$/,
    methods: ["GET"],
    handler: (match) => buildClaimRecordSample(`mem-${match[1]}`),
  },
  {
    // PHI audit-access beacon fired by the member detail page on mount.
    pattern: /\/api\/v1\/members\/([^/?]+)\/audit-access$/,
    methods: ["POST"],
    handler: (match) => ({
      logged: true,
      member_id: match[1],
      accessed_at: new Date().toISOString(),
    }),
  },
  // Member enrollment wizard — validate/preview/apply form submissions.
  {
    pattern: /\/api\/v1\/members\/enrollment\/validate$/,
    methods: ["POST"],
    handler: () => ({
      valid: true,
      total_valid: 847,
      errors: [
        {
          row: 12,
          field: "date_of_birth",
          message: "Invalid date format — expected YYYY-MM-DD",
          original_value: "03/15/1982",
        },
        {
          row: 34,
          field: "group_number",
          message: "Group GRP-9999 not on file",
          original_value: "GRP-9999",
        },
        {
          row: 58,
          field: "coverage_effective_date",
          message: "Effective date more than 90 days in the past",
          original_value: "2023-01-01",
        },
      ],
      warnings: [],
      checked_at: new Date().toISOString(),
    }),
  },
  {
    pattern: /\/api\/v1\/members\/enrollment\/preview$/,
    methods: ["POST"],
    handler: () => ({
      adds: 734,
      updates: 108,
      terms: 5,
      total_records: 847,
      warnings: [
        "5 member terminations require manual review",
        "12 records have missing phone numbers — plan welcome calls unavailable",
      ],
    }),
  },
  {
    pattern: /\/api\/v1\/members\/enrollment\/apply$/,
    methods: ["POST"],
    handler: () => ({
      success: true,
      applied_count: 847,
      enrollment_batch_id: `ENR-2026-${String(Math.floor(Math.random() * 9000) + 1000)}`,
      applied_at: new Date().toISOString(),
    }),
  },
  {
    pattern: /\/api\/v1\/members\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) => {
      const found = MEMBERS.find((m) => m.member_id === match[1]);
      if (!found) return { error: "not_found", message: `Member ${match[1]} not found` };
      return found;
    },
  },
  {
    pattern: /\/api\/v1\/members$/,
    methods: ["GET"],
    handler: () => MEMBERS,
  },

  // ── EDI trading partners ──────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/trading-partners\/([^/?]+)$/,
    methods: ["GET", "PATCH"],
    handler: (match, body) => {
      const tp = TRADING_PARTNERS.find((p) => p.id === match[1]) ?? TRADING_PARTNERS[0];
      return body ? { ...tp, ...(body as Record<string, unknown>) } : tp;
    },
  },
  {
    pattern: /\/trading-partners\/([^/?]+)$/,
    methods: ["GET", "PATCH"],
    handler: (match, body) => {
      const tp = TRADING_PARTNERS.find((p) => p.id === match[1]) ?? TRADING_PARTNERS[0];
      return body ? { ...tp, ...(body as Record<string, unknown>) } : tp;
    },
  },
  {
    pattern: /\/api\/v1\/trading-partners$/,
    methods: ["GET"],
    handler: () => TRADING_PARTNERS,
  },

  // ── EDI transactions ──────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/transactions\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) => EDI_TRANSACTIONS.find((t) => t.id === match[1]) ?? EDI_TRANSACTIONS[0],
  },
  {
    pattern: /\/transactions\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) => EDI_TRANSACTIONS.find((t) => t.id === match[1]) ?? EDI_TRANSACTIONS[0],
  },
  {
    pattern: /\/api\/v1\/transactions$/,
    methods: ["GET"],
    handler: () => EDI_TRANSACTIONS,
  },

  // ── EDI monitor ───────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/monitor\/stats$/,
    methods: ["GET"],
    handler: () => EDI_MONITOR_STATS,
  },

  // ── Cert alerts ───────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/certificates\/alerts$/,
    methods: ["GET"],
    handler: () => CERT_ALERTS,
  },

  // ── Claims (Phase 1B — must precede the /api/v1/claims/:id catch-all) ─────────
  {
    pattern: /\/api\/v1\/claims\/pa-overrides\/summary$/,
    methods: ["GET"],
    handler: () => ({
      pending: PA_OVERRIDES.filter((p) => p.status === "pending").length,
      approved_today: PA_OVERRIDES.filter((p) => p.status === "approved").length,
      denied_today: PA_OVERRIDES.filter((p) => p.status === "denied").length,
      avg_turnaround_hours: 4,
    }),
  },
  {
    pattern: /\/api\/v1\/claims\/pa-overrides\/([^/?]+)\/(approve|deny)$/,
    methods: ["POST"],
    handler: (match, body) => {
      const override = PA_OVERRIDES.find((p) => p.id === match[1]) ?? PA_OVERRIDES[0];
      const action = match[2] as string;
      const b = (body ?? {}) as { notes?: string };
      return {
        ...override,
        status: action === "approve" ? "approved" : "denied",
        approved_at: action === "approve" ? isoDate(0) : undefined,
        approved_by: action === "approve" ? "Current User" : undefined,
        denial_reason: action === "deny" ? (b.notes ?? "Denied") : undefined,
      };
    },
  },
  {
    pattern: /\/api\/v1\/claims\/pa-overrides$/,
    methods: ["GET"],
    handler: () => ({
      items: PA_OVERRIDES,
      total: PA_OVERRIDES.length,
      page: 1,
      page_size: 25,
    }),
  },
  {
    // Enriched claim detail (served at /api/v1/claims/enriched/:id for lookup page)
    pattern: /\/api\/v1\/claims\/enriched\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) => CLAIMS_ENRICHED.find((c) => c.id === match[1]) ?? CLAIMS_ENRICHED[0],
  },
  {
    // Manual claim submission
    pattern: /\/api\/v1\/claims\/manual$/,
    methods: ["POST"],
    handler: (_match, body) => {
      const b = (body ?? {}) as Record<string, unknown>;
      return {
        id: makeUUID(Date.now() % 100000),
        status: "pending",
        created_at: isoDate(0),
        ...b,
      };
    },
  },

  // ── Medical claims ────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/claims\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) => MEDICAL_CLAIMS.find((c) => c.id === match[1]) ?? MEDICAL_CLAIMS[0],
  },
  {
    pattern: /\/api\/v1\/claims$/,
    methods: ["GET"],
    handler: () => ({ items: MEDICAL_CLAIMS, total: MEDICAL_CLAIMS.length }),
  },

  // ── 340B ─────────────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/340b\/summary$/,
    methods: ["GET"],
    handler: () => THREESIXTYFOURTY_SUMMARY,
  },

  // ── Site of care ─────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/analytics\/site-of-care$/,
    methods: ["GET"],
    handler: () => SITE_OF_CARE,
  },

  // ── HCPCS crosswalk ───────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/crosswalk$/,
    methods: ["GET", "POST"],
    handler: () => HCPCS_CROSSWALK,
  },

  // ── Unified spend ─────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/unified-spend$/,
    methods: ["GET", "POST"],
    handler: () => UNIFIED_SPEND,
  },

  // ── DataIQ live metrics ───────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/metrics\/live$/,
    methods: ["GET"],
    handler: async () => {
      const ov = (await getOverview()) as Record<string, unknown>;
      return {
        ...LIVE_METRICS,
        claims_processed: Number(ov.total_claims ?? 0),
        total_billed: String(ov.total_client_billed ?? "0.00"),
        reversal_rate: String(ov.reversal_rate ?? "0.0000"),
        active_cycles: 3,
      };
    },
  },

  // ── DataIQ analytics ──────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/analytics\/drug\/spend-trend$/,
    methods: ["GET"],
    handler: async () => {
      const vol = (await getDailyVolume()) as Array<Record<string, unknown>>;
      // Return last 30 days of daily volume as spend trend
      const recent = vol.slice(-30);
      return recent.map((d) => ({
        date: d.date,
        spend: d.total_client_billed,
        claims: d.total_claims,
        paid_claims: d.paid_claims,
        reversals: d.reversal_claims,
      }));
    },
  },
  {
    pattern: /\/api\/v1\/analytics\/drug\/brand-generic$/,
    methods: ["GET"],
    handler: () => BRAND_GENERIC,
  },
  {
    pattern: /\/api\/v1\/analytics\/drug\/top-by-spend$/,
    methods: ["GET"],
    handler: async () => {
      const ndcs = (await getTopNdcs()) as Array<Record<string, unknown>>;
      return ndcs.slice(0, 20).map((n) => ({
        ndc: n.ndc,
        drug_name: `NDC ${String(n.ndc)}`,
        brand_generic: n.brand_generic,
        total_spend: n.total_client_billed,
        claim_count: n.total_claims,
        avg_per_claim: n.avg_claim_billed,
      }));
    },
  },
  {
    pattern: /\/api\/v1\/analytics\/network\/pharmacy-scorecards$/,
    methods: ["GET"],
    handler: () => PHARMACY_SCORECARDS,
  },
  {
    pattern: /\/api\/v1\/analytics\/network\/adequacy$/,
    methods: ["GET"],
    handler: () => NETWORK_ADEQUACY,
  },
  {
    pattern: /\/api\/v1\/analytics\/member\/adherence$/,
    methods: ["GET"],
    handler: () => MEMBER_ADHERENCE,
  },
  {
    pattern: /\/api\/v1\/analytics\/financial$/,
    methods: ["GET"],
    handler: async () => {
      const [ov, nrids, rr] = await Promise.all([getOverview(), getByNrid(), getReversalRate()]);
      const o = ov as Record<string, unknown>;
      return {
        ...FINANCIAL_METRICS,
        total_client_billed: o.total_client_billed,
        total_pharmacy_paid: o.total_pharmacy_paid,
        total_processing_fees: o.total_processing_fees,
        total_transaction_fees: o.total_transaction_fees,
        reversal_rate: o.reversal_rate,
        by_vendor: nrids,
        reversal_rate_detail: rr,
      };
    },
  },
  {
    pattern: /\/api\/v1\/analytics\/financial\/by-client$/,
    methods: ["GET"],
    handler: async () => {
      const clients = await getTopClients();
      return clients;
    },
  },
  {
    pattern: /\/api\/v1\/analytics\/data-quality$/,
    methods: ["GET"],
    handler: () => DATA_QUALITY,
  },
  {
    pattern: /\/api\/v1\/analytics\/high-cost-members$/,
    methods: ["GET"],
    handler: () => HIGH_COST_MEMBERS,
  },
  {
    pattern: /\/api\/v1\/analytics\/member\/high-cost$/,
    methods: ["GET"],
    handler: () => HIGH_COST_MEMBERS,
  },

  // ── Eligibility check ─────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/eligibility\/check$/,
    methods: ["POST"],
    handler: (_, body) => {
      const b = body as { member_id?: string } | undefined;
      return {
        member_id: b?.member_id ?? "MBR-2026-0001",
        found: true,
        coverage_status: "active",
        coverage_effective_date: isoDate(-365).substring(0, 10),
        plan_name: "Standard PPO",
        group_id: "GRP-4821",
        checked_at: isoDate(0),
      };
    },
  },

  // ── Report preview ────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/reports\/preview$/,
    methods: ["POST"],
    handler: () => ({
      preview_url: "#",
      sample_rows: 25,
      estimated_file_size: "1.2 MB",
    }),
  },

  // ── Accounting cycles (new API paths) ─────────────────────────────────────────
  {
    pattern: /\/api\/v1\/accounting\/cycles\/summary$/,
    methods: ["GET"],
    handler: async () => {
      const [ov] = await Promise.all([getOverview()]);
      const o = ov as Record<string, unknown>;
      return {
        active: 3,
        pending_approval: 2,
        total_ap: String(o.total_pharmacy_paid ?? "0.00"),
        total_ar: String(o.total_client_billed ?? "0.00"),
      };
    },
  },
  {
    pattern: /\/api\/v1\/accounting\/cycles\/([^/?]+)\/claims$/,
    methods: ["GET"],
    handler: (match) => {
      const cycleId = match[1];
      const cycleClaims = CLAIMS_ENRICHED.filter((c) => c.cycle_id === cycleId);
      const result = cycleClaims.length > 0 ? cycleClaims : CLAIMS_ENRICHED.slice(0, 10);
      return { items: result, total: result.length, page: 1, page_size: 25 };
    },
  },
  {
    pattern: /\/api\/v1\/accounting\/cycles\/([^/?]+)\/journal-entries$/,
    methods: ["GET"],
    handler: (match) => {
      const cycleId = match[1];
      const entries = JOURNAL_ENTRIES.filter((je) => je.cycle_id === cycleId);
      const result = entries.length > 0 ? entries : JOURNAL_ENTRIES.slice(0, 6);
      return { items: result, total: result.length, page: 1, page_size: 25 };
    },
  },
  {
    pattern: /\/api\/v1\/accounting\/cycles\/([^/?]+)\/ar-entries$/,
    methods: ["GET"],
    handler: async () => {
      const ov = (await getOverview()) as Record<string, unknown>;
      const ar = String(ov.total_client_billed ?? "0.00");
      const entries = Array.from({ length: 5 }, (_, i) => ({
        id: makeUUID(11000 + i),
        date: isoDate(-i).substring(0, 10),
        client_name: ["Acme Health Partners", "BlueStar Benefits Group", "ClearPath Managed Care"][i % 3],
        description: `AR invoice — cycle claim batch ${i + 1}`,
        amount: money(Number(ar) / 5),
        status: i === 0 ? "pending" : "posted",
      }));
      return { items: entries, total: entries.length };
    },
  },
  {
    pattern: /\/api\/v1\/accounting\/cycles\/([^/?]+)\/ap-entries$/,
    methods: ["GET"],
    handler: async () => {
      const ov = (await getOverview()) as Record<string, unknown>;
      const ap = String(ov.total_pharmacy_paid ?? "0.00");
      const entries = Array.from({ length: 8 }, (_, i) => ({
        id: makeUUID(12000 + i),
        date: isoDate(-i).substring(0, 10),
        pharmacy_name: ["CVS Pharmacy #1047", "Walgreens #3821", "Rite Aid #0542", "Walmart Pharmacy"][i % 4],
        pharmacy_npi: ["1234567890", "2345678901", "3456789012", "4567890123"][i % 4],
        amount: money(Number(ap) / 8),
        status: i === 0 ? "pending" : "posted",
      }));
      return { items: entries, total: entries.length };
    },
  },
  {
    pattern: /\/api\/v1\/accounting\/cycles\/([^/?]+)\/(approve|reject|generate|settle)$/,
    methods: ["POST"],
    handler: (match) => {
      const action = match[2];
      const cycle = BILLING_CYCLES.find((c) => c.id === match[1]) ?? BILLING_CYCLES[0];
      const statusMap: Record<string, string> = {
        approve: "approved",
        reject: "draft",
        generate: "completed",
        settle: "settled",
      };
      return {
        ...cycle,
        status: statusMap[action] ?? cycle.status,
        approved_at: action === "approve" ? isoDate(0) : cycle.approved_at,
        approved_by: action === "approve" ? "Current User" : cycle.approved_by,
        generated_at: action === "generate" ? isoDate(0) : cycle.generated_at,
      };
    },
  },

  // ── Accounting invoices (new API paths) ───────────────────────────────────────
  {
    pattern: /\/api\/v1\/accounting\/invoices\/summary$/,
    methods: ["GET"],
    handler: async () => {
      const ov = (await getOverview()) as Record<string, unknown>;
      return {
        total: INVOICES.length,
        outstanding: String(ov.total_client_billed ?? "0.00"),
        overdue_count: INVOICES.filter((inv) => inv.status === "overdue").length,
        paid_this_month: money(rngInt(50000, 500000)),
      };
    },
  },
  {
    pattern: /\/api\/v1\/accounting\/invoices\/([^/?]+)\/mark-paid$/,
    methods: ["POST"],
    handler: (match) => {
      const inv = INVOICES.find((i) => i.id === match[1]) ?? INVOICES[0];
      return { ...inv, status: "paid", paid_at: isoDate(0) };
    },
  },

  // ── Accounting payments (new API paths) ───────────────────────────────────────
  {
    pattern: /\/api\/v1\/accounting\/payments\/([^/?]+)\/payments$/,
    methods: ["GET"],
    handler: (match) => {
      const batch = PAYMENT_BATCHES.find((b) => b.id === match[1]) ?? PAYMENT_BATCHES[0];
      const pharmacyNames = ["CVS Pharmacy #1047", "Walgreens #3821", "Rite Aid #0542", "Walmart Pharmacy", "Costco Pharmacy"];
      const pharmacyNPIs = ["1234567890", "2345678901", "3456789012", "4567890123", "5678901234"];
      const payments = Array.from({ length: 5 }, (_, i) => ({
        id: makeUUID(13000 + i),
        pharmacy_npi: pharmacyNPIs[i % pharmacyNPIs.length],
        pharmacy_name: pharmacyNames[i % pharmacyNames.length],
        claim_count: rngInt(50, 300),
        amount: money(Number(batch.total_amount) / 5),
        payment_type: "ACH CCD",
        routing_number: ["021000021", "026009593", "121000358", "081000210"][i % 4],
        account_number: `****${String(1000 + i * 111)}`,
        status: "pending",
      }));
      return { items: payments, total: payments.length };
    },
  },

  // ── Accounting journal entries ─────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/accounting\/journal-entries\/summary$/,
    methods: ["GET"],
    handler: () => ({
      total_entries: JOURNAL_ENTRIES.length,
      total_ap: money(JOURNAL_ENTRIES.filter((je) => je.type === "AP").reduce((s, je) => s + Number(je.amount), 0)),
      total_ar: money(JOURNAL_ENTRIES.filter((je) => je.type === "AR").reduce((s, je) => s + Number(je.amount), 0)),
      total_fees: money(JOURNAL_ENTRIES.filter((je) => je.type === "Fee").reduce((s, je) => s + Number(je.amount), 0)),
    }),
  },
  {
    pattern: /\/api\/v1\/accounting\/journal-entries$/,
    methods: ["GET"],
    handler: () => ({
      items: JOURNAL_ENTRIES,
      total: JOURNAL_ENTRIES.length,
      page: 1,
      page_size: 50,
    }),
  },
];

/**
 * Look up a registered handler for the given method + pathname.
 * Returns null if no match found.
 */
export function findHandler(
  method: Method,
  pathname: string
): { match: RegExpMatchArray; handler: Handler } | null {
  for (const route of ROUTES) {
    if (!route.methods.includes(method)) continue;
    const match = pathname.match(route.pattern);
    if (match) {
      return { match, handler: route.handler };
    }
  }
  return null;
}
