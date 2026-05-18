// src/__mocks__/next-server.ts
// Stub for next/server used by vitest. Provides enough of NextResponse and
// NextRequest for the BFF route handler tests to run without a real Next.js install.
// Tests that need specific NextResponse behaviour mock it explicitly via vi.mock().

export class NextResponse extends Response {
  static json(body: unknown, init?: ResponseInit): NextResponse {
    const serialised = JSON.stringify(body);
    const res = new NextResponse(serialised, {
      ...init,
      headers: {
        "content-type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
    return res;
  }

  static next(_opts?: unknown): NextResponse {
    return new NextResponse(null, { status: 200 });
  }

  static redirect(url: string, status = 307): NextResponse {
    return new NextResponse(null, { status, headers: { location: url } });
  }
}

// NextRequest is the standard Request in happy-dom/node — augment with nextUrl.
export class NextRequest extends Request {
  readonly nextUrl: URL;

  constructor(input: string | URL | Request, init?: RequestInit) {
    super(input, init);
    this.nextUrl = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
  }
}
