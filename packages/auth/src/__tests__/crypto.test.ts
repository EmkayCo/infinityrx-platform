import { describe, it, expect } from "vitest";
import { signAccessToken, verifyTokenRaw, assertJwtSecret } from "../crypto.js";
import type { AccessClaims } from "../claims.js";
import { AuthError } from "../errors.js";

const SECRET = "a".repeat(64);
const OTHER_SECRET = "b".repeat(64);

function makeAccessClaims(overrides: Partial<AccessClaims> = {}): AccessClaims {
  const now = Math.floor(Date.now() / 1000);
  return {
    sub: "550e8400-e29b-41d4-a716-446655440000",
    tid: "550e8400-e29b-41d4-a716-446655440001",
    roles: ["platform_admin"],
    typ: "access" as const,
    iat: now,
    exp: now + 900,
    jti: "550e8400-e29b-41d4-a716-446655440002",
    iss: "infinityrx" as const,
    aud: "infinityrx-backend" as const,
    env: "production" as const,
    ...overrides,
  };
}

describe("assertJwtSecret", () => {
  it("accepts a sufficiently long secret in any env", () => {
    expect(() => assertJwtSecret(SECRET, "production")).not.toThrow();
  });
  it("rejects a short secret", () => {
    expect(() => assertJwtSecret("short", "development")).toThrow(/≥32 chars/);
  });
  it("rejects dev placeholder secrets in production", () => {
    expect(() => assertJwtSecret("changeme".padEnd(64, "x"), "production")).toThrow(/dev placeholder/);
  });
});

describe("HS256 mint + verify round-trip", () => {
  it("a token minted with secret A verifies with secret A", async () => {
    const claims = makeAccessClaims();
    const token = await signAccessToken(claims, SECRET);
    const verified = await verifyTokenRaw(token, SECRET, "production");
    expect(verified.sub).toBe(claims.sub);
    expect(verified.tid).toBe(claims.tid);
    expect(verified.env).toBe("production");
  });

  it("a token minted with secret A fails verification with secret B (INVALID_TOKEN)", async () => {
    const token = await signAccessToken(makeAccessClaims(), SECRET);
    await expect(verifyTokenRaw(token, OTHER_SECRET, "production")).rejects.toBeInstanceOf(AuthError);
    await expect(verifyTokenRaw(token, OTHER_SECRET, "production")).rejects.toMatchObject({ code: "INVALID_TOKEN" });
  });

  it("a token minted with env=development fails verification with env=production (WRONG_ENVIRONMENT)", async () => {
    const token = await signAccessToken(makeAccessClaims({ env: "development" }), SECRET);
    await expect(verifyTokenRaw(token, SECRET, "production")).rejects.toMatchObject({ code: "WRONG_ENVIRONMENT" });
  });

  it("an expired token fails with EXPIRED_TOKEN", async () => {
    const now = Math.floor(Date.now() / 1000);
    const token = await signAccessToken(makeAccessClaims({ iat: now - 2000, exp: now - 1000 }), SECRET);
    await expect(verifyTokenRaw(token, SECRET, "production")).rejects.toMatchObject({ code: "EXPIRED_TOKEN" });
  });
});
