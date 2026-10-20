import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const root = path.resolve(__dirname, "../..");
const python = path.join(root, process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python");
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  use: { baseURL: "http://127.0.0.1:3100", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    { command: `"${python}" scripts/serve_smoke_api.py`, cwd: root, url: "http://127.0.0.1:8001/api/v1/health/ready", reuseExistingServer: false, timeout: 60_000 },
    { command: "pnpm dev --port 3100", url: "http://127.0.0.1:3100/login", reuseExistingServer: false, timeout: 120_000,
      env: { INTERNAL_API_URL: "http://127.0.0.1:8001", NEXT_TELEMETRY_DISABLED: "1" } },
  ],
});
