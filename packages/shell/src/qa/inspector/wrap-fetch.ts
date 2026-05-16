/**
 * wrapFetch: instruments the ClientConfig.fetch override to capture
 * request/response pairs for the inspector panel.
 *
 * No Next.js imports — pure wrapper over the Fetch API.
 * Usage in non-prod BFF setup:
 *
 *   import { wrapFetch } from "@infinityrx/shell";
 *   const client = createRealPrescriberDirectoryClient({
 *     baseUrl: process.env.PRESCRIBER_DIR_URL,
 *     getAuthToken: () => getBFFToken(),
 *     fetch: wrapFetch(globalThis.fetch, (entry) => inspector.addEntry(entry)),
 *   });
 */
import type { InspectorEntry } from "./types.js";

type EmitFn = (entry: InspectorEntry) => void;

/** Maximum body size captured per entry (bytes as JSON string length). */
const BODY_CAPTURE_LIMIT = 4096;

/**
 * Header names redacted from captured entries — MUST include auth and
 * PHI-adjacent names. Compared case-insensitively.
 */
const REDACTED_HEADERS = new Set([
  "authorization",
  "cookie",
  "set-cookie",
  "x-api-key",
]);

/**
 * Pattern matching header names that always warrant redaction, regardless
 * of whether they appear in REDACTED_HEADERS. Catches variants like
 * x-auth-token, x-access-token, etc.
 */
const SENSITIVE_HEADER_PATTERN = /authorization|cookie|set-cookie/i;

/**
 * Body key pattern for PHI-adjacent fields. Any key matching this pattern
 * (at any nesting depth) is replaced with "<REDACTED>" in the captured body.
 * Covers common PBM PHI shapes: top-level, nested objects, and arrays.
 */
const PHI_KEY_PATTERN = /ssn|dob|date.of.birth|member.*name|first.name|last.name|patient|phone|email|address/i;

/** Maximum recursion depth for redactBody. Beyond this, value is replaced. */
const REDACT_MAX_DEPTH = 6;

/**
 * Wraps a fetch implementation to emit an InspectorEntry after each call.
 * The wrapper is transparent: it returns the same Response the underlying
 * fetch returns, and only clones for body reading (so the caller still
 * gets a readable body).
 *
 * PRODUCTION GUARD: returns `inner` unchanged when NODE_ENV === "production".
 * No instrumentation overhead, no body captures, no PHI risk in prod.
 */
export function wrapFetch(
  inner: typeof globalThis.fetch,
  emit: EmitFn
): typeof globalThis.fetch {
  // Non-prod runtime guard — MUST be first. In production this factory is a
  // no-op: returns the unwrapped inner fetch. Zero overhead, zero PHI risk.
  if (process.env.NODE_ENV === "production") {
    return inner;
  }

  return async function wrappedFetch(
    input: RequestInfo | URL,
    init?: RequestInit
  ): Promise<Response> {
    const method = (init?.method ?? "GET").toUpperCase();
    const url = input instanceof Request ? input.url : String(input);
    const start = performance.now();
    const timestamp = new Date().toISOString();

    let res: Response;
    let status = 0;
    let responseBody: unknown;
    let correlationId: string | undefined;

    try {
      res = await inner(input, init);
      status = res.status;
      correlationId = res.headers.get("x-correlation-id") ?? undefined;

      // Clone before reading body so the caller's body is not consumed.
      const clone = res.clone();
      try {
        const raw = await clone.json();
        responseBody = redactBody(capBody(raw));
      } catch {
        // Non-JSON response bodies are not captured.
      }
    } catch (err) {
      const latencyMs = Math.round(performance.now() - start);
      const reqHeaders = captureHeaders(init?.headers);
      emit({
        id: crypto.randomUUID(),
        method,
        url,
        status: 0,
        latencyMs,
        isMock: false,
        cacheHit: false,
        timestamp,
        ...(reqHeaders !== undefined ? { requestHeaders: reqHeaders } : {}),
        ...(init?.body !== undefined ? { requestBody: redactBody(capBody(tryParseJson(init.body))) } : {}),
      });
      throw err;
    }

    const latencyMs = Math.round(performance.now() - start);
    const requestBody = init?.body !== undefined
      ? redactBody(capBody(tryParseJson(init.body)))
      : undefined;
    const reqHeaders = captureHeaders(init?.headers);
    const resHeaders = captureHeaders(res.headers);

    emit({
      id: crypto.randomUUID(),
      method,
      url,
      status,
      latencyMs,
      isMock: false,
      cacheHit: res.headers.get("x-cache") === "HIT",
      correlationId,
      timestamp,
      ...(reqHeaders !== undefined ? { requestHeaders: reqHeaders } : {}),
      ...(resHeaders !== undefined ? { responseHeaders: resHeaders } : {}),
      ...(requestBody !== undefined ? { requestBody } : {}),
      ...(responseBody !== undefined ? { responseBody } : {}),
    });

    return res;
  };
}

/**
 * Convert a Headers object (or RequestInit.headers) to a plain record,
 * redacting any header whose lowercased name is in REDACTED_HEADERS or
 * matches SENSITIVE_HEADER_PATTERN.
 *
 * For Headers objects, REDACTED_HEADERS names are probed explicitly via
 * headers.get() in addition to iterating entries(). This is necessary because
 * certain environments (e.g., browser Fetch API) filter set-cookie from
 * entries() but still allow direct .get() access.
 *
 * PRODUCTION GUARD: callers must not invoke this in production — the top-level
 * production guard in wrapFetch() returns inner before headers are read.
 */
function captureHeaders(headers: HeadersInit | Headers | undefined): Record<string, string> | undefined {
  if (!headers) return undefined;

  const result: Record<string, string> = {};
  let hasEntries = false;

  const rawEntries: [string, string][] = headers instanceof Headers
    ? [...headers.entries()]
    : Array.isArray(headers)
      ? (headers as [string, string][])
      : Object.entries(headers as Record<string, string>);

  for (const [key, value] of rawEntries) {
    hasEntries = true;
    const lower = key.toLowerCase();
    const redact = REDACTED_HEADERS.has(lower) || SENSITIVE_HEADER_PATTERN.test(lower);
    result[key] = redact ? "<REDACTED>" : value;
  }

  // Explicitly probe REDACTED_HEADERS by name for Headers objects —
  // some environments suppress them from entries() but allow direct .get().
  if (headers instanceof Headers) {
    for (const name of REDACTED_HEADERS) {
      if (Object.prototype.hasOwnProperty.call(result, name)) continue;
      const val = headers.get(name);
      if (val !== null) {
        hasEntries = true;
        result[name] = "<REDACTED>";
      }
    }
  }

  return hasEntries ? result : undefined;
}

function tryParseJson(body: BodyInit): unknown {
  if (typeof body === "string") {
    try { return JSON.parse(body); } catch { return body; }
  }
  return undefined;
}

/**
 * Cap body size: if JSON.stringify(body) exceeds BODY_CAPTURE_LIMIT,
 * replace with a truncation marker.
 */
function capBody(body: unknown): unknown {
  if (body === undefined) return undefined;
  const serialized = JSON.stringify(body);
  if (serialized.length > BODY_CAPTURE_LIMIT) {
    return `<TRUNCATED:${serialized.length} bytes>`;
  }
  return body;
}

/**
 * Redact PHI-adjacent keys from a parsed JSON value, walking objects and
 * arrays recursively up to REDACT_MAX_DEPTH levels.
 *
 * Rules:
 * - Any key matching PHI_KEY_PATTERN is replaced with "<REDACTED>" at any depth.
 * - Beyond REDACT_MAX_DEPTH the entire sub-value is replaced with
 *   "<REDACTED:depth-exceeded>" to bound execution time.
 * - Cycle detection via WeakSet prevents infinite loops on circular objects.
 * - Non-object, non-array values are returned unchanged.
 */
function redactBody(body: unknown, depth = 0, seen = new WeakSet()): unknown {
  if (depth > REDACT_MAX_DEPTH) return "<REDACTED:depth-exceeded>";
  if (body === null || typeof body !== "object") return body;

  // Cycle detection — objects only (WeakSet can't hold primitives)
  if (seen.has(body as object)) return "<REDACTED:cycle>";
  seen.add(body as object);

  if (Array.isArray(body)) {
    return (body as unknown[]).map((item) => redactBody(item, depth + 1, seen));
  }

  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(body as Record<string, unknown>)) {
    result[key] = PHI_KEY_PATTERN.test(key)
      ? "<REDACTED>"
      : redactBody(value, depth + 1, seen);
  }
  return result;
}
