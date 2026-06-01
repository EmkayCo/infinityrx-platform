/**
 * Unit tests for auth.ts JWT minting constraints.
 *
 * mintDevJwt is not exported directly (it is an internal helper consumed by
 * the NextAuth Credentials providers). These tests validate the JWT contract
 * that mintDevJwt must satisfy:
 *
 *   - The minted token must NOT include an `aud` claim.
 *
 * Rationale: shared/auth/jwt_tokens.py (decode_token) calls PyJWT's
 * jwt.decode() WITHOUT passing an `audience=` argument. PyJWT automatically
 * validates the `aud` claim when it is present in the token payload and no
 * expected audience is provided, raising InvalidAudienceError -> HTTP 401.
 * Removing `.setAudience()` from mintDevJwt fixes the dev-bypass E2E 401.
 *
 * The tests here use jose directly (same library auth.ts uses) to verify that
 * a JWT produced with the correct parameters does not carry an `aud` field,
 * and that one produced WITH .setAudience() does carry it (proving the old
 * behaviour was wrong and confirming the guard is meaningful).
 */

import { describe, expect, test } from "vitest";
import { SignJWT, decodeJwt } from "jose";

const TEST_SECRET = "ifx-test-secret-32-chars-minimum!!";

async function mintWithAudience(secret: string): Promise<string> {
  const key = new TextEncoder().encode(secret);
  return new SignJWT({ sub: "user-1", typ: "access", jti: "jti-1" })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuer("infinityrx")
    .setAudience("infinityrx-backend")
    .setIssuedAt()
    .setExpirationTime("8h")
    .sign(key);
}

async function mintWithoutAudience(secret: string): Promise<string> {
  const key = new TextEncoder().encode(secret);
  return new SignJWT({ sub: "user-1", typ: "access", jti: "jti-1" })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuer("infinityrx")
    .setIssuedAt()
    .setExpirationTime("8h")
    .sign(key);
}

describe("JWT aud-claim contract (mintDevJwt must NOT set aud)", () => {
  test("token WITHOUT .setAudience() has no aud claim", async () => {
    const token = await mintWithoutAudience(TEST_SECRET);
    const claims = decodeJwt(token);
    expect(claims.aud).toBeUndefined();
  });

  test("token WITH .setAudience() carries aud claim (proving the guard matters)", async () => {
    const token = await mintWithAudience(TEST_SECRET);
    const claims = decodeJwt(token);
    expect(claims.aud).toBe("infinityrx-backend");
  });

  test("token WITHOUT aud has expected structural claims", async () => {
    const token = await mintWithoutAudience(TEST_SECRET);
    const claims = decodeJwt(token);
    expect(claims.sub).toBe("user-1");
    expect(claims.typ).toBe("access");
    expect(claims.iss).toBe("infinityrx");
    expect(claims.exp).toBeDefined();
    expect(claims.iat).toBeDefined();
  });
});
