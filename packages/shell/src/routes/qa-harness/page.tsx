import "server-only";
import type { BaseClient } from "@infinityrx/contract";
import { ServicesHealth } from "@infinityrx/qa-harness";
import type { ReactNode } from "react";

// Exported so portals can type their mounting wrappers.
export interface QaHarnessPageProps {
  /**
   * Registered clients to probe. Passed by the portal that mounts this page
   * (it knows which clients are configured for this instance).
   */
  clients: readonly BaseClient[];
}

/**
 * /qa-harness — Services health dashboard.
 *
 * Server component: probes all registered clients' health endpoints
 * and renders the ServicesHealth dashboard. In dev/staging only.
 */
export async function QaHarnessPage({ clients }: QaHarnessPageProps): Promise<ReactNode> {
  return (
    <main>
      <h1>QA Harness — Services Health</h1>
      <ServicesHealth clients={clients as BaseClient[]} />
    </main>
  );
}
