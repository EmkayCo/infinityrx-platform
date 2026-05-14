/**
 * B11 w2 — BFF: POST /api/v1/claims/manual
 *
 * Closes B11 F-005 for the manual-claim path (pre-w2 returned 404).
 * Forwards the form payload from
 * portal/operator/app/claims/manual/page.tsx to the medical-claims
 * backend with the session's JWT + tenant-id injected server-side.
 *
 * Acceptance gate: b11-w0_1-auth-write-isolation.spec.ts F-W03 must
 * flip from HTTP 404 to a 2xx response (or a 4xx with a structured
 * error if the backend rejects the payload shape).
 */
import { NextRequest } from "next/server";
import { resolveSession, phiJson, forwardJson, BACKENDS } from "@/lib/bff";

export async function POST(req: NextRequest) {
  const r = await resolveSession();
  if (!r.ok) return r.response;
  const { session } = r;

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return phiJson(
      { error: { code: "INVALID_JSON", message: "Body is not valid JSON" } },
      { status: 400 }
    );
  }

  // B11 w2 routing decision: forward to billing/claims (the ledger-entry
  // endpoint). Manual claim entry is fundamentally creating a ledger row
  // that downstream consumers (adjudication-engine, medical-claims for
  // medical-type, reclaimrx for FWA scan) react to. A future slice should
  // split on body.claim_type: "pharmacy" → adjudication, "medical" →
  // medical-claims/claims, "compound" → adjudication. For w2 acceptance
  // gate purposes (b11-w0_1 F-W03), billing/claims is the most defensible
  // single target — every claim type ultimately needs a billing record.
  const result = await forwardJson<unknown>(
    `${BACKENDS.billing}/api/v1/billing/claims`,
    session,
    { method: "POST", body, timeoutMs: 8000 }
  );

  if (!result.ok) {
    return phiJson(
      {
        error: {
          code: "UPSTREAM_UNAVAILABLE",
          message: "Medical claims service rejected or did not respond",
          upstream_status: result.status,
        },
      },
      { status: result.status >= 400 ? result.status : 502 }
    );
  }
  return phiJson(result.data);
}
