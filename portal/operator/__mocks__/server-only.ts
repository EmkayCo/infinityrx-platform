/**
 * No-op stub for the Next.js "server-only" package.
 *
 * In production, "server-only" throws when imported outside an RSC/edge
 * context. Vitest runs in jsdom -- this stub suppresses the guard so shell
 * modules that import "server-only" (e.g. qa-mode-middleware.ts) can be
 * unit-tested. The alias is wired in vitest.config.ts test.alias.
 */
export {};
