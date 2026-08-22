import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * The token layer's *shape*, which a browser cannot see (STEP-31a).
 *
 * The browser suite proves what a page renders. It cannot prove that a token
 * is defined in one place and not another — and that distinction is the whole
 * correctness argument for the three-state theme cascade. A page whose dark
 * tokens live only inside the media query looks perfectly correct in a browser
 * set to dark, and is half-themed the moment a user chooses dark explicitly on
 * a light machine.
 *
 * So these two layers are complementary, not redundant: this one reads the
 * stylesheet as text, and several of its assertions have no browser equivalent.
 */

const CSS = readFileSync(fileURLToPath(new URL("./globals.css", import.meta.url)), "utf8");

/** The declarations inside the block carrying `sentinel`, brace-balanced. */
function block(sentinel: string): string {
  const marker = CSS.indexOf(`/* ${sentinel} */`);
  expect(marker, `globals.css has no /* ${sentinel} */ block`).toBeGreaterThan(-1);

  const start = CSS.lastIndexOf("{", marker);
  let depth = 0;
  let index = start;

  for (; index < CSS.length; index += 1) {
    if (CSS[index] === "{") depth += 1;
    else if (CSS[index] === "}") {
      depth -= 1;
      if (depth === 0) break;
    }
  }

  return CSS.slice(start + 1, index);
}

/** Every `--name: value;` declaration in a block, normalised for comparison. */
function declarations(body: string): Map<string, string> {
  return new Map(
    [...body.matchAll(/(--[a-z0-9-]+):\s*([^;]+);/g)].map(([, name, value]) => [
      name,
      value.trim(),
    ]),
  );
}

describe("the three-state theme cascade", () => {
  const media = declarations(block("theme-block: dark-media"));
  const attribute = declarations(block("theme-block: dark-attribute"));

  it("defines the same tokens in the media query and the attribute selector", () => {
    // The failure this prevents: a token defined only in the media query is
    // invisible to an explicit choice, so choosing dark on a light machine
    // yields a page that is dark in some roles and light in the rest.
    expect([...attribute.keys()].sort()).toEqual([...media.keys()].sort());
  });

  it("maps them to the same values", () => {
    for (const [name, value] of media) {
      expect(attribute.get(name), `${name} differs between the two dark blocks`).toBe(value);
    }
  });

  it("defines no dark token ONLY inside a media query", () => {
    for (const name of media.keys()) {
      expect(attribute.has(name), `${name} is defined only inside the media query`).toBe(true);
    }
  });

  it("guards the media query so an explicit light choice wins", () => {
    // Unguarded, the query would override an explicit light choice on a dark
    // machine — a control that is a no-op in exactly one direction.
    expect(CSS).toContain('@media (prefers-color-scheme: dark) {\n  :root:not([data-theme="light"])');
  });

  it("places the attribute block last, so it wins on source order", () => {
    // Both selectors have specificity (0,2,0), so order is what decides.
    // Matched with the opening brace, so prose in the surrounding comments
    // that names either selector cannot satisfy or break this.
    expect(CSS.indexOf(':root[data-theme="dark"] {')).toBeGreaterThan(
      CSS.indexOf("@media (prefers-color-scheme: dark) {"),
    );
  });

  it("declares the native colour scheme in every branch", () => {
    expect(declarations(block("theme-block: light")).get("--color-scheme")).toBeUndefined();
    expect(block("theme-block: light")).toContain("color-scheme: light;");
    expect(block("theme-block: dark-media")).toContain("color-scheme: dark;");
    expect(block("theme-block: dark-attribute")).toContain("color-scheme: dark;");
  });
});

describe("the accepted token values", () => {
  it("adds the two new primitives", () => {
    expect(CSS).toContain("--ivory-75: #FDFAF3;");
    expect(CSS).toContain("--ink-975: #070605;");
  });

  it("repoints the light surfaces onto the warm ladder", () => {
    const light = declarations(block("theme-block: light"));

    expect(light.get("--color-surface")).toBe("var(--ivory-75)");
    expect(light.get("--color-surface-raised")).toBe("var(--ivory-50)");
  });

  it("repoints the dark navigation plane onto the deepest primitive", () => {
    expect(declarations(block("theme-block: dark-attribute")).get("--color-nav-surface")).toBe(
      "var(--ink-975)",
    );
  });

  it("registers --text-4xl in Tailwind's pairing form, not the prototype's", () => {
    // `--text-4xl-lh` is the Artifact's form and registers no line height at
    // all (ADR-007 Decision 11 resolves this against the Artifact).
    expect(CSS).toContain("--text-4xl: 3.25rem;");
    expect(CSS).toContain("--text-4xl--line-height: 1.05;");

    // A declaration, not a mention: the comment above the token names the
    // rejected form deliberately, and a raw substring check would read that
    // explanation as the defect it explains.
    expect(CSS).not.toMatch(/--text-4xl-lh\s*:/);
  });

  it("defines the motion tokens at their accepted values", () => {
    expect(CSS).toContain("--duration-fast: 120ms;");
    expect(CSS).toContain("--duration-base: 180ms;");
    expect(CSS).toContain("--duration-slow: 240ms;");
    expect(CSS).toContain("--ease-standard: cubic-bezier(0.2, 0, 0, 1);");
  });

  it("suppresses animation as well as the duration tokens under reduced motion", () => {
    const reduced = CSS.slice(CSS.indexOf("@media (prefers-reduced-motion: reduce)"));

    // The token remap alone leaves every `animate-pulse` skeleton running:
    // it is an infinite keyframe animation that names no duration token.
    expect(reduced).toContain("--duration-fast: 1ms;");
    expect(reduced).toContain("animation-duration: 1ms !important;");
    expect(reduced).toContain("animation-iteration-count: 1 !important;");
    expect(reduced).toContain("transition-duration: 1ms !important;");
    expect(reduced).toContain("scroll-behavior: auto !important;");
    expect(reduced).toContain("scroll-snap-type: none !important;");
  });
});

describe("the layering rule survives this change", () => {
  it("registers only semantic colour tokens as utilities", () => {
    const theme = CSS.slice(CSS.indexOf("@theme inline"));

    // A primitive registered here would hand components a way to reach past
    // the semantic layer entirely (§3a).
    for (const primitive of ["--ivory-75", "--ink-975", "--verm-600", "--char-800"]) {
      expect(theme).not.toContain(`${primitive}: `);
    }
  });

  it("keeps the scrim a semantic role whose alpha lives in the token", () => {
    // `bg-overlay/40` at each call site is how two dialogs drift apart, and how
    // a scrim ends up tuned for one theme and merely inherited by the other.
    const theme = CSS.slice(CSS.indexOf("@theme inline"));
    expect(theme).toContain("--color-overlay: var(--color-overlay);");

    for (const sentinel of ["theme-block: light", "theme-block: dark-media", "theme-block: dark-attribute"]) {
      const overlay = declarations(block(sentinel)).get("--color-overlay");

      expect(overlay, `${sentinel} declares no scrim`).toMatch(
        /^color-mix\(in srgb, var\(--ink-\d+\) \d+%, transparent\)$/,
      );
    }
  });

  it("defines the three page templates and no fourth", () => {
    const templates = [...CSS.matchAll(/\[data-template="([a-z]+)"\]/g)].map(([, name]) => name);

    expect(new Set(templates)).toEqual(new Set(["cockpit", "workbench", "focus"]));
  });
});
