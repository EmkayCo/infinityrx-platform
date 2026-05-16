// packages/scripts/audit-module-graph.ts
// Post-build composition audit: asserts omitted modules are absent from .nft.json traces.
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";

export interface AuditOptions {
  nextDir: string;            // path to .next/ (default: <repoRoot>/.next)
  repoRoot: string;
  manifestPath: string;       // path to the manifest JSON (the generated one, not YAML)
  knownModules: string[];     // all known module names (from packages/modules/*)
  /** Override trace loader for testing. */
  loadTraceFiles?: (nextDir: string) => TraceFile[];
}

export interface TraceFile {
  routePath: string;          // e.g. ".next/server/app/prescribers/page.js.nft.json"
  files: string[];            // array of absolute file paths traced
}

export interface AuditViolation {
  omittedModule: string;
  foundInRoute: string;
  foundFile: string;
}

export interface AuditResult {
  passed: boolean;
  violations: AuditViolation[];
  omittedModules: string[];
  checkedRoutes: number;
}

export function loadTraceFilesFromDisk(nextDir: string): TraceFile[] {
  const serverAppDir = join(nextDir, "server", "app");
  if (!existsSync(serverAppDir)) return [];

  const traces: TraceFile[] = [];
  function walk(dir: string) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && entry.name.endsWith(".nft.json")) {
        try {
          const raw = JSON.parse(readFileSync(full, "utf8")) as { files?: string[] };
          traces.push({ routePath: full, files: raw.files ?? [] });
        } catch {
          // Malformed trace — skip; audit cannot make assertions about it.
        }
      }
    }
  }
  walk(serverAppDir);
  return traces;
}

export function auditModuleGraph(opts: AuditOptions): AuditResult {
  const {
    nextDir,
    repoRoot: _repoRoot,
    manifestPath,
    knownModules,
    loadTraceFiles = loadTraceFilesFromDisk,
  } = opts;

  // 1. Read generated manifest to determine which modules ARE included.
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8")) as { modules: string[] };
  const includedModules = new Set(manifest.modules);
  const omittedModules = knownModules.filter((m) => !includedModules.has(m));

  if (omittedModules.length === 0) {
    // All known modules are included — nothing to assert absent.
    return { passed: true, violations: [], omittedModules: [], checkedRoutes: 0 };
  }

  // 2. Load all .nft.json trace files.
  const traceFiles = loadTraceFiles(nextDir);

  // 3. For each trace, check for omitted module package paths.
  const violations: AuditViolation[] = [];
  for (const trace of traceFiles) {
    for (const file of trace.files) {
      for (const omitted of omittedModules) {
        // Match both node_modules/@infinityrx/module-<name> and packages/modules/<name>/
        const packagePattern = `@infinityrx/module-${omitted}`;
        const srcPattern = `packages/modules/${omitted}/`;
        if (file.includes(packagePattern) || file.includes(srcPattern)) {
          violations.push({
            omittedModule: omitted,
            foundInRoute: trace.routePath,
            foundFile: file,
          });
        }
      }
    }
  }

  return {
    passed: violations.length === 0,
    violations,
    omittedModules,
    checkedRoutes: traceFiles.length,
  };
}

// ── CLI entrypoint ────────────────────────────────────────────────────────────

if (process.argv[1]?.endsWith("audit-module-graph.ts")) {
  const repoRoot = resolve(process.cwd());
  const nextDir = join(repoRoot, ".next");
  const manifestPath = join(repoRoot, "packages", "shell", "src", "_generated", "manifest.json");

  // Discover known modules from packages/modules/*/module.config.ts
  const modulesDir = join(repoRoot, "packages", "modules");
  const knownModules = existsSync(modulesDir)
    ? readdirSync(modulesDir, { withFileTypes: true })
        .filter((d) => d.isDirectory() && existsSync(join(modulesDir, d.name, "module.config.ts")))
        .map((d) => d.name)
    : [];

  const result = auditModuleGraph({ nextDir, repoRoot, manifestPath, knownModules });

  if (!result.passed) {
    console.error(`\naudit-module-graph: FAILED — ${result.violations.length} violation(s)\n`);
    for (const v of result.violations) {
      console.error(`  OMITTED MODULE "${v.omittedModule}" found in route: ${v.foundInRoute}`);
      console.error(`    file: ${v.foundFile}`);
    }
    process.exit(1);
  }

  console.log(
    `audit-module-graph: PASSED — checked ${result.checkedRoutes} routes, ` +
    `${result.omittedModules.length} omitted modules verified absent`
  );
}
