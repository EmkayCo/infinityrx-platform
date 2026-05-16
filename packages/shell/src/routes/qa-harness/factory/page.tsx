import "server-only";
import { FactoryBindings } from "@infinityrx/qa-harness";
import type { SeedBinding } from "@infinityrx/qa-harness";
import type { ReactNode } from "react";

// Exported so portals can type their mounting wrappers.
export interface FactoryPageProps {
  bindings: SeedBinding[];
  onSeed: (kind: string) => Promise<void>;
}

/**
 * /qa-harness/factory — Test data factory bindings.
 */
export function FactoryPage({ bindings, onSeed }: FactoryPageProps): ReactNode {
  return (
    <main>
      <h1>QA Harness — Test Data Factory</h1>
      <FactoryBindings bindings={bindings} seed={onSeed} />
    </main>
  );
}
