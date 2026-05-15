import type { BaseClient, ClientConfig, ClientFactory } from "../../client-base.js";
import type {
  Npi,
  Prescriber,
  PrescriberSearchRequest,
  PrescriberSearchResponse,
} from "./types.js";
import type { CachePolicy } from "../../cache-policy.js";

export interface PrescriberDirectoryClient extends BaseClient {
  readonly name: "prescriber-directory";

  /** Search prescribers by name/NPI/specialty. Cached per the policy below. */
  search(req: PrescriberSearchRequest): Promise<PrescriberSearchResponse>;

  /** Fetch one prescriber by NPI. Cached aggressively. */
  getByNpi(npi: Npi): Promise<Prescriber | null>;
}

export const PRESCRIBER_DIRECTORY_CACHE_POLICIES: Record<string, CachePolicy> = {
  search: {
    ttl_seconds: 60,
    key: ["prescriber-directory", "search", "{q}", "{state}", "{specialty}", "{cursor}"],
    invalidation_tags: ["prescriber"],
    backend_down: "stale-ok",
  },
  getByNpi: {
    ttl_seconds: 3600,
    key: ["prescriber-directory", "by-npi", "{npi}"],
    invalidation_tags: ["prescriber"],
    backend_down: "fall-back-to-mock",
  },
};

export type PrescriberDirectoryFactory = ClientFactory<PrescriberDirectoryClient>;
export type { ClientConfig };
