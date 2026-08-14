/**
 * FA-04 and FA-11 — the root error boundary, which the STEP-24 tests did not cover.
 *
 * ## Why this file exists
 *
 * `(app)/error-boundary-retry.test.ts` asserts the wiring of the four *route*
 * boundaries and stops there. The root boundary sits outside that group, so it
 * kept `onClick={reset}` while all four of its siblings were fixed, and no test
 * noticed. The STEP-25 audit found it by reading the file.
 *
 * That gap matters more than the count suggests. A route boundary cannot catch a
 * failure in the layout that wraps it, so the root boundary is the one that
 * renders during the API outage STEP-16b handles — and STEP-16b's own manual
 * checklist recorded "a working retry control" against wiring now known to be
 * inert.
 *
 * Two findings, deliberately separate: FA-04 is functional (the retry recovers
 * nothing) and FA-11 is accessibility (a screen reader is never told an error
 * occurred). Same file, same fix commit, but each has its own proof, because
 * either could regress without the other.
 *
 * ## Why source assertions rather than rendering
 *
 * The same reasoning as the route-boundary tests, which applies unchanged here:
 * the suite runs in a node environment with no DOM, and rendering a working
 * retry and a broken one produces byte-identical markup, because the difference
 * is which function the handler holds. A rendering test would pass against the
 * defect, which makes it worse than no test.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

function rootBoundarySource(): string {
  return readFileSync(fileURLToPath(new URL("./error.tsx", import.meta.url)), "utf8");
}

describe("the root error boundary", () => {
  // ------------------------------------------------------------------
  // FA-04 — the retry must actually recover
  // ------------------------------------------------------------------

  it("imports the shared recovery", () => {
    expect(rootBoundarySource()).toContain('from "@/lib/error-recovery"');
  });

  it("builds its handler from the shared recovery", () => {
    expect(rootBoundarySource()).toMatch(/useErrorRecovery\(\s*reset\s*\)/);
  });

  it("does not wire the button straight to reset, which recovers nothing", () => {
    /*
     * **FA-04 itself.** `reset()` clears client state and re-renders the cached
     * payload, which still contains the failure — so the boundary immediately
     * renders again and the user sees no change. This is the wiring the audit
     * found, and the one that must never come back.
     */
    expect(rootBoundarySource()).not.toMatch(/onClick=\{\s*reset\s*\}/);
  });

  it("still offers the user a retry control", () => {
    // Guards the opposite failure: satisfying the rule above by deleting the
    // button rather than fixing it.
    expect(rootBoundarySource()).toContain("Try again");
  });

  // ------------------------------------------------------------------
  // FA-11 — the failure must be announced
  // ------------------------------------------------------------------

  it("announces the failure to assistive technology", () => {
    /*
     * **FA-11.** All four route boundaries carry `role="alert"`; the root
     * boundary carried no role at all, so a screen-reader user reaching the
     * outage path received no announcement that anything had gone wrong.
     */
    expect(rootBoundarySource()).toMatch(/role="alert"/);
  });

  // ------------------------------------------------------------------
  // Properties the fix must not cost
  // ------------------------------------------------------------------

  it("still keeps the engineer-facing detail out of the page", () => {
    /*
     * CLAUDE.md §24: an unexpected failure's message is written for an engineer
     * and can carry internal detail. It goes to the console, never the screen.
     */
    const source = rootBoundarySource();

    expect(source).not.toMatch(/\{\s*error\.message\s*\}/);
    expect(source).not.toMatch(/\{\s*error\.stack\s*\}/);
    expect(source).toContain("console.error");
  });

  it("still surfaces the opaque digest so a report ties to a server log", () => {
    expect(rootBoundarySource()).toContain("error.digest");
  });

  it("still speaks to the user rather than at them", () => {
    // The friendly copy is part of the contract, not decoration — a boundary
    // that recovers correctly but reads like a stack trace has traded one
    // failure for another.
    expect(rootBoundarySource()).toContain("Something went wrong");
  });
});
