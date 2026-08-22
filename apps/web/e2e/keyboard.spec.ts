import type { Page } from "@playwright/test";

import { expect, SHELL_ROUTES, test } from "./support";

/**
 * Propositions 4 and 5 — keyboard traversal, focus visibility, and the skip
 * link.
 *
 * Both contracts have been correct in the shell since STEP-15 and neither had
 * a single test. Any change to the layout could have dropped them and CI would
 * have stayed green, which is the gap this file closes.
 *
 * ## Why the expected sequence is derived, not written down
 *
 * An earlier version of this file walked a fixed 25 steps and asserted that
 * "more than three" elements were reached. That passes on a route with four
 * controls and one that has forty, it says nothing about *order*, and — worst
 * — a new control added tomorrow and left unreachable would not fail it. It
 * measured that tabbing does something, not that tabbing does the right thing.
 *
 * So the expectation is computed from the page itself: every element that is
 * currently rendered, enabled and tabbable, in DOM order, marked with a
 * `data-kb` index so each stop is identified by *identity* rather than by
 * label — two controls can share a label, and a test that cannot tell them
 * apart cannot prove order.
 *
 * The walk then has to reach every one of them, in that order, and leave the
 * document at the end. Add an interactive control anywhere and the expectation
 * grows on its own; make it unreachable and this fails.
 */

/**
 * Elements that are interactive by virtue of what they are.
 *
 * These are expected to be keyboard reachable **whatever their `tabindex`**.
 * Taking a button out of the tab order with `tabindex="-1"` is exactly how a
 * control becomes mouse-only by accident, so the derivation must not quietly
 * agree with it — see the negative-tabindex handling below.
 */
const INHERENTLY_INTERACTIVE = "a[href], button, input, select, textarea";

/** Everything a browser may stop on, including opt-in `[tabindex]` hosts. */
const TABBABLE = `${INHERENTLY_INTERACTIVE}, [tabindex]`;

interface Expected {
  readonly kb: string;
  readonly tag: string;
  readonly label: string;
}

/**
 * Mark every currently tabbable element with its DOM-order index.
 *
 * Exclusions are the ones the platform itself makes, so the list matches what
 * a browser will actually visit: negative `tabindex` (a focus target, not a tab
 * stop — `<main>` is one), disabled controls, anything inside an `inert`
 * subtree or a closed `<dialog>`, and anything with no box at all, which is how
 * the rail is absent below `md` and the drawer is absent while closed.
 */
async function markTabbable(page: Page): Promise<Expected[]> {
  return page.evaluate(([selector, interactive]) => {
    const found: { kb: string; tag: string; label: string }[] = [];
    let index = 0;

    // `querySelectorAll` yields document order, which is the order a browser
    // tabs in for any tree with no positive tabindex — and §9.1 rule 4 forbids
    // a positive tabindex, so document order IS the expected order here.
    for (const element of document.querySelectorAll<HTMLElement>(selector)) {
      const tabindex = element.getAttribute("tabindex");

      // A negative tabindex excuses a *host* element — `<main tabindex="-1">`
      // is a focus target for the skip link and not a tab stop. It does not
      // excuse a button or a link: that is a real control removed from the
      // keyboard's reach, so it stays in the expectation and fails below.
      if (tabindex !== null && Number(tabindex) < 0 && !element.matches(interactive)) continue;
      if ((element as HTMLButtonElement).disabled) continue;
      if (element.closest("[inert]") !== null) continue;

      const dialog = element.closest("dialog");
      if (dialog !== null && !dialog.open) continue;

      // A rendered box, not merely a node: `display: none` yields none.
      if (element.getClientRects().length === 0) continue;

      element.setAttribute("data-kb", String(index));
      found.push({
        kb: String(index),
        tag: element.tagName.toLowerCase(),
        label:
          (element.textContent ?? "").trim().slice(0, 40) ||
          element.getAttribute("aria-label") ||
          element.getAttribute("name") ||
          "",
      });
      index += 1;
    }

    return found;
  }, [TABBABLE, INHERENTLY_INTERACTIVE] as const);
}

interface Stop {
  readonly kb: string | null;
  readonly interactive: boolean;
  readonly label: string;
  readonly ring: boolean;
}

/** Read the focused element, or null once focus has left the document. */
async function currentStop(page: Page): Promise<Stop | null> {
  return page.evaluate((interactive) => {
    const element = document.activeElement as HTMLElement | null;

    if (element === null || element === document.body) {
      return null;
    }

    const style = getComputedStyle(element);

    return {
      kb: element.getAttribute("data-kb"),
      // Anything a user can operate. A stop that is interactive but was not in
      // the expected list is a control the derivation missed — which is a
      // failure, not something to wave through.
      interactive: element.matches(interactive),
      label: (element.textContent ?? "").trim().slice(0, 40),
      // §9.1 rule 2: `outline: none` without an equal replacement is a defect.
      ring: style.outlineStyle !== "none" && Number.parseFloat(style.outlineWidth) > 0,
    };
  }, INHERENTLY_INTERACTIVE);
}

/**
 * Tab from the document start until focus leaves the document.
 *
 * Bounded at the expected length plus a small margin — not a magic walk
 * length: exceeding it means focus never left, which is the definition of a
 * trap outside a modal and is asserted as such by the caller.
 */
async function walk(page: Page, limit: number): Promise<{ stops: Stop[]; exited: boolean }> {
  const stops: Stop[] = [];

  for (let step = 0; step < limit; step += 1) {
    await page.keyboard.press("Tab");

    const stop = await currentStop(page);

    if (stop === null) {
      return { stops, exited: true };
    }

    stops.push(stop);
  }

  return { stops, exited: false };
}

test.describe("skip link", () => {
  test("is the first focusable element and moves focus to main", async ({ page }) => {
    await page.goto("/dashboard");
    // Wait for the route's own content, not merely for `load`. Until the
    // Suspense fallback is replaced there is nothing on the page to tab to,
    // and a test that raced it would be the flaky test that teaches everyone
    // to ignore this suite.
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();

    await page.keyboard.press("Tab");

    const first = await page.evaluate(() => ({
      text: (document.activeElement?.textContent ?? "").trim(),
      href: document.activeElement?.getAttribute("href"),
    }));

    expect(first.text).toBe("Skip to content");
    expect(first.href).toBe("#main-content");

    // Visible once focused — a skip link that stays `sr-only` while focused is
    // invisible to the sighted keyboard user it exists for.
    await expect(page.getByRole("link", { name: "Skip to content" })).toBeVisible();

    await page.keyboard.press("Enter");

    // Proposition 5: focus MOVES. Asserting the href alone would pass against
    // a landmark that is not focusable, where the browser scrolls and leaves
    // focus on <body> — the skip link then appears to work and does not.
    const afterActivation = await page.evaluate(() => ({
      id: document.activeElement?.id,
      tag: document.activeElement?.tagName.toLowerCase(),
    }));

    expect(afterActivation.id).toBe("main-content");
    expect(afterActivation.tag).toBe("main");
  });
});

test.describe("keyboard traversal", () => {
  for (const route of SHELL_ROUTES) {
    test(`${route.path} reaches every interactive element in DOM order`, async ({ page }) => {
      await page.goto(route.path);
      await expect(page.getByRole("heading", { level: 1, name: route.heading })).toBeVisible();

      const expected = await markTabbable(page);

      // A sanity floor on the derivation itself, not on the page: the shell
      // alone guarantees the skip link, the rail identity, four destinations
      // and sign out. If the derivation returned almost nothing, every
      // assertion below would pass vacuously.
      expect(expected.length, `derivation found almost nothing on ${route.path}`).toBeGreaterThan(5);
      expect(expected[0]?.label).toBe("Skip to content");

      const { stops, exited } = await walk(page, expected.length + 5);

      // --- no trap outside a modal ---------------------------------------
      expect(exited, `focus never left the document on ${route.path} — it is trapped`).toBe(true);

      // --- every stop is visibly focused ---------------------------------
      const unfocusable = stops.filter((stop) => !stop.ring).map((stop) => stop.label);
      expect(unfocusable, `no visible focus indicator on: ${unfocusable.join(", ")}`).toEqual([]);

      // --- nothing interactive was visited that we did not expect ---------
      // This is what makes a *new* control fail rather than pass silently: it
      // is either in the derivation, or it is an unexpected interactive stop.
      const unexpected = stops.filter((stop) => stop.interactive && stop.kb === null);
      expect(unexpected.map((stop) => stop.label), "reached an interactive element the derivation did not find").toEqual([]);

      // --- every expected element was reached, in DOM order ---------------
      // A subsequence rather than an equality, because a browser may insert
      // stops of its own (a keyboard-focusable scroll container is the usual
      // one). Those carry no `data-kb`; ours must still appear, all of them,
      // in the order the DOM declares.
      const reached = stops.map((stop) => stop.kb).filter((kb): kb is string => kb !== null);

      expect(reached, `tab order does not match DOM order on ${route.path}`).toEqual(
        expected.map((element) => element.kb),
      );
    });
  }
});
