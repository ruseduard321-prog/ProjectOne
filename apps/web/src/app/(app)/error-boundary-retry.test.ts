/**
 * Every route error boundary wires its retry to the shared recovery (STEP-24).
 *
 * ## Why this file exists separately from `error-recovery.test.ts`
 *
 * That file proves the shared handler works. This one proves the boundaries use
 * it — and the gap between those two is exactly how the original defect
 * survived. All four boundaries had a retry control, three of them documented
 * that it recovered, and nothing anywhere asserted the wiring. A future edit
 * reverting one boundary to `onClick={reset}` would restore a button that looks
 * identical, does nothing, and breaks no test.
 *
 * ## Why source assertions rather than rendering
 *
 * These are Client Components whose defect is behavioural, and the suite runs in
 * a node environment with no DOM (`vitest.config.ts`). Rendering them with
 * `renderToStaticMarkup` — the approach `dashboard-screen.test.tsx` uses — would
 * produce markup in which a working retry and a broken one are byte-identical,
 * because the difference is which function the handler holds. Such a test would
 * pass against the broken code, which makes it worse than none.
 *
 * Adding jsdom and React Testing Library to click four buttons would be two
 * dependencies for four assertions (CLAUDE.md §28), and would still need each
 * boundary rendered inside a router context it does not otherwise require.
 *
 * Reading the source is the least brittle option that actually fails on the
 * defect. It is coupled to an import name and a prop name rather than to markup,
 * class names or copy — the parts of these files most likely to change, and the
 * parts STEP-26's redesign will change. A rename that breaks these tests is a
 * rename that should be reviewed here anyway.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/** The boundaries under the authenticated shell, by route segment. */
const BOUNDARIES = ["dashboard", "projects", "settings", "chat"] as const;

function boundarySource(segment: string): string {
  return readFileSync(fileURLToPath(new URL(`./${segment}/error.tsx`, import.meta.url)), "utf8");
}

describe.each(BOUNDARIES)("the %s error boundary", (segment) => {
  it("imports the shared recovery", () => {
    expect(boundarySource(segment)).toContain('from "@/lib/error-recovery"');
  });

  it("builds its handler from the shared recovery", () => {
    expect(boundarySource(segment)).toMatch(/useErrorRecovery\(\s*reset\s*\)/);
  });

  it("does not wire the button straight to reset, which recovers nothing", () => {
    /*
     * **The regression this file exists for.** `onClick={reset}` re-renders the
     * cached payload that still holds the failure, so the screen never changes.
     * It is the one wiring that must never come back.
     */
    expect(boundarySource(segment)).not.toMatch(/onClick=\{\s*reset\s*\}/);
  });

  it("still offers the user a retry control", () => {
    // Guards the opposite failure: satisfying the rules above by deleting the
    // button entirely.
    expect(boundarySource(segment)).toContain("Try again");
  });
});
