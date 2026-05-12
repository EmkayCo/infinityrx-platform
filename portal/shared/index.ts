/**
 * @infinityrx/portal-shared — barrel export.
 *
 * Source-mode TypeScript package consumed by Next.js apps via
 * `transpilePackages: ["@infinityrx/portal-shared"]` in their
 * next.config.ts. See README.md for the multi-app pattern.
 *
 * Consumers SHOULD prefer subpath imports for tree-shaking:
 *   import { useSse } from "@infinityrx/portal-shared/hooks/use-sse";
 *   import { Skeleton } from "@infinityrx/portal-shared/components/skeleton";
 *
 * The root barrel re-exports a small server-safe surface for
 * convenience and for the W1.14 Next-runtime canary route to assert
 * `Object.keys(root).length > 0` (proves transpilePackages is wired).
 *
 * Adding to this barrel: keep server-safe ONLY (no React-context-using
 * client components, no `"use client"` modules). Client-side helpers
 * stay accessible via subpath imports.
 */

// Server-safe utility functions (string formatting, money formatting, etc.)
export * from "./lib/format";

// Server-safe constants (API URLs, feature flags, ICP nav config)
export * from "./lib/constants";
