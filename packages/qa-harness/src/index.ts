// Public surface of @infinityrx/qa-harness.
// IMPORTANT: This package is a dev/staging tool. Omit from production builds.

export { ServicesHealth, type ServicesHealthProps } from "./services-health.js";
export { MockToggle, type MockToggleProps, type ClientMode } from "./mock-toggle.js";
export { CompositionViewer, type CompositionViewerProps, type CompositionManifest } from "./composition-viewer.js";
export { FactoryBindings, type FactoryBindingsProps, type SeedBinding } from "./factory-bindings.js";
export { CorrelationIdJump, type CorrelationIdJumpProps } from "./correlation-id-jump.js";

// PaySync E2E helpers — seed loader, auth, DB cleanup, browser context
export {
  seedPaysync,
  PAYSYNC_SEED_BINDING,
  DEMO_TENANT_ID,
  type PaysyncSeedOptions,
  type PaysyncSeedResult,
} from "./seeds/paysync-seed.js";

export {
  fetchTestAuthToken,
  injectJwtIntoContext,
  OPERATOR_USER_ID,
  APPROVER_USER_ID,
  AUDITOR_USER_ID,
  type TestAuthOptions,
  type TestAuthResponse,
} from "./e2e/auth-helpers.js";

export {
  cleanupBillingData,
  BILLING_TRUNCATE_ORDER,
  type DbCleanupOptions,
} from "./e2e/db-cleanup.js";

export {
  createPaysyncContext,
  PAYSYNC_E2E_BASE_URLS,
  type PaysyncContextOptions,
  type PaysyncContext,
} from "./e2e/browser-context.js";
