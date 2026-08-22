import { expect, test, THEME_STORAGE_KEY } from "./support";

/**
 * Proposition 7 — explicit theme selection persists, wins over the system
 * preference in BOTH directions, and never flashes the wrong theme.
 *
 * The flash is the part worth being careful about. Asserting the final state
 * after load would pass against an implementation that applies the theme in an
 * effect, which is exactly the defect: the user sees the system theme for one
 * frame and their own for the next, on every full page load. So the assertions
 * below read the theme at `DOMContentLoaded` and at the first animation frame,
 * before anything React does.
 */

const DARK_BACKGROUND = "rgb(15, 14, 13)"; // --ink-950
const LIGHT_BACKGROUND = "rgb(250, 246, 238)"; // --ivory-100

/** Persist an explicit choice before the first navigation of the context. */
async function chooseTheme(page: import("@playwright/test").Page, theme: "light" | "dark") {
  await page.addInitScript(
    ([key, value]) => {
      window.localStorage.setItem(key as string, value as string);
    },
    [THEME_STORAGE_KEY, theme],
  );
}

/** Record what the document looked like before React could touch it. */
async function recordFirstPaint(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    const readings: { atDomContentLoaded?: string | null; atFirstFrame?: string | null } = {};

    document.addEventListener("DOMContentLoaded", () => {
      readings.atDomContentLoaded = document.documentElement.getAttribute("data-theme");
    });

    requestAnimationFrame(() => {
      readings.atFirstFrame = getComputedStyle(document.body).backgroundColor;
    });

    (window as unknown as { __themeReadings: typeof readings }).__themeReadings = readings;
  });
}

test.describe("explicit theme", () => {
  test("dark survives a reload and a client-side navigation", async ({ page }) => {
    await chooseTheme(page, "dark");
    await page.goto("/dashboard");

    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.locator("body")).toHaveCSS("background-color", DARK_BACKGROUND);

    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Settings" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Settings" })).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.locator("body")).toHaveCSS("background-color", DARK_BACKGROUND);
  });

  test("dark wins over a system preference of light", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await chooseTheme(page, "dark");
    await page.goto("/dashboard");

    await expect(page.locator("body")).toHaveCSS("background-color", DARK_BACKGROUND);
  });

  test("light wins over a system preference of dark", async ({ page }) => {
    // The direction that breaks first. An unguarded `prefers-color-scheme`
    // media query overrides an explicit light choice, which makes the control
    // a no-op in exactly one direction — the hardest kind of bug to notice.
    await page.emulateMedia({ colorScheme: "dark" });
    await chooseTheme(page, "light");
    await page.goto("/dashboard");

    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await expect(page.locator("body")).toHaveCSS("background-color", LIGHT_BACKGROUND);
  });

  test("no explicit choice follows the system", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/dashboard");

    await expect(page.locator("html")).not.toHaveAttribute("data-theme", /.*/);
    await expect(page.locator("body")).toHaveCSS("background-color", DARK_BACKGROUND);

    await page.emulateMedia({ colorScheme: "light" });
    await expect(page.locator("body")).toHaveCSS("background-color", LIGHT_BACKGROUND);
  });

  test("the chosen theme is applied before the first paint", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await recordFirstPaint(page);
    await chooseTheme(page, "dark");
    await page.goto("/dashboard");

    const readings = await page.evaluate(
      () => (window as unknown as { __themeReadings: Record<string, string | null> }).__themeReadings,
    );

    // Set while the document was still parsing — so before the body could be
    // painted, not merely before the test looked.
    expect(readings.atDomContentLoaded).toBe("dark");

    // And the very first frame was already dark, on a machine set to light.
    expect(readings.atFirstFrame).toBe(DARK_BACKGROUND);
  });

  test("the native color-scheme follows the token layer", async ({ page }) => {
    // Not a token, and the reason the change was worth making: without it the
    // caret, the selection highlight, the scrollbars and every native control
    // stay in the user agent's light styling under a full dark token set.
    //
    // `chooseTheme` is deliberately NOT used here: it installs an init script,
    // which re-runs on every navigation and would put the value back on the
    // reload below — so the second half of this test would assert nothing.
    await page.goto("/dashboard");
    await page.evaluate((key) => window.localStorage.setItem(key, "dark"), THEME_STORAGE_KEY);
    await page.reload();
    await expect(page.locator("html")).toHaveCSS("color-scheme", "dark");

    await page.evaluate((key) => window.localStorage.setItem(key, "light"), THEME_STORAGE_KEY);
    await page.reload();
    await expect(page.locator("html")).toHaveCSS("color-scheme", "light");
  });
});
