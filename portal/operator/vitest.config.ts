import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: [
      "tests/unit/**/*.test.{ts,tsx}",
      "tests/integration/**/*.test.{ts,tsx}",
    ],
    exclude: ["tests/e2e/**", "node_modules/**", ".next/**"],
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
      // Force all React imports through the single operator-level copy.
      "react": path.resolve(__dirname, "node_modules/react"),
      "react/jsx-runtime": path.resolve(__dirname, "node_modules/react/jsx-runtime"),
      "react/jsx-dev-runtime": path.resolve(__dirname, "node_modules/react/jsx-dev-runtime"),
      "react-dom": path.resolve(__dirname, "node_modules/react-dom"),
      "react-dom/client": path.resolve(__dirname, "node_modules/react-dom/client"),
    },
    dedupe: ["react", "react-dom"],
  },
});
