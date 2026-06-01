/**
 * Tests for the ReclaimRx Detection Runs page.
 * Covers: page renders and empty state.
 */
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

// Mock tanstack query
vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(() => ({
    data: [],
    isLoading: false,
    isError: false,
    error: null,
  })),
}));

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn() })),
  useSearchParams: vi.fn(() => ({ get: vi.fn(() => null) })),
}));

vi.mock("@shared/lib/api-client", () => ({
  apiGet: vi.fn(),
  buildUrl: vi.fn((base: string) => base),
}));

import React from "react";
import RunsPage from "./page";

describe("ReclaimRx Detection Runs page", () => {
  it("renders the page heading", () => {
    render(<RunsPage />);
    expect(screen.getByRole("heading", { name: /Detection Runs/i })).toBeInTheDocument();
  });

  it("renders empty state when no runs", () => {
    render(<RunsPage />);
    expect(screen.getByText(/No detection runs/i)).toBeInTheDocument();
  });
});
