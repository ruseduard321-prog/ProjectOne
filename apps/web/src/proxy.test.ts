import { NextRequest } from "next/server";
import { afterEach, describe, expect, it } from "vitest";

import { NAV_ITEMS } from "@/lib/navigation";
import { config, proxy } from "@/proxy";

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
    expect(config.matcher.join(" ")).not.toContain("/session/expired");
  });

  it("covers the development-only namespace", () => {
    // The proxy is what returns a real 404 for /dev/* in production, and it
    // only runs on matched paths. A missing entry here would serve the session
    // inspector to production — the one outcome STEP-16a exists to prevent.
    expect(config.matcher).toContain("/dev/:path*");
  });
});

describe("development-only routes", () => {
  const originalNodeEnv = process.env.NODE_ENV;

  function setNodeEnv(value: string): void {
    (process.env as Record<string, string>).NODE_ENV = value;
  }

  afterEach(() => {
    setNodeEnv(originalNodeEnv ?? "test");
  });

  function request(path: string): NextRequest {
    return new NextRequest(new URL(path, "http://localhost:3000"));
  }

  it("refuses /dev/* with a 404 in production", () => {
    // 404 rather than 403: a 403 confirms the route exists.
    setNodeEnv("production");

    const response = proxy(request("/dev/session"));

    expect(response.status).toBe(404);
  });

  it("refuses the whole namespace, not just the known page", () => {
    setNodeEnv("production");

    expect(proxy(request("/dev/anything")).status).toBe(404);
  });

  it("serves /dev/* in development without a session", () => {
    // The inspector must render signed out — "why am I signed out" is one of
    // the questions it exists to answer, so a redirect to sign-in would hide
    // exactly the state worth inspecting.
    setNodeEnv("development");

    const response = proxy(request("/dev/session"));

    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
  });

  it("still redirects an unauthenticated shell route in development", () => {
    // Guards against the dev-route branch accidentally short-circuiting the
    // session gate for everything.
    setNodeEnv("development");

    const response = proxy(request("/dashboard"));

    expect(response.status).toBe(307);
  });
});
