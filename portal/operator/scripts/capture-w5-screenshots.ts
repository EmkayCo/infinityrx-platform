#!/usr/bin/env tsx
/**
 * W5.4 — Playwright screenshot capture for the W5 visual QA pass.
 *
 * Reads B10/w5-fixture-map.json (W5.3 output) and walks portal/operator/app/
 * for static routes. Navigates each route against a running `next start` (or
 * compatible server) and records:
 *   - screenshot PNG  → B10/w5-screenshots/<slug>.png
 *   - per-route status, console errors, page errors, failed requests
 *     → B10/w5-capture-results.json
 *
 * Auth: uses the b10-test NextAuth Credentials provider with the
 * B10_TEST_TOKEN from portal/operator/.env.local. This is the same path
 * verified end-to-end in W4.6 (commit 3bbc499 → 2f226ae). The dev-bypass
 * provider is NOT used because it hard-refuses under NODE_ENV=production
 * which is what `next start` boots in.
 *
 * Idempotent: skips routes whose PNG already exists unless --rerun is passed.
 *
 * Prerequisites:
 *   1. portal/operator/.env.local has B10_TEST_MODE=true + B10_TEST_TOKEN
 *   2. Portal is built and running on the base URL (default http://localhost:3000):
 *        cd portal/operator && npm run build && npm run start
 *   3. Playwright Chromium installed: npx playwright install chromium
 *   4. B10/w5-fixture-map.json exists (W5.3 output)
 *
 * Usage (from portal/operator):
 *   npx tsx scripts/capture-w5-screenshots.ts
 *   npx tsx scripts/capture-w5-screenshots.ts --rerun
 *   npx tsx scripts/capture-w5-screenshots.ts --route /claims/[id]
 *   npx tsx scripts/capture-w5-screenshots.ts --base-url http://localhost:3001
 *
 * Exit codes:
 *   0   → every targeted route captured successfully (PNG written)
 *   1   → one or more routes failed catastrophically (timeout / nav error)
 *   2   → prerequisite missing (env, fixture map, Playwright, server)
 *
 * STATE.md (Werkbench) step 4 of the W5 multi-session plan.
 */

import * as fs from "node:fs";
import * as path from "node:path";

// Playwright is a dev dep on portal/operator; tsx resolves it through
// node_modules/.pnpm or the workspace root. We import lazily inside main()
// so missing-install gives a clean error message instead of an import crash.

// ── Paths ────────────────────────────────────────────────────────────────────
const APP_DIR = path.join(process.cwd(), "app");
const REPO_ROOT = path.resolve(process.cwd(), "..", "..");
const B10_DIR = path.join(REPO_ROOT, "B10");
const FIXTURE_MAP_FILE = path.join(B10_DIR, "w5-fixture-map.json");
const SCREENSHOTS_DIR = path.join(B10_DIR, "w5-screenshots");
const RESULTS_FILE = path.join(B10_DIR, "w5-capture-results.json");
const ENV_LOCAL = path.join(process.cwd(), ".env.local");

// ── CLI args ─────────────────────────────────────────────────────────────────
type Args = {
  rerun: boolean;
  routeFilter: string | null;
  baseUrl: string;
};

function parseArgs(argv: string[]): Args {
  const args: Args = { rerun: false, routeFilter: null, baseUrl: "http://localhost:3000" };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--rerun") args.rerun = true;
    else if (a === "--route") args.routeFilter = argv[++i] ?? null;
    else if (a === "--base-url") args.baseUrl = argv[++i] ?? args.baseUrl;
    else if (a === "--help" || a === "-h") {
      console.log("usage: tsx scripts/capture-w5-screenshots.ts [--rerun] [--route <pattern>] [--base-url <url>]");
      process.exit(0);
    }
  }
  return args;
}

// ── .env.local loader (minimal — avoids dotenv dep) ──────────────────────────
function loadEnvLocal(): Record<string, string> {
  if (!fs.existsSync(ENV_LOCAL)) return {};
  const raw = fs.readFileSync(ENV_LOCAL, "utf-8");
  const out: Record<string, string> = {};
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq < 0) continue;
    const k = trimmed.slice(0, eq).trim();
    let v = trimmed.slice(eq + 1).trim();
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
      v = v.slice(1, -1);
    }
    out[k] = v;
  }
  return out;
}

// ── Route discovery ──────────────────────────────────────────────────────────
// Walk app/ for every directory containing page.tsx. Convert filesystem path
// to URL pattern: strip the app/ prefix, drop route-groups "(name)", keep
// dynamic segments "[name]" as-is. Skip private "_" folders and "api/" subtree.

function discoverStaticAndDynamicRoutes(): { static_: string[]; dynamic: string[] } {
  const static_: string[] = [];
  const dynamic: string[] = [];

  function walk(absDir: string, urlRel: string): void {
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(absDir, { withFileTypes: true });
    } catch {
      return;
    }
    // Does this directory have a page.tsx?
    const hasPage = entries.some(
      (e) => e.isFile() && (e.name === "page.tsx" || e.name === "page.ts" || e.name === "page.jsx" || e.name === "page.js")
    );
    if (hasPage) {
      const url = urlRel === "" ? "/" : urlRel;
      if (url.includes("[")) dynamic.push(url);
      else static_.push(url);
    }
    for (const e of entries) {
      if (!e.isDirectory()) continue;
      if (e.name.startsWith("_")) continue;
      if (e.name === "api") continue; // API routes are not user-facing pages
      const isRouteGroup = e.name.startsWith("(") && e.name.endsWith(")");
      const segment = isRouteGroup ? "" : `/${e.name}`;
      walk(path.join(absDir, e.name), `${urlRel}${segment}`);
    }
  }

  walk(APP_DIR, "");
  static_.sort();
  dynamic.sort();
  return { static_, dynamic };
}

// ── Fixture-map types (must match W5.3 output) ───────────────────────────────
type FixtureEntry = {
  route: string;
  classification: "seed" | "placeholder" | "exclude";
  source?: string;
  value?: string;
  field?: string;
  rationale?: string;
};

type FixtureMap = {
  generated_at: string;
  branch: string;
  total_dynamic_routes: number;
  classified: number;
  unclassified: string[];
  entries: FixtureEntry[];
};

// ── URL building ─────────────────────────────────────────────────────────────
// Resolve [param] in a route pattern using the fixture map. Returns null if
// the route is excluded (e.g., NextAuth catch-all).

function resolveUrl(routePattern: string, fixtureMap: FixtureMap): string | null {
  const entry = fixtureMap.entries.find((e) => e.route === routePattern);
  if (!entry) return routePattern; // static route — pass through
  if (entry.classification === "exclude") return null;
  // Replace [param] (and [...param]) with the fixture value.
  return routePattern.replace(/\[\.{0,3}[^\]]+\]/g, encodeURIComponent(entry.value ?? "missing"));
}

// ── Slug for screenshot filenames ────────────────────────────────────────────
// Use the ROUTE PATTERN, not the resolved URL, so filenames stay stable
// across runs even when fixture IDs change.

function slugForRoute(routePattern: string): string {
  if (routePattern === "/") return "_root";
  return routePattern
    .replace(/^\//, "")
    .replace(/\//g, "__")
    .replace(/\[\.{0,3}/g, "")
    .replace(/\]/g, "")
    .replace(/[()]/g, "");
}

// ── Auth helper — b10-test Credentials provider ──────────────────────────────
// Mirrors authenticateDevBypass from tests/fixtures/mock-session.ts but
// targets the b10-test provider with the token from .env.local.

async function authenticateB10TestBypass(
  context: import("@playwright/test").BrowserContext,
  baseUrl: string,
  token: string
): Promise<void> {
  let csrfToken: string | undefined;
  let lastErr: unknown;

  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const resp = await context.request.get(`${baseUrl}/api/auth/csrf`);
      if (resp.status() !== 200) {
        throw new Error(`csrf status=${resp.status()}`);
      }
      const ct = resp.headers()["content-type"] ?? "";
      if (!ct.includes("application/json")) {
        const body = await resp.text();
        throw new Error(`csrf content-type=${ct}; body[0..80]="${body.slice(0, 80)}"`);
      }
      const parsed = (await resp.json()) as { csrfToken?: string };
      if (!parsed.csrfToken) throw new Error(`csrf json missing csrfToken: ${JSON.stringify(parsed)}`);
      csrfToken = parsed.csrfToken;
      break;
    } catch (err) {
      lastErr = err;
      if (attempt < 2) await new Promise((r) => setTimeout(r, 1500));
    }
  }

  if (!csrfToken) {
    throw new Error(`authenticateB10TestBypass: csrf fetch failed after 3 attempts. Last: ${String(lastErr)}`);
  }

  const callback = await context.request.post(`${baseUrl}/api/auth/callback/b10-test`, {
    form: { csrfToken, token, callbackUrl: "/", json: "true" },
    maxRedirects: 0,
  });
  // NextAuth Credentials callback returns 200 with { url } on success or
  // 302 to the error page on failure. We only need the cookie to be set.
  if (callback.status() !== 200 && callback.status() !== 302) {
    throw new Error(`b10-test callback returned status ${callback.status()}`);
  }

  // Sanity-check: /api/auth/session must return a user object after the call.
  const session = await context.request.get(`${baseUrl}/api/auth/session`);
  const sessionJson = (await session.json().catch(() => ({}))) as { user?: unknown };
  if (!sessionJson.user) {
    throw new Error(
      `b10-test sign-in did not produce a session — check B10_TEST_TOKEN matches portal/operator/.env.local and B10_TEST_MODE=true on the server`
    );
  }
}

// ── Per-route capture record ─────────────────────────────────────────────────
type RouteResult = {
  route: string;
  url: string;
  slug: string;
  status: "ok" | "skipped" | "failed";
  http_status?: number;
  console_errors: string[];
  page_errors: string[];
  failed_requests: { url: string; failure: string }[];
  screenshot?: string;
  error?: string;
  elapsed_ms: number;
};

// ── Main ─────────────────────────────────────────────────────────────────────

async function main(): Promise<number> {
  const args = parseArgs(process.argv.slice(2));

  // Prerequisite: fixture map exists
  if (!fs.existsSync(FIXTURE_MAP_FILE)) {
    console.error(`[capture-w5] missing ${path.relative(REPO_ROOT, FIXTURE_MAP_FILE)} — run verify-w5-fixtures.ts first`);
    return 2;
  }
  const fixtureMap = JSON.parse(fs.readFileSync(FIXTURE_MAP_FILE, "utf-8")) as FixtureMap;
  if (fixtureMap.unclassified.length > 0) {
    console.error(`[capture-w5] fixture map has unclassified routes — fix W5.3 gate first`);
    return 2;
  }

  // Prerequisite: B10_TEST_TOKEN
  const env = loadEnvLocal();
  const token = env.B10_TEST_TOKEN || process.env.B10_TEST_TOKEN || "";
  if (!token) {
    console.error(`[capture-w5] missing B10_TEST_TOKEN — set in portal/operator/.env.local`);
    return 2;
  }
  if (env.B10_TEST_MODE !== "true" && process.env.B10_TEST_MODE !== "true") {
    console.warn(`[capture-w5] WARN: B10_TEST_MODE != true in .env.local — server may reject auth`);
  }

  // Prerequisite: Playwright is importable
  let chromium: typeof import("@playwright/test").chromium;
  try {
    ({ chromium } = (await import("@playwright/test")) as typeof import("@playwright/test"));
  } catch (err) {
    console.error(`[capture-w5] @playwright/test not importable: ${(err as Error).message}`);
    return 2;
  }

  // Build route list
  const { static_, dynamic } = discoverStaticAndDynamicRoutes();
  const allRoutes = [...static_, ...dynamic].sort();
  const targeted = args.routeFilter ? allRoutes.filter((r) => r === args.routeFilter || r.includes(args.routeFilter!)) : allRoutes;
  if (targeted.length === 0) {
    console.error(`[capture-w5] no routes matched filter "${args.routeFilter}"`);
    return 2;
  }

  console.log(`[capture-w5] base_url=${args.baseUrl}`);
  console.log(`[capture-w5] discovered ${static_.length} static + ${dynamic.length} dynamic = ${allRoutes.length} routes`);
  console.log(`[capture-w5] targeted ${targeted.length} route(s) (filter=${args.routeFilter ?? "none"}, rerun=${args.rerun})`);

  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

  // Launch browser + authenticate once. The same context is reused for every
  // route so the session cookie persists.
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });

  try {
    await authenticateB10TestBypass(context, args.baseUrl, token);
  } catch (err) {
    console.error(`[capture-w5] auth failed: ${(err as Error).message}`);
    await browser.close();
    return 2;
  }
  console.log(`[capture-w5] authenticated via b10-test`);

  const results: RouteResult[] = [];

  for (const routePattern of targeted) {
    const slug = slugForRoute(routePattern);
    const screenshotPath = path.join(SCREENSHOTS_DIR, `${slug}.png`);
    const url = resolveUrl(routePattern, fixtureMap);

    if (url === null) {
      results.push({
        route: routePattern,
        url: "(excluded)",
        slug,
        status: "skipped",
        console_errors: [],
        page_errors: [],
        failed_requests: [],
        elapsed_ms: 0,
        error: "excluded by W5.3 classification",
      });
      continue;
    }

    if (!args.rerun && fs.existsSync(screenshotPath)) {
      results.push({
        route: routePattern,
        url,
        slug,
        status: "skipped",
        console_errors: [],
        page_errors: [],
        failed_requests: [],
        elapsed_ms: 0,
        error: "screenshot already exists (pass --rerun to overwrite)",
      });
      continue;
    }

    const page = await context.newPage();
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    const failedRequests: { url: string; failure: string }[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("pageerror", (err) => {
      pageErrors.push(err.message);
    });
    page.on("requestfailed", (req) => {
      failedRequests.push({ url: req.url(), failure: req.failure()?.errorText ?? "unknown" });
    });

    const start = Date.now();
    let httpStatus: number | undefined;
    let routeStatus: "ok" | "failed" = "ok";
    let errMsg: string | undefined;

    try {
      const fullUrl = `${args.baseUrl}${url}`;
      const resp = await page.goto(fullUrl, { waitUntil: "networkidle", timeout: 30_000 });
      httpStatus = resp?.status();
      // Give client-side rendering a moment to settle (Next.js hydration).
      await page.waitForTimeout(500);
      await page.screenshot({ path: screenshotPath, fullPage: true });
    } catch (err) {
      routeStatus = "failed";
      errMsg = (err as Error).message;
    }

    const elapsed = Date.now() - start;
    await page.close();

    const result: RouteResult = {
      route: routePattern,
      url,
      slug,
      status: routeStatus,
      http_status: httpStatus,
      console_errors: consoleErrors,
      page_errors: pageErrors,
      failed_requests: failedRequests,
      elapsed_ms: elapsed,
    };
    if (routeStatus === "ok") result.screenshot = path.relative(REPO_ROOT, screenshotPath);
    if (errMsg) result.error = errMsg;
    results.push(result);

    const tag = routeStatus === "ok" ? "OK" : "FAIL";
    const consoleHint = consoleErrors.length > 0 ? ` console:${consoleErrors.length}` : "";
    const pageHint = pageErrors.length > 0 ? ` pageerr:${pageErrors.length}` : "";
    const netHint = failedRequests.length > 0 ? ` netfail:${failedRequests.length}` : "";
    console.log(`[capture-w5] ${tag} ${httpStatus ?? "---"} ${routePattern}${consoleHint}${pageHint}${netHint} (${elapsed}ms)`);
  }

  await browser.close();

  // Write per-run results
  const summary = {
    generated_at: new Date().toISOString(),
    base_url: args.baseUrl,
    rerun: args.rerun,
    route_filter: args.routeFilter,
    discovered_static: static_.length,
    discovered_dynamic: dynamic.length,
    targeted: targeted.length,
    ok: results.filter((r) => r.status === "ok").length,
    skipped: results.filter((r) => r.status === "skipped").length,
    failed: results.filter((r) => r.status === "failed").length,
    results,
  };
  fs.writeFileSync(RESULTS_FILE, JSON.stringify(summary, null, 2) + "\n", "utf-8");

  console.log("");
  console.log(`[capture-w5] DONE — ok=${summary.ok} skipped=${summary.skipped} failed=${summary.failed}`);
  console.log(`[capture-w5] results → ${path.relative(REPO_ROOT, RESULTS_FILE)}`);
  console.log(`[capture-w5] screenshots → ${path.relative(REPO_ROOT, SCREENSHOTS_DIR)}/`);

  return summary.failed > 0 ? 1 : 0;
}

main().then(
  (code) => process.exit(code),
  (err) => {
    console.error(`[capture-w5] uncaught: ${(err as Error).stack ?? String(err)}`);
    process.exit(2);
  }
);
