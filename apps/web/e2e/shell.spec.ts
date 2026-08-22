import { expect, test } from "./support";

/**
 * The shared shell's structure — the contract independent review found missing.
 *
 * The first implementation put a full-width canvas header above a rail that
 * held only four links. The plane therefore began halfway down the screen and
 * read as an empty black block, and the navigation's own chrome — the product
 * identity, the signed-in user — sat on the canvas rather than on the plane it
 * belongs to. These assertions are what stop that arrangement returning.
 */

/** A resolved semantic token, as the browser computes it. */
async function token(page: import("@playwright/test").Page, name: string): Promise<string> {
  return page.evaluate((property) => {
    const probe = document.createElement("div");
    probe.style.color = `var(${property})`;
    document.body.append(probe);
    const value = getComputedStyle(probe).color;
    probe.remove();
    return value;
  }, name);
}

test.describe("the desktop navigation plane", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("is one full-height column starting at the top of the viewport", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();

    const rail = await page.locator("aside").boundingBox();

    expect(rail?.y, "the rail does not start at the top of the viewport").toBe(0);
    expect(rail?.height, "the rail does not span the viewport height").toBe(800);
  });

  test("has no detached full-width header above it", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();

    // The header is mobile-only now. Present in the DOM, absent from the layout.
    await expect(page.locator("header")).toBeHidden();
  });

  test("holds identity, destinations and the signed-in user, in that order", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();

    const rail = page.locator("aside");

    await expect(rail.getByRole("link", { name: "ProjectOne" })).toBeVisible();
    await expect(rail.getByRole("navigation", { name: "Main" })).toBeVisible();
    await expect(rail.getByRole("button", { name: "Sign out" })).toBeVisible();

    // Top to bottom, and vertically ordered — not merely all present.
    const identity = await rail.getByRole("link", { name: "ProjectOne" }).boundingBox();
    const nav = await rail.getByRole("navigation", { name: "Main" }).boundingBox();
    const signOut = await rail.getByRole("button", { name: "Sign out" }).boundingBox();

    expect(identity!.y).toBeLessThan(nav!.y);
    expect(nav!.y).toBeLessThan(signOut!.y);
  });

  test("paints itself with the nav-* family and nothing else", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();

    // ADR-003 Decision 3: a component rendering inside the navigation plane
    // references the `nav-*` family, and one rendering on the canvas never
    // does. The rail's own surface and the text on it are both checked,
    // because the failure this catches is a canvas token leaking onto a dark
    // plane — which looks fine in one theme and fails contrast in the other.
    const navSurface = await token(page, "--color-nav-surface");
    const onNavMuted = await token(page, "--color-text-on-nav-muted");
    const accentOnNav = await token(page, "--color-accent-on-nav");

    const rail = page.locator("aside");

    await expect(rail).toHaveCSS("background-color", navSurface);
    await expect(rail.getByRole("button", { name: "Sign out" })).toHaveCSS("color", onNavMuted);
    await expect(rail.getByRole("link", { name: "Dashboard" })).toHaveCSS("color", accentOnNav);
  });

  test("keeps the signed-in address legible rather than compressed", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();

    const address = page.locator("aside [title]").first();

    await expect(address).toBeVisible();

    const clipped = await address.evaluate(
      (element) => element.scrollWidth > element.clientWidth + 1,
    );

    expect(clipped, "the signed-in address is truncated in the rail").toBe(false);
  });
});

test.describe("exactly one navigation landmark is exposed", () => {
  test("at desktop it is the rail", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();

    await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(1);
    await expect(page.getByRole("button", { name: "Menu" })).toBeHidden();
  });

  test("at mobile it is the drawer's, and only while it is open", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();

    // Closed: the rail is display:none and the drawer's nav is inside a closed
    // <dialog>, so neither is in the accessibility tree.
    await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(0);

    await page.getByRole("button", { name: "Menu" }).click();
    await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(1);
  });
});
