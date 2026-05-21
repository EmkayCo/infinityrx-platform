import type { NextConfig } from "next";
import path from "path";
import { execSync } from "node:child_process";

const sharedDir = path.resolve(__dirname, "../shared");

// Turbopack root must span the whole monorepo (not just portal/) so that
// workspace packages under packages/ are resolvable. npm workspace junctions
// + each package's package.json "exports" field handle module resolution;
// no explicit drive-letter aliases needed (Turbopack rejects them on Windows).
const repoRootDir = path.resolve(__dirname, "..", "..");

// Plan D SP-0: Pre-build hook — run build-manifest.ts to emit _generated/ artifacts.
// The generator validates the manifest schema and fails the build if validation errors exist.
// Runs synchronously before Next.js starts (intentionally blocking).
function runPrebuild() {
  const repoRoot = path.resolve(__dirname, "..", "..");
  try {
    execSync("node --import tsx packages/scripts/build-manifest.ts", {
      cwd: repoRoot,
      stdio: "inherit",
      env: {
        ...process.env,
        INFINITYRX_MANIFEST:
          process.env["INFINITYRX_MANIFEST"] ??
          path.join(repoRoot, "infrastructure", "manifests", "operator-dev.yml"),
        INFINITYRX_GENERATED_OUT:
          path.join(repoRoot, "packages", "shell", "src", "_generated"),
      },
    });
  } catch (err) {
    throw new Error(`build-manifest failed — fix manifest errors before building the portal.\n${String(err)}`);
  }
}

// Run at config evaluation time (= start of next build / next dev).
// Skip during CI test runs to avoid tsx dependency on test agents.
if (process.env["SKIP_PREBUILD"] !== "1") {
  try {
    runPrebuild();
  } catch {
    // Non-fatal during dev — missing generated files degrade gracefully.
    console.warn("[next.config] build-manifest failed — _generated/ may be stale. Run npm run prebuild.");
  }
}

const nextConfig: NextConfig = {
  // Wave B10 (2026-05-12): @infinityrx/portal-shared is consumed as
  // source-mode TypeScript via npm workspace symlink. Next must transpile
  // it (otherwise it tries to load .ts from node_modules as if compiled
  // and fails at runtime). Per Next docs:
  // https://nextjs.org/docs/app/api-reference/config/next-config-js/transpilePackages
  transpilePackages: ["@infinityrx/portal-shared", "@infinityrx/shell", "@infinityrx/ui"], // module-directories + module-paysync removed: transpile source-mode created a 2nd react-query module-graph context -> "No QueryClient set"; resolved via their compiled dist instead (docs/audit/queryclient-turbopack-fix-plan.md)
  turbopack: {
    // Monorepo root (NOT portal/): the module dist aliases below resolve to
    // repoRoot/packages/modules/**, which sit OUTSIDE portal/. Turbopack refuses
    // to resolve modules outside turbopack.root, so root must span the whole repo.
    root: repoRootDir,
    resolveAlias: {
      "@shared": sharedDir,
    },
  },
  webpack: (config) => {
    // Wave B10 (2026-05-12 W1.12): the prior `config.resolve.modules` injection
    // of `operatorModules` was a workaround for the missing-workspace bug
    // (sibling portal/shared couldn't reach portal/operator/node_modules via
    // Node's up-walk). The npm workspace conversion in W1.AB makes this
    // unnecessary — npm hoists shared deps to portal/node_modules/, which
    // Node finds via the standard up-walk from portal/{operator,shared}/.
    // Keep only the @shared alias for the path-based imports.
    config.resolve.alias["@shared"] = sharedDir;
    return config;
  },
  typedRoutes: false,
  async redirects() {
    // Phase 1A route migration — keep old bookmarks working while sidebar
    // moves to the new ICP information architecture.
    return [
      { source: "/billing/claims", destination: "/claims", permanent: false },
      { source: "/billing/cycles", destination: "/accounting/cycles", permanent: false },
      // Regex constraint: negative lookbehind (?<!new) prevents this rule from
      // catching /billing/cycles/new -- the BillingCycleWizard must stay reachable.
      // A bare :id segment would redirect /billing/cycles/new to /accounting/cycles/new
      // (no page exists there), permanently blocking the wizard.
      { source: "/billing/cycles/:slug([^/]+(?<!new))", destination: "/accounting/cycles/:slug", permanent: false },
      { source: "/billing", destination: "/accounting/cycles", permanent: false },
      // ATOMIC edit: remove broken /billing/invoices->/accounting/invoices (destination
      // had no page.tsx) and add reverse in same commit. Adding the reverse alone creates
      // a redirect loop: /billing/invoices->/accounting/invoices->/billing/invoices (508).
      { source: "/accounting/invoices", destination: "/billing/invoices", permanent: false },
      { source: "/payments", destination: "/accounting/payments", permanent: false },
      { source: "/payments/batches/new", destination: "/accounting/payments", permanent: false },
      { source: "/payments/nacha", destination: "/accounting/nacha", permanent: false },
      { source: "/analytics/member", destination: "/analytics/adherence", permanent: false },
      { source: "/analytics/drug-trend", destination: "/analytics/fills", permanent: false },
      { source: "/analytics/network", destination: "/analytics/pharmacies", permanent: false },
      { source: "/analytics/financial", destination: "/analytics/trends", permanent: false },
      { source: "/analytics/data-quality", destination: "/analytics/claims", permanent: false },
      { source: "/analytics", destination: "/analytics/claims", permanent: false },
      { source: "/reporting", destination: "/reporting/library", permanent: false },
      { source: "/edi", destination: "/edi/monitor", permanent: false },
      { source: "/reclaimrx/investigations/new", destination: "/reclaimrx/wizard", permanent: false },
    ];
  },
};

export default nextConfig;
