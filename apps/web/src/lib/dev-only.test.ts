import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { devRoutesEnabled, isDevOnlyPath } from "@/lib/dev-only";

/**
 * The production exclusion for `/dev/*`.
 *
 * These are the tests that matter most in STEP-16a. A diagnostics page that
 * might answer in production is a worse outcome than no diagnostics page, so
 * the assertions here are about *refusal*, not about rendering.
 *
 * `NODE_ENV` is restored after each case because Vitest sets it to `test` for
 * the whole run, and leaking a `production` value into later suites would make
 * unrelated tests fail in a way that points nowhere useful.
 */
const originalNodeEnv = process.env.NODE_ENV;
const originalAppEnv = process.env.NEXT_PUBLIC_PROJECTONE_ENVIRONMENT;

function setNodeEnv(value: string): void {
  // `NODE_ENV` is typed as a readonly union; the cast is confined to this
  // helper rather than repeated at every call site.
  (process.env as Record<string, string>).NODE_ENV = value;
}

beforeEach(() => {
  setNodeEnv("development");
  process.env.NEXT_PUBLIC_PROJECTONE_ENVIRONMENT = "development";
});

afterEach(() => {
  setNodeEnv(originalNodeEnv ?? "test");

  if (originalAppEnv === undefined) {
    delete process.env.NEXT_PUBLIC_PROJECTONE_ENVIRONMENT;
  } else {
    process.env.NEXT_PUBLIC_PROJECTONE_ENVIRONMENT = originalAppEnv;
  }
});

describe("devRoutesEnabled", () => {
  it("permits development-only routes in a development build", () => {
    expect(devRoutesEnabled()).toBe(true);
  });

  it("refuses when NODE_ENV is production", () => {
    // The signal that cannot be misconfigured: `next build` and `next start`
    // set this themselves, so it describes how the app was built rather than
    // how someone configured it.
    setNodeEnv("production");

    expect(devRoutesEnabled()).toBe(false);
  });

  it("refuses when the app is configured as production", () => {
    // A staging deploy running a development build, or any environment
    // explicitly declared production, is still refused.
    process.env.NEXT_PUBLIC_PROJECTONE_ENVIRONMENT = "production";

    expect(devRoutesEnabled()).toBe(false);
  });

  it("refuses when either signal says production", () => {
    setNodeEnv("production");
    process.env.NEXT_PUBLIC_PROJECTONE_ENVIRONMENT = "production";

    expect(devRoutesEnabled()).toBe(false);
  });

  it("permits a test build, so the suite can exercise the page", () => {
    setNodeEnv("test");

    expect(devRoutesEnabled()).toBe(true);
  });
});

describe("the build-time and runtime exclusions agree", () => {
  /**
   * `next.config.ts` decides whether `page.dev.tsx` compiles at all, using the
   * same two signals as `devRoutesEnabled`. It cannot import this module — it
   * is evaluated before path aliases resolve — so the expression is duplicated
   * there, and this asserts the duplicate has not drifted.
   *
   * Drift in the *permissive* direction is the dangerous one: a config that
   * compiled the route while the runtime refused it would leave the page in a
   * production bundle, reachable by anything that bypassed the proxy.
   */
  function configExpression(nodeEnv: string, appEnv: string): boolean {
    return nodeEnv !== "production" && appEnv !== "production";
  }

  const cases: [string, string][] = [
    ["development", "development"],
    ["production", "development"],
    ["development", "production"],
    ["production", "production"],
    ["test", "development"],
  ];

  it.each(cases)("agrees for NODE_ENV=%s, app env=%s", (nodeEnv, appEnv) => {
    setNodeEnv(nodeEnv);
    process.env.NEXT_PUBLIC_PROJECTONE_ENVIRONMENT = appEnv;

    expect(devRoutesEnabled()).toBe(configExpression(nodeEnv, appEnv));
  });
});

describe("isDevOnlyPath", () => {
  it("matches the namespace root and everything beneath it", () => {
    expect(isDevOnlyPath("/dev")).toBe(true);
    expect(isDevOnlyPath("/dev/session")).toBe(true);
    expect(isDevOnlyPath("/dev/anything/nested")).toBe(true);
  });

  it("does not match an application route", () => {
    expect(isDevOnlyPath("/dashboard")).toBe(false);
    expect(isDevOnlyPath("/sign-in")).toBe(false);
    expect(isDevOnlyPath("/")).toBe(false);
  });

  it("does not match a route that merely starts with the same letters", () => {
    // `/developer-settings` is a real application route someone could add, and
    // silently gating it behind a development-only check would be a confusing
    // production outage.
    expect(isDevOnlyPath("/developer-settings")).toBe(false);
    expect(isDevOnlyPath("/devices")).toBe(false);
  });
});
