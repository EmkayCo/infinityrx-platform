import { auth } from "@shared/lib/auth";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

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

export default auth(function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Public paths — minimal layout, no auth required.
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    const headers = trustedRequestHeaders(request);
    headers.set("x-ifx-authenticated", "0");
    return NextResponse.next({ request: { headers } });
  }

  // API routes pass through — each route handles its own auth if needed.
  // Still strip the x-ifx-* trust namespace so API handlers can't be
  // fooled into trusting a client-supplied "I'm authenticated" header.
  if (pathname.startsWith("/api/")) {
    const headers = trustedRequestHeaders(request);
    return NextResponse.next({ request: { headers } });
  }

  // Protected route — verify session (auth() wrapper has already done the
  // JWT parse and placed the result on request.auth).
  const session = (request as unknown as { auth: { user?: unknown } | null }).auth;
  if (!session?.user) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Authenticated — forward the decision to the layout so it doesn't have
  // to re-verify the JWT itself.
  const headers = trustedRequestHeaders(request);
  headers.set("x-ifx-authenticated", "1");
  return NextResponse.next({ request: { headers } });
});

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|data/|.*\\.png|.*\\.svg|.*\\.ico|.*\\.json).*)",
  ],
};
