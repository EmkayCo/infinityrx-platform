// packages/modules/paysync/src/surfaces/uploads/UploadsListPage.tsx
// List view for paysync uploads. Shows status badge, filename, money amount,
// sha256-dedup banner when a 409 conflict is surfaced from the dropzone.
// Receives pre-fetched data via props (BFF/TanStack Query owns the fetch).

import type { ReactElement } from "react";
import type { Upload, UploadStatus } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export interface DedupBanner {
  readonly existingUploadId: string;
  readonly filename: string;
}

export interface UploadsListPageProps {
  readonly uploads: ReadonlyArray<Upload>;
  readonly isLoading: boolean;
  readonly error: string | null;
  /** Set when the most recent POST returned 409 (sha256 dedup). */
  readonly dedupBanner?: DedupBanner;
}

const STATUS_LABELS: Record<UploadStatus, string> = {
  received: "Received",
  parsing: "Parsing",
  validated: "Validated",
  rejected: "Rejected",
  applied: "Applied",
};

// UploadStatus as defined in the contract (Plan A/B). The backend uses
// "validation_failed" internally but the contract maps it to "rejected" for
// the list surface. If the backend ever sends "validation_failed" directly,
// fall back gracefully.
function statusLabel(status: string): string {
  return STATUS_LABELS[status as UploadStatus] ?? status;
}

export function UploadsListPage({
  uploads,
  isLoading,
  error,
  dedupBanner,
}: UploadsListPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="uploads-list-page">
        <div data-testid="uploads-list-loading" role="status" aria-label="Loading uploads">
          Loading uploads...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="uploads-list-page">
        <div data-testid="uploads-list-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="uploads-list-page">
      <h1>Uploads</h1>

      {dedupBanner && (
        <div data-testid="dedup-banner" role="status" aria-label="Duplicate upload detected">
          <span>
            {`"${dedupBanner.filename}" was already uploaded. `}
          </span>
          <a
            data-testid="dedup-banner-link"
            href={`/admin/paysync/uploads/${dedupBanner.existingUploadId}`}
          >
            View existing upload
          </a>
        </div>
      )}

      <table aria-label="Uploads">
        <thead>
          <tr>
            <th scope="col">Filename</th>
            <th scope="col">Status</th>
            <th scope="col">Claims</th>
            <th scope="col">Errors</th>
            <th scope="col">Total Billed</th>
            <th scope="col">Uploaded At</th>
          </tr>
        </thead>
        <tbody>
          {uploads.map((upload) => (
            <tr key={upload.id} data-testid="upload-row">
              <td>
                <a href={`/admin/paysync/uploads/${upload.id}`}>
                  {upload.filename}
                </a>
              </td>
              <td>
                <span data-testid="upload-status-badge" data-status={upload.status}>
                  {statusLabel(upload.status)}
                </span>
              </td>
              <td>{upload.claim_count}</td>
              <td>{upload.row_error_count}</td>
              <td>
                {upload.total_billed_amount !== null ? (
                  <MoneyDisplay value={upload.total_billed_amount} />
                ) : (
                  <span aria-label="not yet computed">-</span>
                )}
              </td>
              <td>
                <time dateTime={upload.uploaded_at}>
                  {new Date(upload.uploaded_at).toLocaleString()}
                </time>
              </td>
            </tr>
          ))}
          {uploads.length === 0 && (
            <tr>
              <td colSpan={6} data-testid="uploads-list-empty">
                No uploads yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
