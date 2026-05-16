import { applyQaModeMiddleware, SHELL_MIDDLEWARE_MATCHER } from "@infinityrx/shell/middleware";
import type { NextRequest } from "next/server";

export function middleware(req: NextRequest) {
  // Apply shell-level cross-cutting middleware (QA mode cookie propagation).
  // Additional middleware (auth, rate-limiting) compose here as the portal grows.
  return applyQaModeMiddleware(req);
}

export const config = {
  matcher: SHELL_MIDDLEWARE_MATCHER,
};
