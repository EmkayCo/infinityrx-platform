// packages/modules/reclaimrx/module.config.ts
// SP-3 ReclaimRx module config.
// Follows SD-4 §3 shape (read by packages/scripts/build-manifest.ts).
// No shared type imported from @infinityrx/shell — `as const` literal per SP-0 Plan A R2.

export const config = {
  name: "reclaimrx",
  routes: [
    "/reclaimrx",
    "/reclaimrx/dashboard",
    "/reclaimrx/investigations",
    "/reclaimrx/investigations/[id]",
    "/reclaimrx/holds",
    "/reclaimrx/fraud-rings",
    "/reclaimrx/fraud-rings/[id]",
    "/reclaimrx/graph-runs",
    "/reclaimrx/thresholds",
    "/reclaimrx/accumulator-anomalies",
  ],
  navEntry: {
    label: "ReclaimRx",
    icon: "shield-check",
    order: 4,
  },
  requires: {
    backends: ["reclaimrx", "core-platform"],
    sharedServices: ["postgres", "redis", "rabbitmq"],
    schemas: ["reclaimrx", "shared", "audit"],
    migrations: ["reclaimrx/0008"],
    env: [
      "RECLAIMRX_URL",
      "CORE_PLATFORM_URL",
    ],
    health: [
      "http://reclaimrx:8007/health",
    ],
    seedData: [],
    queues: ["reclaimrx.accumulator_updated", "reclaimrx.fwa_events"],
    jobs: ["graph_rebuild_fraud_network_graph"],
    buckets: [],
    integrations: [],
    secrets: [],
  },
  shellSurfaces: {
    navOrderSlots: [4],
    cacheTagPrefixes: ["reclaimrx:"],
    commandPaletteScopes: ["reclaimrx.*"],
    routePrefixes: ["/reclaimrx"],
    cacheKeyNamespaces: ["reclaimrx"],
    redisKeyPrefixes: ["tenant:{tenant_id}:reclaimrx:"],
  },
} as const;

export default config;
