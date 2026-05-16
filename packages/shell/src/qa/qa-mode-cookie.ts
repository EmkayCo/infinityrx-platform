/**
 * QA mode toggle: persisted in a session cookie so it survives navigation
 * and multiple tabs in the same origin. This file contains only pure
 * parsing/constant logic — no Next.js imports — so it is testable in
 * happy-dom without a Next.js runtime.
 */

/** Cookie name for the QA mode preference. */
export const QA_MODE_COOKIE = "infinityrx-qa-mode" as const;

/** Valid QA mode values. */
export type QaMode = "real" | "stub";

/**
 * Parses the raw cookie string value into a valid QaMode.
 * Invalid or absent values fall back to "real" (safe production default).
 */
export function parseQaMode(raw: string | undefined): QaMode {
  if (raw === "real" || raw === "stub") return raw;
  return "real";
}

/**
 * Builds the Set-Cookie header value for the QA mode cookie.
 * HttpOnly: false — the toggle UI (client component) needs to read it.
 * SameSite=Lax, Secure (production): adequate for a non-sensitive preference.
 * Max-Age: 86400 (24h session preference lifetime).
 */
export function buildQaModeCookieValue(mode: QaMode, secure: boolean): string {
  const base = `${QA_MODE_COOKIE}=${mode}; Path=/; SameSite=Lax; Max-Age=86400`;
  return secure ? `${base}; Secure` : base;
}
