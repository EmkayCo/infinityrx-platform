import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    testTimeout: 15000,
    setupFiles: ["./tests/setup.ts"],
    include: [
      "tests/unit/**/*.test.{ts,tsx}",
      "tests/integration/**/*.test.{ts,tsx}",
      // Wave B10 W1.14b: Vite-layer regression coverage for the
      // @infinityrx/portal-shared package barrel + subpath imports.
      // (NOT the SC #17 proof — that's the Next-served route at
      // /api/b10-canary, hit by W1.13's run-canary-server.ps1.)
      "tests/canary/**/*.test.{ts,tsx}",
    ],
    exclude: [
      "tests/e2e/**",
      "node_modules/**",
      ".next/**",
      // store.test.ts requires real data files (sources/*.xlsx, public/data/aggregated/*.json)
      // that are not committed to the repo — excluded from standard unit test run.
      "tests/unit/lib/store.test.ts",
    ],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json-summary"],
      include: [
        "app/**/*.{ts,tsx}",
        "components/**/*.{ts,tsx}",
        "lib/**/*.{ts,tsx}",
      ],
      exclude: [
        "**/*.test.*",
        "**/*.d.ts",
        "**/mock-data/**",
        ".next/**",
      ],
    },
    // Deduplicate React across the monorepo. Both portal/operator/node_modules
    // and portal/shared/node_modules contain React. Vitest picks up the wrong
    // instance, causing null-dispatcher hook errors. server.deps.inline forces
    // the module through Vite's transformer which respects the resolve.alias map.
    // Also: lucide-react ^1.8 uses useContext internally which breaks in jsdom
    // under React 19 non-act renders — use the hand-rolled stub.
    server: {
      deps: {
        inline: ["lucide-react"],
      },
    },
    alias: {
      "lucide-react": path.resolve(__dirname, "__mocks__/lucide-react.ts"),
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
      "@shared": path.resolve(__dirname, "../shared"),
      // Wave B10 (2026-05-12): under npm workspaces, react/react-dom are
      // hoisted to portal/node_modules/ (not portal/operator/node_modules/).
      // Pre-B10 these aliases pointed to the operator-nested copy, which
      // was a workaround for portal/shared/node_modules/react existing as
      // a duplicate. W1 verified shared no longer has its own react copy
      // (W1.10 single-instance check passed), so dedupe + workspace
      // hoisting + the path correction below handle singleton correctness.
      "react": path.resolve(__dirname, "../node_modules/react"),
      "react/jsx-runtime": path.resolve(__dirname, "../node_modules/react/jsx-runtime"),
      "react/jsx-dev-runtime": path.resolve(__dirname, "../node_modules/react/jsx-dev-runtime"),
      "react-dom": path.resolve(__dirname, "../node_modules/react-dom"),
      "react-dom/client": path.resolve(__dirname, "../node_modules/react-dom/client"),
    },
    dedupe: ["react", "react-dom"],
  },
});
