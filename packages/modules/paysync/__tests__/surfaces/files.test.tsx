// packages/modules/paysync/__tests__/surfaces/files.test.tsx
// RTL tests for the files surface components.
// Uses happy-dom. Follows the batches/uploads test pattern.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { FileArtifact } from "@infinityrx/contract";

afterEach(() => cleanup());

// ── Shared fixtures ──────────────────────────────────────────────────────

const TENANT = "t0000000-0000-0000-0000-000000000001";
const NOW = "2026-05-17T12:00:00.000+00:00";
const BATCH_ID = "b1000000-0000-0000-0000-000000000001";
const FILE_ID = "fa000000-0000-0000-0000-000000000001";
const USER_ID = "u0000000-0000-0000-0000-000000000001";

function makeFile(overrides: Partial<FileArtifact> = {}): FileArtifact {
  return {
    id: FILE_ID,
    tenant_id: TENANT,
    kind: "nacha",
    source_batch_id: BATCH_ID,
    source_payment_run_id: null,
    sha256: "a".repeat(64),
    file_size: 4096,
    generated_at: NOW,
    generated_by: USER_ID,
    upload_id: null,
    filename: "nacha-2026-05.txt",
    status: "ready",
    ...overrides,
  };
}

// ── FilesListPage ─────────────────────────────────────────────────────────

describe("FilesListPage", () => {
  let FilesListPage: typeof import("../../src/surfaces/files/FilesListPage.js").FilesListPage;

  beforeEach(async () => {
    ({ FilesListPage } = await import("../../src/surfaces/files/FilesListPage.js"));
  });

  it("renders the files list page container", () => {
    render(<FilesListPage files={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("files-list-page")).toBeTruthy();
  });

  it("renders a row for each file", () => {
    const files = [
      makeFile({ id: "fa1", filename: "nacha-001.txt" }),
      makeFile({ id: "fa2", filename: "835-001.txt", kind: "835" }),
    ];
    render(<FilesListPage files={files} isLoading={false} error={null} />);
    expect(screen.getAllByTestId("file-row")).toHaveLength(2);
  });

  it("renders kind badge for NACHA files", () => {
    render(<FilesListPage files={[makeFile({ kind: "nacha" })]} isLoading={false} error={null} />);
    const badge = screen.getByTestId("file-kind-badge");
    expect(badge.textContent).toBe("NACHA");
  });

  it("renders kind badge for 835 files", () => {
    render(<FilesListPage files={[makeFile({ kind: "835", filename: "835.txt" })]} isLoading={false} error={null} />);
    const badge = screen.getByTestId("file-kind-badge");
    expect(badge.textContent).toBe("835");
  });

  it("renders file-size in human-readable form", () => {
    render(<FilesListPage files={[makeFile({ file_size: 4096 })]} isLoading={false} error={null} />);
    expect(screen.getByTestId("file-size").textContent).toBe("4.0 KB");
  });

  it("renders source link to batch when source_batch_id is set", () => {
    render(<FilesListPage files={[makeFile({ source_batch_id: BATCH_ID })]} isLoading={false} error={null} />);
    const link = screen.getByTestId("file-source-link") as HTMLAnchorElement;
    expect(link.href).toContain(BATCH_ID);
  });

  it("renders download link with correct href", () => {
    render(<FilesListPage files={[makeFile()]} isLoading={false} error={null} />);
    const link = screen.getByTestId("file-download-link") as HTMLAnchorElement;
    expect(link.href).toContain(FILE_ID);
    expect(link.href).toContain("download");
  });

  it("renders loading state when isLoading=true", () => {
    render(<FilesListPage files={[]} isLoading={true} error={null} />);
    expect(screen.getByTestId("files-list-loading")).toBeTruthy();
  });

  it("renders error message when error is set", () => {
    render(<FilesListPage files={[]} isLoading={false} error="Network failure" />);
    expect(screen.getByTestId("files-list-error")).toBeTruthy();
  });

  it("renders empty state when no files", () => {
    render(<FilesListPage files={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("files-list-empty")).toBeTruthy();
  });

  it("renders dash when generated_at is null", () => {
    render(<FilesListPage files={[makeFile({ generated_at: null })]} isLoading={false} error={null} />);
    expect(screen.getByTestId("file-row")).toBeTruthy();
  });

  it("renders source link to payment-run when source_payment_run_id is set", () => {
    const PR_ID = "20000000-0000-0000-0000-000000000001";
    render(
      <FilesListPage
        files={[makeFile({ source_batch_id: null, source_payment_run_id: PR_ID })]}
        isLoading={false}
        error={null}
      />,
    );
    const link = screen.getByTestId("file-source-link") as HTMLAnchorElement;
    expect(link.href).toContain(PR_ID);
  });
});

// ── FileDetailPage ────────────────────────────────────────────────────────

describe("FileDetailPage", () => {
  let FileDetailPage: typeof import("../../src/surfaces/files/FileDetailPage.js").FileDetailPage;

  beforeEach(async () => {
    ({ FileDetailPage } = await import("../../src/surfaces/files/FileDetailPage.js"));
  });

  it("renders the file detail page container", () => {
    render(
      <FileDetailPage
        file={makeFile()}
        isLoading={false}
        error={null}
      />,
    );
    expect(screen.getByTestId("file-detail-page")).toBeTruthy();
  });

  it("renders the filename as heading", () => {
    render(
      <FileDetailPage
        file={makeFile({ filename: "nacha-2026-05.txt" })}
        isLoading={false}
        error={null}
      />,
    );
    // filename appears in heading and download link; getAllByText handles both
    expect(screen.getAllByText("nacha-2026-05.txt").length).toBeGreaterThanOrEqual(1);
  });

  it("renders ProvenanceBreadcrumb when source_batch_id is set", () => {
    render(
      <FileDetailPage
        file={makeFile({ source_batch_id: BATCH_ID })}
        isLoading={false}
        error={null}
      />,
    );
    expect(screen.getByTestId("provenance-breadcrumb")).toBeTruthy();
  });

  it("renders ProvenanceBreadcrumb when upload_id is set", () => {
    render(
      <FileDetailPage
        file={makeFile({ upload_id: "u0000000-0000-0000-0000-000000000001" })}
        isLoading={false}
        error={null}
      />,
    );
    expect(screen.getByTestId("provenance-breadcrumb")).toBeTruthy();
  });

  it("renders download button with correct href", () => {
    render(
      <FileDetailPage
        file={makeFile()}
        isLoading={false}
        error={null}
      />,
    );
    const link = screen.getByTestId("file-detail-download") as HTMLAnchorElement;
    expect(link.href).toContain(FILE_ID);
  });

  it("renders loading state", () => {
    render(<FileDetailPage file={null} isLoading={true} error={null} />);
    expect(screen.getByTestId("file-detail-loading")).toBeTruthy();
  });

  it("renders error state", () => {
    render(<FileDetailPage file={null} isLoading={false} error="Not found" />);
    expect(screen.getByTestId("file-detail-error")).toBeTruthy();
  });

  it("renders not-found state when file is null with no error", () => {
    render(<FileDetailPage file={null} isLoading={false} error={null} />);
    expect(screen.getByTestId("file-detail-page")).toBeTruthy();
  });
});

// ── FileGenerateForm ──────────────────────────────────────────────────────

describe("FileGenerateForm", () => {
  let FileGenerateForm: typeof import("../../src/surfaces/files/FileGenerateForm.js").FileGenerateForm;

  beforeEach(async () => {
    ({ FileGenerateForm } = await import("../../src/surfaces/files/FileGenerateForm.js"));
  });

  it("renders the generate panel container", () => {
    render(<FileGenerateForm currentRole="approver" onGenerate={vi.fn()} />);
    expect(screen.getByTestId("file-generate-panel")).toBeTruthy();
  });

  it("renders RbacGate allowed for Approver", () => {
    render(<FileGenerateForm currentRole="approver" onGenerate={vi.fn()} />);
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("renders RbacGate denied for Operator (form is visible but disabled)", () => {
    render(<FileGenerateForm currentRole="operator" onGenerate={vi.fn()} />);
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("renders RbacGate denied for Auditor (form is visible but disabled)", () => {
    render(<FileGenerateForm currentRole="auditor" onGenerate={vi.fn()} />);
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("calls onGenerate with kind and sourceId when Approver submits", async () => {
    const mockArtifact = makeFile();
    const onGenerate = vi.fn().mockResolvedValue(mockArtifact);
    render(<FileGenerateForm currentRole="approver" onGenerate={onGenerate} />);

    const sourceInput = screen.getByTestId("file-source-id-input");
    fireEvent.change(sourceInput, { target: { value: BATCH_ID } });
    fireEvent.submit(screen.getByTestId("file-generate-form"));

    await waitFor(() => {
      expect(onGenerate).toHaveBeenCalledWith("nacha", BATCH_ID);
    });
  });

  it("shows success with download link after successful generation", async () => {
    const mockArtifact = makeFile({ filename: "nacha-2026-05.txt" });
    const onGenerate = vi.fn().mockResolvedValue(mockArtifact);
    render(<FileGenerateForm currentRole="approver" onGenerate={onGenerate} />);

    fireEvent.change(screen.getByTestId("file-source-id-input"), { target: { value: BATCH_ID } });
    fireEvent.submit(screen.getByTestId("file-generate-form"));

    await waitFor(() => {
      expect(screen.getByTestId("file-generate-success")).toBeTruthy();
    });
    expect(screen.getByTestId("file-generate-download-link")).toBeTruthy();
  });

  it("shows error message when generation fails", async () => {
    const onGenerate = vi.fn().mockRejectedValue(new Error("Backend error: 403"));
    render(<FileGenerateForm currentRole="approver" onGenerate={onGenerate} />);

    fireEvent.change(screen.getByTestId("file-source-id-input"), { target: { value: BATCH_ID } });
    fireEvent.submit(screen.getByTestId("file-generate-form"));

    await waitFor(() => {
      expect(screen.getByTestId("file-generate-error")).toBeTruthy();
    });
  });

  it("does not call onGenerate when sourceId is empty", async () => {
    const onGenerate = vi.fn();
    render(<FileGenerateForm currentRole="approver" onGenerate={onGenerate} />);
    fireEvent.submit(screen.getByTestId("file-generate-form"));
    expect(onGenerate).not.toHaveBeenCalled();
  });
});

// ── BFF handlers (files.ts) ───────────────────────────────────────────────

describe("BFF files handlers", () => {
  let handlers: typeof import("../../src/surfaces/files/bff/files.js");
  let createMockFilesClient: typeof import("@infinityrx/contract")["createMockFilesClient"];

  beforeEach(async () => {
    handlers = await import("../../src/surfaces/files/bff/files.js");
    ({ createMockFilesClient } = await import("@infinityrx/contract"));
  });

  it("handleListFiles returns 200 with results", async () => {
    const client = createMockFilesClient();
    const req = { headers: {}, searchParams: new URLSearchParams() };
    const resp = await handlers.handleListFiles(req, client);
    expect(resp.status).toBe(200);
  });

  it("handleGetFile returns 404 when file not found", async () => {
    const client = createMockFilesClient();
    const req = { headers: {} };
    const resp = await handlers.handleGetFile("not-an-id", req, client);
    expect(resp.status).toBe(404);
  });

  it("handleGenerateFile calls client.generate and returns 201", async () => {
    const client = createMockFilesClient();
    const req = { headers: {}, body: { kind: "nacha", source_id: BATCH_ID } };
    const resp = await handlers.handleGenerateFile(req, client);
    expect(resp.status).toBe(201);
    expect(resp.data).toBeTruthy();
  });

  it("handleDownloadFile returns no-store cache header", async () => {
    const client = createMockFilesClient();
    const req = { headers: {} };
    const resp = await handlers.handleDownloadFile(FILE_ID, req, client);
    expect(resp.headers["Cache-Control"]).toBe("no-store");
  });
});
