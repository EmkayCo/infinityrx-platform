/**
 * ColumnMappingStep tests.
 *
 * Covers:
 *   - Loading state while reading file headers
 *   - Auto-match: standard column names matched automatically
 *   - Auto-match: common aliases matched (e.g. "Drug Code" -> ndc)
 *   - Dropdowns: all 8 required fields have a select with the user's headers
 *   - Confirm button: disabled until all 8 fields mapped
 *   - Confirm button: enabled + calls onConfirm with correct mapping
 *   - Cancel: calls onCancel
 *   - Error state: empty file / unparseable header
 *   - XLSX fallback: text inputs instead of dropdowns
 *   - auto badge: shown for auto-matched fields
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { ColumnMappingStep, REQUIRED_FIELDS } from "../ColumnMappingStep";

afterEach(cleanup);

// ── helpers ────────────────────────────────────────────────────────────────

function makeFile(content: string, name = "claims.csv", type = "text/csv"): File {
  return new File([content], name, { type });
}

const STANDARD_HEADER = "ndc,npi,claim_id,date_of_service,quantity,days_supply,amount_billed,member_id";
const NONSTANDARD_HEADER = "Drug Code,Provider NPI,Claim Number,Date of Service,Qty,Days Supply,Billed Amount,Member ID";
const PARTIAL_HEADER = "Drug Code,Provider NPI,Claim Number,Date of Service,Qty,Days Supply,Billed Amount";
// 7 cols -- member_id missing

// ── REQUIRED_FIELDS export ──────────────────────────────────────────────────

describe("REQUIRED_FIELDS constant", () => {
  it("exports exactly 8 required fields", () => {
    expect(REQUIRED_FIELDS).toHaveLength(8);
  });

  it("includes all 8 canonical field keys", () => {
    const keys = REQUIRED_FIELDS.map((f) => f.key);
    expect(keys).toContain("ndc");
    expect(keys).toContain("npi");
    expect(keys).toContain("claim_id");
    expect(keys).toContain("date_of_service");
    expect(keys).toContain("quantity");
    expect(keys).toContain("days_supply");
    expect(keys).toContain("amount_billed");
    expect(keys).toContain("member_id");
  });
});

// ── Loading state ────────────────────────────────────────────────────────────

describe("ColumnMappingStep loading state", () => {
  it("shows loading indicator initially", async () => {
    const file = makeFile(STANDARD_HEADER + "\n00093015005,1234567893,C1,2026-01-01,30,30,99.00,M1");
    render(<ColumnMappingStep file={file} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    // Loading shown synchronously before async file read completes
    expect(screen.getByTestId("mapping-step-loading")).toBeDefined();
  });

  it("transitions to mapping table after file read", async () => {
    const file = makeFile(STANDARD_HEADER + "\nrow");
    render(<ColumnMappingStep file={file} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId("mapping-table")).toBeDefined());
  });
});

// ── Standard headers: auto-match all 8 fields ────────────────────────────────

describe("ColumnMappingStep with standard headers", () => {
  it("auto-matches all 8 fields when headers are already canonical", async () => {
    const file = makeFile(STANDARD_HEADER + "\nrow");
    render(<ColumnMappingStep file={file} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("mapping-table"));

    // All 8 selects should have a non-empty value
    for (const field of REQUIRED_FIELDS) {
      const select = screen.getByTestId(`mapping-select-${field.key}`) as HTMLSelectElement;
      expect(select.value).not.toBe("");
    }
  });

  it("enables Confirm button when all 8 are auto-matched", async () => {
    const file = makeFile(STANDARD_HEADER + "\nrow");
    render(<ColumnMappingStep file={file} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("mapping-table"));

    const btn = screen.getByTestId("mapping-confirm-btn") as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
  });

  it("shows auto badges for auto-matched fields", async () => {
    const file = makeFile(STANDARD_HEADER + "\nrow");
    render(<ColumnMappingStep file={file} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("mapping-table"));

    // At least one auto badge visible
    expect(screen.getAllByText("auto").length).toBeGreaterThan(0);
  });

  it("calls onConfirm with mapping when Confirm clicked", async () => {
    const onConfirm = vi.fn();
    const file = makeFile(STANDARD_HEADER + "\nrow");
    render(<ColumnMappingStep file={file} onConfirm={onConfirm} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("mapping-table"));

    fireEvent.click(screen.getByTestId("mapping-confirm-btn"));
    expect(onConfirm).toHaveBeenCalledOnce();
    const mapping = onConfirm.mock.calls[0][0] as Record<string, string>;
    expect(mapping["ndc"]).toBe("ndc");
    expect(mapping["npi"]).toBe("npi");
  });
});

// ── Non-standard headers: alias auto-match ───────────────────────────────────

describe("ColumnMappingStep with non-standard (aliased) headers", () => {
  it("auto-matches Drug Code -> ndc", async () => {
    const file = makeFile(NONSTANDARD_HEADER + "\nrow");
    render(<ColumnMappingStep file={file} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("mapping-table"));

    const select = screen.getByTestId("mapping-select-ndc") as HTMLSelectElement;
    expect(select.value).toBe("Drug Code");
  });

  it("auto-matches Provider NPI -> npi", async () => {
    const file = makeFile(NONSTANDARD_HEADER + "\nrow");
    render(<ColumnMappingStep file={file} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("mapping-table"));

    const select = screen.getByTestId("mapping-select-npi") as HTMLSelectElement;
    expect(select.value).toBe("Provider NPI");
  });

  it("auto-matches Billed Amount -> amount_billed", async () => {
    const file = makeFile(NONSTANDARD_HEADER + "\nrow");
    render(<ColumnMappingStep file={file} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("mapping-table"));

    const select = screen.getByTestId("mapping-select-amount_billed") as HTMLSelectElement;
    expect(select.value).toBe("Billed Amount");
  });

  it("enables confirm when all non-standard headers are auto-matched", async () => {
    const file = makeFile(NONSTANDARD_HEADER + "\nrow");
    render(<ColumnMappingStep file={file} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("mapping-table"));

    const btn = screen.getByTestId("mapping-confirm-btn") as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
  });

  it("calls onConfirm with {ndc: 'Drug Code', npi: 'Provider NPI', ...}", async () => {
    const onConfirm = vi.fn();
    const file = makeFile(NONSTANDARD_HEADER + "\nrow");
    render(<ColumnMappingStep file={file} onConfirm={onConfirm} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("mapping-table"));

    fireEvent.click(screen.getByTestId("mapping-confirm-btn"));
    const mapping = onConfirm.mock.calls[0][0] as Record<string, string>;
    expect(mapping["ndc"]).toBe("Drug Code");
    expect(mapping["npi"]).toBe("Provider NPI");
    expect(mapping["amount_billed"]).toBe("Billed Amount");
    expect(mapping["member_id"]).toBe("Member ID");
  });
});

// ── Partial headers: confirm disabled until all mapped ────────────────────────

describe("ColumnMappingStep with partial headers (member_id missing)", () => {
  it("disables Confirm button when not all 8 are mapped", async () => {
    const file = makeFile(PARTIAL_HEADER + "\nrow");
    render(<ColumnMappingStep file={file} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("mapping-table"));

    const btn = screen.getByTestId("mapping-confirm-btn") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it("enables Confirm after user manually selects a column for the unmapped field", async () => {
    // Use a header set where member_id has no alias but is present under a custom name
    const header = "Drug Code,Provider NPI,Claim Number,Date of Service,Qty,Days Supply,Billed Amount,Patient Ref";
    const file = makeFile(header + "\nrow");
    const onConfirm = vi.fn();
    render(<ColumnMappingStep file={file} onConfirm={onConfirm} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("mapping-table"));

    // member_id should be unmatched -- select "Patient Ref" manually
    const select = screen.getByTestId("mapping-select-member_id") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "Patient Ref" } });

    await waitFor(() => {
      const btn = screen.getByTestId("mapping-confirm-btn") as HTMLButtonElement;
      expect(btn.disabled).toBe(false);
    });

    fireEvent.click(screen.getByTestId("mapping-confirm-btn"));
    const mapping = onConfirm.mock.calls[0][0] as Record<string, string>;
    expect(mapping["member_id"]).toBe("Patient Ref");
  });
});

// ── Cancel ───────────────────────────────────────────────────────────────────

describe("ColumnMappingStep cancel", () => {
  it("calls onCancel when cancel button clicked", async () => {
    const onCancel = vi.fn();
    const file = makeFile(STANDARD_HEADER + "\nrow");
    render(<ColumnMappingStep file={file} onConfirm={vi.fn()} onCancel={onCancel} />);
    await waitFor(() => screen.getByTestId("mapping-table"));

    fireEvent.click(screen.getByTestId("mapping-cancel-btn"));
    expect(onCancel).toHaveBeenCalledOnce();
  });
});

// ── Error state ───────────────────────────────────────────────────────────────

describe("ColumnMappingStep error state", () => {
  it("shows error when file has no parseable header", async () => {
    // Empty file -> no header
    const file = makeFile("", "empty.csv");
    render(<ColumnMappingStep file={file} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("mapping-step-error"));
    expect(screen.getByTestId("mapping-step-error")).toBeDefined();
  });

  it("error state shows choose-different-file button", async () => {
    const file = makeFile("", "empty.csv");
    const onCancel = vi.fn();
    render(<ColumnMappingStep file={file} onConfirm={vi.fn()} onCancel={onCancel} />);
    await waitFor(() => screen.getByTestId("mapping-step-error"));

    fireEvent.click(screen.getByRole("button", { name: /choose a different file/i }));
    expect(onCancel).toHaveBeenCalledOnce();
  });
});

// ── XLSX fallback ─────────────────────────────────────────────────────────────

describe("ColumnMappingStep XLSX fallback", () => {
  it("renders text inputs instead of dropdowns for .xlsx files", async () => {
    const file = makeFile("binary-xlsx-content", "claims.xlsx",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
    render(<ColumnMappingStep file={file} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("mapping-table"));

    // Should have text inputs, not selects
    const input = screen.getByTestId("mapping-input-ndc") as HTMLInputElement;
    expect(input.tagName.toLowerCase()).toBe("input");
    expect(input.type).toBe("text");
  });

  it("XLSX confirm enabled after typing column names for all 8 fields", async () => {
    const file = makeFile("binary", "claims.xlsx",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
    const onConfirm = vi.fn();
    render(<ColumnMappingStep file={file} onConfirm={onConfirm} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("mapping-table"));

    // Type a value for each field
    for (const field of REQUIRED_FIELDS) {
      fireEvent.change(screen.getByTestId(`mapping-input-${field.key}`), {
        target: { value: `My_${field.key}` },
      });
    }

    await waitFor(() => {
      const btn = screen.getByTestId("mapping-confirm-btn") as HTMLButtonElement;
      expect(btn.disabled).toBe(false);
    });

    fireEvent.click(screen.getByTestId("mapping-confirm-btn"));
    const mapping = onConfirm.mock.calls[0][0] as Record<string, string>;
    expect(mapping["ndc"]).toBe("My_ndc");
    expect(mapping["member_id"]).toBe("My_member_id");
  });
});
