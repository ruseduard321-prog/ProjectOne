import { defineConfig, devices } from "@playwright/test";

/**
 * Browser testing, adopted by [[ADR-007 Product Experience Blueprint Authority
 * and Adoption Boundary]] Decision 13 and configured here by STEP-31a.
 *
 * ## Why a browser at all
 *
 * The repository had no browser in its test harness: Vitest runs with
 * `environment: "node"`, component tests use `renderToStaticMarkup`, and client
 * behaviour is asserted by reading source text. For a step whose subject is
 * focus, keyboard, theme and reflow, reading source text is not a proxy for the
 * behaviour — it is an assertion that the code *looks* correct. jsdom was
 * rejected for the same reason and one more: it has no layout engine, so it
 * cannot answer a reflow or overflow question at all.
 *
 * ## Why `retries: 0`
 *
 * A test retried until it passes is not a proof ([[CLAUDE|CLAUDE.md]] §20a).
 * Instability here is fixed, or the test is removed and reported — never
 * silenced by a retry budget. The same reasoning rules out arbitrary waits: the
 * specs use Playwright's own waiting on state, never `waitForTimeout`.
 *
 * ## Why two servers
 *
 * Every fetch this application makes runs on the server, so a browser-side
 * route mock cannot intercept one. `e2e/stub-api.mjs` answers on a socket
 * instead, and the application is built pointing at it. `NEXT_PUBLIC_*`
 * variables are inlined at build time, which is why the build happens here with
 * the test configuration rather than reusing the pipeline's production build.
 */

const STUB_API_PORT = 3101;
const WEB_PORT = 3100;

const STUB_API_URL = `http://127.0.0.1:${STUB_API_PORT}`;
const BASE_URL = `http://127.0.0.1:${WEB_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  // `*.spec.ts`, deliberately not `*.test.ts`: Vitest's `include` claims
  // `src/**/*.test.ts`, and two runners collecting the same file is a
  // confusing failure the first time someone hits it.
  testMatch: /.*\.spec\.ts/,

  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],

  use: {
    baseURL: BASE_URL,
    // Kept only for a failing run: an artefact per test would make the
    // pipeline slower and the report harder to read for no diagnostic gain.
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: [
    {
      command: "node e2e/stub-api.mjs",
      url: `${STUB_API_URL}/__ready`,
      reuseExistingServer: !process.env.CI,
      stdout: "pipe",
      env: { PROJECTONE_STUB_API_PORT: String(STUB_API_PORT) },
    },
    {
      command: `npm run build && npm run start -- --port ${WEB_PORT}`,
      // `/health` is a public route that renders without a session, so
      // readiness is answered without the suite having to authenticate first.
      url: `${BASE_URL}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      stdout: "pipe",
      env: {
        NEXT_PUBLIC_PROJECTONE_ENVIRONMENT: "development",
        NEXT_PUBLIC_PROJECTONE_API_URL: STUB_API_URL,
      },
    },
  ],
});
