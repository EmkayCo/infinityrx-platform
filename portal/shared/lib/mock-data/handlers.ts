/**
 * Mock endpoint handlers — maps URL patterns to seed data responses.
 * Each entry is a tuple of [pattern, handler].
 * Patterns are matched against the URL pathname (query string stripped).
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
  makeUUID,
  isoDate,
  money,
  rngInt,
  PRIMARY_TENANT,
} from "./seed";

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
type Handler = (match: RegExpMatchArray, body?: unknown) => unknown;

interface RouteEntry {
  pattern: RegExp;
  methods: Method[];
  handler: Handler;
}

const ROUTES: RouteEntry[] = [
  // ── Health ──────────────────────────────────────────────────────────────────
  {
    pattern: /\/health\/detailed$/,
    methods: ["GET"],
    handler: () => ({
      status: "healthy",
      services: SERVICE_HEALTH,
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
  {
    pattern: /\/api\/v1\/users$/,
    methods: ["GET"],
    handler: () => ({ users: USERS }),
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
    handler: () => ACTIVITY_EVENTS.slice(0, 20),
  },

  // ── Billing Cycles (summary widgets) ────────────────────────────────────────
  {
    pattern: /\/billing-cycles\/active$/,
    methods: ["GET"],
    handler: () => ({
      count: 5,
      total_amount: "13247891.23",
      next_action: "Approve 2 cycles awaiting sign-off",
    }),
  },
  {
    pattern: /\/billing\/v1\/dashboard$|\/api\/v1\/billing\/dashboard$/,
    methods: ["GET"],
    handler: () => ({
      active_cycles: 5,
      pending_approval: 2,
      claims_today: 847,
      claims_mtd: 18423,
      claims_ytd: 284750,
      ap_mtd: "4823451.20",
      ar_mtd: "4438175.10",
      fee_mtd: "192938.05",
    }),
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
    handler: (match) =>
      BILLING_CYCLES.find((c) => c.id === match[1]) ?? BILLING_CYCLES[0],
  },
  {
    pattern: /\/billing\/v1\/cycles$/,
    methods: ["GET", "POST"],
    handler: (_, body) => {
      if (body) {
        return { ...BILLING_CYCLES[0], id: makeUUID(999), status: "draft" };
      }
      return {
        items: BILLING_CYCLES,
        total: BILLING_CYCLES.length,
        page: 1,
        page_size: 25,
      };
    },
  },

  // ── Claims (billing) ─────────────────────────────────────────────────────────
  {
    pattern: /\/billing\/v1\/claims\/summary$/,
    methods: ["GET"],
    handler: () => ({
      today: rngInt(400, 1200),
      mtd: rngInt(8000, 25000),
      ytd: rngInt(100000, 350000),
    }),
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
    pattern: /\/billing\/v1\/ar\/summary$|\/api\/v1\/ar\/summary$/,
    methods: ["GET"],
    handler: () => ({
      receivable: "4438175.10",
      payable: "4823451.20",
      net: "-385276.10",
    }),
  },
  {
    pattern: /\/billing\/v1\/ap-records\/summary$/,
    methods: ["GET"],
    handler: () => ({
      total_ap: "4823451.20",
      total_ar: "4438175.10",
      net_outstanding: "-385276.10",
      this_cycle: "1423891.20",
      this_month: "4823451.20",
      last_updated: isoDate(0),
    }),
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
    handler: () => ({
      ap_total: "1423891.20",
      ar_total: "1309579.90",
      fee_total: "56955.65",
      net_settlement: "1309579.90",
      journal_entries: [
        { account: "Accounts Payable", debit: "1423891.20", credit: "0.00", description: "Pharmacy dispensing claims" },
        { account: "Accounts Receivable", debit: "0.00", credit: "1366935.55", description: "Client invoice" },
        { account: "Revenue - Admin Fee", debit: "0.00", credit: "56955.65", description: "Administrative fee" },
      ],
    }),
  },
  {
    pattern: /\/billing\/v1\/uploads\/([^/?]+)\/validate$/,
    methods: ["POST"],
    handler: () => ({
      upload_id: makeUUID(997),
      total_rows: 2847,
      valid_count: 2830,
      warning_count: 12,
      error_count: 5,
      errors: [
        { row: 14, field: "pharmacy_npi", error_message: "NPI failed Luhn check", original_value: "1234567890" },
        { row: 87, field: "drug_ndc", error_message: "NDC not found in formulary", original_value: "99999-9999-99" },
      ],
      warnings: [
        { row: 23, field: "days_supply", warning_message: "Unusually high days supply (180)", original_value: "180" },
      ],
    }),
  },

  // ── Payment batches (summary widgets) ────────────────────────────────────────
  {
    pattern: /\/payment-batches\/pending$/,
    methods: ["GET"],
    handler: () => ({
      count: 3,
      total_amount: "847205.50",
    }),
  },

  // ── Payment batches CRUD ──────────────────────────────────────────────────────
  {
    pattern: /\/batches\/routing-preview$/,
    methods: ["POST"],
    handler: () => [
      { vendor: "nacha", vendor_name: "NACHA ACH", client_id: makeUUID(100), client_name: "Acme Health Partners", payment_count: 423, total_amount: "423891.20" },
      { vendor: "echo", vendor_name: "Echo Health", client_id: makeUUID(101), client_name: "BlueStar Benefits Group", payment_count: 287, total_amount: "287450.10" },
    ],
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
    handler: (_, body) => {
      if (body) return { ...PAYMENT_BATCHES[0], id: makeUUID(996), status: "draft" };
      return { items: PAYMENT_BATCHES, total: PAYMENT_BATCHES.length, page: 1, page_size: 25 };
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
  {
    pattern: /\/dashboard$/,
    methods: ["GET"],
    handler: () => ({
      pending_batches: PAYMENT_BATCHES.filter((b) => b.status === "pending_approval").length,
      total_pending_amount: PAYMENT_BATCHES.filter((b) => b.status === "pending_approval")
        .reduce((sum, b) => sum + Number(b.total_amount), 0)
        .toFixed(2),
      settled_today: "2847205.50",
      returned_today: ACH_RETURNS.filter((r) => !r.resolved).length,
      vendor_health: VENDORS_LIST,
    }),
  },

  // ── ReclaimRx FWA ─────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/fwa\/dashboard$/,
    methods: ["GET"],
    handler: () => FWA_DASHBOARD,
  },
  {
    pattern: /\/flags\/summary$/,
    methods: ["GET"],
    handler: () => ({
      today: 7,
      week: 34,
      high_severity: 14,
    }),
  },

  // ── Investigations ────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/investigations\/([^/?]+)$/,
    methods: ["GET", "PATCH"],
    handler: (match, body) => {
      const inv = INVESTIGATIONS.find((i) => i.id === match[1]) ?? INVESTIGATIONS[0];
      return body ? { ...inv, ...(body as Record<string, unknown>) } : inv;
    },
  },
  {
    pattern: /\/api\/v1\/investigations\/summary$/,
    methods: ["GET"],
    handler: () => ({
      active: INVESTIGATIONS.filter((i) => i.status !== "resolved").length,
      by_stage: {
        new: INVESTIGATIONS.filter((i) => i.status === "new").length,
        assigned: INVESTIGATIONS.filter((i) => i.status === "assigned").length,
        evidence: INVESTIGATIONS.filter((i) => i.status === "evidence").length,
        demand: INVESTIGATIONS.filter((i) => i.status === "demand").length,
        resolved: INVESTIGATIONS.filter((i) => i.status === "resolved").length,
      },
    }),
  },
  {
    pattern: /\/api\/v1\/investigations$/,
    methods: ["GET"],
    handler: () => INVESTIGATIONS,
  },

  // ── Recovery ──────────────────────────────────────────────────────────────────
  {
    pattern: /\/recovery\/pipeline$/,
    methods: ["GET"],
    handler: () => {
      const estimated = RECOVERY_ROWS.reduce((s, r) => s + Number(r.estimated), 0);
      const demanded = RECOVERY_ROWS.reduce((s, r) => s + Number(r.demanded), 0);
      const collected = RECOVERY_ROWS.reduce((s, r) => s + Number(r.collected), 0);
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
    handler: () => RECOVERY_ROWS,
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
    handler: () => ({
      reports: GENERATED_REPORTS.slice(0, 5).map((r) => ({
        id: r.id,
        name: r.template_name,
        generated_at: r.generated_at ?? isoDate(-1),
      })),
    }),
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
    handler: (match) => PHARMACIES.find((p) => p.npi === match[1]) ?? PHARMACIES[0],
  },
  {
    pattern: /\/api\/v1\/pharmacies$/,
    methods: ["GET"],
    handler: () => ({ items: PHARMACIES, total: PHARMACIES.length }),
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
    handler: () => ({ items: PRESCRIBERS, total: PRESCRIBERS.length }),
  },

  // ── Drug database ─────────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/drugs\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) => DRUGS.find((d) => d.ndc === match[1]) ?? DRUGS[0],
  },
  {
    pattern: /\/api\/v1\/drugs$/,
    methods: ["GET"],
    handler: () => ({ items: DRUGS, total: DRUGS.length }),
  },

  // ── Member management ─────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/members\/([^/?]+)$/,
    methods: ["GET"],
    handler: (match) => MEMBERS.find((m) => m.member_id === match[1]) ?? MEMBERS[0],
  },
  {
    pattern: /\/api\/v1\/members$/,
    methods: ["GET"],
    handler: () => ({ items: MEMBERS, total: MEMBERS.length }),
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
    handler: () => LIVE_METRICS,
  },

  // ── DataIQ analytics ──────────────────────────────────────────────────────────
  {
    pattern: /\/api\/v1\/analytics\/drug\/spend-trend$/,
    methods: ["GET"],
    handler: () => DRUG_SPEND_TREND,
  },
  {
    pattern: /\/api\/v1\/analytics\/drug\/brand-generic$/,
    methods: ["GET"],
    handler: () => BRAND_GENERIC,
  },
  {
    pattern: /\/api\/v1\/analytics\/drug\/top-by-spend$/,
    methods: ["GET"],
    handler: () => TOP_BY_SPEND,
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
    handler: () => FINANCIAL_METRICS,
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
