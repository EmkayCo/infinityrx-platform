import { describe, it, expect } from "vitest";
import { mintDevJwt } from "../dev-jwt.js";
import { verifyAccessToken } from "../verify.js";
import { InMemoryRevocationRepo } from "../revocation-repo.js";

const SECRET = "d".repeat(64);

describe("mintDevJwt", () => {
  it("mints a valid token in development", async () => {
    const repo = new InMemoryRevocationRepo();
    const tokens = await mintDevJwt({ env: "development", secret: SECRET, repo });
    const claims = await verifyAccessToken({
      token: tokens.access_token, secret: SECRET, env: "development", repo,
    });
    expect(claims.env).toBe("development");
    expect(claims.roles).toContain("platform_admin");
  });

  it("refuses to mint in production", async () => {
    const repo = new InMemoryRevocationRepo();
    await expect(
      mintDevJwt({ env: "production", secret: SECRET, repo }),
    ).rejects.toThrow(/refused/i);
  });

  it("dev token rejected by prod backend (WRONG_ENVIRONMENT)", async () => {
    const repo = new InMemoryRevocationRepo();
    const tokens = await mintDevJwt({ env: "development", secret: SECRET, repo });
    // Prod backend verifies with env='production'; dev token has env='development'
    await expect(
      verifyAccessToken({ token: tokens.access_token, secret: SECRET, env: "production", repo }),
    ).rejects.toMatchObject({ code: "WRONG_ENVIRONMENT" });
  });
});
