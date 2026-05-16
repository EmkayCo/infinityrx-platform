import { describe, it, expect, vi, afterEach } from "vitest";

vi.mock("server-only", () => ({}));
// next/server is mocked so we can test the middleware logic without a real Next.js runtime.
vi.mock("next/server", () => {
  return {
    NextResponse: {
      next: vi.fn(({ request }: { request: { headers: Headers } }) => {
        return {
          headers: new Headers(request.headers),
          cookies: { get: vi.fn(), set: vi.fn() },
        };
      }),
    },
  };
});

import { QA_MODE_COOKIE, type QaMode } from "../qa/qa-mode-cookie.js";
import { QA_MODE_HEADER, applyQaModeMiddleware } from "../qa/qa-mode-middleware.js";

function makeReq(cookieValue?: string, url = "http://localhost/dashboard"): unknown {
  const cookies = new Map<string, string>();
  if (cookieValue !== undefined) cookies.set(QA_MODE_COOKIE, cookieValue);
  return {
    url,
    cookies: { get: (name: string) => (cookies.has(name) ? { value: cookies.get(name) } : undefined) },
    headers: new Headers(),
  };
}

// Satisfy unused import lint — QaMode is used implicitly via the type system
const _: QaMode = "real";
void _;

describe("applyQaModeMiddleware", () => {
  afterEach(() => {
    delete process.env["INFINITYRX_ENV"];
  });

  it("defaults to 'real' when cookie is absent and sets x-infinityrx-qa-mode header", () => {
    process.env["INFINITYRX_ENV"] = "development";
    const res = applyQaModeMiddleware(makeReq() as never);
    expect(res.headers.get(QA_MODE_HEADER)).toBe("real");
  });

  it("preserves existing 'stub' cookie value in non-production", () => {
    process.env["INFINITYRX_ENV"] = "development";
    const res = applyQaModeMiddleware(makeReq("stub") as never);
    expect(res.headers.get(QA_MODE_HEADER)).toBe("stub");
  });

  it("forces 'real' in production regardless of cookie value", () => {
    process.env["INFINITYRX_ENV"] = "production";
    const res = applyQaModeMiddleware(makeReq("stub") as never);
    expect(res.headers.get(QA_MODE_HEADER)).toBe("real");
  });

  it("sets Set-Cookie header when cookie is absent", () => {
    process.env["INFINITYRX_ENV"] = "development";
    const res = applyQaModeMiddleware(makeReq() as never);
    expect(res.headers.get("Set-Cookie")).toContain(QA_MODE_COOKIE);
  });
});
