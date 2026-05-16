// packages/scripts/generate-eslint-zones.test.ts
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { describe, expect, it } from "vitest";
import {
  buildZones,
  generateEslintZones,
  type GenerateZonesOptions,
} from "./generate-eslint-zones.js";

function makeTmpDir() {
  const dir = join(tmpdir(), `eslint-zones-test-${randomUUID()}`);
  mkdirSync(dir, { recursive: true });
  return dir;
}

describe("buildZones", () => {
  it("0 modules → 0 zones", () => {
    expect(buildZones([])).toHaveLength(0);
  });

  it("1 module → 0 zones (no siblings)", () => {
    expect(buildZones(["prescriber-directory"])).toHaveLength(0);
  });

  it("2 modules → 2 zones (N*(N-1) = 2)", () => {
    const zones = buildZones(["alpha", "beta"]);
    expect(zones).toHaveLength(2);
    const targets = zones.map((z) => z.target);
    expect(targets).toContain("./packages/modules/alpha/**");
    expect(targets).toContain("./packages/modules/beta/**");
  });

  it("3 modules → 6 zones (N*(N-1) = 6)", () => {
    expect(buildZones(["a", "b", "c"])).toHaveLength(6);
  });

  it("no zone has target === from (same-module imports never forbidden)", () => {
    const zones = buildZones(["x", "y", "z"]);
    for (const zone of zones) {
      // target = ./packages/modules/x/** from = ./packages/modules/y/** — x !== y
      const targetName = zone.target.match(/modules\/([^/]+)\//)?.[1];
      const fromName = zone.from.match(/modules\/([^/]+)\//)?.[1];
      expect(targetName).not.toBe(fromName);
    }
  });

  it("zone message names both modules for readable lint output", () => {
    const zones = buildZones(["reclaimrx", "paysync"]);
    const rxToPay = zones.find((z) => z.target.includes("reclaimrx") && z.from.includes("paysync"));
    expect(rxToPay?.message).toContain("reclaimrx");
    expect(rxToPay?.message).toContain("paysync");
  });
});

describe("generateEslintZones", () => {
  it("writes eslint-zones.mjs with GENERATED_MODULE_ZONES export (STILL-OPEN-3 fix)", () => {
    const outputDir = makeTmpDir();
    generateEslintZones({
      repoRoot: makeTmpDir(),
      outputDir,
      discoverModuleNames: () => ["prescriber-directory"],
    } satisfies GenerateZonesOptions);

    // STILL-OPEN-3a: output is .mjs not .ts (Node ESM can import .mjs at runtime)
    const content = readFileSync(join(outputDir, "eslint-zones.mjs"), "utf8");
    expect(content).toContain("GENERATED_MODULE_ZONES");
    expect(content).toContain("input_hash: sha256:");
    // .mjs must not contain TypeScript syntax (no interface, type annotations, "as const")
    expect(content).not.toContain("interface ZoneEntry");
    expect(content).not.toContain("ZoneEntry[]");
  });

  it("two runs with same module list produce identical inputHash", () => {
    const outputDir = makeTmpDir();
    const opts: GenerateZonesOptions = {
      repoRoot: makeTmpDir(), outputDir,
      discoverModuleNames: () => ["alpha", "beta"],
    };
    const r1 = generateEslintZones(opts);
    const r2 = generateEslintZones(opts);
    expect(r1.inputHash).toBe(r2.inputHash);
  });

  it("different module list produces different inputHash (staleness detection works)", () => {
    const outputDir = makeTmpDir();
    const base = makeTmpDir();
    const r1 = generateEslintZones({ repoRoot: base, outputDir, discoverModuleNames: () => ["alpha"] });
    const r2 = generateEslintZones({ repoRoot: base, outputDir, discoverModuleNames: () => ["alpha", "beta"] });
    expect(r1.inputHash).not.toBe(r2.inputHash);
  });

  it("reports correct zoneCount in result object", () => {
    const outputDir = makeTmpDir();
    const result = generateEslintZones({
      repoRoot: makeTmpDir(), outputDir,
      discoverModuleNames: () => ["a", "b", "c"],
    });
    expect(result.zoneCount).toBe(6);
  });
});
