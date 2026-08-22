import { expect, SHELL_ROUTES, test } from "./support";

/**
 * Proposition 10 — narrow-viewport reflow and horizontal overflow.
 *
 * [[Design System]] §9a rule 4 is unambiguous: *the page never scrolls
 * horizontally*. jsdom cannot answer this at all — it has no layout engine —
 * which is one of the two reasons the browser layer exists.
 *
 * 320px is included deliberately. It is below every declared breakpoint and is
 * the width §9a rule 5 has in mind when it says no layout is "desktop-only".
 */

const VIEWPORTS = [
  { name: "320 — the floor", width: 320, height: 720 },
  { name: "375 — a phone", width: 375, height: 812 },
  { name: "640 — sm", width: 640, height: 800 },
  { name: "768 — md, the rail appears", width: 768, height: 800 },
  { name: "1024 — lg", width: 1024, height: 800 },
  { name: "1280 — xl", width: 1280, height: 900 },
] as const;

test.describe("reflow", () => {
  for (const viewport of VIEWPORTS) {
    for (const route of SHELL_ROUTES) {
      test(`${route.path} does not scroll horizontally at ${viewport.name}`, async ({ page }) => {
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        await page.goto(route.path);
        await expect(page.getByRole("heading", { level: 1, name: route.heading })).toBeVisible();

        const overflow = await page.evaluate(() => {
          const root = document.documentElement;

          // Sub-pixel layout rounding can leave a fraction; a real overflow is
          // never a fraction of a pixel, so the tolerance keeps this from
          // being the flaky test that teaches everyone to ignore the suite.
          return {
            scrollWidth: root.scrollWidth,
            clientWidth: root.clientWidth,
            widest:
              [...document.querySelectorAll<HTMLElement>("body *")]
                .filter((element) => element.getBoundingClientRect().right > root.clientWidth + 1)
                .map((element) => `${element.tagName.toLowerCase()}.${element.className}`)
                .at(0) ?? null,
          };
        });

        expect(
          overflow.scrollWidth,
          `content overflows; first offender: ${overflow.widest ?? "unknown"}`,
        ).toBeLessThanOrEqual(overflow.clientWidth + 1);
      });
    }
  }

  test("the rail is persistent from md and a drawer below it", async ({ page }) => {
    // §9a rule 2, and §9a rule 6: content hidden at a breakpoint is reachable
    // another way — the destinations move into the drawer, they do not vanish.
    await page.setViewportSize({ width: 767, height: 800 });
    await page.goto("/dashboard");
    await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Menu" })).toBeVisible();

    await page.setViewportSize({ width: 768, height: 800 });
    await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Menu" })).toBeHidden();
  });

  test("touch targets clear 44px on a coarse pointer", async ({ page }) => {
    // §9.1 rule 9. The rail is where a thumb lands first on a phone.
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Menu" }).click();

    const links = page.getByRole("dialog").getByRole("link");

    for (const link of await links.all()) {
      const box = await link.boundingBox();
      expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
    }
  });
});
