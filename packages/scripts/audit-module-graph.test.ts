// packages/scripts/audit-module-graph.test.ts
import { describe, expect, it } from "vitest";
import {
  auditModuleGraph,
  type AuditOptions,
  type TraceFile,
} from "./audit-module-graph.js";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";

function makeTmpManifest(modules: string[]): string {
  const dir = join(tmpdir(), `audit-test-${randomUUID()}`);
  mkdirSync(dir, { recursive: true });
  const manifestPath = join(dir, "manifest.json");
  writeFileSync(manifestPath, JSON.stringify({ modules }, null, 2));
  return manifestPath;
}

function makeOpts(overrides: Partial<AuditOptions> & { modules: string[] }): AuditOptions {
  return {
    nextDir: "/irrelevant",
    repoRoot: "/irrelevant",
    manifestPath: makeTmpManifest(overrides.modules),
    knownModules: overrides.knownModules ?? overrides.modules,
    loadTraceFiles: overrides.loadTraceFiles ?? (() => []),
  };
}

describe("auditModuleGraph", () => {
  it("all modules included → passed immediately with 0 checkedRoutes", () => {
    const result = auditModuleGraph(makeOpts({ modules: ["prescriber-directory"], knownModules: ["prescriber-directory"] }));
    expect(result.passed).toBe(true);
    expect(result.omittedModules).toHaveLength(0);
    expect(result.checkedRoutes).toBe(0);
  });

  it("omitted module absent from all traces → passed", () => {
    const traces: TraceFile[] = [
      { routePath: ".next/server/app/prescribers/page.js.nft.json",
        files: ["/node_modules/@infinityrx/module-prescriber-directory/dist/index.js"] },
    ];
    const result = auditModuleGraph(makeOpts({
      modules: ["prescriber-directory"],
      knownModules: ["prescriber-directory", "reclaimrx"],
      loadTraceFiles: () => traces,
    }));
    expect(result.passed).toBe(true);
    expect(result.violations).toHaveLength(0);
    expect(result.omittedModules).toEqual(["reclaimrx"]);
  });

  it("omitted module present in a trace → failed with violation detail", () => {
    const traces: TraceFile[] = [
      {
        routePath: ".next/server/app/prescribers/page.js.nft.json",
        files: [
          "/node_modules/@infinityrx/module-prescriber-directory/dist/index.js",
          "/node_modules/@infinityrx/module-reclaimrx/dist/index.js", // should be absent
        ],
      },
    ];
    const result = auditModuleGraph(makeOpts({
      modules: ["prescriber-directory"],
      knownModules: ["prescriber-directory", "reclaimrx"],
      loadTraceFiles: () => traces,
    }));
    expect(result.passed).toBe(false);
    expect(result.violations).toHaveLength(1);
    expect(result.violations[0]!.omittedModule).toBe("reclaimrx");
    expect(result.violations[0]!.foundInRoute).toContain("prescribers");
  });

  it("omitted module found via src path (packages/modules/<name>/) → violation", () => {
    const traces: TraceFile[] = [
      { routePath: ".next/server/app/page.js.nft.json",
        files: ["/repo/packages/modules/reclaimrx/src/index.ts"] },
    ];
    const result = auditModuleGraph(makeOpts({
      modules: [],
      knownModules: ["reclaimrx"],
      loadTraceFiles: () => traces,
    }));
    expect(result.passed).toBe(false);
    expect(result.violations[0]!.foundFile).toContain("packages/modules/reclaimrx");
  });

  it("multiple omitted modules each produce separate violations", () => {
    const traces: TraceFile[] = [
      {
        routePath: ".next/server/app/page.js.nft.json",
        files: [
          "/node_modules/@infinityrx/module-reclaimrx/dist/index.js",
          "/node_modules/@infinityrx/module-paysync/dist/index.js",
        ],
      },
    ];
    const result = auditModuleGraph(makeOpts({
      modules: [],
      knownModules: ["reclaimrx", "paysync"],
      loadTraceFiles: () => traces,
    }));
    expect(result.passed).toBe(false);
    expect(result.violations).toHaveLength(2);
  });

  it("no .nft.json files → passed (nothing to check)", () => {
    const result = auditModuleGraph(makeOpts({
      modules: [],
      knownModules: ["reclaimrx"],
      loadTraceFiles: () => [],
    }));
    expect(result.passed).toBe(true);
    expect(result.checkedRoutes).toBe(0);
  });
});
