/**
 * next-auth.d.ts -- type augmentation for Auth.js v5 (next-auth@5).
 *
 * Adds custom fields written by auth.ts jwt() and session() callbacks so
 * TypeScript knows the session shape and stops flagging access_token etc.
 * This is compile-time hygiene ONLY -- does not affect runtime behaviour.
 *
 * Runtime 403 root cause (WS3-C3 investigation):
 *   resolveSession() 403 INCOMPLETE_SESSION requires live DevTools inspection
 *   to determine which field (jwt/tenantId/userId) is undefined.
 *   Candidate B (refresh failure) ruled out: auth.ts preserves token.access_token
 *   on RefreshAccessTokenError. Most likely Candidate A (cookie overflow >4KB).
 *   BLOCKED-needs-login. See docs/audit/F0-plan-2026-05-21.md §WS3-C3.
 */
import "next-auth";

declare module "next-auth" {
  interface Session {
    access_token?: string;
    error?: string;
    mfa_required?: boolean;
    mfa_challenge_token?: string;
  }
  interface User {
    tenant_id?: string;
    permissions?: string[];
    role?: string;
    mfa_enrolled?: boolean;
    access_token?: string;
    refresh_token?: string;
    expires_at?: number;
    mfa_required?: boolean;
    mfa_challenge_token?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id?: string;
    role?: string;
    tenant_id?: string;
    permissions?: string[];
    mfa_enrolled?: boolean;
    access_token?: string;
    refresh_token?: string;
    expires_at?: number;
    error?: string;
    mfa_required?: boolean;
    mfa_challenge_token?: string;
  }
}
