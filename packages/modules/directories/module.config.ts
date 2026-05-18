// packages/modules/directories/module.config.ts
// SP-2 Directories module config.
// Follows SD-4 §3 shape (read by packages/scripts/build-manifest.ts).
// No shared type imported from @infinityrx/shell — `as const` literal per SP-0 Plan A R2.

export const config = {
  name: "directories",
  routes: [
    "/directories",
    "/directories/prescribers",
    "/directories/prescribers/[npi]",
    "/directories/pharmacies",
    "/directories/pharmacies/[npi]",
    "/directories/drugs",
    "/directories/drugs/[ndc]",
    "/directories/codes/hcpcs",
    "/directories/codes/icd10",
    "/directories/pricing",
    "/directories/exclusions",
    "/directories/ingestion",
    "/directories/audit",
  ],
  navEntry: {
    label: "Directories",
    icon: "database",
    order: 3,
  },
  requires: {
    backends: ["prescriber-directory", "pharmacy-directory", "drug-database", "core-platform"],
    sharedServices: ["postgres", "redis"],
    schemas: ["prescriber_dir", "pharmacy_dir", "drug_db", "shared", "audit"],
    migrations: [],
    env: [
      "PRESCRIBER_DIRECTORY_URL",
      "PHARMACY_DIRECTORY_URL",
      "DRUG_DATABASE_URL",
      "CORE_PLATFORM_URL",
    ],
    health: [
      "http://prescriber-directory:8010/health",
      "http://pharmacy-directory:8009/health",
      "http://drug-database:8011/health",
    ],
    seedData: ["directories/fixtures"],
    queues: [],
    jobs: [],
    buckets: [],
    integrations: ["shared-ingestion-api"],
    secrets: [],
  },
  shellSurfaces: {
    navOrderSlots: [3],
    cacheTagPrefixes: ["dir:"],
    commandPaletteScopes: ["directories.*"],
    routePrefixes: ["/directories"],
    cacheKeyNamespaces: ["dir"],
    redisKeyPrefixes: ["dir:"],
  },
} as const;

export default config;
