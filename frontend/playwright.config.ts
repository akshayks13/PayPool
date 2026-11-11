import { defineConfig } from "@playwright/test";
import path from "node:path";
import os from "node:os";

const database = path.join(os.tmpdir(), `paypool-browser-${process.pid}.db`);
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  workers: 1,
  fullyParallel: false,
  use: { baseURL: "http://localhost:3100", trace: "retain-on-failure" },
  webServer: [
    {
      command:
        ".venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8100",
      cwd: path.resolve(__dirname, "../backend"),
      url: "http://127.0.0.1:8100/health",
      timeout: 60_000,
      env: {
        DATABASE_URL: `sqlite:///${database}`,
        PAYPOOL_POSTGIS: "false",
        PAYPOOL_DEMO_MODE: "true",
        PAYPOOL_PAYMENT_PROVIDER: "demo",
        PAYPOOL_LLM_PROVIDER: "deterministic",
        PAYPOOL_ENABLE_LEGACY_API: "false",
        PAYPAL_LOGIN_ENABLED: "false",
        PAYPOOL_FRONTEND_URL: "http://localhost:3100",
      },
    },
    {
      command: "npm run dev -- --port 3100 --hostname localhost",
      url: "http://localhost:3100",
      timeout: 90_000,
      env: {
        API_BASE_URL: "http://127.0.0.1:8100",
        NEXT_TELEMETRY_DISABLED: "1",
      },
    },
  ],
});
