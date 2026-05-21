import { auth } from "@shared/lib/auth";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import {
  QA_MODE_COOKIE,
  QA_MODE_HEADER,
  parseQaMode,
  buildQaModeCookieValue,
} from "@infinityrx/shell/middleware";

const PUBLIC_PATHS = ["/login", "/mfa", "/api/auth"];

function trustedRequestHeaders(request: NextRequest): Headers {
  // Start from the incoming request headers, then strip any client-supplied
  // header in our own trust namespace. Downstream Server Components read
  // `x-ifx-*` as authoritative, so we must guarantee the client can't forge it.
  const headers = new Headers(request.headers);
  for (const key of Array.from(headers.keys())) {
    if (key.toLowerCase().startsWith("x-ifx-")) {
      headers.delete(key);
    }
  }
  return headers;
}

/**
 * Resolve QA mode from the request cookie and inject it as a request header
 * so RSCs can read it via next/headers without re-parsing the cookie.
 * In production (INFINITYRX_ENV=production) the mode is forced to "real".
 *
 * Previously handled by portal/operator/middleware.ts (applyQaModeMiddleware).
 * middleware.ts was deleted because Next 16 errors when both middleware.ts and
 * proxy.ts exist ("Both middleware file and proxy file are detected").
 */
function applyQaMode(
  request: NextRequest,
  headers: Headers,
  response: NextResponse,
): void {
  const isProduction = process.env["INFINITYRX_ENV"] === "production";
  const rawCookie = request.cookies.get(QA_MODE_COOKIE)?.value;
  const resolved = isProduction ? "real" : parseQaMode(rawCookie);

  // Inject resolved value as a request-side header (read by RSCs via next/headers).
  headers.set(QA_MODE_HEADER, resolved);

  // Persist the cookie on the response if absent or if production is forcing a reset.
  if (!rawCookie || (isProduction && rawCookie !== "real")) {
    const isSecure = request.url.startsWith("https://");
    response.headers.set("Set-Cookie", buildQaModeCookieValue(resolved, isSecure));
  }
}

export default auth(function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Public paths -- minimal layout, no auth required.
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    const headers = trustedRequestHeaders(request);
    headers.set("x-ifx-authenticated", "0");
    const res = NextResponse.next({ request: { headers } });
    applyQaMode(request, headers, res);
    return NextResponse.next({ request: { headers } });
  }

  // API routes pass through -- each route handles its own auth if needed.
  // Still strip the x-ifx-* trust namespace so API handlers can't be
  // fooled into trusting a client-supplied "I'm authenticated" header.
  if (pathname.startsWith("/api/")) {
    const headers = trustedRequestHeaders(request);
    const res = NextResponse.next({ request: { headers } });
    applyQaMode(request, headers, res);
    return NextResponse.next({ request: { headers } });
  }

  // Protected route -- verify session (auth() wrapper has already done the
  // JWT parse and placed the result on request.auth).
  const session = (request as unknown as { auth: { user?: unknown } | null }).auth;
  if (!session?.user) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Authenticated -- forward the decision to the layout so it doesn't have
  // to re-verify the JWT itself.
  const headers = trustedRequestHeaders(request);
  headers.set("x-ifx-authenticated", "1");
  const res = NextResponse.next({ request: { headers } });
  applyQaMode(request, headers, res);
  return NextResponse.next({ request: { headers } });
});

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|data/|.*\\.png|.*\\.svg|.*\\.ico|.*\\.json).*)",
  ],
};