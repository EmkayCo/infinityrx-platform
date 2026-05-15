import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import type { BaseClient } from "@infinityrx/contract";
import { ServicesHealth } from "../services-health.js";

function makeMockClient(name: string, ok: boolean, latency_ms = 10): BaseClient {
  return {
    name,
    cachePolicies: {},
    probeHealth: vi.fn().mockResolvedValue({ ok, latency_ms, error: ok ? undefined : "timeout" }),
  };
}

describe("ServicesHealth", () => {
  it("shows service names", async () => {
    const clients = [makeMockClient("prescriber-directory", true)];
    render(<ServicesHealth clients={clients} pollIntervalMs={0} />);
    await waitFor(() => expect(screen.getByText("prescriber-directory")).toBeDefined());
  });

  it("shows green status for a healthy service", async () => {
    const clients = [makeMockClient("prescriber-directory", true)];
    render(<ServicesHealth clients={clients} pollIntervalMs={0} />);
    await waitFor(() => {
      expect(screen.getByText("healthy")).toBeDefined();
    });
  });

  it("shows red status for an unhealthy service", async () => {
    const clients = [makeMockClient("billing", false)];
    render(<ServicesHealth clients={clients} pollIntervalMs={0} />);
    await waitFor(() => {
      expect(screen.getByText("unhealthy")).toBeDefined();
    });
  });

  it("shows latency for each service", async () => {
    const clients = [makeMockClient("prescriber-directory", true, 42)];
    render(<ServicesHealth clients={clients} pollIntervalMs={0} />);
    await waitFor(() => {
      expect(screen.getByText(/42\s*ms/)).toBeDefined();
    });
  });

  it("shows the error message for an unhealthy service", async () => {
    const clients = [makeMockClient("billing", false)];
    render(<ServicesHealth clients={clients} pollIntervalMs={0} />);
    await waitFor(() => {
      expect(screen.getByText("timeout")).toBeDefined();
    });
  });

  it("handles multiple clients", async () => {
    const clients = [
      makeMockClient("prescriber-directory", true),
      makeMockClient("billing", false),
    ];
    render(<ServicesHealth clients={clients} pollIntervalMs={0} />);
    await waitFor(() => {
      expect(screen.getByText("prescriber-directory")).toBeDefined();
      expect(screen.getByText("billing")).toBeDefined();
    });
  });
});
