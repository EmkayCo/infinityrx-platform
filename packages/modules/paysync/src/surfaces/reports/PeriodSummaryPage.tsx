// packages/modules/paysync/src/surfaces/reports/PeriodSummaryPage.tsx
// Read-only aggregate summary for a billing period.
// All monetary totals are Decimal strings from the server -- rendered via MoneyDisplay.
// All roles can view. Period selector is a prop (BFF/TanStack Query owns the fetch).

import type { ReactElement } from "react";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export interface PeriodSummaryPageProps {
  readonly periodLabel: string;
  readonly totalBilled: string | null;
  readonly totalPaid: string | null;
  readonly totalVariance: string | null;
  readonly totalAdjustments: string | null;
  readonly totalFees: string | null;
  readonly claimCount: number;
  readonly cycleCount: number;
  readonly invoiceCount: number;
  readonly paymentRunCount: number;
  readonly isLoading: boolean;
  readonly error: string | null;
}

export function PeriodSummaryPage({
  periodLabel,
  totalBilled,
  totalPaid,
  totalVariance,
  totalAdjustments,
  totalFees,
  claimCount,
  cycleCount,
  invoiceCount,
  paymentRunCount,
  isLoading,
  error,
}: PeriodSummaryPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="period-summary-page">
        <div data-testid="period-summary-loading" role="status" aria-label="Loading period summary">
          Loading period summary...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="period-summary-page">
        <div data-testid="period-summary-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="period-summary-page">
      <h1>Period Summary</h1>

      <dl>
        <dt>Period</dt>
        <dd data-testid="period-summary-period-label">{periodLabel}</dd>

        <dt>Total Billed</dt>
        <dd>
          {totalBilled !== null ? (
            <MoneyDisplay value={totalBilled} />
          ) : (
            <span aria-label="not available">-</span>
          )}
        </dd>

        <dt>Total Paid</dt>
        <dd>
          {totalPaid !== null ? (
            <MoneyDisplay value={totalPaid} />
          ) : (
            <span aria-label="not available">-</span>
          )}
        </dd>

        <dt>Variance</dt>
        <dd>
          {totalVariance !== null ? (
            <MoneyDisplay value={totalVariance} />
          ) : (
            <span aria-label="not available">-</span>
          )}
        </dd>

        <dt>Adjustments</dt>
        <dd>
          {totalAdjustments !== null ? (
            <MoneyDisplay value={totalAdjustments} />
          ) : (
            <span aria-label="not available">-</span>
          )}
        </dd>

        <dt>Fees</dt>
        <dd>
          {totalFees !== null ? (
            <MoneyDisplay value={totalFees} />
          ) : (
            <span aria-label="not available">-</span>
          )}
        </dd>

        <dt>Claims</dt>
        <dd data-testid="period-summary-claim-count">{claimCount}</dd>

        <dt>Cycles</dt>
        <dd data-testid="period-summary-cycle-count">{cycleCount}</dd>

        <dt>Invoices</dt>
        <dd data-testid="period-summary-invoice-count">{invoiceCount}</dd>

        <dt>Payment Runs</dt>
        <dd data-testid="period-summary-payment-run-count">{paymentRunCount}</dd>
      </dl>
    </div>
  );
}
