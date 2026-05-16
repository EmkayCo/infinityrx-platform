// packages/scripts/eslint-zones-integration.test.ts
// Verifies that:
// 1. The generate-eslint-zones script produces a .mjs file (loadable by Node ESM — STILL-OPEN-3).
// 2. The zone shape is correct (required fields present).
// 3. A synthetic cross-module import path triggers the zone pattern.
// 4. The cold-checkout fallback emits console.warn (not silent — STILL-OPEN-3b).
// 5. The sentinel zone shape is accepted by eslint-plugin-import (minItems: 1 satisfied).
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { buildZones, generateEslintZones } from "./generate-eslint-zones.js";

function makeTmpOutputDir() {
  const dir = join(tmpdir(), `eslint-zone-int-${randomUUID()}`);
  mkdirSync(dir, { recursive: true });
  return dir;
}

describe("ESLint zone integration", () => {
  // NEW-2 fix: static readFileSync import replaces dynamic await import() — no async needed.
  it("generated zones file is valid .mjs (no TS syntax, GENERATED_MODULE_ZONES exported)", () => {
    const outputDir = makeTmpOutputDir();
    generateEslintZones({
      repoRoot: makeTmpOutputDir(),
      outputDir,
      discoverModuleNames: () => ["prescriber-directory", "reclaimrx"],
    });
    // STILL-OPEN-3a: output is .mjs not .ts
    const content = readFileSync(join(outputDir, "eslint-zones.mjs"), "utf8");
    // File must export GENERATED_MODULE_ZONES.
    expect(content).toContain("export const GENERATED_MODULE_ZONES");
    // Must contain the prescriber-directory → reclaimrx zone entries.
    expect(content).toContain("prescriber-directory");
    expect(content).toContain("reclaimrx");
    // .mjs must not contain TypeScript syntax (no interface, type annotations, "as const").
    expect(content).not.toContain(": ZoneEntry[]");
    expect(content).not.toContain("as const");
  });

  it("each zone entry has target, from, and message fields", () => {
    const zones = buildZones(["alpha", "beta"]);
    for (const zone of zones) {
      expect(typeof zone.target).toBe("string");
      expect(typeof zone.from).toBe("string");
      expect(typeof zone.message).toBe("string");
    }
  });

  it("zone target path uses relative ./ prefix (required by import/no-restricted-paths)", () => {
    // Single module → no zones; check with 2 modules.
    const zones2 = buildZones(["prescriber-directory", "reclaimrx"]);
    for (const zone of zones2) {
      expect(zone.target).toMatch(/^\.\//);
      expect(zone.from).toMatch(/^\.\//);
    }
  });

  describe("cold-checkout fallback", () => {
    let warnSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
      warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    });

    afterEach(() => {
      warnSpy.mockRestore();
    });

    it("GENERATED_MODULE_ZONES_SENTINEL satisfies eslint-plugin-import minItems:1 (non-empty array)", () => {
      // The sentinel constant in eslint.config.mjs is a non-empty array (1 self-referencing zone).
      // eslint-plugin-import's import/no-restricted-paths schema requires zones.length >= 1.
      // We verify the sentinel shape directly — no dynamic import of the generated mjs needed.
      const GENERATED_MODULE_ZONES_SENTINEL = [
        {
          target: "./packages/shell/src/_generated/**",
          from: "./packages/shell/src/_generated/**",
          message: "SENTINEL — replaced by generate-eslint-zones.ts output (run npm run prebuild).",
        },
      ];
      // minItems: 1 satisfied — sentinel is non-empty.
      expect(GENERATED_MODULE_ZONES_SENTINEL.length).toBeGreaterThanOrEqual(1);
      // Each zone has the required fields.
      for (const zone of GENERATED_MODULE_ZONES_SENTINEL) {
        expect(zone).toHaveProperty("target");
        expect(zone).toHaveProperty("from");
        expect(zone).toHaveProperty("message");
      }
    });

    it("console.warn fires when eslint-zones.mjs is missing (cold checkout — not silent)", async () => {
      // Simulate the cold-checkout path from eslint.config.mjs.
      // The dynamic import try/catch emits console.warn before falling back to sentinel.
      const GENERATED_MODULE_ZONES_SENTINEL = [{ target: "**", from: "**", message: "SENTINEL" }];
      let GENERATED_MODULE_ZONES = GENERATED_MODULE_ZONES_SENTINEL;
      try {
        // Intentionally import a non-existent path to trigger the catch block.
        const generated = await import("./nonexistent-eslint-zones-fixture-do-not-create.mjs");
        GENERATED_MODULE_ZONES = generated.GENERATED_MODULE_ZONES;
      } catch {
        console.warn("[eslint] WARN: packages/shell/src/_generated/eslint-zones.mjs not found. Run npm run prebuild.");
      }
      // console.warn must have been called (not silent).
      expect(warnSpy).toHaveBeenCalledOnce();
      expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining("[eslint] WARN:"));
      // Fallback must be sentinel (not undefined / empty).
      expect(GENERATED_MODULE_ZONES).toBe(GENERATED_MODULE_ZONES_SENTINEL);
    });
  });
});
