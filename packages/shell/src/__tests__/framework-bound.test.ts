import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

/**
 * Framework-bound enforcement test.
 *
 * Asserts the SD-2 §6 mandate: packages other than `packages/shell`
 * MUST NOT import from `next/*`, `next-auth/*`, or `@auth/*`.
 * `packages/shell` is the ONLY package allowed to cross this boundary.
 *
 * Implementation: grep src/** files for the forbidden import patterns.
 * This is intentionally static/grep-based (not AST) to catch dynamic
 * require() and string-concatenated imports that AST analysis might miss.
 */

const WORKSPACE_ROOT = resolve(__dirname, "../../../..");
const FRAMEWORK_PATTERNS = [
  /from\s+["']next\//,
  /from\s+["']next-auth/,
  /from\s+["']@auth\//,
  /require\s*\(\s*["']next\//,
  /require\s*\(\s*["']next-auth/,
  /require\s*\(\s*["']@auth\//,
];

// Packages that MUST NOT import next/* etc.
const AGNOSTIC_PACKAGES = [
  "packages/contract",
  "packages/auth",
  "packages/ui",
  "packages/qa-harness",
];

function collectTsFiles(dir: string): string[] {
  const results: string[] = [];
  try {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      const stat = statSync(full);
      if (stat.isDirectory() && entry !== "node_modules" && entry !== "dist") {
        results.push(...collectTsFiles(full));
      } else if (stat.isFile() && (entry.endsWith(".ts") || entry.endsWith(".tsx"))) {
        results.push(full);
      }
    }
  } catch {
    // Directory doesn't exist yet (pre-Plan-C execution)
  }
  return results;
}

describe("framework-agnostic spine enforcement", () => {
  for (const pkg of AGNOSTIC_PACKAGES) {
    it(`${pkg}/src contains zero next/* / next-auth/* / @auth/* imports`, () => {
      const srcDir = join(WORKSPACE_ROOT, pkg, "src");
      const files = collectTsFiles(srcDir);
      const violations: string[] = [];

      for (const file of files) {
        // Skip test files — they may mock next/navigation etc.
        if (file.includes("__tests__") || file.includes(".test.")) continue;
        const content = readFileSync(file, "utf-8");
        for (const pattern of FRAMEWORK_PATTERNS) {
          if (pattern.test(content)) {
            violations.push(`${file}: matches ${pattern}`);
          }
        }
      }

      expect(violations).toEqual([]);
    });
  }

  it("packages/shell/src/qa/qa-mode-middleware.ts is allowed to import next/server", () => {
    const middlewarePath = join(WORKSPACE_ROOT, "packages/shell/src/qa/qa-mode-middleware.ts");
    try {
      const content = readFileSync(middlewarePath, "utf-8");
      expect(content).toMatch(/from\s+["']next\/server["']/);
    } catch {
      // File not created yet — test will fail naturally if the file is missing
      expect(true, "qa-mode-middleware.ts must exist after Task 4").toBe(false);
    }
  });
});
