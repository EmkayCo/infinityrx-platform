// packages/modules/paysync/src/surfaces/files/FileGenerateForm.tsx
// Form for generating a NACHA or 835 file from a source batch/payment-run.
// RbacGate "approver" -- operator and auditor see the form disabled.
// Write-path fail-fast: backend error shows an error message; no optimistic updates.

import { useState, type ReactElement, type FormEvent } from "react";
import type { FileArtifact } from "@infinityrx/contract";
import { RbacGate } from "../../components/RbacGate.js";
import type { RbacRole } from "../../inbox/types.js";

export interface FileGenerateFormProps {
  readonly currentRole: RbacRole;
  readonly onGenerate: (kind: string, sourceId: string) => Promise<FileArtifact>;
}

type FormState =
  | { status: "idle" }
  | { status: "submitting" }
  | { status: "success"; artifact: FileArtifact }
  | { status: "error"; message: string };

const FILE_KINDS = [
  { value: "nacha", label: "NACHA (ACH payment file)" },
  { value: "835", label: "835 (Remittance Advice)" },
];

export function FileGenerateForm({
  currentRole,
  onGenerate,
}: FileGenerateFormProps): ReactElement {
  const [kind, setKind] = useState<string>("nacha");
  const [sourceId, setSourceId] = useState<string>("");
  const [formState, setFormState] = useState<FormState>({ status: "idle" });

  async function handleSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    if (!sourceId.trim()) return;
    setFormState({ status: "submitting" });
    try {
      const artifact = await onGenerate(kind, sourceId.trim());
      setFormState({ status: "success", artifact });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "File generation failed";
      setFormState({ status: "error", message });
    }
  }

  const form = (
    <form data-testid="file-generate-form" onSubmit={handleSubmit}>
      <div>
        <label htmlFor="file-kind-select">File kind</label>
        <select
          id="file-kind-select"
          data-testid="file-kind-select"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          {FILE_KINDS.map((k) => (
            <option key={k.value} value={k.value}>
              {k.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="file-source-id-input">Source batch / payment run ID</label>
        <input
          id="file-source-id-input"
          data-testid="file-source-id-input"
          type="text"
          value={sourceId}
          onChange={(e) => setSourceId(e.target.value)}
          placeholder="UUID of source batch or payment run"
        />
      </div>

      <button
        data-testid="file-generate-submit"
        type="submit"
        disabled={formState.status === "submitting" || !sourceId.trim()}
        aria-busy={formState.status === "submitting"}
      >
        {formState.status === "submitting" ? "Generating..." : "Generate File"}
      </button>

      {formState.status === "success" && (
        <div data-testid="file-generate-success" role="status">
          <span>File generated: </span>
          <a
            data-testid="file-generate-download-link"
            href={`/api/paysync/files/${formState.artifact.id}/download`}
            download={formState.artifact.filename}
          >
            {formState.artifact.filename}
          </a>
        </div>
      )}

      {formState.status === "error" && (
        <div data-testid="file-generate-error" role="alert">
          {formState.message}
        </div>
      )}
    </form>
  );

  return (
    <div data-testid="file-generate-panel">
      <h2>Generate File</h2>
      <RbacGate role="approver" currentRole={currentRole}>
        {form}
      </RbacGate>
    </div>
  );
}
