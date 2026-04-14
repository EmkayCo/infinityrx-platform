/**
 * Mock data layer — intercepts API calls when NEXT_PUBLIC_USE_MOCK_DATA=true.
 *
 * Usage: imported by api-client.ts. Do not import directly in application code.
 */

import { findHandler } from "./handlers";

export function isMockEnabled(): boolean {
  return process.env.NEXT_PUBLIC_USE_MOCK_DATA === "true";
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function randDelay(): number {
  // 80–250ms to feel realistic; use a deterministic-ish spread
  return 80 + Math.floor(Math.random() * 170);
}

/**
 * Extract just the pathname from a potentially full URL, stripping host and query string.
 * e.g. "http://localhost:8001/billing/v1/cycles?page=1" → "/billing/v1/cycles"
 */
function extractPathname(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.pathname;
  } catch {
    // Not a full URL — treat as relative path
    return url.split("?")[0];
  }
}

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

/**
 * Route an API call through the mock handler registry.
 * If no handler matches, returns a plausible empty shell and logs a warning.
 */
export async function mockResponse<T>(
  method: HttpMethod,
  url: string,
  body?: unknown
): Promise<T> {
  await sleep(randDelay());

  const pathname = extractPathname(url);
  const entry = findHandler(method, pathname);

  if (!entry) {
    console.warn(`[mock] unmatched: ${method} ${pathname}`);
    // Return a plausible shell for list-shaped vs detail endpoints
    const isListPath =
      !pathname.match(/\/[0-9a-f-]{32,}$/) && !pathname.match(/\/[A-Z0-9-]{8,}$/i);
    return (isListPath ? { items: [], total: 0 } : {}) as T;
  }

  const result = await Promise.resolve(entry.handler(entry.match, body));
  return result as T;
}
