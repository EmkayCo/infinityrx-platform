// packages/modules/prescriber-directory/src/factory.ts
// BLOCK 6 fix: Plan B HEAD exports factory functions, not classes.
// Actual exports from @infinityrx/contract (per wave/B10-w5:packages/contract/src/index.ts):
//   createRealPrescriberDirectoryClient(config: ClientConfig): PrescriberDirectoryClient
//   createMockPrescriberDirectoryClient(): PrescriberDirectoryClient
import type {
  PrescriberDirectoryClient,
  ClientConfig,
} from "@infinityrx/contract";
import {
  createRealPrescriberDirectoryClient,
  createMockPrescriberDirectoryClient,
} from "@infinityrx/contract";

type SupportedEnv = "development" | "mock" | "production";

export interface PrescriberDirectoryFactoryConfig extends ClientConfig {
  /** Backend base URL. Required when env is "production" or "mock". */
  baseUrl?: string;
}

/**
 * Returns the correct PrescriberDirectoryClient implementation for the given env.
 *
 * - development  → mock client (no network calls, in-memory fixture from Plan B)
 * - mock / production → real HTTP client (requires baseUrl in config)
 *
 * This is the SP-0 reference factory pattern. Every module in subsequent
 * waves ships a factory with this exact shape.
 *
 * Note for maintainers: delegates to Plan B's factory functions from @infinityrx/contract.
 * If Plan B renames these exports, this factory and its tests break at compile time (tsc -b).
 */
export function createPrescriberDirectoryClient(
  env: SupportedEnv,
  config: PrescriberDirectoryFactoryConfig
): PrescriberDirectoryClient {
  if (env === "development") {
    // createMockPrescriberDirectoryClient() takes no config — mock has in-memory fixture.
    return createMockPrescriberDirectoryClient();
  }

  if (!config.baseUrl) {
    throw new Error(
      `createPrescriberDirectoryClient: "baseUrl" is required for env="${env}". ` +
      `Set PRESCRIBER_DIRECTORY_URL in the environment.`
    );
  }

  return createRealPrescriberDirectoryClient({ ...config, baseUrl: config.baseUrl });
}
