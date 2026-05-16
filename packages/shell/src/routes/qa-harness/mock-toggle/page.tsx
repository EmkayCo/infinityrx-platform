import "server-only";
import type { BaseClient } from "@infinityrx/contract";
import { MockToggle } from "@infinityrx/qa-harness";
import type { ReactNode } from "react";

// Exported so portals can type their mounting wrappers.
export interface MockTogglePageProps {
  clients: readonly BaseClient[];
  onToggle: (clientName: string, mode: "real" | "mock") => void;
}

/**
 * /qa-harness/mock-toggle — Per-client real/mock toggle.
 */
export function MockTogglePage({ clients, onToggle }: MockTogglePageProps): ReactNode {
  return (
    <main>
      <h1>QA Harness — Mock/Real Toggle</h1>
      <MockToggle clients={clients as BaseClient[]} onToggle={onToggle} />
    </main>
  );
}
