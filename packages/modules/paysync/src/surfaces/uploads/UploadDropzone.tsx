// packages/modules/paysync/src/surfaces/uploads/UploadDropzone.tsx
// Drag-and-drop / file-picker for CSV or XLSX uploads.
// Per spec §5.4: when disabled (Auditor role), renders visually disabled
// with aria-disabled="true" — never hidden.
// On 409 sha256 dedup: renders a banner linking to the existing upload.

import { useRef, type ReactElement, type ChangeEvent } from "react";

export interface UploadDropzoneProps {
  readonly onUpload: (file: File) => void;
  readonly disabled: boolean;
  readonly disabledReason?: string;
  /** Set when a previous POST returned 409 (sha256 dedup). */
  readonly dupUploadId?: string;
  /** Upload progress 0-100. undefined = not uploading. */
  readonly progress?: number;
}

const ACCEPTED_TYPES =
  ".csv,.xlsx,.txt,.psv," +
  "text/csv," +
  "text/plain," +
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

export function UploadDropzone({
  onUpload,
  disabled,
  disabledReason,
  dupUploadId,
  progress,
}: UploadDropzoneProps): ReactElement {
  const inputRef = useRef<HTMLInputElement | null>(null);

  function handleChange(e: ChangeEvent<HTMLInputElement>): void {
    if (disabled) return;
    const file = e.target.files?.[0];
    if (file) {
      onUpload(file);
      // Reset the input so the same file can be re-selected after fixing issues.
      e.target.value = "";
    }
  }

  function handleDropzoneClick(): void {
    if (!disabled) inputRef.current?.click();
  }

  function handleKeyDown(e: React.KeyboardEvent): void {
    if (!disabled && (e.key === "Enter" || e.key === " ")) {
      inputRef.current?.click();
    }
  }

  return (
    <div
      data-testid="upload-dropzone"
      aria-label="Dropzone area"
      aria-disabled={disabled ? "true" : undefined}
    >
      {dupUploadId && (
        <div data-testid="dropzone-dedup-banner" role="status">
          <span>This file was already uploaded. </span>
          <a href={`/admin/paysync/uploads/${dupUploadId}`} data-testid="dropzone-dedup-link">
            View existing upload
          </a>
        </div>
      )}

      <div
        data-testid="dropzone-target"
        aria-disabled={disabled ? "true" : undefined}
        title={disabled && disabledReason ? disabledReason : undefined}
        onClick={handleDropzoneClick}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={disabled ? -1 : 0}
        style={disabled ? { pointerEvents: "none", opacity: 0.5 } : undefined}
      >
        <input
          ref={inputRef}
          data-testid="upload-file-input"
          type="file"
          accept={ACCEPTED_TYPES}
          disabled={disabled}
          onChange={handleChange}
          aria-label="Select a CSV, XLSX, or pipe-delimited (.txt/.psv) file to upload"
          style={{ display: "none" }}
        />
        <p>
          {disabled
            ? (disabledReason ?? "Upload is not available for your role")
            : "Click or drag a CSV, XLSX, or pipe-delimited (.txt/.psv) file here to upload"}
        </p>
      </div>

      {progress !== undefined && (
        <div data-testid="upload-progress" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
          <div style={{ width: `${progress}%` }} />
          <span>{progress}%</span>
        </div>
      )}
    </div>
  );
}
