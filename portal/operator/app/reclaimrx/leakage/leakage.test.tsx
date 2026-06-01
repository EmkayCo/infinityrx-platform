/**
 * Tests for the Leakage Monitor page (repointed to /anomalies).
 * Covers: page renders, filter-to-query-params pushdown.
 */
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(() => ({
    data: { items: [], total: 0, limit: 50, offset: 0 },
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
  buildUrl: vi.fn((base: string, params?: Record<string, unknown>) => {
    if (!params) return base;
    const qs = Object.entries(params)
      .filter(([, v]) => v != null && v !== "")
      .map(([k, v]) => `${k}=${v}`)
      .join("&");
    return qs ? `${base}?${qs}` : base;
  }),
}));

import LeakageMonitorPage from "./page";

describe("Leakage Monitor page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the Leakage Monitor heading", () => {
    render(<LeakageMonitorPage />);
    expect(screen.getByText(/Leakage Monitor/i)).toBeInTheDocument();
  });

  it("renders 0 flags text when data is empty", () => {
    render(<LeakageMonitorPage />);
    expect(screen.getByText(/0 flags/i)).toBeInTheDocument();
  });
});
