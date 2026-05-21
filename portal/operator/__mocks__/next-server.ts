/**
 * Minimal stub for next/server in vitest/jsdom environment.
 *
 * qa-mode-middleware.ts imports NextResponse from next/server.
 * This stub provides enough surface area for the module to load
 * without error in unit tests. The middleware behavior itself is
 * tested via e2e/playwright.
 */
export class NextResponse {
  static next(_init?: unknown) {
    return new NextResponse();
  }
  static redirect(_url: string | URL) {
    return new NextResponse();
  }
  readonly headers = new Headers();
}