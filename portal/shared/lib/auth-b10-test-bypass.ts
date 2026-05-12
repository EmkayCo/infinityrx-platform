/**
 * Wave B10 W4.6 — env-gated test-mode bypass for `next start` runtime probe.
 *
 * Extracted into its own module (separate from auth.ts) so it can be
 * unit-tested without loading NextAuth at module-init time — vitest cannot
 * resolve `next/server` through the NextAuth import chain in this monorepo.
 *
 * Hard-refuses unless ALL of:
 *   - process.env.B10_TEST_MODE === "true"
 *   - process.env.B10_TEST_TOKEN is non-empty
 *   - creds.token matches B10_TEST_TOKEN via constant-time byte compare
 *
 * security.md compliance: constant-time comparison on all secret/token
 * validation. The compare folds per-byte XOR diffs into a single accumulator
 * so the loop's wall-clock time depends on length only, not byte position
 * of the first mismatch.
 *
 * Returns the B10 Test Admin user object on match, null on any refusal.
 *
 * DO NOT EXPAND the user object's `permissions` beyond `["*"]` without
 * matching the threat model — the bypass user IS platform_admin, full stop.
 * Tighter scoping is not the goal here; gating is.
 */

export interface B10TestBypassUser {
  id: string;
  email: string;
  name: string;
  role: string;
  tenant_id: string;
  permissions: string[];
  mfa_enrolled: boolean;
  access_token: string;
  refresh_token: string;
  expires_at: number;
}

export function authorizeB10TestBypass(
  creds: { token?: unknown } | undefined | null
): B10TestBypassUser | null {
  if (process.env.B10_TEST_MODE !== "true") return null;
  const expected = process.env.B10_TEST_TOKEN;
  if (!expected || !creds?.token) return null;
  const a = Buffer.from(String(creds.token));
  const b = Buffer.from(expected);
  if (a.length !== b.length) return null;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  if (diff !== 0) return null;
  const now = Math.floor(Date.now() / 1000);
  return {
    id: "b10-test-admin-00000000-0000-0000-0000-000000000001",
    email: "b10-test@infinityrx.local",
    name: "B10 Test Admin",
    role: "platform_admin",
    tenant_id: "00000000-0000-0000-0000-000000000001",
    permissions: ["*"],
    mfa_enrolled: true,
    access_token: "b10-test-token",
    refresh_token: "b10-test-refresh",
    expires_at: now + 60 * 60, // 1 hour — test runs are short
  };
}
