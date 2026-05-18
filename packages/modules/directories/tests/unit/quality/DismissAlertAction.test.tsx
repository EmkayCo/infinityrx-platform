// tests/unit/quality/DismissAlertAction.test.tsx
// DismissAlertAction component tests (SP-2 Plan D Task D-3).
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  cleanup,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import React from "react";
import { DismissAlertAction } from "../../../src/quality/DismissAlertAction.js";

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockResolvedValue({ status: 204 });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("DismissAlertAction", () => {
  it("renders a 'Dismiss' button", () => {
    const onDismissed = vi.fn();
    render(<DismissAlertAction source="nppes" onDismissed={onDismissed} />);
    expect(screen.getByRole("button", { name: /dismiss/i })).toBeTruthy();
  });

  it("calls POST to dismiss endpoint when clicked", async () => {
    const onDismissed = vi.fn();
    render(<DismissAlertAction source="nppes" onDismissed={onDismissed} />);
    fireEvent.click(screen.getByRole("button", { name: /dismiss/i }));
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(1));
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("/api/directories/quality/dismiss/nppes");
    expect(opts?.method).toBe("POST");
  });

  it("calls onDismissed callback after successful POST (204)", async () => {
    const onDismissed = vi.fn();
    render(<DismissAlertAction source="fda_ndc" onDismissed={onDismissed} />);
    fireEvent.click(screen.getByRole("button", { name: /dismiss/i }));
    await waitFor(() => expect(onDismissed).toHaveBeenCalledTimes(1));
  });

  it("shows error message when POST returns 404", async () => {
    mockFetch.mockResolvedValue({ status: 404 });
    const onDismissed = vi.fn();
    render(<DismissAlertAction source="bpg" onDismissed={onDismissed} />);
    fireEvent.click(screen.getByRole("button", { name: /dismiss/i }));
    await waitFor(() => screen.getByRole("alert"));
    expect(screen.getByRole("alert").textContent).toMatch(/not dismissible/i);
    expect(onDismissed).not.toHaveBeenCalled();
  });

  it("shows error message when fetch throws (network error)", async () => {
    mockFetch.mockRejectedValue(new Error("network error"));
    const onDismissed = vi.fn();
    render(<DismissAlertAction source="nppes" onDismissed={onDismissed} />);
    fireEvent.click(screen.getByRole("button", { name: /dismiss/i }));
    await waitFor(() => screen.getByRole("alert"));
    expect(screen.getByRole("alert").textContent).toMatch(/network error/i);
    expect(onDismissed).not.toHaveBeenCalled();
  });

  it("URL-encodes source name in the fetch URL", async () => {
    const onDismissed = vi.fn();
    render(<DismissAlertAction source="state_medicaid_bins" onDismissed={onDismissed} />);
    fireEvent.click(screen.getByRole("button", { name: /dismiss/i }));
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(1));
    const [url] = mockFetch.mock.calls[0];
    expect(String(url)).toContain(encodeURIComponent("state_medicaid_bins"));
  });
});
