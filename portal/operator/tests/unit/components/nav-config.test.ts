/**
 * F0 WS1 - Nav-config single source of truth guard.
 *
 * Dead link guard: every href in NAV_MODULES (top-level + children) must have
 * a matching page.tsx under the Next.js app directory. Any href with no page
 * fails the test, preventing dead nav links from reaching users.
 *
 * Uniqueness guard: no two nav entries share the same href.
 */
import { describe, it, expect } from "vitest";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { NAV_MODULES } from "@/components/layout/nav-config";

const APP_DIR = resolve(__dirname, "../../../app");

function hrefToPagePath(href: string): string {
  if (href === "/") return resolve(APP_DIR, "page.tsx");
  const segments = href.replace(/^\//, "");
  return resolve(APP_DIR, segments, "page.tsx");
}

function collectAllHrefs(): Array<{ label: string; href: string }> {
  const result: Array<{ label: string; href: string }> = [];
  for (const mod of NAV_MODULES) {
    result.push({ label: mod.label, href: mod.href });
    if (mod.children) {
      for (const child of mod.children) {
        result.push({ label: `${mod.label} -> ${child.label}`, href: child.href });
      }
    }
  }
  return result;
}

describe("nav-config dead link guard", () => {
  const allHrefs = collectAllHrefs();

  for (const { label, href } of allHrefs) {
    it(`"${label}" (${href}) has a matching page.tsx`, () => {
      const pagePath = hrefToPagePath(href);
      expect(
        existsSync(pagePath),
        `Dead nav link: "${label}" -> "${href}" has no page at ${pagePath}`
      ).toBe(true);
    });
  }
});

describe("nav-config uniqueness guard", () => {
  it("no two child nav entries share the same href", () => {
    // Module-level hrefs intentionally match their first child (both point at
    // the same landing page). We only enforce uniqueness across children.
    const childHrefs: string[] = [];
    for (const mod of NAV_MODULES) {
      if (mod.children) {
        for (const child of mod.children) {
          childHrefs.push(child.href);
        }
      }
    }
    const duplicates = childHrefs.filter((h, i) => childHrefs.indexOf(h) !== i);
    expect(duplicates, `Duplicate child hrefs: ${duplicates.join(", ")}`).toEqual([]);
  });
});
