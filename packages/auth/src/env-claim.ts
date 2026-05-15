import { z } from "zod";

/**
 * The `env` claim per SD-1 §4. Tokens minted in one environment cannot be
 * accepted in another even if the secret were shared (which it MUST NOT be).
 * Defense-in-depth on top of per-environment JWT_SECRET separation.
 */
export const EnvClaimSchema = z.enum(["development", "mock", "production"]);
export type EnvClaim = z.infer<typeof EnvClaimSchema>;

/** Resolve the running process's environment from INFINITYRX_ENV. Throws if missing/invalid. */
export function resolveEnvClaim(env: string | undefined): EnvClaim {
  const result = EnvClaimSchema.safeParse(env);
  if (!result.success) {
    throw new Error(
      `INFINITYRX_ENV must be one of: development, mock, production. Got: ${JSON.stringify(env)}`,
    );
  }
  return result.data;
}
