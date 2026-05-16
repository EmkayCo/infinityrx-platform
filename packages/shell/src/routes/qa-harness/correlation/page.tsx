import "server-only";
import { CorrelationIdJump } from "@infinityrx/qa-harness";
import type { ReactNode } from "react";

/**
 * /qa-harness/correlation — Correlation ID quick-jump.
 */
export function CorrelationPage(): ReactNode {
  return (
    <main>
      <h1>QA Harness — Correlation ID Quick Jump</h1>
      <CorrelationIdJump />
    </main>
  );
}
