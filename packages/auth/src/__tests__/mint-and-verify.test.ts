import { describe, it, expect } from "vitest";
import { mintTokenPair } from "../mint.js";
import { verifyAccessToken, verifyRefreshToken } from "../verify.js";
import { InMemoryRevocationRepo } from "../revocation-repo.js";

const SECRET = "x".repeat(64);

function setup() {
  return {
    repo: new InMemoryRevocationRepo(),
    sub: "550e8400-e29b-41d4-a716-446655440000",
    tid: "550e8400-e29b-41d4-a716-446655440001",
    roles: ["platform_admin"] as string[],
  };
}

describe("mintTokenPair + verifyAccessToken happy path", () => {
  it("a freshly minted access token verifies cleanly", async () => {
    const { repo, sub, tid, roles } = setup();
    const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo });
    const claims = await verifyAccessToken({ token: tokens.access_token, secret: SECRET, env: "production", repo });
    expect(claims.sub).toBe(sub);
    expect(claims.tid).toBe(tid);
    expect(claims.roles).toEqual(roles);
    expect(claims.typ).toBe("access");
  });

  it("a freshly minted refresh token verifies cleanly", async () => {
    const { repo, sub, tid, roles } = setup();
    const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo });
    const claims = await verifyRefreshToken({ token: tokens.refresh_token, secret: SECRET, env: "production", repo });
    expect(claims.sub).toBe(sub);
    expect(claims.typ).toBe("refresh");
  });
});

describe("revocation paths", () => {
  it("a revoked access jti fails with REVOKED_TOKEN", async () => {
    const { repo, sub, tid, roles } = setup();
    const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo });
    // Extract jti by verifying first (trusted path)
    const claims = await verifyAccessToken({ token: tokens.access_token, secret: SECRET, env: "production", repo });
    await repo.revoke(claims.jti, "logout", 1000);
    await expect(
      verifyAccessToken({ token: tokens.access_token, secret: SECRET, env: "production", repo }),
    ).rejects.toMatchObject({ code: "REVOKED_TOKEN" });
  });

  it("tokens_valid_since cutoff rejects pre-reset access tokens (inclusive <=)", async () => {
    const { repo, sub, tid, roles } = setup();
    const now = Math.floor(Date.now() / 1000);
    const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo, now });
    // Cutoff at same second as iat — inclusive <= should reject
    await repo.setTokensValidSince(sub, now);
    await expect(
      verifyAccessToken({ token: tokens.access_token, secret: SECRET, env: "production", repo }),
    ).rejects.toMatchObject({ code: "REVOKED_TOKEN" });
  });

  it("post-reset mint clamps iat to cutoff + 1 (same-second login is accepted)", async () => {
    const { repo, sub, tid, roles } = setup();
    const now = Math.floor(Date.now() / 1000);
    await repo.setTokensValidSince(sub, now);
    const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo, now });
    // New token should verify because mint clamped iat to now+1 (strictly > cutoff)
    const claims = await verifyAccessToken({ token: tokens.access_token, secret: SECRET, env: "production", repo });
    expect(claims.iat).toBeGreaterThan(now);
  });
});

describe("typ enforcement", () => {
  it("an access token rejected at the refresh endpoint with WRONG_TOKEN_TYPE", async () => {
    const { repo, sub, tid, roles } = setup();
    const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo });
    await expect(
      verifyRefreshToken({ token: tokens.access_token, secret: SECRET, env: "production", repo }),
    ).rejects.toMatchObject({ code: "WRONG_TOKEN_TYPE" });
  });

  it("a refresh token rejected at protected route with WRONG_TOKEN_TYPE", async () => {
    const { repo, sub, tid, roles } = setup();
    const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo });
    await expect(
      verifyAccessToken({ token: tokens.refresh_token, secret: SECRET, env: "production", repo }),
    ).rejects.toMatchObject({ code: "WRONG_TOKEN_TYPE" });
  });
});

describe("InMemoryRevocationRepo consumeRefresh atomicity", () => {
  it("first consume returns true; second returns false (replay)", async () => {
    const { repo } = setup();
    const jti = crypto.randomUUID();
    expect(await repo.consumeRefresh(jti, "rotation", 1000)).toBe(true);
    expect(await repo.consumeRefresh(jti, "rotation", 1000)).toBe(false);
  });
});

// SD-1 §11 contract test #e — refresh token rejected after password reset.
describe("refresh after password reset", () => {
  it("a refresh token whose iat <= tokens_valid_since[sub] is rejected with REVOKED_TOKEN", async () => {
    const { repo, sub, tid, roles } = setup();
    const now = Math.floor(Date.now() / 1000);
    const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo, now });
    // Admin / password-reset sets cutoff at `now` (same second as token iat)
    await repo.setTokensValidSince(sub, now);
    await expect(
      verifyRefreshToken({ token: tokens.refresh_token, secret: SECRET, env: "production", repo }),
    ).rejects.toMatchObject({ code: "REVOKED_TOKEN" });
  });
});

// SD-1 §11 contract test #f — Redis-unreachable maps to REVOCATION_CHECK_FAILED.
class UnreachableRevocationRepo {
  async isRevoked(): Promise<boolean> { throw new Error("ECONNREFUSED"); }
  async consumeRefresh(): Promise<boolean> { throw new Error("ECONNREFUSED"); }
  async getTokensValidSince(): Promise<number | null> { throw new Error("ECONNREFUSED"); }
  async setTokensValidSince(): Promise<void> { throw new Error("ECONNREFUSED"); }
  async revoke(): Promise<void> { throw new Error("ECONNREFUSED"); }
}

describe("Redis unreachable", () => {
  it("verifyAccessToken returns REVOCATION_CHECK_FAILED when repo throws", async () => {
    const workingRepo = new InMemoryRevocationRepo();
    const sub = "550e8400-e29b-41d4-a716-446655440000";
    const tid = "550e8400-e29b-41d4-a716-446655440001";
    const tokens = await mintTokenPair({ sub, tid, roles: [], env: "production", secret: SECRET, repo: workingRepo });
    const brokenRepo = new UnreachableRevocationRepo();
    await expect(
      verifyAccessToken({ token: tokens.access_token, secret: SECRET, env: "production", repo: brokenRepo }),
    ).rejects.toMatchObject({ code: "REVOCATION_CHECK_FAILED" });
  });

  it("verifyRefreshToken returns REVOCATION_CHECK_FAILED when repo throws", async () => {
    const workingRepo = new InMemoryRevocationRepo();
    const sub = "550e8400-e29b-41d4-a716-446655440000";
    const tid = "550e8400-e29b-41d4-a716-446655440001";
    const tokens = await mintTokenPair({ sub, tid, roles: [], env: "production", secret: SECRET, repo: workingRepo });
    const brokenRepo = new UnreachableRevocationRepo();
    await expect(
      verifyRefreshToken({ token: tokens.refresh_token, secret: SECRET, env: "production", repo: brokenRepo }),
    ).rejects.toMatchObject({ code: "REVOCATION_CHECK_FAILED" });
  });
});

