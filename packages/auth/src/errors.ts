/**
 * Auth error codes per SD-1 §8. Backend middleware + portal adapters use these.
 * Numeric values are NOT exposed — only the string codes.
 */
export type AuthErrorCode =
  | "MISSING_BEARER"
  | "INVALID_TOKEN"
  | "MALFORMED_TOKEN"
  | "WRONG_ISSUER"
  | "WRONG_AUDIENCE"
  | "WRONG_ENVIRONMENT"
  | "WRONG_TOKEN_TYPE"
  | "EXPIRED_TOKEN"
  | "REVOKED_TOKEN"
  | "REFRESH_REPLAY"
  | "REVOCATION_CHECK_FAILED";

export class AuthError extends Error {
  readonly code: AuthErrorCode;
  readonly correlationId?: string;

  constructor(code: AuthErrorCode, message: string, correlationId?: string) {
    super(message);
    this.name = "AuthError";
    this.code = code;
    // exactOptionalPropertyTypes: must not assign undefined to optional property.
    // Conditionally set only when a value is present.
    if (correlationId !== undefined) {
      this.correlationId = correlationId;
    }
  }
}

/** Stable per-code message. Backends MUST NOT vary these to avoid information leak. */
export const AUTH_ERROR_MESSAGES: Record<AuthErrorCode, string> = {
  MISSING_BEARER: "Authorization header missing or malformed",
  INVALID_TOKEN: "Token signature verification failed",
  MALFORMED_TOKEN: "Token is missing required claims",
  WRONG_ISSUER: "Token issuer is not infinityrx",
  WRONG_AUDIENCE: "Token audience is not infinityrx-backend",
  WRONG_ENVIRONMENT: "Token environment does not match this server's environment",
  WRONG_TOKEN_TYPE: "Token type is not valid for this route",
  EXPIRED_TOKEN: "Token expiration time has passed",
  REVOKED_TOKEN: "Token has been revoked",
  REFRESH_REPLAY: "Refresh token has already been consumed",
  REVOCATION_CHECK_FAILED: "Revocation repository is unreachable",
};
