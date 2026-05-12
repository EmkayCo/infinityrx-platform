# `@infinityrx/portal-shared`

Shared codebase for InfinityRx portal apps.

**Pattern:** source-mode TypeScript package consumed by Next.js apps via `transpilePackages` (no compile step). Multi-app-ready from day one — current consumer is `portal/operator`; future consumers (member portal, manufacturer portal) use the same package via npm workspace symlink.

This package was extracted from `portal/operator` during Wave B10 (2026-05-12) to fix a Turbopack module-resolution bug introduced when Next 16 made Turbopack the default for `next dev`.

---

## Why source-mode (no build step)?

Bundlers (Turbopack, webpack, vite) consume TypeScript directly. A build step would add latency to every `portal/shared/*.ts` edit (re-build → re-transpile → re-load) for zero runtime benefit. Source-mode keeps DX fast.

The trade-off: consumers MUST declare `transpilePackages: ["@infinityrx/portal-shared"]` in their `next.config.ts`. Without this, Next will try to load TypeScript files from `node_modules` as if they were already compiled — and fail at runtime.

---

## Package shape

| Field | Value | Why |
|---|---|---|
| `name` | `@infinityrx/portal-shared` | Scoped package name; `private: true` so it can never accidentally publish to npm registry |
| `version` | `0.0.0` | Workspace-internal; not semver-tracked |
| `main` | `./index.ts` | Entry point for default import; barrel re-exports server-safe surface |
| `types` | `./index.ts` | TS resolution; same file as main since source-mode has no separate `.d.ts` |
| `exports` | Subpath map for `./components/*`, `./hooks/*`, `./lib/*`, `./types/*`, `./design-system/*` | Allows `import x from "@infinityrx/portal-shared/hooks/use-sse"` |
| `dependencies` | `@dnd-kit/utilities`, `clsx`, `lucide-react`, `tailwind-merge` | Non-singleton deps; safe to deduplicate or duplicate |
| `peerDependencies` | `react`, `react-dom`, `next`, `next-auth` | **Singleton-required.** Two-React bugs are silent and devastating. Consumer MUST satisfy. |

`peerDependenciesMeta` marks all four peers as required (not optional).

---

## How a consumer wires this in

In the consumer's `next.config.ts`:

```ts
const nextConfig: NextConfig = {
  transpilePackages: ["@infinityrx/portal-shared"],
  // ... rest of config
};
```

In the consumer's `package.json`:

```json
{
  "dependencies": {
    "@infinityrx/portal-shared": "*"
  }
}
```

(npm workspaces resolves `*` to a symlink in `node_modules/@infinityrx/portal-shared/` pointing at `portal/shared/`.)

In the consumer's `tsconfig.json`, the existing `@shared/*` path alias (mapping to `../shared/*`) is preserved for back-compat. Code can use either:

```ts
// Path-aliased (legacy; works for B10):
import { Skeleton } from "@shared/components/skeleton";

// Package-named (multi-app-ready; preferred for new code):
import { Skeleton } from "@infinityrx/portal-shared/components/skeleton";
```

---

## Adding new exports

For new modules in this package:

1. Place under the appropriate subdir (`components/`, `hooks/`, `lib/`, `types/`, `design-system/`).
2. If server-safe (no React context, no client-only APIs), consider re-exporting from `index.ts` for the root barrel.
3. If client-only (uses `useState`, `useEffect`, etc.), DO NOT re-export from `index.ts` — leave subpath-only access. The root barrel is server-safe by contract.
4. If introducing a new external dependency, add it to `dependencies` in `portal/shared/package.json` (or `peerDependencies` if it's React-context/singleton-bearing). Do NOT rely on the consumer's transitive resolution.

---

## Adding a new portal app

Future portal apps (e.g., `portal/member/`, `portal/manufacturer/`) add themselves under the workspace root:

1. Create `portal/member/package.json` declaring `"@infinityrx/portal-shared": "*"` as a dependency.
2. Add `"member"` to the `workspaces` array in `portal/package.json`.
3. Set `transpilePackages: ["@infinityrx/portal-shared"]` in the new app's `next.config.ts`.
4. Run `npm install` from `portal/`.

The new app immediately has access to all of `@infinityrx/portal-shared`'s exports.

---

## What's NOT in this package

- Operator-specific routes, components, pages — those live in `portal/operator/app/`.
- Backend code (modules/) — different repo subtree, different tech stack (Python/FastAPI).

---

## References

- Wave B10 charter: `Werkbench/projects/infinityrx-platform/waves/B10/charter.md` (LOCKED v3)
- Wave B10 plan: `Werkbench/projects/infinityrx-platform/waves/B10/plan.md` (LOCKED v6)
- Next.js `transpilePackages` docs: https://nextjs.org/docs/app/api-reference/config/next-config-js/transpilePackages
- npm workspaces docs: https://docs.npmjs.com/cli/v10/using-npm/workspaces
