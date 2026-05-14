/**
 * B11 w2 — BFF (backend-for-frontend) shared helper.
 *
 * Per codex spec consult R1 Q1: dashboard data orchestration belongs in
 * Next.js route handlers, NOT browser-side direct backend calls. This
 * module centralizes the session→headers conversion so every route
 * handler gets:
 *   - 401 when there is no session
 *   - 403 when the session's tenant claim is missing
 *   - x-tenant-id derived from JWT, never from the browser
 *   - Authorization: Bearer <jwt> attached automatically
 *
 * Failure-mode handling follows codex's enumerated list for w2:
 *   - Never trust browser-supplied x-tenant-id (we derive from session)
 *   - Default Cache-Control: no-store on PHI responses
 *   - Upstream errors normalized — never leak raw backend bodies
 *   - Distinguish empty data from unavailable data in the response shape
 */
import { NextResponse } from "next/server";
import { auth } from "@shared/lib/auth";

export interface BffSession {
  jwt: string;
  tenantId: string;
  userId: string;
  roles: string[];
}

/**
 * Decode a HS256 JWT body without verification — for cross-claim checks
 * only (e.g., confirming session.tenant_id matches JWT.tid). The token
 * was already minted by us; we re-extract the tid claim to detect
 * session-vs-token drift where a stale session could carry a tenant
 * the JWT was never signed for.
 *
 * NOT a security boundary — backends still verify the JWT signature
 * with JWT_SECRET. This is a portal-side defense-in-depth check.
 */
function readJwtClaim(jwt: string, claim: string): string | null {
  try {
    const parts = jwt.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(
      Buffer.from(parts[1], "base64url").toString("utf-8")
    ) as Record<string, unknown>;
    const v = payload[claim];
    return typeof v === "string" ? v : null;
  } catch {
    return null;
  }
}

function logBff(event: string, fields: Record<string, unknown>): void {
  // Structured single-line log so observability platforms can ingest
  // BFF telemetry without sampling free-form messages. Keep PHI out.
  // eslint-disable-next-line no-console
  console.log(JSON.stringify({ svc: "bff", event, ...fields }));
}

/**
 * Resolve the active NextAuth session and extract the bits a BFF route
 * handler needs. Returns either a usable session or a NextResponse the
 * caller should return directly.
 *
 * Defense-in-depth: verifies session.tenant_id matches JWT.tid claim
 * before forwarding. Mismatch → 403, logged with the discrepancy. Stops
 * a stale/malformed session from telling the BFF to inject a tenant
 * header the JWT doesn't authorize.
 */
export async function resolveSession(): Promise<
  { ok: true; session: BffSession } | { ok: false; response: NextResponse }
> {
  const session = await auth();
  if (!session) {
    logBff("session_missing", {});
    return {
      ok: false,
      response: NextResponse.json(
        { error: { code: "UNAUTHENTICATED", message: "No active session" } },
        { status: 401, headers: { "Cache-Control": "no-store" } }
      ),
    };
  }
  // The auth.ts session callback writes these onto `session.user` + `session.access_token`.
  const u = (session.user ?? {}) as Record<string, unknown>;
  const jwt = (session as unknown as { access_token?: string }).access_token;
  const tenantId = u["tenant_id"] as string | undefined;
  const userId = u["id"] as string | undefined;
  const roles = (u["permissions"] as string[] | undefined) ?? [];

  if (!jwt || !tenantId || !userId) {
    logBff("session_incomplete", {
      has_jwt: !!jwt,
      has_tenant_id: !!tenantId,
      has_user_id: !!userId,
    });
    return {
      ok: false,
      response: NextResponse.json(
        {
          error: {
            code: "INCOMPLETE_SESSION",
            message: "Session is missing required claims (jwt/tenant_id/user_id)",
          },
        },
        { status: 403, headers: { "Cache-Control": "no-store" } }
      ),
    };
  }
  // Defense-in-depth: session.tenant_id MUST match JWT.tid. If they
  // disagree, the session was tampered with or refresh-token rotation
  // crossed tenants. Either way: 403 immediately and log.
  const jwtTid = readJwtClaim(jwt, "tid");
  if (jwtTid && jwtTid !== tenantId) {
    logBff("session_jwt_tenant_mismatch", {
      session_tenant_id: tenantId,
      jwt_tid: jwtTid,
      user_id: userId,
    });
    return {
      ok: false,
      response: NextResponse.json(
        {
          error: {
            code: "TENANT_CLAIM_MISMATCH",
            message: "Session tenant_id does not match JWT tid claim",
          },
        },
        { status: 403, headers: { "Cache-Control": "no-store" } }
      ),
    };
  }
  return { ok: true, session: { jwt, tenantId, userId, roles } };
}

/**
 * Standard headers to attach to every upstream backend call from a BFF route.
 * Caller may add Content-Type for POST/PUT/PATCH.
 */
export function backendHeaders(session: BffSession): Record<string, string> {
  return {
    Authorization: `Bearer ${session.jwt}`,
    "x-tenant-id": session.tenantId,
  };
}

/**
 * PHI-safe NextResponse.json helper — always Cache-Control: no-store.
 * Use for any response containing PHI (member data, claim data, audit data).
 */
export function phiJson(
  body: unknown,
  init: ResponseInit = {}
): NextResponse {
  return NextResponse.json(body, {
    ...init,
    headers: {
      "Cache-Control": "no-store",
      ...(init.headers ?? {}),
    },
  });
}

/**
 * Typed failure reasons surfaced by forwardJson. Lets callers
 * distinguish a backend that's down (TIMEOUT/NETWORK) from a backend
 * that responded with a non-2xx status (UPSTREAM_ERROR) from a backend
 * that returned a body the client couldn't parse (PARSE_ERROR).
 *
 * Pre-w2.x this collapsed everything into `{ degraded: true }` which
 * hid backend contract regressions as data-unavailability. Codex
 * adversarial R1 flagged it as a BLOCK.
 */
export type ForwardFailure =
  | { reason: "TIMEOUT"; status: 0; url: string }
  | { reason: "NETWORK"; status: 0; url: string; error: string }
  | { reason: "UPSTREAM_ERROR"; status: number; url: string }
  | { reason: "PARSE_ERROR"; status: number; url: string; error: string };

/**
 * Forward a request to an upstream backend with a typed failure envelope.
 *
 * Recommended `timeoutMs`:
 *   - 3000 (3s)  read/dashboard convenience calls
 *   - 8000 (8s)  write paths (claim submit, audit-bearing operations)
 *   - 15000      long-running upstreams (avoid in user-facing paths)
 *
 * Default is 5000. Callers SHOULD set it explicitly when the call is
 * audit-bearing or PHI-write.
 */
export async function forwardJson<T>(
  url: string,
  session: BffSession,
  options: { method?: string; body?: unknown; timeoutMs?: number } = {}
): Promise<{ ok: true; data: T } | { ok: false; failure: ForwardFailure }> {
  const { method = "GET", body, timeoutMs = 5000 } = options;
  const controller = new AbortController();
  let didTimeout = false;
  const timer = setTimeout(() => {
    didTimeout = true;
    controller.abort();
  }, timeoutMs);
  let resp: Response;
  try {
    resp = await fetch(url, {
      method,
      headers: {
        ...backendHeaders(session),
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
      cache: "no-store",
    });
  } catch (err) {
    clearTimeout(timer);
    const failure: ForwardFailure = didTimeout
      ? { reason: "TIMEOUT", status: 0, url }
      : { reason: "NETWORK", status: 0, url, error: String(err) };
    logBff("forward_failed", { ...failure, method, tenant: session.tenantId });
    return { ok: false, failure };
  }
  clearTimeout(timer);
  if (!resp.ok) {
    const failure: ForwardFailure = {
      reason: "UPSTREAM_ERROR",
      status: resp.status,
      url,
    };
    logBff("forward_upstream_error", { ...failure, method, tenant: session.tenantId });
    return { ok: false, failure };
  }
  try {
    const data = (await resp.json()) as T;
    return { ok: true, data };
  } catch (err) {
    const failure: ForwardFailure = {
      reason: "PARSE_ERROR",
      status: resp.status,
      url,
      error: String(err),
    };
    logBff("forward_parse_error", {
      reason: failure.reason,
      status: failure.status,
      url: failure.url,
      method,
      tenant: session.tenantId,
    });
    return { ok: false, failure };
  }
}

/**
 * Backend module ports — used by BFF routes to know where to forward.
 * Mirror of modules/.../main.py port assignments. Single source of truth
 * for portal→backend addressing.
 */
export const BACKENDS = {
  corePlatform: "http://localhost:8000",
  billing: "http://localhost:8001",
  paymentProcessing: "http://localhost:8002",
  reclaimrx: "http://localhost:8003",
  reporting: "http://localhost:8004",
  ediCompliance: "http://localhost:8005",
  medicalClaims: "http://localhost:8006",
  aiNlp: "http://localhost:8007",
  dataiq: "http://localhost:8008",
  pharmacyDirectory: "http://localhost:8009",
  prescriberDirectory: "http://localhost:8010",
  drugDatabase: "http://localhost:8011",
  memberManagement: "http://localhost:8012",
  adjudicationEngine: "http://localhost:8013",
} as const;
