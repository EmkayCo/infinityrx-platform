import { describe, it, expect, vi, afterEach } from "vitest";
import {
  OPERATOR_USER_ID,
  APPROVER_USER_ID,
  AUDITOR_USER_ID,
  fetchTestAuthToken,
} from "../auth-helpers.js";

describe("auth-helpers constants", () => {
  it("OPERATOR_USER_ID matches alice fixture", () => {
    expect(OPERATOR_USER_ID).toBe("usr-00000000-0000-0000-0000-000000000001");
  });

  it("APPROVER_USER_ID matches bob fixture", () => {
    expect(APPROVER_USER_ID).toBe("usr-00000000-0000-0000-0000-000000000002");
  });

  it("AUDITOR_USER_ID matches carol fixture", () => {
    expect(AUDITOR_USER_ID).toBe("usr-00000000-0000-0000-0000-000000000003");
  });
});

describe("fetchTestAuthToken", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs to /api/v1/core/test-auth/token and returns the token", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ access_token: "jwt.header.payload", token_type: "bearer" }),
    });
    vi.stubGlobal("fetch", mockFetch);

    const token = await fetchTestAuthToken({
      baseURL: "http://localhost:8000",
      userId: OPERATOR_USER_ID,
    });

    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/v1/core/test-auth/token");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body.user_id).toBe(OPERATOR_USER_ID);
    expect(token).toBe("jwt.header.payload");
  });

  it("throws on non-2xx response", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: "test-auth blocked in production" }),
    });
    vi.stubGlobal("fetch", mockFetch);

    await expect(
      fetchTestAuthToken({ baseURL: "http://localhost:8000", userId: OPERATOR_USER_ID })
    ).rejects.toThrow("403");
  });
});
