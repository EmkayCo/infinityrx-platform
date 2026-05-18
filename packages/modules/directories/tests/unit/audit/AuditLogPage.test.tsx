// tests/unit/audit/AuditLogPage.test.tsx
// AuditLogPage component tests (SP-2 Plan D Task D-4).
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuditLogPage } from "../../../src/audit/AuditLogPage.js";

const mockFetch = vi.fn();

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function wrap(ui: React.ReactElement) {
  return render(
    <QueryClientProvider client={makeClient()}>{ui}</QueryClientProvider>,
  );
}

const SAMPLE_AUDIT_PAGE = {
  items: [
    {
      id: 1,
      action: "POST /api/v1/data-ingestion/nppes/trigger",
      module: "prescriber_directory",
      entity_type: "ingestion_run",
      entity_id: "nppes",
      user_id: "00000000-0000-0000-0000-000000000001",
      timestamp: "2026-05-15T03:00:00Z",
      correlation_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    },
    {
      id: 2,
      action: "POST /api/v1/data-ingestion/fda_ndc/trigger",
      module: "prescriber_directory",
      entity_type: "ingestion_run",
      entity_id: "fda_ndc",
      user_id: "00000000-0000-0000-0000-000000000001",
      timestamp: "2026-05-14T03:00:00Z",
      correlation_id: null,
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
};

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => SAMPLE_AUDIT_PAGE,
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("AuditLogPage", () => {
  it("renders loading state initially", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    wrap(<AuditLogPage />);
    expect(screen.getByText(/loading audit events/i)).toBeTruthy();
  });

  it("renders table with timestamp, action, source, actor columns", async () => {
    wrap(<AuditLogPage />);
    await waitFor(() => screen.getByRole("table"));
    const table = screen.getByRole("table");
    expect(table).toBeTruthy();
    // Column headers
    expect(screen.getByText(/timestamp/i)).toBeTruthy();
    expect(screen.getByText(/action/i)).toBeTruthy();
  });

  it("renders audit entries from BFF response", async () => {
    wrap(<AuditLogPage />);
    await waitFor(() =>
      screen.getByText(/POST \/api\/v1\/data-ingestion\/nppes\/trigger/),
    );
    expect(
      screen.getByText(/POST \/api\/v1\/data-ingestion\/nppes\/trigger/),
    ).toBeTruthy();
  });

  it("shows run ID link for entry with correlation_id", async () => {
    const onRunIdClick = vi.fn();
    wrap(<AuditLogPage onRunIdClick={onRunIdClick} />);
    await waitFor(() => screen.getAllByRole("button"));
    // The correlation_id link is rendered as a button.
    const runLinks = screen.getAllByRole("button", { name: /open run details/i });
    expect(runLinks.length).toBeGreaterThanOrEqual(1);
  });

  it("renders two table rows for two audit entries", async () => {
    wrap(<AuditLogPage />);
    // Wait for the table to appear.
    await waitFor(() => screen.getByRole("table"));
    // Both entries should be present — wait for row count.
    await waitFor(() => {
      const rows = document.querySelectorAll("[data-audit-id]");
      expect(rows.length).toBe(2);
    });
  });

  it("shows empty state when no events returned", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], total: 0, limit: 50, offset: 0 }),
    });
    wrap(<AuditLogPage />);
    await waitFor(() =>
      screen.getByText(/no ingestion audit events yet/i),
    );
    expect(screen.getByText(/no ingestion audit events yet/i)).toBeTruthy();
  });

  it("shows no-access state when core-platform returns 403", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ error: { code: "FORBIDDEN" } }),
    });
    wrap(<AuditLogPage />);
    await waitFor(() =>
      screen.getByText(/do not have permission/i),
    );
    expect(screen.getByText(/do not have permission/i)).toBeTruthy();
  });

  it("shows error state when fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("network error"));
    wrap(<AuditLogPage />);
    await waitFor(() => screen.getByText(/unable to load audit events/i));
    expect(screen.getByText(/unable to load audit events/i)).toBeTruthy();
  });
});
