/**
 * Wave B10 — W1.14a Next-runtime package-name canary route.
 *
 * Path: /api/b10-canary (initially planned as /api/__b10_canary but renamed
 * during W1.13 execute — Next.js App Router treats folders prefixed with `_`
 * or `__` as PRIVATE and excludes them from routing, returning 404).
 *
 * Hit by W1.13 dual-bundler canary under both `next dev --turbopack` and
 * `next dev --webpack` to prove `transpilePackages: ["@infinityrx/portal-shared"]`
 * actually works at Next runtime (not just at Vite/vitest layer per ER4 + codex
 * R2 §2.1 absorption).
 *
 * Imports BOTH:
 *   - root barrel via namespace import: `import * as root from "@infinityrx/portal-shared"`
 *   - one subpath export: `import { useSSE } from "@infinityrx/portal-shared/hooks/use-sse"`
 *
 * The subpath import exercises the `exports` map in portal/shared/package.json,
 * proving multi-app-ready packaging (codex R3 PLAN-time tightening c).
 *
 * Returns 200 + JSON with proof of resolution. Curl this from the W1.13 runner.
 *
 * **DO NOT** call this in production traffic — it's a B10-only canary. Keep it
 * checked in past B10 close as regression protection (ER5: codex confirmed
 * proxy.ts:33 passes /api/ through without auth redirect, so this route doesn't
 * need to live behind auth). At W6 closeout, decide: keep as permanent
 * regression artifact OR remove. Default: keep, with this comment header
 * documenting it as B10 regression coverage.
 */

import { NextResponse } from "next/server";

// ER4: namespace import on the root barrel — `Object.keys(root).length > 0`
// proves the package resolves and exports something. Default-export style
// would be ambiguous since the package has no default export.
import * as root from "@infinityrx/portal-shared";

// Subpath import via the exports map. The `useSSE` symbol is a React hook
// (defined as `export function useSSE<T>(...)` in portal/shared/hooks/use-sse.ts).
// We don't CALL the hook here — we just verify the import resolves and the
// symbol is a function at module load time.
import { useSSE } from "@infinityrx/portal-shared/hooks/use-sse";

export const dynamic = "force-dynamic"; // Always evaluate at request time
export const runtime = "nodejs"; // Explicit; not edge

export async function GET() {
  const root_keys = Object.keys(root);

  return NextResponse.json(
    {
      ok: true,
      wave: "B10",
      task: "W1.14a Next-runtime package-name canary",
      timestamp: new Date().toISOString(),
      proof: {
        // Root barrel proof — non-empty key list means barrel resolved
        root_resolved: root_keys.length > 0,
        root_key_count: root_keys.length,
        root_keys: root_keys.slice(0, 20), // First 20 for inspection (in case the barrel grows)
        // Subpath export proof — useSSE should be a function (the React hook)
        subpath_resolved: typeof useSSE === "function",
        subpath_export_type: typeof useSSE,
        subpath_export_name: useSSE?.name ?? null,
      },
    },
    { status: 200 }
  );
}
