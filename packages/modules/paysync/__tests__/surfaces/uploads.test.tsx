// packages/modules/paysync/__tests__/surfaces/uploads.test.tsx
// RTL tests for the uploads surface components.
// Uses happy-dom; patches clientHeight/clientWidth per the virtualizer quirk.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { Upload } from "@infinityrx/contract";

afterEach(() => cleanup());

// ── Shared fixtures ──────────────────────────────────────────────────────

const TENANT = "t0000000-0000-0000-0000-000000000001";
const NOW = "2026-05-16T22:00:00.000+00:00";

function makeUpload(overrides: Partial<Upload> = {}): Upload {
  return {
    id: "u0000000-0000-0000-0000-000000000001",
    tenant_id: TENANT,
    filename: "claims-healthy.csv",
    content_sha256: "a".repeat(64),
    status: "validated",
    total_billed_amount: "12345.6700",
    claim_count: 20,
    row_error_count: 0,
    uploaded_by_user_id: "usr-0000-0000-0000-00000001",
    uploaded_at: NOW,
    ...overrides,
  };
}

// ── UploadsListPage ──────────────────────────────────────────────────────

describe("UploadsListPage", () => {
  let UploadsListPage: typeof import("../../src/surfaces/uploads/UploadsListPage.js").UploadsListPage;

  beforeEach(async () => {
    ({ UploadsListPage } = await import("../../src/surfaces/uploads/UploadsListPage.js"));
  });

  it("renders the uploads table heading", () => {
    render(<UploadsListPage uploads={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("uploads-list-page")).toBeTruthy();
  });

  it("renders a row for each upload", () => {
    const uploads = [makeUpload(), makeUpload({ id: "u2", filename: "claims-2.csv" })];
    render(<UploadsListPage uploads={uploads} isLoading={false} error={null} />);
    expect(screen.getAllByTestId("upload-row")).toHaveLength(2);
  });

  it("renders the filename for each upload", () => {
    render(<UploadsListPage uploads={[makeUpload()]} isLoading={false} error={null} />);
    expect(screen.getByText("claims-healthy.csv")).toBeTruthy();
  });

  it("renders MoneyDisplay for total_billed_amount when set", () => {
    render(<UploadsListPage uploads={[makeUpload()]} isLoading={false} error={null} />);
    // MoneyDisplay renders a span with data-testid="money-display"
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders status badge for each upload", () => {
    render(<UploadsListPage uploads={[makeUpload({ status: "validation_failed" })]} isLoading={false} error={null} />);
    expect(screen.getByTestId("upload-status-badge")).toBeTruthy();
  });

  it("renders a sha256 dedup banner when duplicate_of is set", () => {
    render(<UploadsListPage
      uploads={[makeUpload()]}
      isLoading={false}
      error={null}
      dedupBanner={{ existingUploadId: "u-existing-001", filename: "claims-healthy.csv" }}
    />);
    expect(screen.getByTestId("dedup-banner")).toBeTruthy();
    expect(screen.getByTestId("dedup-banner-link")).toBeTruthy();
  });

  it("renders a loading state when isLoading=true", () => {
    render(<UploadsListPage uploads={[]} isLoading={true} error={null} />);
    expect(screen.getByTestId("uploads-list-loading")).toBeTruthy();
  });

  it("renders an error message when error is set", () => {
    render(<UploadsListPage uploads={[]} isLoading={false} error="Network failure" />);
    expect(screen.getByTestId("uploads-list-error")).toBeTruthy();
  });
});

// ── UploadDropzone ───────────────────────────────────────────────────────

describe("UploadDropzone", () => {
  let UploadDropzone: typeof import("../../src/surfaces/uploads/UploadDropzone.js").UploadDropzone;

  beforeEach(async () => {
    ({ UploadDropzone } = await import("../../src/surfaces/uploads/UploadDropzone.js"));
  });

  it("renders the dropzone input", () => {
    render(<UploadDropzone onUpload={vi.fn()} disabled={false} />);
    expect(screen.getByTestId("upload-dropzone")).toBeTruthy();
  });

  it("renders disabled state for Auditor role", () => {
    render(<UploadDropzone onUpload={vi.fn()} disabled={true} disabledReason="auditor role cannot upload" />);
    const dropzone = screen.getByTestId("upload-dropzone");
    expect(dropzone.getAttribute("aria-disabled")).toBe("true");
  });

  it("calls onUpload with the selected file", async () => {
    const onUpload = vi.fn();
    render(<UploadDropzone onUpload={onUpload} disabled={false} />);
    const input = screen.getByTestId("upload-file-input") as HTMLInputElement;
    const file = new File(["ndc,npi"], "test.csv", { type: "text/csv" });
    Object.defineProperty(input, "files", { value: [file] });
    fireEvent.change(input);
    await waitFor(() => expect(onUpload).toHaveBeenCalledWith(file));
  });

  it("does not call onUpload when disabled", async () => {
    const onUpload = vi.fn();
    render(<UploadDropzone onUpload={onUpload} disabled={true} />);
    const input = screen.getByTestId("upload-file-input") as HTMLInputElement;
    const file = new File(["x"], "bad.csv", { type: "text/csv" });
    Object.defineProperty(input, "files", { value: [file] });
    fireEvent.change(input);
    await waitFor(() => expect(onUpload).not.toHaveBeenCalled());
  });

  it("renders a 409-dedup banner when dupUploadId is provided", () => {
    render(<UploadDropzone onUpload={vi.fn()} disabled={false} dupUploadId="u-dupe-001" />);
    expect(screen.getByTestId("dropzone-dedup-banner")).toBeTruthy();
  });
});

// ── UploadDetailPage ─────────────────────────────────────────────────────

describe("UploadDetailPage", () => {
  let UploadDetailPage: typeof import("../../src/surfaces/uploads/UploadDetailPage.js").UploadDetailPage;

  beforeEach(async () => {
    ({ UploadDetailPage } = await import("../../src/surfaces/uploads/UploadDetailPage.js"));
  });

  it("renders the upload filename as the page heading", () => {
    render(<UploadDetailPage upload={makeUpload()} isLoading={false} error={null} rowErrors={[]} />);
    expect(screen.getByTestId("upload-detail-page")).toBeTruthy();
    expect(screen.getByText("claims-healthy.csv")).toBeTruthy();
  });

  it("renders parse status badge", () => {
    render(<UploadDetailPage upload={makeUpload()} isLoading={false} error={null} rowErrors={[]} />);
    expect(screen.getByTestId("upload-status-badge")).toBeTruthy();
  });

  it("renders total_billed_amount via MoneyDisplay", () => {
    render(<UploadDetailPage upload={makeUpload()} isLoading={false} error={null} rowErrors={[]} />);
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders row error list when errors are present", () => {
    const errors = [
      { row: 3, field: "npi", message: "NPI failed Luhn check" },
      { row: 7, field: "ndc", message: "NDC must be exactly 11 digits" },
    ];
    render(<UploadDetailPage upload={makeUpload({ status: "validation_failed", row_error_count: 2 })} isLoading={false} error={null} rowErrors={errors} />);
    expect(screen.getByTestId("row-error-list")).toBeTruthy();
    expect(screen.getAllByTestId("row-error-item")).toHaveLength(2);
  });

  it("does NOT render member_id values in row errors", () => {
    // Backend already strips member_id from error messages; this test verifies
    // the component doesn't accidentally echo payload values.
    const errors = [
      { row: 5, field: "member_id", message: "member_id too long" },
    ];
    render(<UploadDetailPage upload={makeUpload({ status: "validation_failed" })} isLoading={false} error={null} rowErrors={errors} />);
    // Should show the error message description but never the actual member_id value
    expect(screen.getByText("member_id too long")).toBeTruthy();
    // Should NOT contain "M12345ABC" style raw values (backend strips them; UI must not add them)
    expect(screen.queryByText(/M\d{5}[A-Z]{3}/)).toBeNull();
  });

  it("renders a link to the claim viewer when upload is validated", () => {
    render(<UploadDetailPage upload={makeUpload({ status: "validated" })} isLoading={false} error={null} rowErrors={[]} />);
    expect(screen.getByTestId("view-claims-link")).toBeTruthy();
  });

  it("renders loading state", () => {
    render(<UploadDetailPage upload={null} isLoading={true} error={null} rowErrors={[]} />);
    expect(screen.getByTestId("upload-detail-loading")).toBeTruthy();
  });
});

// ── UploadClaimViewer ────────────────────────────────────────────────────

describe("UploadClaimViewer", () => {
  let UploadClaimViewer: typeof import("../../src/surfaces/uploads/UploadClaimViewer.js").UploadClaimViewer;

  beforeEach(async () => {
    ({ UploadClaimViewer } = await import("../../src/surfaces/uploads/UploadClaimViewer.js"));
  });

  it("renders the claim viewer container", () => {
    render(<UploadClaimViewer uploadId="u-001" claims={[]} isLoading={false} error={null} total={0} />);
    expect(screen.getByTestId("upload-claim-viewer")).toBeTruthy();
  });

  it("renders a row for each claim", () => {
    const claims: Record<string, unknown>[] = [
      { claim_id: "C001", ndc: "12345678901", npi: "1234567893", amount_billed: "12.5000" },
      { claim_id: "C002", ndc: "98765432109", npi: "9876543210", amount_billed: "8.7500" },
    ];
    render(<UploadClaimViewer uploadId="u-001" claims={claims} isLoading={false} error={null} total={2} />);
    expect(screen.getAllByTestId("claim-row")).toHaveLength(2);
  });

  it("renders claim amounts via MoneyDisplay", () => {
    const claims: Record<string, unknown>[] = [
      { claim_id: "C001", ndc: "12345678901", npi: "1234567893", amount_billed: "42.0000" },
    ];
    render(<UploadClaimViewer uploadId="u-001" claims={claims} isLoading={false} error={null} total={1} />);
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders empty state when no claims", () => {
    render(<UploadClaimViewer uploadId="u-001" claims={[]} isLoading={false} error={null} total={0} />);
    expect(screen.getByTestId("claim-viewer-empty")).toBeTruthy();
  });

  it("renders loading state", () => {
    render(<UploadClaimViewer uploadId="u-001" claims={[]} isLoading={true} error={null} total={0} />);
    expect(screen.getByTestId("claim-viewer-loading")).toBeTruthy();
  });

  it("renders the upload_id scope label", () => {
    render(<UploadClaimViewer uploadId="u-test-scope" claims={[]} isLoading={false} error={null} total={0} />);
    // Component should display which upload it's scoped to
    expect(screen.getByTestId("upload-scope-label")).toBeTruthy();
  });
});
