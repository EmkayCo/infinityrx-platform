/**
 * Wave B10 W4.6 — unit coverage for the env-gated test-mode bypass.
 *
 * The bypass is security-critical (issues platform_admin sessions on
 * token match), so it must hit the 100% security-path coverage bar in
 * .claude/rules/testing.md. The runtime probe via `next start` already
 * verified the happy path; this suite locks the rejection branches.
 *
 * The function is extracted as a top-level export in portal/shared/lib/auth.ts
 * specifically so we can call it here without spinning NextAuth's full
 * provider chain.
 */

import { afterEach, describe, expect, test, vi } from "vitest";
import { authorizeB10TestBypass } from "@shared/lib/auth-b10-test-bypass";

// The bypass module is NextAuth-free, so we only need to stub the
// bypass-specific env vars per test. AUTH_SECRET / NEXTAUTH_URL are
// unnecessary here.

afterEach(() => {
  vi.unstubAllEnvs();
});

const VALID_TOKEN = "1cda29872719b5ebb00ab7e9583d74f9a6435908388f5543b8c7b54bf8d182e5";

describe("authorizeB10TestBypass — positive path", () => {
  test("returns the B10 Test Admin user when env + token match", () => {
    vi.stubEnv("B10_TEST_MODE", "true");
    vi.stubEnv("B10_TEST_TOKEN", VALID_TOKEN);

    const before = Math.floor(Date.now() / 1000);
    const user = authorizeB10TestBypass({ token: VALID_TOKEN });
    const after = Math.floor(Date.now() / 1000);

    expect(user).not.toBeNull();
    expect(user).toMatchObject({
      id: "b10-test-admin-00000000-0000-0000-0000-000000000001",
      email: "b10-test@infinityrx.local",
      name: "B10 Test Admin",
      role: "platform_admin",
      tenant_id: "00000000-0000-0000-0000-000000000001",
      permissions: ["*"],
      mfa_enrolled: true,
      access_token: "b10-test-token",
      refresh_token: "b10-test-refresh",
    });
    // expires_at must be ~1 hour out (allow 2-second clock skew vs the
    // pre/post timestamps).
    expect(user!.expires_at).toBeGreaterThanOrEqual(before + 3600 - 2);
    expect(user!.expires_at).toBeLessThanOrEqual(after + 3600 + 2);
  });
});

describe("authorizeB10TestBypass — rejection paths", () => {
  test("refuses when B10_TEST_MODE is missing", () => {
    vi.stubEnv("B10_TEST_MODE", "");
    vi.stubEnv("B10_TEST_TOKEN", VALID_TOKEN);
    expect(authorizeB10TestBypass({ token: VALID_TOKEN })).toBeNull();
  });

  test("refuses when B10_TEST_MODE is anything other than 'true'", () => {
    vi.stubEnv("B10_TEST_MODE", "TRUE");
    vi.stubEnv("B10_TEST_TOKEN", VALID_TOKEN);
    expect(authorizeB10TestBypass({ token: VALID_TOKEN })).toBeNull();

    vi.stubEnv("B10_TEST_MODE", "1");
    expect(authorizeB10TestBypass({ token: VALID_TOKEN })).toBeNull();

    vi.stubEnv("B10_TEST_MODE", "yes");
    expect(authorizeB10TestBypass({ token: VALID_TOKEN })).toBeNull();
  });

  test("refuses when B10_TEST_TOKEN is missing", () => {
    vi.stubEnv("B10_TEST_MODE", "true");
    vi.stubEnv("B10_TEST_TOKEN", "");
    expect(authorizeB10TestBypass({ token: VALID_TOKEN })).toBeNull();
  });

  test("refuses when creds is null or undefined", () => {
    vi.stubEnv("B10_TEST_MODE", "true");
    vi.stubEnv("B10_TEST_TOKEN", VALID_TOKEN);
    expect(authorizeB10TestBypass(null)).toBeNull();
    expect(authorizeB10TestBypass(undefined)).toBeNull();
  });

  test("refuses when creds.token is missing", () => {
    vi.stubEnv("B10_TEST_MODE", "true");
    vi.stubEnv("B10_TEST_TOKEN", VALID_TOKEN);
    expect(authorizeB10TestBypass({})).toBeNull();
    expect(authorizeB10TestBypass({ token: undefined })).toBeNull();
    expect(authorizeB10TestBypass({ token: "" })).toBeNull();
  });

  test("refuses when token length differs from expected (early return)", () => {
    vi.stubEnv("B10_TEST_MODE", "true");
    vi.stubEnv("B10_TEST_TOKEN", VALID_TOKEN);
    // Length mismatch: short string
    expect(authorizeB10TestBypass({ token: "short" })).toBeNull();
    // Length mismatch: too long
    expect(authorizeB10TestBypass({ token: VALID_TOKEN + "X" })).toBeNull();
  });

  test("refuses when token has correct length but wrong content", () => {
    vi.stubEnv("B10_TEST_MODE", "true");
    vi.stubEnv("B10_TEST_TOKEN", VALID_TOKEN);
    // Same length, last char differs (forces full XOR fold)
    const wrong = VALID_TOKEN.slice(0, -1) + (VALID_TOKEN.endsWith("5") ? "6" : "5");
    expect(wrong.length).toBe(VALID_TOKEN.length);
    expect(authorizeB10TestBypass({ token: wrong })).toBeNull();

    // Same length, first char differs
    const wrong2 = (VALID_TOKEN.startsWith("1") ? "2" : "1") + VALID_TOKEN.slice(1);
    expect(wrong2.length).toBe(VALID_TOKEN.length);
    expect(authorizeB10TestBypass({ token: wrong2 })).toBeNull();
  });

  test("constant-time compare folds all byte diffs (middle-byte mismatch)", () => {
    vi.stubEnv("B10_TEST_MODE", "true");
    vi.stubEnv("B10_TEST_TOKEN", VALID_TOKEN);
    const mid = Math.floor(VALID_TOKEN.length / 2);
    const wrong = VALID_TOKEN.slice(0, mid) + "Z" + VALID_TOKEN.slice(mid + 1);
    expect(wrong.length).toBe(VALID_TOKEN.length);
    expect(authorizeB10TestBypass({ token: wrong })).toBeNull();
  });

  test("coerces non-string token to string before comparing", () => {
    vi.stubEnv("B10_TEST_MODE", "true");
    vi.stubEnv("B10_TEST_TOKEN", "12345");
    // Number that stringifies to the token still matches (defensive: this
    // is the documented coercion behavior in the function; users of this
    // bypass are expected to send strings, but a numeric form-post should
    // not crash the gate)
    expect(authorizeB10TestBypass({ token: 12345 })).not.toBeNull();
    // But a different number rejects
    expect(authorizeB10TestBypass({ token: 67890 })).toBeNull();
  });
});

describe("authorizeB10TestBypass — output shape invariants", () => {
  test("returned user always has platform_admin role and wildcard permissions", () => {
    vi.stubEnv("B10_TEST_MODE", "true");
    vi.stubEnv("B10_TEST_TOKEN", VALID_TOKEN);
    const u = authorizeB10TestBypass({ token: VALID_TOKEN });
    expect(u!.role).toBe("platform_admin");
    expect(u!.permissions).toEqual(["*"]);
  });

  test("returned user has the canonical B10 tenant_id", () => {
    vi.stubEnv("B10_TEST_MODE", "true");
    vi.stubEnv("B10_TEST_TOKEN", VALID_TOKEN);
    const u = authorizeB10TestBypass({ token: VALID_TOKEN });
    expect(u!.tenant_id).toBe("00000000-0000-0000-0000-000000000001");
  });

  test("session expires in exactly 1 hour (not 8h like the dev-bypass)", () => {
    vi.stubEnv("B10_TEST_MODE", "true");
    vi.stubEnv("B10_TEST_TOKEN", VALID_TOKEN);
    const now = Math.floor(Date.now() / 1000);
    const u = authorizeB10TestBypass({ token: VALID_TOKEN });
    const ttl = u!.expires_at - now;
    expect(ttl).toBeGreaterThanOrEqual(3598);
    expect(ttl).toBeLessThanOrEqual(3602);
  });
});
