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
 * Resolve the active NextAuth session and extract the bits a BFF route
 * handler needs. Returns either a usable session or a NextResponse the
 * caller should return directly.
 */
export async function resolveSession(): Promise<
  { ok: true; session: BffSession } | { ok: false; response: NextResponse }
> {
  const session = await auth();
  if (!session) {
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
 * Forward a request to an upstream backend with a timeout. Returns either
 * the parsed JSON or a "degraded state" marker so callers can distinguish
 * empty-from-backend vs backend-unreachable.
 */
export async function forwardJson<T>(
  url: string,
  session: BffSession,
  options: { method?: string; body?: unknown; timeoutMs?: number } = {}
): Promise<{ ok: true; data: T } | { ok: false; status: number; degraded: true }> {
  const { method = "GET", body, timeoutMs = 5000 } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch(url, {
      method,
      headers: {
        ...backendHeaders(session),
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
      cache: "no-store",
    });
    if (!resp.ok) {
      return { ok: false, status: resp.status, degraded: true };
    }
    const data = (await resp.json()) as T;
    return { ok: true, data };
  } catch {
    return { ok: false, status: 0, degraded: true };
  } finally {
    clearTimeout(timer);
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
