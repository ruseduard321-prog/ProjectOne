import { describe, expect, it } from "vitest";

import { isActiveRoute, NAV_ITEMS } from "@/lib/navigation";

/**
 * Tests for shell navigation.
 *
 * `isActiveRoute` is segment-aware rather than a plain `startsWith`, and the
 * difference is invisible until a sibling route shares a prefix. That is the
 * case worth locking down — it is the kind of bug that ships because the nav
 * "looks right" on every route that exists today.
 */

describe("isActiveRoute", () => {
  it("matches the route exactly", () => {
    expect(isActiveRoute("/projects", "/projects")).toBe(true);
  });

  it("marks a parent section active for a nested route", () => {
    expect(isActiveRoute("/projects", "/projects/abc")).toBe(true);
    expect(isActiveRoute("/projects", "/projects/abc/edit")).toBe(true);
  });

  it("does not match a sibling route sharing a prefix", () => {
    // The reason for the segment check: `startsWith` would light up Projects.
    expect(isActiveRoute("/projects", "/projects-archive")).toBe(false);
  });

  it("does not match an unrelated route", () => {
    expect(isActiveRoute("/projects", "/settings")).toBe(false);
  });

  it("marks exactly one nav item active for any shell route", () => {
    for (const item of NAV_ITEMS) {
      const active = NAV_ITEMS.filter((candidate) =>
        isActiveRoute(candidate.href, item.href),
      );

      expect(active).toHaveLength(1);
      expect(active[0]?.href).toBe(item.href);
    }
  });
});

describe("NAV_ITEMS", () => {
  it("has no duplicate destinations", () => {
    const hrefs = NAV_ITEMS.map((item) => item.href);

    expect(new Set(hrefs).size).toBe(hrefs.length);
  });

  it("uses absolute paths", () => {
    for (const item of NAV_ITEMS) {
      expect(item.href.startsWith("/")).toBe(true);
    }
  });
});
