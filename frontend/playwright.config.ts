import { existsSync } from "fs";
import { resolve } from "path";
import { defineConfig, devices } from "@playwright/test";

// Prefer the backend's virtualenv interpreter locally (so the e2e server gets
// the project's pinned deps, not whatever global `python` resolves to). On CI
// there is no venv — requirements are installed into the runner's python — so
// we fall back to `python`. An absolute path is used so the shell resolves it
// on Windows regardless of the webServer cwd.
const venvPy =
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python";
const venvPath = resolve(process.cwd(), "../backend/.venv", venvPy);
const backendPython = existsSync(venvPath) ? `"${venvPath}"` : "python";

/**
 * End-to-end smoke test config (Task 2).
 *
 * Brings up the real stack and drives it through a browser:
 *   1. the FastAPI backend on an ephemeral SQLite DB with a seeded admin
 *      (`app.scripts.serve_e2e` — no shell operators, so identical on
 *      Windows and Linux CI), and
 *   2. the Next.js frontend, proxying /api to that backend.
 *
 * Locally, `reuseExistingServer` lets you run against servers you already have
 * up; in CI both are started fresh.
 */
const BACKEND_PORT = 8000;
const FRONTEND_PORT = 3000;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  timeout: 60_000,
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command: `${backendPython} -m app.scripts.serve_e2e`,
      cwd: "../backend",
      url: `http://localhost:${BACKEND_PORT}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        DATABASE_URL: "sqlite+aiosqlite:///./e2e.db",
        NEO4J_ENABLED: "false",
        SEARCH_BACKEND: "inmemory",
        AI_PROVIDER: "heuristic",
        E2E_BACKEND_PORT: String(BACKEND_PORT),
        // Pin admin creds so the smoke test is hermetic regardless of any local
        // .env (and independent of which CWD pydantic resolves .env from).
        FIRST_ADMIN_EMAIL: "admin@atlas.example.com",
        FIRST_ADMIN_PASSWORD: "ChangeMe123!",
      },
    },
    {
      command: "npm run dev",
      url: `http://localhost:${FRONTEND_PORT}/login`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { BACKEND_URL: `http://localhost:${BACKEND_PORT}` },
    },
  ],
});
