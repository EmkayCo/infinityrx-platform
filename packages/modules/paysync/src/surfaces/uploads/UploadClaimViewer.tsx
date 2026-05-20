// packages/modules/paysync/src/surfaces/uploads/UploadClaimViewer.tsx
// Paginated claim list scoped to a single upload_id.
// Receives pre-fetched claims via props (BFF/TanStack Query owns the fetch).
// Decimal money amounts rendered via MoneyDisplay (string passthrough, no float).

import type { ReactElement } from "react";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export interface UploadClaimViewerProps {
  readonly uploadId: string;
  readonly claims: ReadonlyArray<Record<string, unknown>>;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly total: number;
}

export function UploadClaimViewer({
  uploadId,
  claims,
  isLoading,
  error,
  total,
}: UploadClaimViewerProps): ReactElement {
  return (
    <div data-testid="upload-claim-viewer">
      <div data-testid="upload-scope-label" aria-label={`Claims for upload ${uploadId}`}>
        Upload: <code>{uploadId}</code>
      </div>

      {isLoading && (
        <div data-testid="claim-viewer-loading" role="status" aria-label="Loading claims">
          Loading claims...
        </div>
      )}

      {error && (
        <div data-testid="claim-viewer-error" role="alert">
          {error}
        </div>
      )}

      {!isLoading && !error && claims.length === 0 && (
        <div data-testid="claim-viewer-empty" role="status">
          No claims found for this upload.
        </div>
      )}

      {!isLoading && !error && claims.length > 0 && (
        <>
          <p data-testid="claim-viewer-total">
            Showing {claims.length} of {total} claims
          </p>
          <table aria-label="Parsed claims">
            <thead>
              <tr>
                <th scope="col">Claim ID</th>
                <th scope="col">NDC</th>
                <th scope="col">NPI</th>
                <th scope="col">Amount Billed</th>
                <th scope="col">Date of Service</th>
              </tr>
            </thead>
            <tbody>
              {claims.map((claim, i) => (
                <tr key={(claim["claim_id"] as string | undefined) ?? String(i)} data-testid="claim-row">
                  <td>{String(claim["claim_id"] ?? "-")}</td>
                  <td>{String(claim["ndc"] ?? "-")}</td>
                  <td>{String(claim["npi"] ?? "-")}</td>
                  <td>
                    {typeof claim["amount_billed"] === "string" ? (
                      <MoneyDisplay value={claim["amount_billed"]} />
                    ) : (
                      <span>-</span>
                    )}
                  </td>
                  <td>{String(claim["date_of_service"] ?? "-")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
