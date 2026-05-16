import "server-only";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import {
  QA_MODE_COOKIE,
  parseQaMode,
  buildQaModeCookieValue,
  type QaMode,
} from "./qa-mode-cookie.js";

/** Request header name propagated by middleware to RSCs. */
export const QA_MODE_HEADER = "x-infinityrx-qa-mode" as const;

/**
 * QA mode middleware handler.
 *
 * Called from the portal's Next.js middleware.ts.
 * Reads the qa_mode cookie from the request; if absent, defaults to "real"
 * and sets the cookie on the response. Always propagates the resolved value
 * as x-infinityrx-qa-mode header for RSC consumers (next/headers).
 *
 * In production (INFINITYRX_ENV=production), qa_mode is forced to "real"
 * regardless of the cookie value — the toggle is a dev/staging tool only.
 */
export function applyQaModeMiddleware(req: NextRequest): NextResponse {
  const isProduction = process.env["INFINITYRX_ENV"] === "production";
  const rawCookie = req.cookies.get(QA_MODE_COOKIE)?.value;
  const resolved: QaMode = isProduction ? "real" : parseQaMode(rawCookie);

  const res = NextResponse.next({
    request: {
      headers: new Headers({
        ...Object.fromEntries(req.headers.entries()),
        [QA_MODE_HEADER]: resolved,
      }),
    },
  });

  // Set the cookie on the response if it was absent or if production is
  // forcing a reset to "real".
  const isSecure = req.url.startsWith("https://");
  if (!rawCookie || (isProduction && rawCookie !== "real")) {
    res.headers.set("Set-Cookie", buildQaModeCookieValue(resolved, isSecure));
  }

  return res;
}
