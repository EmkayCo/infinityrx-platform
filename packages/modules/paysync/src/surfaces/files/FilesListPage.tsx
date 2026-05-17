// packages/modules/paysync/src/surfaces/files/FilesListPage.tsx
// List view for paysync generated file artifacts.
// Columns: kind badge, filename, file_size, generated_at, source link, download button.
// Data received via props (BFF/TanStack Query owns the fetch).

import type { ReactElement } from "react";
import type { FileArtifact, FileArtifactKind } from "@infinityrx/contract";

export interface FilesListPageProps {
  readonly files: ReadonlyArray<FileArtifact>;
  readonly isLoading: boolean;
  readonly error: string | null;
}

const KIND_LABELS: Record<FileArtifactKind, string> = {
  nacha: "NACHA",
  x12_835: "835",
  x12_837: "837",
  x12_270: "270",
  x12_271: "271",
  x12_276: "276",
  x12_277: "277",
  x12_278: "278",
  x12_834: "834",
  x12_999: "999",
  ncpdp_batch: "NCPDP Batch",
};

function kindLabel(kind: string): string {
  return KIND_LABELS[kind as FileArtifactKind] ?? kind;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function sourceHref(file: FileArtifact): string | null {
  if (file.source_batch_id) {
    return `/admin/paysync/batches/${file.source_batch_id}`;
  }
  if (file.source_payment_run_id) {
    return `/admin/paysync/payment-runs/${file.source_payment_run_id}`;
  }
  return null;
}

export function FilesListPage({
  files,
  isLoading,
  error,
}: FilesListPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="files-list-page">
        <div data-testid="files-list-loading" role="status" aria-label="Loading files">
          Loading files...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="files-list-page">
        <div data-testid="files-list-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="files-list-page">
      <h1>Generated Files</h1>

      {files.length === 0 ? (
        <div data-testid="files-list-empty" role="status">
          No files generated yet.
        </div>
      ) : (
        <table aria-label="Generated files">
          <thead>
            <tr>
              <th scope="col">Kind</th>
              <th scope="col">Filename</th>
              <th scope="col">Size</th>
              <th scope="col">Generated At</th>
              <th scope="col">Source</th>
              <th scope="col">Download</th>
            </tr>
          </thead>
          <tbody>
            {files.map((file) => {
              const src = sourceHref(file);
              return (
                <tr key={file.id} data-testid="file-row">
                  <td>
                    <span data-testid="file-kind-badge" data-kind={file.kind}>
                      {kindLabel(file.kind)}
                    </span>
                  </td>
                  <td>
                    <a href={`/admin/paysync/files/${file.id}`}>
                      {file.filename}
                    </a>
                  </td>
                  <td data-testid="file-size">
                    {formatBytes(file.file_size)}
                  </td>
                  <td>
                    {file.generated_at ? (
                      <time dateTime={file.generated_at}>
                        {new Date(file.generated_at).toLocaleString()}
                      </time>
                    ) : (
                      <span aria-label="not yet generated">-</span>
                    )}
                  </td>
                  <td>
                    {src ? (
                      <a data-testid="file-source-link" href={src}>
                        {file.source_batch_id ? "Batch" : "Payment Run"}
                      </a>
                    ) : (
                      <span aria-label="no source">-</span>
                    )}
                  </td>
                  <td>
                    <a
                      data-testid="file-download-link"
                      href={`/api/paysync/files/${file.id}/download`}
                      download={file.filename}
                    >
                      Download
                    </a>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
