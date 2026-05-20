// packages/modules/paysync/src/surfaces/uploads/UploadDetailPage.tsx
// Detail view for a single paysync upload. Shows parse status, row-error list
// (PHI-safe: never displays member_id values), and a link to the claim viewer.
// Per .claude/rules/phi-compliance.md: Cache-Control: no-store enforced at the
// BFF/API level; this component itself never logs or stores PHI.

import type { ReactElement } from "react";
import type { Upload } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export interface RowError {
  readonly row: number;
  readonly field: string;
  /** Description of the failure -- must NEVER contain the actual member_id value. */
  readonly message: string;
}

export interface UploadDetailPageProps {
  readonly upload: Upload | null;
  readonly isLoading: boolean;
  readonly error: string | null;
  /** Per-row parse errors from Upload.row_errors. Backend strips PHI values. */
  readonly rowErrors: ReadonlyArray<RowError>;
}

export function UploadDetailPage({
  upload,
  isLoading,
  error,
  rowErrors,
}: UploadDetailPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="upload-detail-loading" role="status" aria-label="Loading upload">
        Loading...
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="upload-detail-error" role="alert">
        {error}
      </div>
    );
  }

  if (!upload) {
    return (
      <div data-testid="upload-detail-page">
        <p>Upload not found.</p>
      </div>
    );
  }

  return (
    <div data-testid="upload-detail-page">
      <h1>{upload.filename}</h1>

      <section aria-label="Upload summary">
        <dl>
          <dt>Status</dt>
          <dd>
            <span data-testid="upload-status-badge" data-status={upload.status}>
              {upload.status}
            </span>
          </dd>

          <dt>Claims</dt>
          <dd>{upload.claim_count}</dd>

          <dt>Errors</dt>
          <dd>{upload.row_error_count}</dd>

          <dt>Total Billed</dt>
          <dd>
            {upload.total_billed_amount !== null ? (
              <MoneyDisplay value={upload.total_billed_amount} />
            ) : (
              <span aria-label="not yet computed">-</span>
            )}
          </dd>

          <dt>Uploaded At</dt>
          <dd>
            <time dateTime={upload.uploaded_at}>
              {new Date(upload.uploaded_at).toLocaleString()}
            </time>
          </dd>

          <dt>SHA-256</dt>
          <dd>
            <code data-testid="upload-sha256" style={{ fontFamily: "monospace", fontSize: "0.75em" }}>
              {upload.content_sha256}
            </code>
          </dd>
        </dl>
      </section>

      {upload.status === "validated" && (
        <a
          data-testid="view-claims-link"
          href={`/admin/paysync/uploads/${upload.id}/claims`}
        >
          View parsed claims
        </a>
      )}

      {rowErrors.length > 0 && (
        <section aria-label="Row validation errors" data-testid="row-error-list">
          <h2>Validation Errors ({rowErrors.length})</h2>
          <p>
            The following rows failed validation. No member data is shown per PHI policy.
          </p>
          <ul>
            {rowErrors.map((err, i) => (
              <li key={i} data-testid="row-error-item">
                <strong>Row {err.row}</strong>
                {" — "}
                <span data-testid="row-error-field">{err.field}</span>
                {": "}
                <span data-testid="row-error-message">{err.message}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
