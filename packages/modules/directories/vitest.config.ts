import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      "@infinityrx/contract": resolve(here, "../../contract/src/index.ts"),
      "@infinityrx/auth": resolve(here, "../../auth/src/index.ts"),
      "@infinityrx/ui": resolve(here, "../../ui/src/index.ts"),
      "@infinityrx/shell": resolve(here, "../../shell/src/index.ts"),
      "@infinityrx/qa-harness": resolve(here, "../../qa-harness/src/index.ts"),
      // next/* not installed in this package; provide stubs so Vite resolves
      // imports before vi.mock() intercepts them in BFF tests.
      "next/server": resolve(here, "src/__mocks__/next-server.ts"),
    },
  },
  test: {
    include: ["tests/**/*.test.{ts,tsx}", "src/**/*.test.{ts,tsx}"],
    environment: "happy-dom",
    passWithNoTests: true,
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/surfaces/**", "src/ingestion/**", "src/quality/**", "src/audit/**"],
    },
  },
});
