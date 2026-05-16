// Mock for the `server-only` package used in vitest context.
// In production Next.js, `server-only` prevents client-side imports.
// In vitest (happy-dom), it's a no-op — tests mock it explicitly via vi.mock().
export {};
