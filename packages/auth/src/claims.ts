import { z } from "zod";
import { EnvClaimSchema } from "./env-claim.js";

/** Per SD-1 §2. `.strict()` rejects unknown keys (Ajv-equivalent additionalProperties:false). */
export const AccessClaimsSchema = z.object({
  sub: z.string().uuid(),
  tid: z.string().uuid(),
  roles: z.array(z.string()),
  typ: z.literal("access"),
  iat: z.number().int(),
  exp: z.number().int(),
  jti: z.string().uuid(),
  iss: z.literal("infinityrx"),
  aud: z.literal("infinityrx-backend"),
  env: EnvClaimSchema,
}).strict();
export type AccessClaims = z.infer<typeof AccessClaimsSchema>;

/** Per SD-1 §3. No tid, no roles on refresh. `.strict()` REJECTS tid/roles — non-strict z.object would silently strip them. */
export const RefreshClaimsSchema = z.object({
  sub: z.string().uuid(),
  typ: z.literal("refresh"),
  iat: z.number().int(),
  exp: z.number().int(),
  jti: z.string().uuid(),
  iss: z.literal("infinityrx"),
  aud: z.literal("infinityrx-backend"),
  env: EnvClaimSchema,
}).strict();
export type RefreshClaims = z.infer<typeof RefreshClaimsSchema>;

export const ISSUER = "infinityrx" as const;
export const AUDIENCE = "infinityrx-backend" as const;
