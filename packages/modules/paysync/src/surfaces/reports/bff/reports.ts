// packages/modules/paysync/src/surfaces/reports/bff/reports.ts
// Next.js BFF route handlers for the paysync reports surface.
// All reports are read-only -- no mutations. All roles can access.
// Cache-Control: no-store on period summary (financial aggregate data).

import type { CyclesClient, JournalClient } from "@infinityrx/contract";

export interface BffRequest {
  readonly headers: Record<string, string | undefined>;
  readonly searchParams?: URLSearchParams;
}

export interface BffResponse<T> {
  readonly data: T;
  readonly status: number;
  readonly headers: Record<string, string>;
}

// Minimal client interface for the reports BFF -- uses existing CyclesClient
// and JournalClient from contract. Period summary is a server-computed aggregate
// returned via CyclesClient; a dedicated backend endpoint is Plan F+ scope.
// TODO(Plan-F): wire to a dedicated /api/paysync/reports/period-summary backend
// endpoint once the billing module exposes it.

export interface ReportsClient {
  readonly cycles: CyclesClient;
  readonly journal: JournalClient;
  getPeriodSummary(periodLabel: string): Promise<PeriodSummaryData | null>;
}

export interface PeriodSummaryData {
  readonly period_label: string;
  readonly tenant_id: string;
  readonly total_claims: number;
  readonly total_billed: string | null;
  readonly total_paid: string | null;
  readonly total_adjustments: string | null;
  readonly total_fees: string | null;
  readonly total_variance: string | null;
  readonly cycle_count: number;
  readonly invoice_count: number;
  readonly payment_run_count: number;
  readonly generated_at: string;
}

/**
 * GET /api/paysync/reports/cycles
 * Proxies to CyclesClient.list -- all statuses, paginated.
 * Read-only: all roles. No Cache-Control override (BFF default applies).
 */
export async function handleListCycleReports(
  req: BffRequest,
  client: CyclesClient,
): Promise<BffResponse<Awaited<ReturnType<CyclesClient["list"]>>>> {
  const params = req.searchParams ?? new URLSearchParams();
  const cursorVal = params.get("cursor");
  const listReq: { limit?: number; cursor?: string } = {
    limit: params.has("limit") ? Number(params.get("limit")) : 50,
    ...(cursorVal !== null ? { cursor: cursorVal } : {}),
  };
  const data = await client.list(listReq);
  return { data, status: 200, headers: {} };
}

/**
 * GET /api/paysync/reports/journal-entries
 * Proxies to JournalClient.list with optional period_label / entry_type filters.
 * Read-only: all roles.
 */
export async function handleListJournalEntriesReport(
  req: BffRequest,
  client: JournalClient,
): Promise<BffResponse<Awaited<ReturnType<JournalClient["list"]>>>> {
  const params = req.searchParams ?? new URLSearchParams();
  const cursorVal = params.get("cursor");
  const listReq: { limit?: number; cursor?: string } = {
    limit: params.has("limit") ? Number(params.get("limit")) : 50,
    ...(cursorVal !== null ? { cursor: cursorVal } : {}),
  };
  const data = await client.list(listReq);
  return { data, status: 200, headers: {} };
}

/**
 * GET /api/paysync/reports/period-summary/[period_label]
 * Returns an aggregate PeriodSummary for the given period.
 * Cache-Control: no-store -- financial aggregate, must never serve stale.
 * Returns 404 when no data exists for the period.
 */
export async function handleGetPeriodSummary(
  periodLabel: string,
  _req: BffRequest,
  client: ReportsClient,
): Promise<BffResponse<PeriodSummaryData | null>> {
  const data = await client.getPeriodSummary(periodLabel);
  if (data === null) {
    return { data: null, status: 404, headers: {} };
  }
  return {
    data,
    status: 200,
    headers: { "Cache-Control": "no-store" },
  };
}
