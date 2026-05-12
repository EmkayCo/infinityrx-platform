// Config change-set admin API — wraps the Wave 27 SW3 endpoints
// on adjudication-engine's /admin/config/* surface.
//
// simulateChangeSet replays recent claims against the staged
// configuration effective at the change set's effective_date and
// reports outcome diffs (flipped PASS/REJECT, reject-code changes).
// Read-only.
//
// applyChangeSet transitions an approved change set to 'applied',
// atomically terminating predecessor parameter rows at the change
// set's scope. Write-effectful.
//
// Both require platform_admin role; the backend returns 403 for
// other roles and 422 for invalid change_set_id UUIDs.

import { apiPost } from "./api-client";
import { API_URLS } from "./constants";

const BASE = `${API_URLS.adjudicationEngine}/admin/config`;


export interface ClaimDiff {
  claim_id: string;
  current_outcome: "PASS" | "REJECT";
  future_outcome: "PASS" | "REJECT";
  current_reject_code: string | null;
  future_reject_code: string | null;
  current_amounts: Record<string, string>;
  future_amounts: Record<string, string>;
  // Wave 31 B2: per-key money delta (future - current), Decimal-as-str.
  amount_delta: Record<string, string>;
  flipped: boolean;
  // diff_keys may include 'outcome' / 'reject_code' / 'flags' / 'amounts'
  diff_keys: string[];
}


export interface SimulateChangeSetRequest {
  change_set_id: string;
  sample_size?: number;
  days_back?: number;
}


export interface SimulateChangeSetResponse {
  change_set_id: string;
  change_set_status: string;
  change_set_effective_date: string; // ISO date YYYY-MM-DD
  scenarios_evaluated: number;
  flipped_count: number;
  findings: ClaimDiff[];
}


export interface ApplyChangeSetRequest {
  change_set_id: string;
}


export interface ApplyChangeSetResponse {
  change_set_id: string;
  new_status: string;
  rows_terminated: number;
}


export async function simulateChangeSet(
  body: SimulateChangeSetRequest,
): Promise<SimulateChangeSetResponse> {
  return apiPost<SimulateChangeSetResponse>(
    `${BASE}/simulate-change-set`, body,
  );
}


export async function applyChangeSet(
  body: ApplyChangeSetRequest,
): Promise<ApplyChangeSetResponse> {
  return apiPost<ApplyChangeSetResponse>(
    `${BASE}/apply-change-set`, body,
  );
}
