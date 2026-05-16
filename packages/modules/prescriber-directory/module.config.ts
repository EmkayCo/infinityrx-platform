// packages/modules/prescriber-directory/module.config.ts
// SP-0 reference module config. SD-4 §3 mandates this shape.
// The manifest validator reads this file to verify transitive-closure completeness.

export const config = {
  name: "prescriber-directory",
  routes: [
    "/prescribers",
    "/prescribers/:npi",
    "/prescribers/search",
  ],
  navEntry: {
    label: "Prescribers",
    icon: "user-md",
    order: 10,
  },
  requires: {
    backends: ["prescriber-directory", "core-platform"],
    sharedServices: ["postgres", "redis"],
    schemas: ["prescriber_directory_v1", "core_v1"],
    migrations: ["core", "prescriber-directory"],
    env: ["DATABASE_URL_PRESCRIBER_DIRECTORY"],
    health: ["http://prescriber-directory:8030/health"],
    seedData: ["reference/nppes"],
    queues: [],
    jobs: [],
    buckets: [],
    integrations: [],
    secrets: ["secret://db/prescriber-directory"],
  },
  shellSurfaces: {
    navOrderSlots: [10],
    cacheTagPrefixes: ["prescriber-directory:"],
    commandPaletteScopes: ["prescribers.*"],
    routePrefixes: ["/prescribers"],
    cacheKeyNamespaces: ["prescriber-directory:"],
    redisKeyPrefixes: ["tenant:*:prescriber-directory:"],
    rabbitExchanges: [],
  },
  surfaceKinds: ["server", "client"] as Array<"server" | "client">,
  entitlements: { requiredScope: null },
} as const;
