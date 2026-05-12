import type { NextConfig } from "next";
import path from "path";

const sharedDir = path.resolve(__dirname, "../shared");

const nextConfig: NextConfig = {
  // Wave B10 (2026-05-12): @infinityrx/portal-shared is consumed as
  // source-mode TypeScript via npm workspace symlink. Next must transpile
  // it (otherwise it tries to load .ts from node_modules as if compiled
  // and fails at runtime). Per Next docs:
  // https://nextjs.org/docs/app/api-reference/config/next-config-js/transpilePackages
  transpilePackages: ["@infinityrx/portal-shared"],
  turbopack: {
    root: path.resolve(__dirname, ".."),
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
      { source: "/billing", destination: "/accounting/cycles", permanent: false },
      { source: "/billing/invoices", destination: "/accounting/invoices", permanent: false },
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
