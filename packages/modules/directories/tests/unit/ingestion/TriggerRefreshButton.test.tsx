// tests/unit/ingestion/TriggerRefreshButton.test.tsx
// TriggerRefreshButton unit tests (SP-2 Plan C Task C-3).
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import React from "react";

// Mock sonner before importing component
vi.mock("sonner", () => ({
  toast: {
    warning: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
  },
}));

import { toast } from "sonner";
import { TriggerRefreshButton } from "../../../src/ingestion/TriggerRefreshButton.js";

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("TriggerRefreshButton", () => {
  it("renders button with correct label", () => {
    render(
      <TriggerRefreshButton
        source="fda_ndc"
        onRunStarted={vi.fn()}
      />,
    );
    expect(screen.getByTestId("trigger-refresh-fda_ndc")).toBeTruthy();
    expect(screen.getByText("Refresh")).toBeTruthy();
  });

  it("is disabled when disabled prop is true", () => {
    render(
      <TriggerRefreshButton
        source="fda_ndc"
        onRunStarted={vi.fn()}
        disabled
      />,
    );
    const btn = screen.getByTestId("trigger-refresh-fda_ndc") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it("calls onRunStarted with run_id on 200 response", async () => {
    const onRunStarted = vi.fn();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ run_id: "run-abc", source: "fda_ndc", status: "running" }),
    });

    render(
      <TriggerRefreshButton source="fda_ndc" onRunStarted={onRunStarted} />,
    );
    fireEvent.click(screen.getByTestId("trigger-refresh-fda_ndc"));

    await waitFor(() => expect(onRunStarted).toHaveBeenCalledWith("run-abc"));
  });

  it("shows spinner while loading", async () => {
    let resolveResp: (v: unknown) => void;
    const pending = new Promise((res) => { resolveResp = res; });
    mockFetch.mockReturnValueOnce(pending);

    render(
      <TriggerRefreshButton source="fda_ndc" onRunStarted={vi.fn()} />,
    );
    fireEvent.click(screen.getByTestId("trigger-refresh-fda_ndc"));

    await waitFor(() =>
      expect(screen.getByTestId("trigger-spinner")).toBeTruthy(),
    );

    resolveResp!({
      ok: true,
      status: 200,
      json: async () => ({ run_id: "r", source: "fda_ndc", status: "running" }),
    });
  });

  it("shows 409 toast with correct message when run already in-flight", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 409, json: async () => ({}) });

    render(
      <TriggerRefreshButton source="fda_ndc" onRunStarted={vi.fn()} />,
    );
    fireEvent.click(screen.getByTestId("trigger-refresh-fda_ndc"));

    await waitFor(() =>
      expect(toast.warning).toHaveBeenCalledWith(
        expect.stringContaining("already running for fda_ndc"),
      ),
    );
  });

  it("shows 404 toast with correlation_id when source not found", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({
        error: { code: "SOURCE_NOT_FOUND", correlation_id: "cid-abc" },
      }),
    });

    render(
      <TriggerRefreshButton source="fda_ndc" onRunStarted={vi.fn()} />,
    );
    fireEvent.click(screen.getByTestId("trigger-refresh-fda_ndc"));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        expect.stringContaining("cid-abc"),
      ),
    );
  });

  it("shows error toast for non-200/404/409 responses", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ error: { correlation_id: "cid-500" } }),
    });

    render(
      <TriggerRefreshButton source="fda_ndc" onRunStarted={vi.fn()} />,
    );
    fireEvent.click(screen.getByTestId("trigger-refresh-fda_ndc"));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        expect.stringContaining("cid-500"),
      ),
    );
  });

  it("shows network error toast when fetch throws", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network down"));

    render(
      <TriggerRefreshButton source="fda_ndc" onRunStarted={vi.fn()} />,
    );
    fireEvent.click(screen.getByTestId("trigger-refresh-fda_ndc"));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        expect.stringContaining("Network down"),
      ),
    );
  });

  it("does not call fetch when disabled", () => {
    render(
      <TriggerRefreshButton source="fda_ndc" onRunStarted={vi.fn()} disabled />,
    );
    fireEvent.click(screen.getByTestId("trigger-refresh-fda_ndc"));
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
