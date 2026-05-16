import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      // In the worktree, packages/contract/dist/ may not exist (tsc -b not run yet).
      // Point vitest at the contract source directory so tests resolve TS source directly.
      "@infinityrx/contract": resolve(here, "../../contract/src/index.ts"),
    },
  },
  test: {
    include: ["__tests__/**/*.test.ts"],
    environment: "node",
  },
});
