import { expect, test, THEME_STORAGE_KEY } from "./support";

/**
 * R5 — the modal scrim subdues the page it covers, in BOTH themes.
 *
 * The defect this replaces was invisible to every check the suite already had.
 * The scrim was `backdrop:bg-text/40`, and `--color-text` is a near-black in
 * light mode and ivory in dark mode — so the same class darkened the page in
 * one theme and washed it out with a grey veil in the other. Nothing failed:
 * the drawer opened, focus was trapped, contrast passed, because contrast is
 * measured on foregrounds and nothing is rendered on a scrim.
 *
 * So the property asserted here is POLARITY, not contrast: whatever the scrim
 * resolves to, compositing it over the page must make the page darker. That is
 * a claim about the running browser's computed `::backdrop` colour, which is
 * the one place the token, the utility, the theme cascade and the user agent's
 * top-layer rendering all meet.
 *
 * Reverting the drawer to `text/40` fails this in dark mode, on the polarity
 * assertion. That the confirm dialog paints the SAME scrim is proved
 * statically instead — see `shell-contracts.test.ts` — because the e2e
 * fixtures deliberately serve no assets, so no confirm dialog exists to open
 * in this app, and inventing one to satisfy a test would change what every
 * other spec derives from the page.
 */

// Below `md` (768px), the only width at which the drawer exists.
test.use({ viewport: { width: 375, height: 812 } });

interface Rgba {
  readonly r: number;
  readonly g: number;
  readonly b: number;
  readonly a: number;
}

/**
 * A computed colour -> 0-255 channels and an alpha.
 *
 * Two forms, because the browser picks the form and the test does not: an
 * opaque background computes to `rgb(250, 246, 238)`, while a `color-mix()`
 * computes to `color(srgb 0.0588 0.0549 0.0509 / 0.45)`. Reading only the
 * first would make this spec silently unable to see the very value it exists
 * to measure.
 */
function parseColor(value: string): Rgba {
  const legacy = value.match(/rgba?\(([^)]+)\)/);
  if (legacy) {
    const parts = legacy[1].split(/[,\s/]+/).map((part) => Number.parseFloat(part));
    return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 };
  }

  const srgb = value.match(/color\(srgb\s+([^)]+)\)/);
  if (srgb) {
    const parts = srgb[1].split(/[\s/]+/).map((part) => Number.parseFloat(part));
    return { r: parts[0] * 255, g: parts[1] * 255, b: parts[2] * 255, a: parts.length > 3 ? parts[3] : 1 };
  }

  const oklab = value.match(/oklab\(([^)]+)\)/);
  expect(oklab, `not a colour this test can read: ${value}`).not.toBeNull();

  const [lightness, aAxis, bAxis, alpha = 1] = oklab![1]
    .split(/[\s/]+/)
    .map((part) => Number.parseFloat(part));

  return { ...oklabToSrgb(lightness, aAxis, bAxis), a: alpha };
}

/**
 * Oklab -> sRGB, per CSS Color 4.
 *
 * Present because the browser, not the test, chooses the serialisation: any
 * opacity modifier — `bg-overlay/40`, and the `bg-text/40` this step replaced —
 * computes to `oklab()`. A spec that could not read that form would answer
 * "unreadable" where it was asked "lighter or darker", which is not a verdict.
 */
function oklabToSrgb(lightness: number, aAxis: number, bAxis: number): Omit<Rgba, "a"> {
  const l = (lightness + 0.3963377774 * aAxis + 0.2158037573 * bAxis) ** 3;
  const m = (lightness - 0.1055613458 * aAxis - 0.0638541728 * bAxis) ** 3;
  const s = (lightness - 0.0894841775 * aAxis - 1.291485548 * bAxis) ** 3;

  const encode = (linear: number) => {
    const clamped = Math.min(1, Math.max(0, linear));
    const gamma = clamped <= 0.0031308 ? 12.92 * clamped : 1.055 * clamped ** (1 / 2.4) - 0.055;
    return gamma * 255;
  };

  return {
    r: encode(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    g: encode(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    b: encode(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s),
  };
}

/** WCAG 2.1 relative luminance — the same formula `check-contrast.py` uses. */
function luminance({ r, g, b }: Rgba): number {
  const linear = (channel: number) => {
    const c = channel / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };

  return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
}

/** Alpha-composite `over` onto `beneath`, the way the browser paints it. */
function composite(over: Rgba, beneath: Rgba): Rgba {
  const mix = (o: number, b: number) => over.a * o + (1 - over.a) * b;
  return { r: mix(over.r, beneath.r), g: mix(over.g, beneath.g), b: mix(over.b, beneath.b), a: 1 };
}

for (const theme of ["light", "dark"] as const) {
  test(`the drawer's scrim darkens the page in the ${theme} theme`, async ({ page }) => {
    // The system preference is set to the OPPOSITE of the explicit choice, so
    // a scrim that silently followed the media query rather than the token
    // cascade would be measured in the wrong theme and caught here.
    await page.emulateMedia({ colorScheme: theme === "dark" ? "light" : "dark" });
    await page.addInitScript(
      ([key, value]) => window.localStorage.setItem(key as string, value as string),
      [THEME_STORAGE_KEY, theme],
    );

    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);

    await page.getByRole("button", { name: "Menu" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();

    const [scrimColor, pageColor] = await page.evaluate(() => {
      const dialog = document.querySelector("dialog[open]");
      if (!dialog) throw new Error("the drawer is not open");

      return [
        getComputedStyle(dialog, "::backdrop").backgroundColor,
        getComputedStyle(document.body).backgroundColor,
      ];
    });

    const scrim = parseColor(scrimColor);
    const beneath = parseColor(pageColor);

    // 1. Translucent. An opaque veil is a screen, not a scrim: the page it
    //    covers has to stay visible for the drawer to read as being ON it.
    expect(scrim.a, `the scrim is not translucent: ${scrimColor}`).toBeGreaterThan(0);
    expect(scrim.a, `the scrim is opaque: ${scrimColor}`).toBeLessThan(1);

    // 2. Dark in itself. This is the assertion `text/40` fails in dark mode,
    //    where `--color-text` is ivory and the veil is lighter than the page.
    expect(
      luminance(scrim),
      `the scrim (${scrimColor}) is lighter than the page it covers (${pageColor})`,
    ).toBeLessThan(luminance(beneath));

    // 3. And the composited result is what the user actually sees.
    const veiled = luminance(composite(scrim, beneath));
    expect(veiled, `the scrim does not subdue the page: ${pageColor} + ${scrimColor}`).toBeLessThan(
      luminance(beneath),
    );
  });
}
