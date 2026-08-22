import { test as base, type Page } from "@playwright/test";

import { NAV_ITEMS } from "../src/lib/navigation";
import { ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE } from "../src/lib/session-cookies";
import { THEME_STORAGE_KEY } from "../src/lib/theme";

/**
 * Shared setup for the browser suite.
 *
 * Constants are **imported from the application** rather than restated here.
 * A spec that hardcodes `"projectone_access_token"` or its own copy of the
 * navigation list still passes after the application renames either one, which
 * makes it a test of the test rather than of the product.
 */

export { NAV_ITEMS, THEME_STORAGE_KEY };

/** Every route the authenticated shell serves today, with its `h1`. */
export const SHELL_ROUTES = [
  { path: "/dashboard", heading: "Dashboard", template: "cockpit" },
  { path: "/projects", heading: "Projects", template: "workbench" },
  { path: "/projects/22222222-2222-2222-2222-222222222222", heading: "E2E Project", template: "workbench" },
  { path: "/chat", heading: "AI Chat", template: "workbench" },
  { path: "/settings", heading: "Settings", template: "workbench" },
] as const;

/** The public surfaces, which carry the Focus template and no shell chrome. */
export const PUBLIC_ROUTES = [
  { path: "/sign-in", template: "focus" },
  { path: "/sign-up", template: "focus" },
] as const;

/**
 * Sign the browser context in.
 *
 * Cookies are injected rather than obtained by driving the sign-in form,
 * because the stub API issues no real credentials. This exercises the
 * production gate rather than bypassing it: the proxy still requires a session
 * cookie to be present, and `requireProfile()` still presents the token to the
 * API, which still refuses a request that arrives without one.
 *
 * `secure: false` because the suite runs over http on localhost. The
 * application's own cookie writer still sets `secure` in production — this
 * writes a cookie, it does not change how the application writes one.
 */
export async function signIn(page: Page): Promise<void> {
  await page.context().addCookies(
    [ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE].map((name) => ({
      name,
      value: "e2e-session-token",
      domain: "127.0.0.1",
      path: "/",
      httpOnly: true,
      secure: false,
      sameSite: "Lax" as const,
    })),
  );
}

/**
 * A test that starts signed in.
 *
 * An `auto` fixture rather than an override of `page`: overriding erases the
 * built-in test *options* from the resulting type, and `test.use({ viewport })`
 * / `test.use({ reducedMotion })` then stop type-checking. This composes
 * instead of replacing, so every Playwright option stays available.
 */
export const test = base.extend<{ signedIn: void }>({
  signedIn: [
    async ({ page }, use) => {
      await signIn(page);
      await use();
    },
    { auto: true },
  ],
});

export { expect } from "@playwright/test";
