/**
 * F0 WS2-C1 - next.config.ts redirect safety guards.
 *
 * Guards:
 *   1. No redirect loops (no source appears as another redirect's destination).
 *   2. The /billing/cycles/:slug regex constraint excludes the literal "new"
 *      segment - /billing/cycles/new must NOT be caught by the slug rule.
 *   3. /billing/cycles/abc123 IS redirected to /accounting/cycles/abc123.
 *   4. /accounting/invoices redirects to /billing/invoices (dead-nav fix).
 *   5. The broken /billing/invoices -> /accounting/invoices redirect is gone.
 */
import { describe, it, expect } from "vitest";

// Import the redirects array directly from next.config.ts.
// We resolve it synchronously by calling the async redirects() function.
// vitest runs in Node.js so the fs-based prebuild check is skipped via
// SKIP_PREBUILD=1 (set in env below). We only need the redirects array.
import nextConfig from "@/next.config";

type Redirect = {
  source: string;
  destination: string;
  permanent: boolean;
};

async function getRedirects(): Promise<Redirect[]> {
  return (await nextConfig.redirects?.()) as Redirect[];
}

/**
 * Check whether a path matches a Next.js redirect source pattern.
 * Handles:
 *   - Literal paths: "/billing"
 *   - Named segments without inline regex: ":id" -> matches any single segment
 *   - Named segments WITH inline regex: ":slug([^/]+(?<!new))" -> uses the
 *     inline pattern verbatim. We extract the inline regex and use it directly.
 *
 * Strategy: split the source on named-segment tokens, escape literal parts,
 * substitute segment patterns, then compile. This avoids the escaping
 * conflict where literal `.` in paths would be double-escaped if we ran a
 * blanket escape first.
 */
function matchesSource(source: string, path: string): boolean {
  // Tokenise: split on :name(pattern) or :name
  // Token types: "literal" | "segment-with-regex" | "segment-plain"
  const TOKEN = /:([a-zA-Z][a-zA-Z0-9]*)(\((?:[^)(]|\((?:[^)(]|\([^)(]*\))*\))*\))?/g;
  let regexStr = "^";
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  TOKEN.lastIndex = 0;
  while ((match = TOKEN.exec(source)) !== null) {
    // Escape the literal part before this segment token
    const literal = source.slice(lastIndex, match.index);
    regexStr += literal.replace(/[.+?^${}()|[\]\\]/g, "\\$&");
    // Segment with inline regex: use the inline pattern verbatim
    if (match[2]) {
      // match[2] is e.g. "([^/]+(?<!new))" — the parens are already there
      regexStr += match[2];
    } else {
      // Plain named segment: match any single path segment
      regexStr += "([^/]+)";
    }
    lastIndex = match.index + match[0].length;
  }
  // Escape remaining literal tail
  regexStr += source.slice(lastIndex).replace(/[.+?^${}()|[\]\\]/g, "\\$&");
  regexStr += "$";

  try {
    return new RegExp(regexStr).test(path);
  } catch {
    return source === path;
  }
}

describe("redirect loop detection", () => {
  it("no redirect source also appears as a redirect destination", async () => {
    const redirects = await getRedirects();
    const sources = new Set(redirects.map((r) => r.source));
    const loops = redirects.filter((r) => sources.has(r.destination));
    expect(
      loops.map((r) => `${r.source} -> ${r.destination}`),
      "Redirect loop detected"
    ).toEqual([]);
  });
});

describe("/billing/cycles slug redirect constraint", () => {
  it("/billing/cycles/new is NOT matched by the slug redirect rule", async () => {
    const redirects = await getRedirects();
    const slugRule = redirects.find(
      (r) => r.source.includes("/billing/cycles/") && r.source.includes(":slug")
    );
    expect(slugRule, "slug redirect rule not found in next.config.ts").toBeDefined();
    if (!slugRule) return;

    const matched = matchesSource(slugRule.source, "/billing/cycles/new");
    expect(matched, "/billing/cycles/new must NOT be caught by slug rule").toBe(false);
  });

  it("/billing/cycles/abc123 IS redirected to /accounting/cycles/abc123", async () => {
    const redirects = await getRedirects();
    const slugRule = redirects.find(
      (r) => r.source.includes("/billing/cycles/") && r.source.includes(":slug")
    );
    expect(slugRule).toBeDefined();
    if (!slugRule) return;

    const matched = matchesSource(slugRule.source, "/billing/cycles/abc123");
    expect(matched, "/billing/cycles/abc123 should match slug rule").toBe(true);
  });

  it("/billing/cycles/cycle-2026-04 IS redirected", async () => {
    const redirects = await getRedirects();
    const slugRule = redirects.find(
      (r) => r.source.includes("/billing/cycles/") && r.source.includes(":slug")
    );
    expect(slugRule).toBeDefined();
    if (!slugRule) return;

    const matched = matchesSource(slugRule.source, "/billing/cycles/cycle-2026-04");
    expect(matched, "/billing/cycles/cycle-2026-04 should match slug rule").toBe(true);
  });
});

describe("invoice redirect correctness", () => {
  it("/accounting/invoices redirects to /billing/invoices", async () => {
    const redirects = await getRedirects();
    const rule = redirects.find((r) => r.source === "/accounting/invoices");
    expect(rule, "/accounting/invoices redirect not found").toBeDefined();
    expect(rule?.destination).toBe("/billing/invoices");
  });

  it("broken /billing/invoices -> /accounting/invoices redirect is gone", async () => {
    const redirects = await getRedirects();
    const brokenRule = redirects.find(
      (r) => r.source === "/billing/invoices" && r.destination === "/accounting/invoices"
    );
    expect(
      brokenRule,
      "/billing/invoices -> /accounting/invoices creates a loop and must be removed"
    ).toBeUndefined();
  });
});

describe("existing redirects preserved", () => {
  it("/billing -> /accounting/cycles still present", async () => {
    const redirects = await getRedirects();
    const rule = redirects.find((r) => r.source === "/billing");
    expect(rule?.destination).toBe("/accounting/cycles");
  });

  it("/billing/claims -> /claims still present", async () => {
    const redirects = await getRedirects();
    const rule = redirects.find((r) => r.source === "/billing/claims");
    expect(rule?.destination).toBe("/claims");
  });

  it("/payments -> /accounting/payments still present", async () => {
    const redirects = await getRedirects();
    const rule = redirects.find((r) => r.source === "/payments");
    expect(rule?.destination).toBe("/accounting/payments");
  });
});
