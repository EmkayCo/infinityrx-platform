// @vitest-environment node
/**
 * Mock handler contract tests.
 *
 * For every URL the portal actually calls (scraped from the codebase), verify
 * that `mockResponse()`:
 *   - returns data (not undefined, not the unmatched-fallback shell)
 *   - matches the TypeScript shape the consuming page expects
 *   - contains monetary fields as valid decimals (no NaN, no null, no undefined)
 *
 * This file is the single biggest regression-protection net in the suite. It
 * would have caught every bug from Prompt 10 automatically.
 *
 * Environment: node (not jsdom). Several handlers call `loadAgg()` which
 * branches on `typeof window`. In jsdom `window` is defined, pushing loadAgg
 * to the client HTTP-fetch path that would try to hit localhost:3000. In node,
 * window is undefined and loadAgg reads from disk via fs/promises.
 */
import { describe, it, expect, beforeAll } from "vitest";
import { mockResponse } from "@shared/lib/mock-data";
import { expectShape, expectValidMoney } from "../../fixtures/test-helpers";

// Set env var so isMockEnabled() returns true for the mock layer's code path
// (mockResponse is called directly here; isMockEnabled is only checked by apiGet).
beforeAll(() => {
  process.env.NEXT_PUBLIC_USE_MOCK_DATA = "true";
});

// ─── Health ──────────────────────────────────────────────────────────────────
describe("mock handler: /health/detailed", () => {
  it("returns all fields the system-health page requires", async () => {
    const data = await mockResponse<Record<string, unknown>>("GET", "/health/detailed");
    expectShape(data, [
      "services",
      "database_healthy",
      "redis_healthy",
      "event_bus_healthy",
      "dlq_depth",
      "checked_at",
    ]);
    expect(typeof data.dlq_depth).toBe("number");
    expect(typeof data.database_healthy).toBe("boolean");
    expect(typeof data.redis_healthy).toBe("boolean");
    expect(typeof data.event_bus_healthy).toBe("boolean");
    expect(Array.isArray(data.services)).toBe(true);
  });
});

// ─── Admin / Tenants ─────────────────────────────────────────────────────────
describe("mock handler: /admin/tenants", () => {
  it("returns tenants[] wrapper with required fields (regression: CR-1)", async () => {
    const data = await mockResponse<{ tenants: unknown[] }>("GET", "/admin/tenants");
    expectShape(data, ["tenants"]);
    expect(Array.isArray(data.tenants)).toBe(true);
    expect(data.tenants.length).toBeGreaterThan(0);

    for (const tenant of data.tenants as Record<string, unknown>[]) {
      // These are the fields the page actually uses.
      expectShape(tenant, [
        "id",
        "name",
        "slug",
        "active",
        "mfa_required",
        "max_concurrent_sessions",
        "features",
      ]);
      expect(typeof tenant.active, `${tenant.name}.active is boolean`).toBe("boolean");
      expect(typeof tenant.features, `${tenant.name}.features is object`).toBe("object");
      expect(tenant.features, `${tenant.name}.features is not null`).not.toBeNull();
      // Object.keys(tenant.features) must not throw — this was the Prompt 10 crash.
      expect(() => Object.keys(tenant.features as object)).not.toThrow();
    }
  });
});

// ─── Admin / Users ───────────────────────────────────────────────────────────
describe("mock handler: /admin/users", () => {
  it("returns users[] with role and mfa_enrolled fields", async () => {
    const data = await mockResponse<{ users: unknown[] }>("GET", "/admin/users");
    expectShape(data, ["users"]);
    expect(Array.isArray(data.users)).toBe(true);
    expect(data.users.length).toBeGreaterThan(0);
    for (const user of data.users as Record<string, unknown>[]) {
      expectShape(user, ["id", "email", "name", "role", "mfa_enrolled"]);
    }
  });
});

// ─── Audit log ───────────────────────────────────────────────────────────────
describe("mock handler: /audit/entries", () => {
  it("returns {entries, total, page, page_size} wrapper (regression: HI-4)", async () => {
    const data = await mockResponse<Record<string, unknown>>("GET", "/audit/entries");
    expectShape(data, ["entries", "total", "page", "page_size"]);
    expect(Array.isArray(data.entries)).toBe(true);
    expect((data.entries as unknown[]).length).toBeGreaterThan(0);
    expect(typeof data.total).toBe("number");
  });
});

// ─── Analytics / Network ─────────────────────────────────────────────────────
describe("mock handler: /api/v1/analytics/network/pharmacy-scorecards", () => {
  it("returns scorecards[] with network_tier, reject_rate, mac_ratio (regression: CR-2)", async () => {
    const data = await mockResponse<unknown[]>(
      "GET",
      "/api/v1/analytics/network/pharmacy-scorecards"
    );
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBeGreaterThan(0);

    for (const row of data as Record<string, unknown>[]) {
      expectShape(row, [
        "pharmacy_name",
        "npi",
        "network_tier",
        "claim_volume",
        "avg_cost_per_claim",
        "reject_rate",
        "mac_ratio",
      ]);
      // network_tier must be a string — the Prompt 10 crash was
      // `(undefined).replace("_", " ")` in the cell renderer.
      expect(typeof row.network_tier).toBe("string");
      expect(() => (row.network_tier as string).replace("_", " ")).not.toThrow();
      expect(typeof row.reject_rate).toBe("number");
      expect(typeof row.mac_ratio).toBe("number");
      expect(typeof row.claim_volume).toBe("number");
      expectValidMoney(row.avg_cost_per_claim, `${row.pharmacy_name}.avg_cost_per_claim`);
    }
  });
});

describe("mock handler: /api/v1/analytics/network/adequacy", () => {
  it("returns adequacy summary with coverage percentages", async () => {
    const data = await mockResponse<Record<string, unknown>>(
      "GET",
      "/api/v1/analytics/network/adequacy"
    );
    expectShape(data, [
      "total_members",
      "members_within_5mi",
      "members_within_10mi",
      "coverage_pct_5mi",
      "coverage_pct_10mi",
      "gap_counties",
    ]);
    expect(typeof data.coverage_pct_5mi).toBe("number");
    expect(typeof data.coverage_pct_10mi).toBe("number");
    expect(Array.isArray(data.gap_counties)).toBe(true);
  });
});

// ─── Analytics / Member ──────────────────────────────────────────────────────
describe("mock handler: /api/v1/analytics/member/high-cost", () => {
  it("returns high-cost members (regression: HI-3)", async () => {
    const data = await mockResponse<unknown[]>(
      "GET",
      "/api/v1/analytics/member/high-cost"
    );
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBeGreaterThan(0);
    for (const row of data as Record<string, unknown>[]) {
      expectShape(row, ["member_id", "masked_name", "specialty_drug_count", "ytd_spend"]);
      expectValidMoney(row.ytd_spend, "ytd_spend");
    }
  });
});

describe("mock handler: /api/v1/analytics/member/adherence", () => {
  it("returns adherence records with PDC scores", async () => {
    const data = await mockResponse<unknown[]>("GET", "/api/v1/analytics/member/adherence");
    expect(Array.isArray(data)).toBe(true);
    for (const row of data as Record<string, unknown>[]) {
      expectShape(row, ["drug_class", "pdc_score", "cms_threshold", "member_count"]);
      expect(typeof row.pdc_score).toBe("number");
    }
  });
});

// ─── AR Summary (home widget) ────────────────────────────────────────────────
describe("mock handler: /ar/summary", () => {
  it("returns {receivable, payable, net} for the home widget (regression: HI-2)", async () => {
    const data = await mockResponse<Record<string, unknown>>("GET", "/ar/summary");
    expectShape(data, ["receivable", "payable", "net"]);
    expectValidMoney(data.receivable, "receivable");
    expectValidMoney(data.payable, "payable");
    expectValidMoney(data.net, "net");
  });

  it("is also reachable via /api/v1/ar/summary and /billing/v1/ar/summary", async () => {
    const a = await mockResponse<Record<string, unknown>>("GET", "/api/v1/ar/summary");
    const b = await mockResponse<Record<string, unknown>>("GET", "/billing/v1/ar/summary");
    expectShape(a, ["receivable", "payable", "net"]);
    expectShape(b, ["receivable", "payable", "net"]);
  });
});

// ─── ReclaimRx ───────────────────────────────────────────────────────────────
describe("mock handler: /api/v1/fwa/dashboard", () => {
  it("returns FWA stats with severity_breakdown + trend_90d", async () => {
    const data = await mockResponse<Record<string, unknown>>("GET", "/api/v1/fwa/dashboard");
    expectShape(data, [
      "new_flags_today",
      "new_flags_this_week",
      "severity_breakdown",
      "trend_90d",
      "top_flagged_entities",
    ]);
    const sev = data.severity_breakdown as Record<string, number>;
    expect(sev).toHaveProperty("critical");
    expect(sev).toHaveProperty("high");
    expect(sev).toHaveProperty("medium");
    expect(sev).toHaveProperty("low");
    expect(Array.isArray(data.trend_90d)).toBe(true);
    expect(Array.isArray(data.top_flagged_entities)).toBe(true);
  });
});

describe("mock handler: /api/v1/recovery", () => {
  it("returns RecoveryRecord[] with all required fields", async () => {
    const data = await mockResponse<unknown[]>("GET", "/api/v1/recovery");
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBeGreaterThan(0);
    for (const row of data as Record<string, unknown>[]) {
      expectShape(row, [
        "id",
        "investigation_id",
        "entity_name",
        "flag_type",
        "estimated",
        "demanded",
        "collected",
        "delta",
        "status",
        "updated_at",
      ]);
      expectValidMoney(row.estimated, "estimated");
      expectValidMoney(row.demanded, "demanded");
      expectValidMoney(row.collected, "collected");
      expectValidMoney(row.delta, "delta");
    }
  });
});

describe("mock handler: /api/v1/investigations", () => {
  it("returns investigations[] with flag nested objects", async () => {
    const data = await mockResponse<unknown[]>("GET", "/api/v1/investigations");
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBeGreaterThan(0);
    for (const inv of data as Record<string, unknown>[]) {
      expectShape(inv, ["id", "status", "flag", "days_open", "estimated_recovery"]);
      const flag = inv.flag as Record<string, unknown>;
      expectShape(flag, ["flag_type", "severity", "entity_name"]);
    }
  });
});

describe("mock handler: /api/v1/investigations/:id (not found) — regression: MED-1", () => {
  it("returns {error: not_found} for a garbage UUID instead of falling back to first", async () => {
    const data = await mockResponse<Record<string, unknown>>(
      "GET",
      "/api/v1/investigations/garbage-uuid-00000000"
    );
    expect(data.error).toBe("not_found");
    expect(data).not.toHaveProperty("flag");
  });

  it("returns a real investigation for a valid UUID", async () => {
    // First fetch the list to grab a real id
    const list = (await mockResponse<unknown[]>("GET", "/api/v1/investigations")) as Record<
      string,
      unknown
    >[];
    const realId = list[0].id as string;
    const data = await mockResponse<Record<string, unknown>>(
      "GET",
      `/api/v1/investigations/${realId}`
    );
    expect(data.error).toBeUndefined();
    expect(data.id).toBe(realId);
    expectShape(data, ["flag", "status", "evidence_items"]);
  });
});

describe("mock handler: /api/v1/investigations/:id/audit-access (regression: raw fetch→apiPost)", () => {
  it("accepts POST and returns logged: true", async () => {
    const data = await mockResponse<Record<string, unknown>>(
      "POST",
      "/api/v1/investigations/some-id/audit-access",
      {}
    );
    expect(data.logged).toBe(true);
    expect(data.investigation_id).toBe("some-id");
  });
});

// ─── Directories ─────────────────────────────────────────────────────────────
describe("mock handler: /api/v1/pharmacies (regression: MED-2)", () => {
  it("returns a bare array of rich pharmacy records (not aggregation wrapper)", async () => {
    const data = await mockResponse<unknown[]>("GET", "/api/v1/pharmacies");
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBeGreaterThan(5);
    for (const p of data as Record<string, unknown>[]) {
      expectShape(p, [
        "id",
        "npi",
        "name",
        "address_line1",
        "city",
        "state",
        "zip",
        "phone",
        "pharmacy_type",
        "network_status",
      ]);
    }
  });
});

describe("mock handler: /api/v1/prescribers (regression: MED-2)", () => {
  it("returns a bare array of rich prescriber records", async () => {
    const data = await mockResponse<unknown[]>("GET", "/api/v1/prescribers");
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBeGreaterThan(5);
    for (const p of data as Record<string, unknown>[]) {
      expectShape(p, [
        "id",
        "npi",
        "first_name",
        "last_name",
        "specialty",
        "dea_status",
        "state_license_status",
      ]);
    }
  });
});

describe("mock handler: /api/v1/drugs (regression: MED-2)", () => {
  it("returns a bare array of rich drug records", async () => {
    const data = await mockResponse<unknown[]>("GET", "/api/v1/drugs");
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBeGreaterThan(5);
    for (const d of data as Record<string, unknown>[]) {
      expectShape(d, [
        "id",
        "ndc",
        "brand_name",
        "generic_name",
        "manufacturer",
        "strength",
        "dosage_form",
        "therapeutic_class",
      ]);
      // NDC must be 11 characters (standard format)
      expect((d.ndc as string).length).toBe(11);
    }
  });
});

describe("mock handler: /api/v1/members (regression: MED-2)", () => {
  it("returns a bare array of PHI-masked member records", async () => {
    const data = await mockResponse<unknown[]>("GET", "/api/v1/members");
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBeGreaterThan(5);
    for (const m of data as Record<string, unknown>[]) {
      expectShape(m, [
        "id",
        "member_id",
        "masked_name",
        "masked_dob",
        "coverage_status",
        "plan_name",
        "accumulator",
      ]);
      // PHI must be redacted — full_name should be null, masked_name should not contain real names
      expect(m.full_name).toBeNull();
      expect(m.date_of_birth).toBeNull();
    }
  });
});

// ─── Medical Claims ──────────────────────────────────────────────────────────
describe("mock handler: /api/v1/340b/summary", () => {
  it("returns 340B summary with flagged_count and program totals", async () => {
    const data = await mockResponse<Record<string, unknown>>("GET", "/api/v1/340b/summary");
    expectShape(data, [
      "flagged_count",
      "entity_match_count",
      "total_program_amount",
      "potential_savings",
      "recent_claims",
    ]);
    expect(typeof data.flagged_count).toBe("number");
    expectValidMoney(data.total_program_amount, "total_program_amount");
    expectValidMoney(data.potential_savings, "potential_savings");
    expect(Array.isArray(data.recent_claims)).toBe(true);
  });
});

describe("mock handler: /api/v1/analytics/site-of-care", () => {
  it("returns site-of-care breakdown with POS and billed/paid amounts", async () => {
    const data = await mockResponse<unknown[]>("GET", "/api/v1/analytics/site-of-care");
    expect(Array.isArray(data)).toBe(true);
    for (const row of data as Record<string, unknown>[]) {
      expectShape(row, [
        "place_of_service",
        "pos_description",
        "claim_count",
        "total_billed",
        "total_paid",
      ]);
      expectValidMoney(row.total_billed, "total_billed");
      expectValidMoney(row.total_paid, "total_paid");
    }
  });
});

// ─── Prompt 13 additions ─────────────────────────────────────────────────────
describe("mock handler: /api/v1/pharmacies/:npi/claims (Prompt 13)", () => {
  it("returns a ClaimRecord[] sample for the pharmacy detail page", async () => {
    const data = await mockResponse<unknown[]>(
      "GET",
      "/api/v1/pharmacies/8084000017/claims"
    );
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBeGreaterThan(0);
    for (const row of data as Record<string, unknown>[]) {
      expectShape(row, [
        "id",
        "date_of_service",
        "ndc",
        "drug_name",
        "billed_amount",
        "paid_amount",
        "status",
      ]);
      expectValidMoney(row.billed_amount, "billed_amount");
      expectValidMoney(row.paid_amount, "paid_amount");
    }
  });

  it("is deterministic per seed (same NPI → same claims)", async () => {
    const a = (await mockResponse<unknown[]>(
      "GET",
      "/api/v1/pharmacies/8084000017/claims"
    )) as Record<string, unknown>[];
    const b = (await mockResponse<unknown[]>(
      "GET",
      "/api/v1/pharmacies/8084000017/claims"
    )) as Record<string, unknown>[];
    expect(a[0].id).toBe(b[0].id);
  });
});

describe("mock handler: /api/v1/members/:id/claims (Prompt 13)", () => {
  it("returns a ClaimRecord[] sample for the member detail page", async () => {
    const data = await mockResponse<unknown[]>(
      "GET",
      "/api/v1/members/MBR-2026-0001/claims"
    );
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBeGreaterThan(0);
  });
});

describe("mock handler: /api/v1/members/:id/audit-access (Prompt 13)", () => {
  it("accepts POST and returns logged: true with member_id echo", async () => {
    const data = await mockResponse<Record<string, unknown>>(
      "POST",
      "/api/v1/members/MBR-2026-0001/audit-access",
      {}
    );
    expect(data.logged).toBe(true);
    expect(data.member_id).toBe("MBR-2026-0001");
  });
});

describe("mock handler: /api/v1/members/enrollment/* (Prompt 13)", () => {
  it("validate returns errors + total_valid (shape the enroll page consumes)", async () => {
    const data = await mockResponse<Record<string, unknown>>(
      "POST",
      "/api/v1/members/enrollment/validate",
      { filename: "test.csv", size: 1234 }
    );
    expectShape(data, ["valid", "total_valid", "errors", "warnings"]);
    expect(typeof data.total_valid).toBe("number");
    expect(Array.isArray(data.errors)).toBe(true);
  });

  it("preview returns EnrollmentPreview with adds/updates/terms", async () => {
    const data = await mockResponse<Record<string, unknown>>(
      "POST",
      "/api/v1/members/enrollment/preview",
      { filename: "test.csv", size: 1234 }
    );
    expectShape(data, ["adds", "updates", "terms", "total_records", "warnings"]);
    expect(typeof data.adds).toBe("number");
    expect(Array.isArray(data.warnings)).toBe(true);
  });

  it("apply returns success + enrollment_batch_id", async () => {
    const data = await mockResponse<Record<string, unknown>>(
      "POST",
      "/api/v1/members/enrollment/apply",
      { filename: "test.csv", size: 1234 }
    );
    expect(data.success).toBe(true);
    expect(typeof data.enrollment_batch_id).toBe("string");
  });
});

describe("mock handler: /api/v1/members/:id — not-found (regression for MED-1 ripple)", () => {
  it("returns {error: not_found} for a bogus member id instead of falling back to MEMBERS[0]", async () => {
    const data = await mockResponse<Record<string, unknown>>(
      "GET",
      "/api/v1/members/BOGUS-MEMBER-DOES-NOT-EXIST"
    );
    expect(data.error).toBe("not_found");
  });
});

// ─── Unmatched URL fallback ──────────────────────────────────────────────────
describe("mock handler: unmatched URL fallback", () => {
  it("returns a fallback shape (shell object) for unknown paths", async () => {
    const data = await mockResponse<Record<string, unknown>>(
      "GET",
      "/api/v1/xyzzy-nothing-here"
    );
    // Either {items: [], total: 0} (list shape) or {} (detail shape) — both
    // are acceptable fallbacks. The important thing is that it returns an
    // object, not undefined, and doesn't throw.
    expect(data).toBeDefined();
    expect(typeof data).toBe("object");
  });
});
