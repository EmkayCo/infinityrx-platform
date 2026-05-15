// Public surface of @infinityrx/auth.

export {
  AccessClaimsSchema,
  RefreshClaimsSchema,
  ISSUER,
  AUDIENCE,
  type AccessClaims,
  type RefreshClaims,
} from "./claims.js";

export {
  EnvClaimSchema,
  resolveEnvClaim,
  type EnvClaim,
} from "./env-claim.js";

export {
  signAccessToken,
  signRefreshToken,
  verifyTokenRaw,
  assertJwtSecret,
} from "./crypto.js";

export {
  AuthError,
  AUTH_ERROR_MESSAGES,
  type AuthErrorCode,
} from "./errors.js";
