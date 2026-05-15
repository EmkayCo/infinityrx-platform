import { SignJWT, jwtVerify, type JWTPayload } from "jose";
import {
  JWTExpired,
  JWTClaimValidationFailed,
  JWSSignatureVerificationFailed,
  JWSInvalid,
  JWTInvalid,
  JOSEError,
} from "jose/errors";
import { AccessClaimsSchema, RefreshClaimsSchema, ISSUER, AUDIENCE, type AccessClaims, type RefreshClaims } from "./claims.js";
import { resolveEnvClaim, type EnvClaim } from "./env-claim.js";
import { AuthError, AUTH_ERROR_MESSAGES } from "./errors.js";

const ALGORITHM = "HS256" as const;

const DEV_PLACEHOLDER_SECRETS = new Set([
  "changeme",
  "dev-secret",
  "secret",
  "test",
  "your-secret-here",
]);

/**
 * Per SD-1 §4 startup check. Refuses to operate in production with a known
 * dev-placeholder secret.
 */
export function assertJwtSecret(secret: string | undefined, env: EnvClaim): void {
  if (!secret || secret.length < 32) {
    throw new Error(`JWT_SECRET must be ≥32 chars (got length=${secret?.length ?? 0})`);
  }
  if (env === "production") {
    const lower = secret.toLowerCase();
    const isPlaceholder = Array.from(DEV_PLACEHOLDER_SECRETS).some((p) => lower.startsWith(p));
    if (isPlaceholder) {
      throw new Error(
        "JWT_SECRET is a known dev placeholder. Production refuses to start with this secret.",
      );
    }
  }
}

function secretKey(secret: string): Uint8Array {
  return new TextEncoder().encode(secret);
}

export async function signAccessToken(claims: AccessClaims, secret: string): Promise<string> {
  AccessClaimsSchema.parse(claims);
  const key = secretKey(secret);
  return await new SignJWT({
    tid: claims.tid,
    roles: claims.roles,
    typ: claims.typ,
    env: claims.env,
  })
    .setProtectedHeader({ alg: ALGORITHM })
    .setIssuer(claims.iss)
    .setAudience(claims.aud)
    .setSubject(claims.sub)
    .setJti(claims.jti)
    .setIssuedAt(claims.iat)
    .setExpirationTime(claims.exp)
    .sign(key);
}

export async function signRefreshToken(claims: RefreshClaims, secret: string): Promise<string> {
  RefreshClaimsSchema.parse(claims);
  const key = secretKey(secret);
  return await new SignJWT({
    typ: claims.typ,
    env: claims.env,
  })
    .setProtectedHeader({ alg: ALGORITHM })
    .setIssuer(claims.iss)
    .setAudience(claims.aud)
    .setSubject(claims.sub)
    .setJti(claims.jti)
    .setIssuedAt(claims.iat)
    .setExpirationTime(claims.exp)
    .sign(key);
}

/**
 * Throws AuthError for any §8 check failure. Caller still runs §8.5 revocation checks.
 * Maps jose's typed errors via instanceof (NOT substring matching on .message — that
 * was brittle; codex pass-1 BLOCK).
 *
 * jose error hierarchy (from `jose/errors`):
 *   - JOSEError (base)
 *     - JWTExpired                        -> EXPIRED_TOKEN
 *     - JWTClaimValidationFailed          -> WRONG_ISSUER / WRONG_AUDIENCE (check `claim` field)
 *     - JWSSignatureVerificationFailed    -> INVALID_TOKEN
 *     - JWSInvalid / JWTInvalid           -> MALFORMED_TOKEN
 *     - other JOSEError subclasses        -> INVALID_TOKEN (fallback)
 */
export async function verifyTokenRaw(token: string, secret: string, env: EnvClaim): Promise<JWTPayload> {
  const key = secretKey(secret);
  try {
    const { payload } = await jwtVerify(token, key, {
      issuer: ISSUER,
      audience: AUDIENCE,
      algorithms: [ALGORITHM],
      clockTolerance: 30,
    });
    if (payload.env !== env) {
      throw new AuthError("WRONG_ENVIRONMENT", AUTH_ERROR_MESSAGES.WRONG_ENVIRONMENT);
    }
    return payload;
  } catch (e) {
    if (e instanceof AuthError) throw e;
    if (e instanceof JWTExpired) {
      throw new AuthError("EXPIRED_TOKEN", AUTH_ERROR_MESSAGES.EXPIRED_TOKEN);
    }
    if (e instanceof JWTClaimValidationFailed) {
      // jose attaches the failed-claim name to e.claim (e.g. 'iss', 'aud')
      const claim = (e as JWTClaimValidationFailed).claim;
      if (claim === "iss") throw new AuthError("WRONG_ISSUER", AUTH_ERROR_MESSAGES.WRONG_ISSUER);
      if (claim === "aud") throw new AuthError("WRONG_AUDIENCE", AUTH_ERROR_MESSAGES.WRONG_AUDIENCE);
      throw new AuthError("MALFORMED_TOKEN", AUTH_ERROR_MESSAGES.MALFORMED_TOKEN);
    }
    if (e instanceof JWSSignatureVerificationFailed) {
      throw new AuthError("INVALID_TOKEN", AUTH_ERROR_MESSAGES.INVALID_TOKEN);
    }
    if (e instanceof JWSInvalid || e instanceof JWTInvalid) {
      throw new AuthError("MALFORMED_TOKEN", AUTH_ERROR_MESSAGES.MALFORMED_TOKEN);
    }
    if (e instanceof JOSEError) {
      throw new AuthError("INVALID_TOKEN", AUTH_ERROR_MESSAGES.INVALID_TOKEN);
    }
    // Unknown error — re-throw to preserve diagnostics
    throw e;
  }
}

export { resolveEnvClaim, type EnvClaim };
