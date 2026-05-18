// tests/unit/ingestion/RunProgressBar.test.tsx
// RunProgressBar unit tests (SP-2 Plan C Task C-3).
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act, cleanup } from "@testing-library/react";
import React from "react";

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    warning: vi.fn(),
    success: vi.fn(),
  },
}));

import { toast } from "sonner";
import { RunProgressBar } from "../../../src/ingestion/RunProgressBar.js";

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

function makeRunResp(
  status: string,
  processed = 0,
  total: number | null = null,
  errorMsg: string | null = null,
) {
  return {
    ok: true,
    status: 200,
    json: async () => ({
      id: "run-1",
      source: "fda_ndc",
      status,
      records_processed: processed,
      records_in_source: total,
      error_message: errorMsg,
    }),
  };
}

describe("RunProgressBar", () => {
  it("renders progress bar container", async () => {
    mockFetch.mockResolvedValue(makeRunResp("running", 100, 1000));

    render(
      <RunProgressBar runId="run-1" source="fda_ndc" onComplete={vi.fn()} pollIntervalMs={60000} />,
    );

    await waitFor(() =>
      expect(screen.getByTestId("run-progress-bar")).toBeTruthy(),
    );
  });

  it("shows records_processed / records_in_source when total is known", async () => {
    mockFetch.mockResolvedValue(makeRunResp("running", 500, 2000));

    render(
      <RunProgressBar runId="run-1" source="fda_ndc" onComplete={vi.fn()} pollIntervalMs={60000} />,
    );

    await waitFor(() =>
      expect(screen.getByTestId("progress-label")).toBeTruthy(),
    );
    expect(screen.getByTestId("progress-label").textContent).toContain("500");
    expect(screen.getByTestId("progress-label").textContent).toContain("2,000");
  });

  it("shows indeterminate state when records_in_source is null", async () => {
    mockFetch.mockResolvedValue(makeRunResp("running", 0, null));

    render(
      <RunProgressBar runId="run-1" source="fda_ndc" onComplete={vi.fn()} pollIntervalMs={60000} />,
    );

    await waitFor(() =>
      expect(screen.getByTestId("progress-label-indeterminate")).toBeTruthy(),
    );
  });

  it("calls onComplete when status is 'completed'", async () => {
    const onComplete = vi.fn();
    mockFetch.mockResolvedValue(makeRunResp("completed", 1000, 1000));

    render(
      <RunProgressBar
        runId="run-1"
        source="fda_ndc"
        onComplete={onComplete}
        pollIntervalMs={60000}
      />,
    );

    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce(), { timeout: 3000 });
    expect(onComplete.mock.calls[0][0].status).toBe("completed");
  });

  it("shows 'completed' text when status is done", async () => {
    mockFetch.mockResolvedValue(makeRunResp("completed", 1000, 1000));

    render(
      <RunProgressBar runId="run-1" source="fda_ndc" onComplete={vi.fn()} pollIntervalMs={60000} />,
    );

    await waitFor(() =>
      expect(screen.getByTestId("progress-complete")).toBeTruthy(),
      { timeout: 3000 },
    );
    expect(screen.getByTestId("progress-complete").textContent).toBe("completed");
  });

  it("shows error toast when status is 'failed'", async () => {
    mockFetch.mockResolvedValue(
      makeRunResp("failed", 0, null, "CSV parse error on row 3"),
    );

    render(
      <RunProgressBar
        runId="run-1"
        source="fda_ndc"
        onComplete={vi.fn()}
        pollIntervalMs={60000}
      />,
    );

    await waitFor(() => expect(toast.error).toHaveBeenCalledOnce(), { timeout: 3000 });
    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("CSV parse error on row 3"),
    );
  });

  it("polls again after interval — second poll resolves as completed", async () => {
    // Use real timers but very short interval (100ms)
    mockFetch
      .mockResolvedValueOnce(makeRunResp("running", 100, 1000))
      .mockResolvedValueOnce(makeRunResp("completed", 1000, 1000));

    const onComplete = vi.fn();
    render(
      <RunProgressBar
        runId="run-1"
        source="fda_ndc"
        onComplete={onComplete}
        pollIntervalMs={100}
      />,
    );

    // After first fetch resolves, running state shows
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(1), { timeout: 2000 });

    // Wait for second poll (100ms interval) + fetch to resolve
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2), { timeout: 2000 });
    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce(), { timeout: 2000 });
  });

  it("does not crash when fetch throws (network error)", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));

    render(
      <RunProgressBar runId="run-1" source="fda_ndc" onComplete={vi.fn()} pollIntervalMs={60000} />,
    );

    // Should render without crashing even with network errors
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(screen.getByTestId("run-progress-bar")).toBeTruthy();
    // toast.error should NOT be called for network errors (keeps polling silently)
    expect(toast.error).not.toHaveBeenCalled();
  });
});
