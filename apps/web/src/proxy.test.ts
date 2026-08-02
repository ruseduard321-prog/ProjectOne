import { describe, expect, it } from "vitest";

import { NAV_ITEMS } from "@/lib/navigation";
import { config } from "@/proxy";

describe("proxy matcher", () => {
  /**
   * The matcher is written by hand, and a shell route missing from it loses the
   * 307 the proxy exists to provide. The layout gate still refuses the request,
   * so the failure is quiet — which is exactly why it is asserted here rather
   * than left to review.
   */
  it("covers every navigable shell route", () => {
    for (const item of NAV_ITEMS) {
      expect(config.matcher).toContain(`${item.href}/:path*`);
    }
  });

  it("does not gate the authentication routes", () => {
    // A matcher that caught /sign-in would redirect it to itself.
    const gated = config.matcher.join(" ");

    expect(gated).not.toContain("/sign-in");
    expect(gated).not.toContain("/sign-up");
  });

  it("does not gate the session-expiry handler", () => {
    // That route exists to clear a dead cookie. Gating it on holding a live
    // session would make the only escape from a dead one unreachable.
    expect(config.matcher.join(" ")).not.toContain("/session");
  });
});
