import { describe, expect, it } from "vitest";

import {
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  hasErrors,
  validateSignIn,
  validateSignUp,
} from "@/lib/credentials";

describe("validateSignUp", () => {
  it("accepts a well-formed email and a long-enough password", () => {
    expect(validateSignUp("user@example.com", "correct horse")).toEqual({});
  });

  it("rejects a missing email", () => {
    expect(validateSignUp("   ", "correct horse").email).toBeDefined();
  });

  it("rejects a malformed email", () => {
    expect(validateSignUp("user@example", "correct horse").email).toBeDefined();
    expect(validateSignUp("user example.com", "correct horse").email).toBeDefined();
  });

  it("rejects a password below the API's own floor", () => {
    const password = "a".repeat(PASSWORD_MIN_LENGTH - 1);

    expect(validateSignUp("user@example.com", password).password).toBeDefined();
  });

  it("accepts a password exactly at the floor", () => {
    const password = "a".repeat(PASSWORD_MIN_LENGTH);

    expect(validateSignUp("user@example.com", password).password).toBeUndefined();
  });

  it("rejects a password above the API's ceiling", () => {
    const password = "a".repeat(PASSWORD_MAX_LENGTH + 1);

    expect(validateSignUp("user@example.com", password).password).toBeDefined();
  });
});

describe("validateSignIn", () => {
  it("accepts any non-empty password", () => {
    // Deliberately shorter than the sign-up floor: a length rule here would
    // distinguish a short legacy password from a wrong one, which tells an
    // attacker their guess was the wrong shape rather than merely wrong.
    expect(validateSignIn("user@example.com", "short").password).toBeUndefined();
  });

  it("rejects an empty password", () => {
    expect(validateSignIn("user@example.com", "").password).toBeDefined();
  });

  it("rejects a malformed email", () => {
    expect(validateSignIn("nope", "whatever").email).toBeDefined();
  });
});

describe("hasErrors", () => {
  it("is false for a clean result", () => {
    expect(hasErrors({})).toBe(false);
  });

  it("is true when any field failed", () => {
    expect(hasErrors({ email: "Enter your email address." })).toBe(true);
  });
});
