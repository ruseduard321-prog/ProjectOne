import { describe, expect, it } from "vitest";

import { parseEnv } from "@/lib/env";

/**
 * Tests for environment validation.
 *
 * STEP-06 asked only for one trivial test proving the runner executes. These
 * cover real behavior instead: `parseEnv` was deliberately separated from the
 * live `process.env` in STEP-05 so it could be tested, and a placeholder test
 * would leave that seam unused while still turning the suite green — which
 * proves the runner works and nothing else.
 */

const VALID = {
  NEXT_PUBLIC_PROJECTONE_ENVIRONMENT: "development",
  NEXT_PUBLIC_PROJECTONE_API_URL: "http://127.0.0.1:8000",
};

describe("parseEnv", () => {
  it("accepts a valid configuration", () => {
    const env = parseEnv(VALID);

    expect(env.environment).toBe("development");
    expect(env.apiUrl).toBe("http://127.0.0.1:8000");
  });

  it("accepts every documented environment", () => {
    for (const environment of ["development", "staging", "production"]) {
      const env = parseEnv({ ...VALID, NEXT_PUBLIC_PROJECTONE_ENVIRONMENT: environment });

      expect(env.environment).toBe(environment);
    }
  });

  it("rejects a missing environment and names the variable", () => {
    expect(() =>
      parseEnv({ ...VALID, NEXT_PUBLIC_PROJECTONE_ENVIRONMENT: undefined }),
    ).toThrow(/NEXT_PUBLIC_PROJECTONE_ENVIRONMENT is required/);
  });

  it("rejects an unknown environment rather than passing it through", () => {
    // "prod" is the plausible typo. Silently accepting it would let a deploy
    // run in an environment nothing else in the system knows about.
    expect(() => parseEnv({ ...VALID, NEXT_PUBLIC_PROJECTONE_ENVIRONMENT: "prod" })).toThrow(
      /must be one of/,
    );
  });

  it("rejects a malformed API URL", () => {
    expect(() => parseEnv({ ...VALID, NEXT_PUBLIC_PROJECTONE_API_URL: "not-a-url" })).toThrow(
      /must be a valid absolute URL/,
    );
  });

  it("reports every problem at once, not just the first", () => {
    // A misconfigured deploy should be fixable in one pass rather than one
    // variable per restart.
    const act = () =>
      parseEnv({
        NEXT_PUBLIC_PROJECTONE_ENVIRONMENT: undefined,
        NEXT_PUBLIC_PROJECTONE_API_URL: undefined,
      });

    expect(act).toThrow(/NEXT_PUBLIC_PROJECTONE_ENVIRONMENT/);
    expect(act).toThrow(/NEXT_PUBLIC_PROJECTONE_API_URL/);
  });

  it("treats an empty string as missing", () => {
    // An unset variable in CI often arrives as "" rather than undefined.
    expect(() => parseEnv({ ...VALID, NEXT_PUBLIC_PROJECTONE_ENVIRONMENT: "" })).toThrow(
      /is required/,
    );
  });
});
