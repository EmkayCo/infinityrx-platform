// packages/modules/paysync/src/surfaces/files/FileDetailPage.tsx
// Detail view for a single file artifact.
// Shows metadata + ProvenanceBreadcrumb back to source batch/payment-run + originating upload.
// Includes a download button (Cache-Control: no-store enforced by the BFF handler).

import type { ReactElement } from "react";
import type { FileArtifact } from "@infinityrx/contract";
import { ProvenanceBreadcrumb, type ProvenanceLink } from "../../components/ProvenanceBreadcrumb.js";

export interface FileDetailPageProps {
  readonly file: FileArtifact | null;
  readonly isLoading: boolean;
  readonly error: string | null;
}

export function FileDetailPage({
  file,
  isLoading,
  error,
}: FileDetailPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="file-detail-loading" role="status" aria-label="Loading file">
        Loading...
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="file-detail-error" role="alert">
        {error}
      </div>
    );
  }

  if (!file) {
    return (
      <div data-testid="file-detail-page">
        <p>File not found.</p>
      </div>
    );
  }

  // Build provenance chain: upload (if known) -> batch/payment-run -> file
  const chain: ProvenanceLink[] = [];
  if (file.upload_id) {
    chain.push({
      label: `Upload ${file.upload_id.slice(0, 8)}...`,
      href: `/admin/paysync/uploads/${file.upload_id}`,
    });
  }
  if (file.source_batch_id) {
    chain.push({
      label: `Batch ${file.source_batch_id.slice(0, 8)}...`,
      href: `/admin/paysync/batches/${file.source_batch_id}`,
    });
  } else if (file.source_payment_run_id) {
    chain.push({
      label: `Payment Run ${file.source_payment_run_id.slice(0, 8)}...`,
      href: `/admin/paysync/payment-runs/${file.source_payment_run_id}`,
    });
  }
  chain.push({
    label: file.filename,
    href: `/admin/paysync/files/${file.id}`,
  });

  return (
    <div data-testid="file-detail-page">
      {chain.length > 1 && <ProvenanceBreadcrumb chain={chain} />}

      <h1>{file.filename}</h1>

      <section aria-label="File metadata">
        <dl>
          <dt>Kind</dt>
          <dd data-testid="file-detail-kind">{file.kind}</dd>

          <dt>Status</dt>
          <dd data-testid="file-detail-status">{file.status}</dd>

          <dt>File Size</dt>
          <dd data-testid="file-detail-size">{file.file_size} bytes</dd>

          <dt>SHA-256</dt>
          <dd data-testid="file-detail-sha256">{file.sha256}</dd>

          <dt>Generated At</dt>
          <dd>
            {file.generated_at ? (
              <time dateTime={file.generated_at}>
                {new Date(file.generated_at).toLocaleString()}
              </time>
            ) : (
              <span>-</span>
            )}
          </dd>
        </dl>
      </section>

      <a
        data-testid="file-detail-download"
        href={`/api/paysync/files/${file.id}/download`}
        download={file.filename}
      >
        Download {file.filename}
      </a>
    </div>
  );
}
