import { describe, it, expect } from "vitest";
import { mintTokenPair } from "../mint.js";
import { performRefresh } from "../refresh-adapter.js";
import { InMemoryRevocationRepo } from "../revocation-repo.js";
import { readJtiUnsafe } from "../single-flight.js";

const SECRET = "r".repeat(64);

async function setup() {
  const repo = new InMemoryRevocationRepo();
  const sub = "550e8400-e29b-41d4-a716-446655440000";
  const tid = "550e8400-e29b-41d4-a716-446655440001";
  const roles = ["platform_admin"];
  const tokens = await mintTokenPair({ sub, tid, roles, env: "production", secret: SECRET, repo });
  const loadUserContext = async () => ({ tid, roles });
  return { repo, sub, tid, roles, tokens, loadUserContext };
}

describe("performRefresh", () => {
  it("a fresh refresh token rotates to a new pair", async () => {
    const { repo, tokens, loadUserContext } = await setup();
    const newPair = await performRefresh({
      refreshToken: tokens.refresh_token,
      secret: SECRET,
      env: "production",
      repo,
      loadUserContext,
    });
    expect(newPair.access_token).not.toBe(tokens.access_token);
    expect(newPair.refresh_token).not.toBe(tokens.refresh_token);
  });

  it("the same refresh token used twice yields REFRESH_REPLAY on the second call", async () => {
    const { repo, tokens, loadUserContext } = await setup();
    await performRefresh({
      refreshToken: tokens.refresh_token, secret: SECRET, env: "production", repo, loadUserContext,
    });
    await expect(
      performRefresh({
        refreshToken: tokens.refresh_token, secret: SECRET, env: "production", repo, loadUserContext,
      }),
    ).rejects.toMatchObject({ code: "REFRESH_REPLAY" });
  });

  it("two concurrent refresh attempts race: exactly one wins, the other gets REFRESH_REPLAY", async () => {
    const { repo, tokens, loadUserContext } = await setup();
    const a = performRefresh({
      refreshToken: tokens.refresh_token, secret: SECRET, env: "production", repo, loadUserContext,
    });
    const b = performRefresh({
      refreshToken: tokens.refresh_token, secret: SECRET, env: "production", repo, loadUserContext,
    });
    const results = await Promise.allSettled([a, b]);
    const fulfilled = results.filter((r) => r.status === "fulfilled");
    const rejected = results.filter((r) => r.status === "rejected");
    expect(fulfilled.length).toBe(1);
    expect(rejected.length).toBe(1);
    expect((rejected[0] as PromiseRejectedResult).reason).toMatchObject({ code: "REFRESH_REPLAY" });
  });

  it("a refresh token revoked via logout yields REVOKED_TOKEN, not REFRESH_REPLAY", async () => {
    const { repo, tokens, loadUserContext } = await setup();
    const jti = readJtiUnsafe(tokens.refresh_token);
    await repo.revoke(jti, "logout", 1000);
    await expect(
      performRefresh({
        refreshToken: tokens.refresh_token, secret: SECRET, env: "production", repo, loadUserContext,
      }),
    ).rejects.toMatchObject({ code: "REVOKED_TOKEN" });
  });
});
