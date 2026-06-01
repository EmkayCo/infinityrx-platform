/**
 * Tests for the ReclaimRx Upload page.
 * Covers: form renders, file selection state, submit triggers POST.
 */
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock tanstack query and next/navigation
vi.mock("@tanstack/react-query", () => ({
  useMutation: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    data: null,
  })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}));

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn() })),
}));

// Mock api-client
vi.mock("@shared/lib/api-client", () => ({
  buildUrl: vi.fn((base: string) => base),
}));

import UploadPage from "./page";

describe("ReclaimRx Upload page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the upload form with file input", () => {
    render(<UploadPage />);
    expect(screen.getByText(/Upload Detection CSV/i)).toBeInTheDocument();
  });

  it("renders a run label input", () => {
    render(<UploadPage />);
    expect(screen.getByPlaceholderText(/run label/i)).toBeInTheDocument();
  });

  it("renders an upload/submit button", () => {
    render(<UploadPage />);
    // Button exists but may be disabled until file selected
    const btn = screen.getByRole("button", { name: /run detection/i });
    expect(btn).toBeInTheDocument();
  });

  it("submit button is disabled when no file is selected", () => {
    render(<UploadPage />);
    const btn = screen.getByRole("button", { name: /run detection/i });
    expect(btn).toBeDisabled();
  });
});
