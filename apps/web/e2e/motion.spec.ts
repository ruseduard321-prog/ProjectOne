import { expect, test } from "./support";

/**
 * Proposition 11 — reduced motion is genuinely suppressed.
 *
 * "Genuinely" is the operative word. The token remap alone would leave every
 * loading skeleton animating: `animate-pulse` is an infinite keyframe
 * animation that names no duration token, and there are forty of them in the
 * product. Both halves of the block are therefore asserted separately.
 */

/**
 * The three duration tokens, in milliseconds.
 *
 * Read as numbers rather than compared as strings: the build minifies `120ms`
 * to `.12s`, so a string comparison would assert the minifier's output format
 * rather than the duration.
 */
async function durationsMs(page: import("@playwright/test").Page): Promise<number[]> {
  return page.evaluate(() => {
    const style = getComputedStyle(document.documentElement);

    return ["--duration-fast", "--duration-base", "--duration-slow"].map((token) => {
      const raw = style.getPropertyValue(token).trim();
      return raw.endsWith("ms") ? parseFloat(raw) : parseFloat(raw) * 1000;
    });
  });
}

test.describe("reduced motion", () => {
  // `emulateMedia` rather than a `test.use` option: `reducedMotion` is a
  // context option in this version, and emulating it per page keeps the
  // refusal visible in the test that depends on it.
  test.beforeEach(async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
  });

  test("the duration tokens collapse", async ({ page }) => {
    await page.goto("/dashboard");

    expect(await durationsMs(page)).toEqual([1, 1, 1]);
  });

  test("transitions do not run", async ({ page }) => {
    await page.goto("/dashboard");

    const link = page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Projects" });
    const duration = await link.evaluate((element) => getComputedStyle(element).transitionDuration);

    // Every comma-separated component, not just the first.
    for (const part of duration.split(",")) {
      expect(parseFloat(part)).toBeLessThanOrEqual(0.001);
    }
  });

  test("skeleton animations do not run", async ({ page }) => {
    // Rendered directly rather than raced against a real loading state: a test
    // that has to catch a Suspense fallback mid-flight is a flaky test, and a
    // flaky proof is not a proof.
    await page.goto("/dashboard");

    const animation = await page.evaluate(() => {
      const probe = document.createElement("div");
      probe.className = "animate-pulse";
      document.body.append(probe);

      const style = getComputedStyle(probe);
      const reading = {
        duration: style.animationDuration,
        iterations: style.animationIterationCount,
      };

      probe.remove();
      return reading;
    });

    for (const part of animation.duration.split(",")) {
      expect(parseFloat(part)).toBeLessThanOrEqual(0.001);
    }

    expect(animation.iterations).toBe("1");
  });
});

test.describe("motion is present when it is not refused", () => {
  test("the duration tokens carry their real values", async ({ page }) => {
    // The control for the tests above: without this, a stylesheet that set
    // every duration to 1ms unconditionally would pass all of them.
    await page.goto("/dashboard");

    expect(await durationsMs(page)).toEqual([120, 180, 240]);
  });
});
