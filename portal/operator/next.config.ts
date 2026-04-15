import type { NextConfig } from "next";
import path from "path";

const sharedDir = path.resolve(__dirname, "../shared");
const operatorModules = path.resolve(__dirname, "node_modules");

const nextConfig: NextConfig = {
  turbopack: {
    root: path.resolve(__dirname, ".."),
    resolveAlias: {
      "@shared": sharedDir,
    },
  },
  webpack: (config) => {
    config.resolve.alias["@shared"] = sharedDir;
    if (Array.isArray(config.resolve.modules)) {
      if (!config.resolve.modules.includes(operatorModules)) {
        config.resolve.modules = [operatorModules, ...config.resolve.modules];
      }
    } else {
      config.resolve.modules = [operatorModules, "node_modules"];
    }
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
