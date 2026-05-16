// Stub for next/server in vitest context.
// Tests that use next/server mock it explicitly via vi.mock().
export class NextResponse {
  static next(_opts?: unknown) {
    return { headers: new Headers(), cookies: {} };
  }
  static redirect(_url: string) {
    return { headers: new Headers() };
  }
}
export type NextRequest = {
  url: string;
  cookies: { get: (name: string) => { value: string } | undefined };
  headers: Headers;
};
