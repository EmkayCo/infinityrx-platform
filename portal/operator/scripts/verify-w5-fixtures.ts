#!/usr/bin/env tsx
/**
 * W5.3 — Fixture-completeness gate for dynamic routes.
 *
 * Walks portal/operator/app/ for every [param] directory, classifies each
 * route by its fixture source, and writes B10/w5-fixture-map.json — the
 * input the W5.4 screenshot capture script will consume.
 *
 * The gate's job is to force a visible decision on EVERY dynamic route:
 *   - "seed":        a mock-data export with at least one resolvable record
 *   - "placeholder": no seed; capture renders 404/empty-state (allowlist decides)
 *   - (missing):     UNCLASSIFIED → gate fails
 *
 * Exit codes:
 *   0   → every dynamic route is classified AND seed entries resolve
 *   1   → one or more dynamic routes are unclassified or have empty seed
 *   2   → tree-walk or seed-import failure
 *
 * Usage (from portal/operator):
 *   npx tsx scripts/verify-w5-fixtures.ts
 *
 * STATE.md (Werkbench) step 3 of the W5 multi-session plan.
 */

import * as fs from "node:fs";
import * as path from "node:path";

import * as seeds from "@shared/lib/mock-data/seed";

// ── Paths ────────────────────────────────────────────────────────────────────
// Script runs from portal/operator/ (npx tsx cwd). B10/ output lands at repo root.
const APP_DIR = path.join(process.cwd(), "app");
const REPO_ROOT = path.resolve(process.cwd(), "..", "..");
const OUT_DIR = path.join(REPO_ROOT, "B10");
const OUT_FILE = path.join(OUT_DIR, "w5-fixture-map.json");

// ── Classification: every dynamic route MUST appear here ─────────────────────
// `seed`        → resolves the first record's id-like field for capture.
// `placeholder` → static value (e.g. "test-recon-id") for the W5.4 capture to
//                 navigate; the W5.5 allowlist accepts a 404 or empty-state.
// `exclude`     → API/catch-all routes that aren't user-facing pages.
//
// Adding a new dynamic route under app/ MUST also add an entry here, OR
// this gate fails. That's the point — the gate is a forcing function.

type RouteSpec =
  | { kind: "seed"; seed: keyof typeof seeds; rationale?: string }
  | { kind: "placeholder"; value: string; rationale: string }
  | { kind: "exclude"; rationale: string };

const ROUTE_FIXTURE_SOURCES: Record<string, RouteSpec> = {
  "/accounting/cycles/[id]": { kind: "seed", seed: "BILLING_CYCLES" },
  "/accounting/invoices/[id]": { kind: "seed", seed: "INVOICES" },
  "/accounting/payments/[id]": { kind: "seed", seed: "PAYMENT_BATCHES" },
  "/admin/network/pay-to-entities/[entityId]": {
    kind: "placeholder",
    value: "test-entity-id",
    rationale: "No dedicated pay-to-entity seed; W5.5 allowlist accepts 404",
  },
  "/admin/paysync/bank-settlements/[settlementId]": {
    kind: "placeholder",
    value: "test-settlement-id",
    rationale: "Bank settlements have no direct seed; paysync-api falls back",
  },
  "/admin/paysync/batches/[batchId]": { kind: "seed", seed: "PAYMENT_BATCHES" },
  "/admin/paysync/cycles/[cycleId]": { kind: "seed", seed: "BILLING_CYCLES" },
  "/admin/paysync/invoices/[invoiceId]": { kind: "seed", seed: "INVOICES" },
  "/admin/paysync/reconciliations/[reconId]": {
    kind: "placeholder",
    value: "test-recon-id",
    rationale: "Reconciliations are per-cycle, not by reconId; route falls back",
  },
  "/api/auth/[...nextauth]": {
    kind: "exclude",
    rationale: "NextAuth catch-all — not a page route",
  },
  "/billing/cycles/[id]": { kind: "seed", seed: "BILLING_CYCLES" },
  "/billing/invoices/[id]": { kind: "seed", seed: "INVOICES" },
  "/claims/[id]": { kind: "seed", seed: "CLAIMS" },
  "/clients/[id]": { kind: "seed", seed: "CLIENTS" },
  "/directories/drugs/[ndc]": { kind: "seed", seed: "DRUGS" },
  "/directories/members/[id]": { kind: "seed", seed: "MEMBERS" },
  "/directories/pharmacies/[npi]": { kind: "seed", seed: "PHARMACIES" },
  "/directories/prescribers/[npi]": { kind: "seed", seed: "PRESCRIBERS" },
  "/edi/partners/[id]": { kind: "seed", seed: "TRADING_PARTNERS" },
  "/edi/transactions/[id]": { kind: "seed", seed: "EDI_TRANSACTIONS" },
  "/medical-claims/claims/[id]": { kind: "seed", seed: "MEDICAL_CLAIMS" },
  "/payments/batches/[id]": { kind: "seed", seed: "PAYMENT_BATCHES" },
  "/programs/[id]": { kind: "seed", seed: "PROGRAMS" },
  "/reclaimrx/investigations/[id]": { kind: "seed", seed: "INVESTIGATIONS" },
  "/reporting/library/[templateId]": { kind: "seed", seed: "REPORT_TEMPLATES" },
  "/reporting/viewer/[reportId]": { kind: "seed", seed: "GENERATED_REPORTS" },
};

// ── Tree walk ────────────────────────────────────────────────────────────────
// Walk app/ once and collect every directory whose name is [...] or [name].
// Each one is a dynamic-segment leaf in the route tree. Multiple [param]
// segments in one path (e.g. /a/[x]/b/[y]) are supported — we emit one entry
// per leaf parameter.

function discoverDynamicRoutes(): string[] {
  const found: string[] = [];

  function walk(absDir: string, rel: string): void {
    const entries = fs.readdirSync(absDir, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      // Skip Next.js route groups "(name)" — they don't appear in the URL.
      // Skip private-folder prefix "_" and platform conventions.
      if (entry.name.startsWith("_")) continue;
      const segment = entry.name.startsWith("(") && entry.name.endsWith(")") ? "" : `/${entry.name}`;
      const nextRel = `${rel}${segment}`;
      const nextAbs = path.join(absDir, entry.name);
      if (entry.name.startsWith("[") && entry.name.endsWith("]")) {
        // Record this dynamic route. Don't recurse deeper for fixture purposes —
        // the immediate parent's [param] is what the capture script binds.
        // (If a deeper /[a]/[b] structure ever exists, we'd need extension.)
        found.push(nextRel);
      }
      walk(nextAbs, nextRel);
    }
  }

  walk(APP_DIR, "");
  return found.sort();
}

// ── Fixture resolution ───────────────────────────────────────────────────────
// For "seed" specs, pick the FIRST record's id-shaped field. Try the URL
// parameter name first (e.g. "ndc" → record.ndc), then "id" as fallback.

function paramName(route: string): string {
  const last = route.split("/").pop() ?? "";
  return last.replace(/^\[\.\.\./, "").replace(/^\[/, "").replace(/\]$/, "");
}

function resolveSeedFixture(
  route: string,
  seedName: keyof typeof seeds
): { value: string; field: string } | { error: string } {
  const arr = (seeds as Record<string, unknown>)[seedName];
  if (!Array.isArray(arr)) {
    return { error: `seed "${seedName}" is not an array (got ${typeof arr})` };
  }
  if (arr.length === 0) {
    return { error: `seed "${seedName}" is empty` };
  }
  const first = arr[0] as Record<string, unknown>;
  const param = paramName(route);
  // Try the URL parameter name verbatim, then "id" as fallback.
  for (const candidate of [param, "id"]) {
    const v = first[candidate];
    if (typeof v === "string" && v.length > 0) {
      return { value: v, field: candidate };
    }
    if (typeof v === "number") {
      return { value: String(v), field: candidate };
    }
  }
  return {
    error: `seed "${seedName}" record[0] has no usable "${param}" or "id" field (keys: ${Object.keys(first).slice(0, 8).join(",")})`,
  };
}

// ── Output map shape ─────────────────────────────────────────────────────────

type FixtureEntry = {
  route: string;
  classification: "seed" | "placeholder" | "exclude";
  source?: string;
  value?: string;
  field?: string;
  rationale?: string;
};

type OutputMap = {
  generated_at: string;
  branch: string;
  total_dynamic_routes: number;
  classified: number;
  unclassified: string[];
  entries: FixtureEntry[];
};

// ── Main ─────────────────────────────────────────────────────────────────────

function main(): number {
  let discovered: string[];
  try {
    discovered = discoverDynamicRoutes();
  } catch (err) {
    console.error(`[verify-w5-fixtures] tree-walk failed: ${(err as Error).message}`);
    return 2;
  }

  const entries: FixtureEntry[] = [];
  const unclassified: string[] = [];
  const resolutionErrors: string[] = [];

  for (const route of discovered) {
    const spec = ROUTE_FIXTURE_SOURCES[route];
    if (!spec) {
      unclassified.push(route);
      continue;
    }
    if (spec.kind === "exclude") {
      entries.push({ route, classification: "exclude", rationale: spec.rationale });
      continue;
    }
    if (spec.kind === "placeholder") {
      entries.push({
        route,
        classification: "placeholder",
        value: spec.value,
        rationale: spec.rationale,
      });
      continue;
    }
    // spec.kind === "seed"
    const resolved = resolveSeedFixture(route, spec.seed);
    if ("error" in resolved) {
      resolutionErrors.push(`${route} → ${spec.seed}: ${resolved.error}`);
      continue;
    }
    entries.push({
      route,
      classification: "seed",
      source: String(spec.seed),
      value: resolved.value,
      field: resolved.field,
      rationale: spec.rationale,
    });
  }

  // Also flag classifications that exist in the map but no longer exist in app/.
  const stale = Object.keys(ROUTE_FIXTURE_SOURCES).filter((k) => !discovered.includes(k));

  const branch = (() => {
    try {
      // Read .git/HEAD relative to repo root — avoid spawning git for portability.
      const headFile = path.join(REPO_ROOT, ".git", "HEAD");
      const raw = fs.readFileSync(headFile, "utf-8").trim();
      const m = raw.match(/^ref:\s*refs\/heads\/(.+)$/);
      return m ? m[1] : raw.slice(0, 8);
    } catch {
      return "unknown";
    }
  })();

  const output: OutputMap = {
    generated_at: new Date().toISOString(),
    branch,
    total_dynamic_routes: discovered.length,
    classified: entries.length,
    unclassified,
    entries,
  };

  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(OUT_FILE, JSON.stringify(output, null, 2) + "\n", "utf-8");

  // ── Report ─────────────────────────────────────────────────────────────────
  console.log(`[verify-w5-fixtures] discovered ${discovered.length} dynamic routes`);
  console.log(`[verify-w5-fixtures] classified ${entries.length}`);
  const seedCount = entries.filter((e) => e.classification === "seed").length;
  const placeholderCount = entries.filter((e) => e.classification === "placeholder").length;
  const excludeCount = entries.filter((e) => e.classification === "exclude").length;
  console.log(
    `[verify-w5-fixtures]   seed=${seedCount} placeholder=${placeholderCount} exclude=${excludeCount}`
  );
  console.log(`[verify-w5-fixtures] output → ${path.relative(REPO_ROOT, OUT_FILE)}`);

  if (stale.length > 0) {
    console.warn(`[verify-w5-fixtures] WARN — map has ${stale.length} stale entries (no matching route under app/):`);
    for (const r of stale) console.warn(`  - ${r}`);
  }

  let failed = false;
  if (unclassified.length > 0) {
    console.error(`[verify-w5-fixtures] FAIL — ${unclassified.length} unclassified dynamic route(s):`);
    for (const r of unclassified) console.error(`  - ${r}  (add to ROUTE_FIXTURE_SOURCES)`);
    failed = true;
  }
  if (resolutionErrors.length > 0) {
    console.error(`[verify-w5-fixtures] FAIL — ${resolutionErrors.length} seed resolution error(s):`);
    for (const e of resolutionErrors) console.error(`  - ${e}`);
    failed = true;
  }

  if (failed) return 1;
  console.log("[verify-w5-fixtures] OK");
  return 0;
}

process.exit(main());
