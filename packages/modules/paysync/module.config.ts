// packages/modules/paysync/module.config.ts
// SP-1 PaySync module config.
// `config` follows SD-4 §3 shape (read by packages/scripts/build-manifest.ts:36-77).
// `paysyncComposition` carries paysync-specific runtime composition (rbac matrix,
// inbox kind registrations, route-to-surface map, navTree, qa). Per Plan A R2,
// no shared type is imported from @infinityrx/shell — the `as const` literal is
// sufficient; build-manifest reads the literal via dynamic import and
// structurally validates the SD-4 fields.

export const config = {
  name: "paysync",
  routes: [
    "/admin/paysync",
    "/admin/paysync/uploads",
    "/admin/paysync/cycles",
    "/admin/paysync/batches",
    "/admin/paysync/carryovers",
    "/admin/paysync/invoices",
    "/admin/paysync/payment-runs",
    "/admin/paysync/files",
    "/admin/paysync/settlements",
    "/admin/paysync/reconcile",
    "/admin/paysync/journal",
    "/admin/paysync/reports",
    "/admin/paysync/setup",
  ],
  navEntry: {
    label: "PaySync",
    icon: "credit-card",
    order: 20,
  },
  requires: {
    backends: ["billing", "payment-processing", "core-platform"],
    sharedServices: ["postgres", "redis"],
    schemas: ["billing_v1", "payment_processing_v1", "core_v1"],
    migrations: ["core", "billing", "payment-processing"],
    env: [
      "DATABASE_URL_BILLING",
      "DATABASE_URL_PAYMENT_PROCESSING",
      "PAYSYNC_UPLOAD_DIR",
      "PAYSYNC_HASH_CHAIN_SYNC_LIMIT",
    ],
    health: [
      "http://billing:8040/health",
      "http://payment-processing:8050/health",
    ],
    seedData: [],
    queues: ["paysync.upload.parsed"],
    jobs: ["paysync.uploads.retention", "paysync.audit.hash-chain.verify"],
    buckets: [],
    integrations: [],
    secrets: [
      "secret://db/billing",
      "secret://db/payment-processing",
    ],
  },
  shellSurfaces: {
    navOrderSlots: [20],
    cacheTagPrefixes: ["paysync:"],
    commandPaletteScopes: ["paysync.*"],
    routePrefixes: ["/admin/paysync"],
    cacheKeyNamespaces: ["paysync:"],
    redisKeyPrefixes: ["tenant:*:paysync:"],
    rabbitExchanges: ["paysync"],
  },
  surfaceKinds: ["server", "client"] as Array<"server" | "client">,
  entitlements: { requiredScope: null },
} as const;

// Paysync-specific runtime composition. NOT read by SD-4 manifest tooling.
// Consumed by:
//   - Surface mounting (Plans B–E)
//   - Inbox card registry (via the dynamic imports below)
//   - qa-harness role switcher chip (qa-harness only, never production)
export const paysyncComposition = {
  displayName: "PaySync",
  rbac: {
    operator: [
      "paysync.upload", "paysync.upload.view", "paysync.batch.draft",
      "paysync.cycle.view", "paysync.carryover.view", "paysync.journal.view",
      "paysync.audit.view",
    ],
    approver: [
      "paysync.upload", "paysync.upload.view", "paysync.batch.draft",
      "paysync.cycle.view", "paysync.carryover.view", "paysync.journal.view",
      "paysync.audit.view",
      "paysync.cycle.close", "paysync.invoice.send", "paysync.payment_run.release",
      "paysync.nacha.generate", "paysync.835.generate", "paysync.reconcile.finalize",
      "paysync.discrepancy.resolve", "paysync.manual_ap.commit", "paysync.setup.mutate",
    ],
    auditor: [
      "paysync.read", "paysync.upload.view", "paysync.journal.view",
      "paysync.journal.verify", "paysync.audit.view",
    ],
  },
  inboxItemKinds: [
    { kind: "upload_pending_review",              card: () => import("./src/inbox/cards/UploadPendingReviewCard.js")    },
    { kind: "upload_validated_awaiting_batching", card: () => import("./src/inbox/cards/UploadValidatedCard.js")        },
    { kind: "cycle_pending_close",                card: () => import("./src/inbox/cards/CyclePendingCloseCard.js")      },
    { kind: "cycle_close_review",                 card: () => import("./src/inbox/cards/CycleCloseReviewCard.js")       },
    { kind: "batch_drafted",                      card: () => import("./src/inbox/cards/BatchDraftedCard.js")           },
    { kind: "ar_invoice_draft",                   card: () => import("./src/inbox/cards/ArInvoiceDraftCard.js")         },
    { kind: "ap_payment_run_held",                card: () => import("./src/inbox/cards/ApPaymentRunHeldCard.js")       },
    { kind: "banking_discrepancy",                card: () => import("./src/inbox/cards/BankingDiscrepancyCard.js")     },
    { kind: "reconciliation_pending",             card: () => import("./src/inbox/cards/ReconciliationPendingCard.js")  },
    { kind: "carryover_open",                     card: () => import("./src/inbox/cards/CarryoverOpenCard.js")          },
    { kind: "journal_periodic_review",            card: () => import("./src/inbox/cards/JournalPeriodicReviewCard.js")  },
  ],
  routeSurfaces: {
    "/admin/paysync":              "uploads",        // Inbox at index
    "/admin/paysync/uploads":      "uploads",
    "/admin/paysync/cycles":       "cycles",
    "/admin/paysync/batches":      "batches",
    "/admin/paysync/carryovers":   "carryovers",
    "/admin/paysync/invoices":     "invoices",
    "/admin/paysync/payment-runs": "payment-runs",
    "/admin/paysync/files":        "files",
    "/admin/paysync/settlements":  "bank-settlements",
    "/admin/paysync/reconcile":    "reconciliations",
    "/admin/paysync/journal":      "journal",
    "/admin/paysync/reports":      "reports",
    "/admin/paysync/setup":        "setup",
  },
  navTree: {
    primary: [
      { label: "Inbox",    path: "/admin/paysync",             icon: "inbox"      },
      { label: "History",  path: "/admin/paysync/uploads",     icon: "clock"      },
      { label: "Journal",  path: "/admin/paysync/journal",     icon: "book-open"  },
      { label: "Reports",  path: "/admin/paysync/reports",     icon: "bar-chart"  },
      { label: "Setup",    path: "/admin/paysync/setup",       icon: "settings"   },
    ],
  },
  qa: {
    RoleSwitcherChip: () => import("./src/components/dev-only/RoleSwitcherChip.js"),
  },
} as const;
