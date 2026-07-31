import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

/**
 * Vitest configuration for the web application.
 *
 * Deliberately minimal. No jsdom environment and no React Testing Library yet:
 * every component in the app is currently a Server Component with no
 * interactivity, so a DOM test environment would be dependencies added for
 * tests that do not exist (CLAUDE.md §28). Component testing arrives with the
 * first Client Component, at STEP-15.
 */
export default defineConfig({
  test: {
    // Node, not jsdom — see above.
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    // An empty suite must exit 0. A pipeline that goes red because nothing was
    // written yet teaches everyone to ignore it (STEP-06).
    passWithNoTests: true,
  },
  resolve: {
    // Mirrors the "@/*" path alias in tsconfig.json. Vitest does not read
    // tsconfig paths on its own, so a test importing "@/lib/env" would fail to
    // resolve without this.
    //
    // fileURLToPath, not URL.pathname: on Windows the latter yields
    // "/D:/path/src", with a leading slash that does not resolve.
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});
