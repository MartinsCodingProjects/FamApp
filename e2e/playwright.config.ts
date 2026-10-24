// Playwright E2E against a local instance (`make e2e`, CI job `e2e`). Needs a browser, so it
// runs in CI or on the notebook, not on the home server (BUILDPLAN A6).
import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.E2E_PORT ?? 5174);

export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never", outputFolder: "../e2e-results/html" }]] : "list",
  outputDir: "../e2e-results/artifacts",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: "retain-on-failure",
    locale: "de-DE",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "../tools/e2e-server.sh",
    url: `http://127.0.0.1:${port}/setup`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: { E2E_PORT: String(port) },
  },
});
