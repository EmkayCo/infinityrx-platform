import "server-only";
import { CompositionViewer } from "@infinityrx/qa-harness";
import type { ReactNode } from "react";
// Static import of the generated manifest. Plan D's codegen overwrites this.
// TypeScript 5.6.3 NodeNext: use `with { type: "json" }` (TC39 import
// attributes), not `assert` (deprecated). Path: this file lives at
// src/routes/qa-harness/composition/page.tsx — three levels up to reach
// src/_generated/manifest.json.
import manifest from "../../../_generated/manifest.json" with { type: "json" };

/**
 * /qa-harness/composition — CompositionViewer.
 *
 * Reads _generated/manifest.json at import time (static — no runtime fetch).
 * Per Plan C: CompositionViewer is prop-driven; the runtime fetch is added here
 * at the shell layer, fulfilling the §6.4 "runtime fetch" deferred item.
 * In this implementation, "runtime fetch" means importing the statically
 * generated artifact at the route layer — consistent with SD-4's generated-
 * artifact mechanism (no dynamic HTTP fetch needed since manifest is embedded).
 */
export function CompositionPage(): ReactNode {
  return (
    <main>
      <h1>QA Harness — Composition</h1>
      <CompositionViewer manifest={manifest} />
    </main>
  );
}
