import { expect, test } from "./support";

/**
 * Proposition 6 — the mobile drawer's focus contract.
 *
 * [[Design System]] §9a rule 2 has required this since it was written: the
 * drawer traps focus while open, closes on `Escape`, and returns focus to the
 * control that opened it. Until this step the shell had no drawer at all, so
 * the rule described nothing.
 *
 * A drawer whose focus escapes is a drawer a keyboard user can lose inside a
 * page they cannot see, which is why every clause is asserted separately
 * rather than inferred from the drawer merely opening.
 */

// Below `md` (768px), where the rail is not persistent.
test.use({ viewport: { width: 375, height: 812 } });

async function focusedText(page: import("@playwright/test").Page) {
  return page.evaluate(() => (document.activeElement?.textContent ?? "").trim());
}

test.describe("mobile drawer", () => {
  test("the rail is replaced by a trigger at a narrow viewport", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();

    await expect(page.getByRole("button", { name: "Menu" })).toBeVisible();

    // Exactly one navigation landmark is exposed at any width: the rail is
    // display:none here, and the drawer's is inside a closed <dialog>.
    await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(0);
  });

  test("traps focus, closes on Escape, and returns focus to the trigger", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();

    const trigger = page.getByRole("button", { name: "Menu" });
    await trigger.click();

    const drawer = page.getByRole("dialog");
    await expect(drawer).toBeVisible();
    await expect(drawer.getByRole("navigation", { name: "Main" })).toBeVisible();

    // --- the trap -------------------------------------------------------
    // Tab far enough to wrap past the last control several times over. If
    // focus could escape, it would reach the shell behind the drawer — the
    // skip link, the trigger, the brand, Sign out — well inside this.
    //
    // The assertion is "never reaches a control outside the drawer" rather
    // than "every stop is inside the drawer", because Chromium wraps a modal's
    // focus cycle THROUGH `<body>`: the observed order is the four
    // destinations, then `<body>`, then Close, then round again. `<body>` is
    // the wrap point, not an escape — nothing outside the dialog is reachable
    // from it, and the next Tab lands back inside.
    const trail: { text: string; inDialog: boolean; isBody: boolean }[] = [];

    for (let step = 0; step < 12; step += 1) {
      await page.keyboard.press("Tab");
      trail.push(
        await page.evaluate(() => {
          const element = document.activeElement;

          return {
            text: (element?.textContent ?? "").trim().slice(0, 30),
            inDialog: element !== null && element.closest("dialog") !== null,
            isBody: element === document.body,
          };
        }),
      );
    }

    const escaped = trail.filter((stop) => !stop.inDialog && !stop.isBody);
    expect(escaped, `focus escaped the open drawer to ${escaped.map((s) => s.text).join(", ")}`).toEqual([]);

    // And it really did cycle: every control in the drawer was reached.
    // Derived from the drawer itself rather than written down, so a control
    // added to it later has to be reachable or this fails — the same rule the
    // route traversal proof applies to the page.
    const controls = await drawer.evaluate((dialog) =>
      [...dialog.querySelectorAll<HTMLElement>("a[href], button, input, select, textarea")]
        .filter((element) => element.getClientRects().length > 0)
        .map((element) => (element.textContent ?? "").trim().slice(0, 30)),
    );

    expect(controls.length, "the drawer has almost no controls — did it render?").toBeGreaterThan(4);

    const reached = new Set(trail.filter((stop) => stop.inDialog).map((stop) => stop.text));
    expect(reached).toEqual(new Set(controls));

    // --- Escape ---------------------------------------------------------
    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden();

    // --- focus return ---------------------------------------------------
    // Not "focus is somewhere sensible": the control that opened it. Anything
    // else strands the user at the top of the document.
    expect(await focusedText(page)).toBe("Menu");
    await expect(trigger).toBeFocused();
  });

  test("carries the same three regions as the rail", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
    await page.getByRole("button", { name: "Menu" }).click();

    const drawer = page.getByRole("dialog");

    // Identity, destinations, signed-in user — the rail's regions at a
    // different width, not a reduced version of them. Sign-out in particular
    // lives here rather than in the mobile header, where a real address had to
    // be squeezed into an unreadable fragment beside a trigger and a wordmark.
    await expect(drawer.getByText("ProjectOne", { exact: true })).toBeVisible();
    await expect(drawer.getByRole("navigation", { name: "Main" })).toBeVisible();
    await expect(drawer.getByRole("button", { name: "Sign out" })).toBeVisible();

    // The address is readable, not clipped to a fragment.
    const address = drawer.locator("[title]").first();
    await expect(address).toBeVisible();

    const clipped = await address.evaluate(
      (element) => element.scrollWidth > element.clientWidth + 1,
    );

    expect(clipped, "the signed-in address is truncated in the drawer").toBe(false);
  });

  test("the mobile header does not carry the signed-in address", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();

    // It moved to the drawer deliberately. A header that carries it at 375px
    // compresses it to nothing, which is what the correction removed.
    await expect(page.locator("header")).toBeVisible();

    // The drawer is a descendant of `<header>` in the DOM, so a plain locator
    // would reach into it and find exactly the content this asserts is absent.
    // The comparison is therefore against the header's own chrome, with the
    // dialog subtree removed.
    const chrome = await page.evaluate(() => {
      const header = document.querySelector("header");

      if (header === null) {
        return null;
      }

      const withoutDrawer = header.cloneNode(true) as HTMLElement;
      for (const dialog of withoutDrawer.querySelectorAll("dialog")) {
        dialog.remove();
      }

      return (withoutDrawer.textContent ?? "").trim();
    });

    expect(chrome, "the mobile header still carries the signed-in address").not.toContain("@");
    expect(chrome, "the mobile header still carries the sign-out control").not.toContain("Sign out");

    // What it does carry: the drawer trigger and the product identity.
    expect(chrome).toContain("Menu");
    expect(chrome).toContain("ProjectOne");
  });

  test("choosing a destination navigates and closes the drawer", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
    await page.getByRole("button", { name: "Menu" }).click();

    const drawer = page.getByRole("dialog");
    await drawer.getByRole("link", { name: "Projects" }).click();

    await expect(page.getByRole("heading", { level: 1, name: "Projects" })).toBeVisible();

    // A drawer left open over the page it just navigated to is one the user
    // has to dismiss twice.
    await expect(drawer).toBeHidden();
    await expect(page.getByRole("button", { name: "Menu" })).toBeFocused();
  });

  test("the Close control dismisses it and returns focus too", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();

    const trigger = page.getByRole("button", { name: "Menu" });
    await trigger.click();

    await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();

    await expect(page.getByRole("dialog")).toBeHidden();
    await expect(trigger).toBeFocused();
  });
});
