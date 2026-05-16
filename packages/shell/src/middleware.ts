/**
 * Shell middleware export.
 *
 * portal/operator/middleware.ts imports this to compose shell middleware
 * into the portal's Next.js middleware chain.
 *
 * Provides:
 *  - applyQaModeMiddleware: reads qa_mode cookie; propagates x-infinityrx-qa-mode header
 *  - SHELL_MIDDLEWARE_MATCHER: recommended route matcher (all routes except static assets)
 */
export { applyQaModeMiddleware, QA_MODE_HEADER } from "./qa/qa-mode-middleware.js";
export { QA_MODE_COOKIE, parseQaMode, type QaMode } from "./qa/qa-mode-cookie.js";

/**
 * Recommended Next.js middleware matcher for the shell middleware.
 * Excludes _next static, _next image, favicon.ico, and public folder.
 */
export const SHELL_MIDDLEWARE_MATCHER = [
  "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
] as const;
