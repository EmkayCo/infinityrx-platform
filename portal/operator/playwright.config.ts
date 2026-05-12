import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for InfinityRx Operator Portal E2E tests.
 *
 * Tests run against the dev server. `webServer` auto-starts it and reuses an
 * existing instance if one is already running — important because `next dev`
 * is slow to boot.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false, // the dev server isn't built for parallel hits
  workers: 1, // single worker — Turbopack HMR gets confused under concurrent compiles
  retries: 0, // retries mask flaky issues; surface failures immediately in dev
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: "http://localhost:3000",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    actionTimeout: 10_000,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "npm run dev",
    port: 3000,
    // Wave B10 (2026-05-12 W4.4): reuseExistingServer defaults to FALSE so
    // every Playwright run boots a fresh server bound to the current commit
    // (codex ADVERSARIAL R1 A5 + R2 N3 absorption). Opt back into reuse via
    // PW_REUSE_SERVER=true for fast iteration when you know the dev server
    // is already serving the right code.
    reuseExistingServer: process.env.PW_REUSE_SERVER === "true",
    timeout: 60_000,
  },
});
