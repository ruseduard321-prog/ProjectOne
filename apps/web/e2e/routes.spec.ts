import { expect, NAV_ITEMS, PUBLIC_ROUTES, SHELL_ROUTES, test } from "./support";

/**
 * Propositions 1, 2, 3, 14 and 15 — the routes that exist, the navigation that
 * points at them, and the template that wraps them.
 *
 * The static suite already asserts that `NAV_ITEMS` matches the proxy matcher
 * and that exactly one item can be active for any shell route. What it cannot
 * assert is that any of those destinations actually *resolves*, or that the
 * shell renders what the route tree promises. That is what these do.
 */

test.describe("existing routes", () => {
  for (const route of SHELL_ROUTES) {
    test(`${route.path} renders its own heading`, async ({ page }) => {
      const response = await page.goto(route.path);

      // Proposition 2: reachable and still its own screen, not a redirect to
      // a generic one. The heading is the cheapest thing only this route has.
      expect(response?.status()).toBe(200);
      await expect(page.getByRole("heading", { level: 1, name: route.heading })).toBeVisible();
    });

    test(`${route.path} is wrapped in the ${route.template} template`, async ({ page }) => {
      const response = await page.goto(route.path);

      // Proposition 15, first half: the template is in the SERVER's response.
      //
      // `response.text()` is the document body the server actually sent.
      // `page.content()` is not — it serializes the live, hydrated DOM, so it
      // would report the attribute just as happily if a client effect had
      // added it after paint, which is precisely the implementation ADR-007
      // Decision 8 rejects. The two are only distinguishable here.
      const documentBody = await response!.text();
      expect(documentBody, "data-template is absent from the server's response").toContain(
        `data-template="${route.template}"`,
      );

      // Second half: hydration did not change it. Same value, exactly one
      // wrapper, and nothing on `<body>`.
      await expect(page.locator(`[data-template="${route.template}"]`)).toHaveCount(1);
      await expect(page.locator("body")).not.toHaveAttribute("data-template", /.*/);
      await expect(page.locator("body")).not.toHaveAttribute("data-view", /.*/);
    });
  }

  for (const route of PUBLIC_ROUTES) {
    test(`${route.path} is public and carries the ${route.template} template`, async ({
      browser,
    }) => {
      // A fresh context with no session: these must render signed OUT.
      const context = await browser.newContext();
      const page = await context.newPage();
      const response = await page.goto(route.path);

      expect(response?.status()).toBe(200);
      expect(await response!.text()).toContain(`data-template="${route.template}"`);
      await expect(page.locator(`[data-template="${route.template}"]`)).toHaveCount(1);

      await context.close();
    });
  }

  test("an unauthenticated request to the shell is refused, not served", async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto("/dashboard");

    // The gate is unchanged by this step and this asserts it stayed that way.
    expect(new URL(page.url()).pathname).toBe("/sign-in");
    await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(0);

    await context.close();
  });
});

test.describe("navigation", () => {
  test("every rendered destination resolves", async ({ page }) => {
    await page.goto("/dashboard");

    const rail = page.getByRole("navigation", { name: "Main" });
    const links = rail.getByRole("link");

    // Proposition 1: what is rendered, not what is exported. A nav that
    // rendered a fifth link would fail here even though NAV_ITEMS has four.
    await expect(links).toHaveCount(NAV_ITEMS.length);

    for (const item of NAV_ITEMS) {
      const response = await page.goto(item.href);
      expect(response?.status(), `${item.href} did not resolve`).toBe(200);
    }
  });

  test("exactly one item is active per route, and it carries aria-current", async ({ page }) => {
    for (const item of NAV_ITEMS) {
      await page.goto(item.href);

      const rail = page.getByRole("navigation", { name: "Main" });

      // Proposition 3, in the live DOM. `aria-current` has existed and been
      // correct since STEP-15 with no test at all: colour alone does not
      // convey "you are here" to assistive technology.
      await expect(rail.locator("[aria-current='page']")).toHaveCount(1);
      await expect(rail.getByRole("link", { name: item.label })).toHaveAttribute(
        "aria-current",
        "page",
      );
    }
  });

  test("a nested route keeps its parent section active", async ({ page }) => {
    await page.goto("/projects/22222222-2222-2222-2222-222222222222");

    const rail = page.getByRole("navigation", { name: "Main" });

    await expect(rail.locator("[aria-current='page']")).toHaveCount(1);
    await expect(rail.getByRole("link", { name: "Projects" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  test("the template survives a client-side navigation", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.locator("[data-template='cockpit']")).toHaveCount(1);

    // Proposition 15's second half: a client-side transition, not a reload.
    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Projects" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Projects" })).toBeVisible();

    await expect(page.locator("[data-template='workbench']")).toHaveCount(1);
    await expect(page.locator("[data-template='cockpit']")).toHaveCount(0);
    await expect(page.locator("body")).not.toHaveAttribute("data-template", /.*/);
  });
});

test.describe("the lifecycle control renders a real state", () => {
  test("project detail offers Move to Planning and never exposes undefined", async ({ page }) => {
    // Found by the 200% zoom audit, not by any check: the fixture offered a
    // transition to `scripting`, which is not a member of `ApiProjectStatus`,
    // so `transitionLabel()` interpolated a missing lookup and the button read
    // "Move to undefined". Every existing assertion still passed — the page
    // rendered, the heading was right, nothing overflowed.
    //
    // Asserted on the RENDERED label rather than on the payload, because the
    // stub is plain JavaScript and nothing type-checks its fixtures. This is
    // the check that would have caught it.
    await page.goto("/projects/22222222-2222-2222-2222-222222222222");
    await expect(page.getByRole("heading", { level: 1, name: "E2E Project" })).toBeVisible();

    await expect(page.getByRole("button", { name: "Move to Planning" })).toBeVisible();

    // Not scoped to the button: `undefined` reaching the page from any lookup
    // — a status, a label, a name — is the defect, wherever it surfaces.
    await expect(page.locator("body")).not.toContainText("undefined");
  });
});

test.describe("no speculative surface entered the product", () => {
  test("the proposed routes are not served", async ({ page }) => {
    // Proposition 14. The blueprint is coherent and persuasive, which is what
    // makes these dangerous: each one is `Proposed` and owned by no step.
    for (const path of ["/studio", "/library", "/recipes", "/review", "/plan", "/runs", "/activity"]) {
      const response = await page.goto(path);
      expect(response?.status(), `${path} resolved, but no step owns it`).toBe(404);
    }
  });
});
