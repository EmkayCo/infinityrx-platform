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
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
      "@shared": path.resolve(__dirname, "../shared"),
      // Force a single React instance — shared/ has its own node_modules/react
      // which causes "Cannot read properties of null (reading 'useState')" in jsdom.
      react: path.resolve(__dirname, "node_modules/react"),
      "react-dom": path.resolve(__dirname, "node_modules/react-dom"),
      "react/jsx-runtime": path.resolve(__dirname, "node_modules/react/jsx-runtime"),
      "lucide-react": path.resolve(__dirname, "node_modules/lucide-react"),
    },
    dedupe: ["react", "react-dom", "lucide-react"],
  },
});
