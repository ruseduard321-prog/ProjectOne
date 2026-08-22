import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { NAV_ITEMS } from "@/lib/navigation";

/**
 * The shell contracts that hold in the source rather than in a rendered page.
 *
 * Propositions 12, 14 and the static halves of 1 and 15. The browser suite
 * asserts what a running page does; these assert what the repository contains
 * — which is where "no speculative route entered the product" and "the four
 * async states are still defined" actually live.
 */

const APP = fileURLToPath(new URL("./(app)", import.meta.url));
const SRC = fileURLToPath(new URL("..", import.meta.url));

const SEGMENTS = ["dashboard", "projects", "chat", "settings"] as const;

function read(relativePath: string): string {
  return readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)), "utf8");
}

/**
 * A file with its comments removed.
 *
 * Every assertion below is about what the code *does*, and this codebase
 * documents its decisions at length — including, deliberately, by naming the
 * techniques it rejects. A raw substring search reads those explanations as
 * the very defects they explain: `PageTemplate` says "nothing here reads
 * `usePathname()`", and "React Testing Library" contains a proposed route
 * noun. Stripping comments is what keeps the check about the product.
 *
 * `(?<!:)` spares `http://` from the line-comment rule.
 */
function code(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/(?<!:)\/\/[^\n]*/g, " ");
}

/** Every file under `src`, so a repository-wide claim can actually be one. */
function sourceFiles(directory: string = SRC): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = `${directory}/${entry.name}`;

    if (entry.isDirectory()) {
      return sourceFiles(path);
    }

    return /\.(ts|tsx|css)$/.test(entry.name) ? [path] : [];
  });
}

describe("navigation destinations resolve to real routes", () => {
  it("every nav item has a route directory", () => {
    // Proposition 1's static half. The browser proves each destination
    // answers; this proves the answer comes from a route that exists rather
    // than from a rewrite or a catch-all.
    const routes = new Set(
      readdirSync(APP, { withFileTypes: true })
        .filter((entry) => entry.isDirectory())
        .map((entry) => `/${entry.name}`),
    );

    for (const item of NAV_ITEMS) {
      expect(routes, `${item.href} has no route directory`).toContain(item.href);
    }
  });

  it("still has exactly four destinations", () => {
    // ADR-007 Decision 12: navigation grows when routes do, and this step
    // creates no route. Four before, four after.
    expect(NAV_ITEMS).toHaveLength(4);
    expect(NAV_ITEMS.map((item) => item.href)).toEqual([
      "/dashboard",
      "/projects",
      "/chat",
      "/settings",
    ]);
  });
});

describe("page templates are server-rendered and scoped", () => {
  it("assigns a template to every existing route, in a server layout", () => {
    for (const segment of SEGMENTS) {
      const layout = read(`./(app)/${segment}/layout.tsx`);

      expect(layout).toContain("<PageTemplate template=");
      // A Server Component: a client layout could not put the attribute in the
      // first byte of HTML, which is the whole contract (ADR-007 Decision 8).
      expect(layout).not.toContain('"use client"');
    }

    expect(read("./(auth)/layout.tsx")).toContain('<PageTemplate template="focus">');
  });

  it("never derives the template from the pathname", () => {
    // The prototype mutates the attribute on navigation. Reading the pathname
    // to decide it would reintroduce exactly the hydration race Decision 8
    // rejects that technique for.
    expect(code(read("../components/shell/PageTemplate.tsx"))).not.toContain("usePathname");
  });

  it("keeps per-template state off <body>", () => {
    const root = read("./layout.tsx");

    expect(root).not.toContain("data-template");
    expect(root).not.toMatch(/<body[^>]*data-/);
  });
});

describe("the four async states survive", () => {
  it("every loading fallback still announces itself", () => {
    // Proposition 12. `role="status"` is what makes a skeleton perceivable to
    // assistive technology rather than a silent pause.
    for (const segment of SEGMENTS) {
      expect(read(`./(app)/${segment}/loading.tsx`), segment).toContain('role="status"');
    }

    expect(read("./(app)/loading.tsx")).toContain('role="status"');
  });

  it("every error boundary announces, and none leaks the exception", () => {
    for (const segment of SEGMENTS) {
      const source = read(`./(app)/${segment}/error.tsx`);

      expect(source, segment).toContain('role="alert"');
      // A raw exception in the UI is a leak and a dead end for the user
      // (§10, CLAUDE.md §24).
      expect(source, segment).not.toContain("{error.message}");
      expect(source, segment).not.toContain("{error.stack}");
    }
  });
});

describe("no proposed capability entered the product", () => {
  it("introduces none of the blueprint's proposed product nouns", () => {
    // Proposition 14. The blueprint's own README is explicit that `recipe` and
    // `deliverable` "do not exist as product nouns anywhere in the repository
    // today". They still do not.
    const nouns = ["deliverable", "recipe", "studio", "library", "masters", "artboard"];
    const offenders: string[] = [];

    for (const file of sourceFiles()) {
      // This file names the nouns in order to forbid them. Scanning itself
      // would make the check permanently red for stating what it checks.
      if (file.endsWith("shell-contracts.test.ts")) {
        continue;
      }

      const source = code(readFileSync(file, "utf8")).toLowerCase();

      for (const noun of nouns) {
        // Whole words: an identifier, not a fragment of a longer one.
        if (new RegExp(`\\b${noun}\\b`).test(source)) {
          offenders.push(`${file.slice(SRC.length + 1)} contains "${noun}"`);
        }
      }
    }

    expect(offenders).toEqual([]);
  });

  it("creates no route beyond the ones that already existed", () => {
    const segments = readdirSync(APP, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name)
      .sort();

    // The activity/audit and workflow-run routes stay open plan gaps: ADR-007
    // Decision 3 records them and creates neither.
    expect(segments).toEqual(["chat", "dashboard", "projects", "settings"]);
  });
});

describe("the modal scrim is one shared semantic contract", () => {
  const SCRIM = "backdrop:bg-overlay";

  it("both dialogs paint the same scrim", () => {
    // Two consumers, one contract. The browser suite proves the drawer's scrim
    // resolves and has the right polarity; this proves the confirm dialog
    // reaches for the identical role rather than a second, drifting one.
    for (const component of ["../components/shell/MobileNav.tsx", "../components/shell/ConfirmDialog.tsx"]) {
      expect(code(read(component)), `${component} does not use the shared scrim`).toContain(SCRIM);
    }
  });

  it("no dialog anywhere styles its own backdrop", () => {
    // The defect this closes: `backdrop:bg-text/40`. `text` is a semantic
    // token, so no layering rule was broken — but it is ivory in dark mode, so
    // the scrim LIGHTENED the page it existed to subdue. Any `backdrop:`
    // utility other than the shared role is that failure returning, whether it
    // reaches for `text`, a `nav-*` role or a per-component opacity.
    const offenders = sourceFiles()
      // This file carries the pattern it searches for, exactly as the noun
      // check above does. Scanning itself would make it permanently red.
      .filter((file) => !file.endsWith("shell-contracts.test.ts"))
      .flatMap((file) =>
        [...code(readFileSync(file, "utf8")).matchAll(/backdrop:[a-z0-9/[\]-]+/g)].map(
          (match) => `${file.slice(SRC.length + 1)}: ${match[0]}`,
        ),
      )
      .filter((occurrence) => !occurrence.endsWith(SCRIM));

    expect(offenders).toEqual([]);
  });
});
