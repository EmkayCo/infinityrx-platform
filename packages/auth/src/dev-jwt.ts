import { mintTokenPair, type MintedTokens } from "./mint.js";
import type { EnvClaim } from "./env-claim.js";
import type { RevocationRepo } from "./revocation-repo.js";

export interface DevJwtOptions {
  sub?: string;
  tid?: string;
  roles?: string[];
  env: EnvClaim;
  secret: string;
  repo: RevocationRepo;
}

const DEV_ADMIN_ID = "00000000-0000-4000-8000-000000000001";
const DEV_TENANT_ID = "00000000-0000-4000-8000-000000000002";

/**
 * Per SD-1 §7: single source of truth for dev/test JWT issuance. Refuses to
 * mint in production. Mints with `env != "production"` so prod backends with
 * INFINITYRX_ENV=production reject the token via the WRONG_ENVIRONMENT check.
 */
export async function mintDevJwt(opts: DevJwtOptions): Promise<MintedTokens> {
  if (opts.env === "production") {
    throw new Error(
      "mintDevJwt refused: env=production. Dev paths must not run in production. " +
      "Set INFINITYRX_ENV=development or mock.",
    );
  }
  return await mintTokenPair({
    sub: opts.sub ?? DEV_ADMIN_ID,
    tid: opts.tid ?? DEV_TENANT_ID,
    roles: opts.roles ?? ["platform_admin"],
    env: opts.env,
    secret: opts.secret,
    repo: opts.repo,
  });
}

export const DEV_IDENTITY = {
  sub: DEV_ADMIN_ID,
  tid: DEV_TENANT_ID,
} as const;
