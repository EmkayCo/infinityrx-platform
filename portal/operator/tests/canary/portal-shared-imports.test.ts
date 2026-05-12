/**
 * Wave B10 — W1.14b vitest regression test.
 *
 * Companion to the W1.14a Next-runtime canary route at
 * `app/api/__b10_canary/route.ts`. THIS test verifies the
 * `@infinityrx/portal-shared` package resolves under VITEST/VITE's
 * resolver (which is NOT the same as Next/Turbopack's resolver per
 * codex R2 §2.1 absorption).
 *
 * Vitest passing here does NOT prove SC #17 — that's the Next route's job
 * (curled by the W1.13 W4.6 dual-bundler runner). This test exists as
 * regression coverage that survives B10 close: if a future change breaks
 * the package's export map or barrel, the vitest suite catches it during
 * `npm run test`.
 */

import { describe, it, expect } from "vitest";

// Same import shape as the canary route: namespace + named-from-subpath.
import * as root from "@infinityrx/portal-shared";
import { useSSE } from "@infinityrx/portal-shared/hooks/use-sse";

describe("@infinityrx/portal-shared — B10 canary regression", () => {
  it("resolves the root barrel import (non-empty key list)", () => {
    const keys = Object.keys(root);
    expect(keys.length).toBeGreaterThan(0);
  });

  it("resolves the ./hooks/use-sse subpath export (useSSE is a function)", () => {
    expect(typeof useSSE).toBe("function");
    // useSSE is exported as a named function so .name should match
    expect(useSSE.name).toBe("useSSE");
  });

  it("documents that vitest != Next runtime", () => {
    // Plant marker so any future regression that disables Vite-layer
    // resolution still leaves a clear "use the Next runtime canary too"
    // signal in the failing test's name.
    expect(true).toBe(true);
  });
});
