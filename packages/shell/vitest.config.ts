import { defineConfig } from "vitest/config";
import { resolve } from "node:path";

export default defineConfig({
  resolve: {
    alias: {
      // Workspace packages that may not be built yet — point vitest at their src.
      // This avoids "Failed to resolve entry for package" errors in test runs.
      "@infinityrx/ui": resolve(__dirname, "../ui/src/index.ts"),
      "@infinityrx/qa-harness": resolve(__dirname, "../qa-harness/src/index.ts"),
      "@infinityrx/auth": resolve(__dirname, "../auth/src/index.ts"),
      "@infinityrx/contract": resolve(__dirname, "../contract/src/index.ts"),
      // server-only: mock package — tests mock this explicitly but the resolver
      // needs a real file to satisfy Vite's module resolution before mocking fires.
      "server-only": resolve(__dirname, "src/__mocks__/server-only.ts"),
      // next/* modules: not installed in this package (peerDeps); provide stubs so
      // Vite doesn't fail on import analysis before vi.mock() intercepts.
      "next/navigation": resolve(__dirname, "src/__mocks__/next-navigation.ts"),
      "next/server": resolve(__dirname, "src/__mocks__/next-server.ts"),
    },
  },
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx", "src/__tests__/**/*.test.ts", "src/__tests__/**/*.test.tsx"],
    environment: "happy-dom",
    globals: true,
  },
});
