/**
 * Decoded identity surface exposed to RSCs.
 * Mirrors SD-1 §2 access-token claims (sub, tid, roles).
 * access_token and refresh_token are NOT included — they remain
 * inside the encrypted next-auth session payload, server-readable only.
 */
export interface UserIdentity {
  /** user_id (UUID string) — maps to JWT claim `sub` */
  readonly sub: string;
  /** tenant_id (UUID string) — maps to JWT claim `tid` */
  readonly tid: string;
  /** authorization roles — maps to JWT claim `roles` */
  readonly roles: readonly string[];
  /** whether MFA enrollment is complete */
  readonly mfaEnrolled: boolean;
}

/** Sentinel returned when no authenticated session exists. */
export type SessionUser = UserIdentity | null;
