/**
 * F0 WS3-C1 - UploadDropzone accept allowlist guard.
 *
 * Per PRD §7.2 Step 1: accepts CSV, Excel, and pipe-delimited (configurable
 * per client). Pipe-delimited files use .txt or .psv with text/plain MIME type.
 *
 * Tests assert the hidden file input's accept attribute includes all required
 * MIME types and extensions, and that the existing .csv/.xlsx types are not
 * regressed. Also covers disabled state and dedup banner (regression guard).
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { UploadDropzone } from "../UploadDropzone";

afterEach(cleanup);

const noop = () => {};

function getFileInput() {
  return screen.getByTestId("upload-file-input") as HTMLInputElement;
}

describe("UploadDropzone accept attribute - pipe-delimited support (WS3-C1)", () => {
  it("accept includes text/plain (pipe-delimited MIME type)", () => {
    render(<UploadDropzone onUpload={noop} disabled={false} />);
    expect(getFileInput().accept).toContain("text/plain");
  });

  it("accept includes .txt extension", () => {
    render(<UploadDropzone onUpload={noop} disabled={false} />);
    expect(getFileInput().accept).toContain(".txt");
  });

  it("accept includes .psv extension", () => {
    render(<UploadDropzone onUpload={noop} disabled={false} />);
    expect(getFileInput().accept).toContain(".psv");
  });

  it("accept still includes .csv (regression guard)", () => {
    render(<UploadDropzone onUpload={noop} disabled={false} />);
    expect(getFileInput().accept).toContain(".csv");
  });

  it("accept still includes .xlsx (regression guard)", () => {
    render(<UploadDropzone onUpload={noop} disabled={false} />);
    expect(getFileInput().accept).toContain(".xlsx");
  });

  it("accept still includes text/csv (regression guard)", () => {
    render(<UploadDropzone onUpload={noop} disabled={false} />);
    expect(getFileInput().accept).toContain("text/csv");
  });

  it("accept still includes the xlsx MIME type (regression guard)", () => {
    render(<UploadDropzone onUpload={noop} disabled={false} />);
    expect(getFileInput().accept).toContain(
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    );
  });
});

describe("UploadDropzone disabled state (regression guard)", () => {
  it("renders with aria-disabled=true when disabled", () => {
    render(<UploadDropzone onUpload={noop} disabled={true} disabledReason="Auditor role" />);
    const dropzone = screen.getByTestId("upload-dropzone");
    expect(dropzone.getAttribute("aria-disabled")).toBe("true");
  });

  it("shows disabledReason text when disabled", () => {
    render(<UploadDropzone onUpload={noop} disabled={true} disabledReason="Auditor role" />);
    expect(screen.getByText("Auditor role")).toBeDefined();
  });

  it("file input is disabled when disabled=true", () => {
    render(<UploadDropzone onUpload={noop} disabled={true} />);
    expect(getFileInput().disabled).toBe(true);
  });
});

describe("UploadDropzone dedup banner (regression guard)", () => {
  it("renders dedup banner with link when dupUploadId is provided", () => {
    render(<UploadDropzone onUpload={noop} disabled={false} dupUploadId="upl-abc" />);
    expect(screen.getByTestId("dropzone-dedup-banner")).toBeDefined();
    const link = screen.getByTestId("dropzone-dedup-link") as HTMLAnchorElement;
    expect(link.href).toContain("/admin/paysync/uploads/upl-abc");
  });

  it("does not render dedup banner when dupUploadId is absent", () => {
    render(<UploadDropzone onUpload={noop} disabled={false} />);
    expect(screen.queryByTestId("dropzone-dedup-banner")).toBeNull();
  });
});

describe("UploadDropzone progress bar (regression guard)", () => {
  it("renders progress bar when progress is defined", () => {
    render(<UploadDropzone onUpload={noop} disabled={false} progress={42} />);
    const bar = screen.getByTestId("upload-progress");
    expect(bar.getAttribute("aria-valuenow")).toBe("42");
  });

  it("does not render progress bar when progress is undefined", () => {
    render(<UploadDropzone onUpload={noop} disabled={false} />);
    expect(screen.queryByTestId("upload-progress")).toBeNull();
  });
});

describe("UploadDropzone onUpload callback", () => {
  it("calls onUpload with the selected file", async () => {
    const onUpload = vi.fn();
    render(<UploadDropzone onUpload={onUpload} disabled={false} />);
    const input = getFileInput();
    const file = new File(["col1|col2\nval1|val2"], "data.txt", { type: "text/plain" });
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
    expect(onUpload).toHaveBeenCalledWith(file);
  });

  it("does not call onUpload when disabled", async () => {
    const onUpload = vi.fn();
    render(<UploadDropzone onUpload={onUpload} disabled={true} />);
    const input = getFileInput();
    const file = new File(["data"], "data.csv", { type: "text/csv" });
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
    expect(onUpload).not.toHaveBeenCalled();
  });
});
