// src/__mocks__/sonner.ts
// Minimal stub for the sonner toast library.
// Used by vitest alias so ingestion components can import 'sonner'
// without the package being installed in this workspace.
// Tests that need to assert on toast calls use vi.mock("sonner", ...) to
// replace this stub with a spy-equipped implementation.

export const toast = {
  success: (_message: string, _opts?: unknown) => undefined,
  error: (_message: string, _opts?: unknown) => undefined,
  warning: (_message: string, _opts?: unknown) => undefined,
  info: (_message: string, _opts?: unknown) => undefined,
};

export default toast;
