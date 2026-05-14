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

  // B11 w2.x routing — branches on body.claim_type:
  //   pharmacy + compound → adjudication-engine /claims/adjudicate
  //                          (these need clinical adjudication first; the
  //                           billing ledger is created by adjudication's
  //                           downstream event consumers, not the portal)
  //   medical            → medical-claims /api/v1/medical-claims/claims
  //                          (medical claims have their own validation
  //                           and crosswalk pipeline)
  //   unknown / missing  → 400 with explicit code so the operator sees
  //                          which field was wrong — better than
  //                          silently misrouting to a ledger that won't
  //                          reflect a clinically-processed claim
  //
  // Codex adversarial R1 BLOCKED the prior "everything → billing/claims"
  // shape because the system-of-record consequence of misrouting is real:
  // an audit later sees a ledger artifact rather than a clinically/
  // adjudicatively processed claim.
  const claimType = (body && typeof body === "object"
    ? ((body as Record<string, unknown>).claim_type as string | undefined)
    : undefined
  )?.toLowerCase();

  let upstreamUrl: string;
  switch (claimType) {
    case "pharmacy":
    case "compound":
      upstreamUrl = `${BACKENDS.adjudicationEngine}/claims/adjudicate`;
      break;
    case "medical":
      upstreamUrl = `${BACKENDS.medicalClaims}/api/v1/medical-claims/claims`;
      break;
    default:
      return phiJson(
        {
          error: {
            code: "INVALID_CLAIM_TYPE",
            message:
              "body.claim_type must be one of: pharmacy, medical, compound",
            received: claimType ?? null,
          },
        },
        { status: 400 }
      );
  }

  const result = await forwardJson<unknown>(upstreamUrl, session, {
    method: "POST",
    body,
    timeoutMs: 8000,
  });

  if (!result.ok) {
    const f = result.failure;
    return phiJson(
      {
        error: {
          code: f.reason,
          message: `billing/claims upstream ${f.reason.toLowerCase().replace("_", " ")}`,
          upstream_status: f.status,
        },
      },
      // Propagate the upstream 4xx (so the operator sees real validation
      // errors), 502 for backend down (TIMEOUT/NETWORK), 500 for upstream
      // 5xx, 500 for parse errors (backend contract drift).
      {
        status:
          f.reason === "UPSTREAM_ERROR" && f.status >= 400 && f.status < 500
            ? f.status
            : f.reason === "TIMEOUT" || f.reason === "NETWORK"
              ? 502
              : 500,
      }
    );
  }
  return phiJson(result.data);
}
