/**
 * Client-side credential validation.
 *
 * Pure functions with no React and no framework, so the rules are unit-testable
 * without rendering anything — business logic does not belong inside a
 * component (CLAUDE.md §35).
 *
 * **This is a convenience, not a control.** The API validates every field
 * again (`app/schemas/auth.py`), and it is that check which is authoritative.
 * What this buys is a user learning their password is too short before a
 * round-trip, rather than after one.
 *
 * The bounds deliberately mirror the API's own so the two cannot disagree: a
 * client rule stricter than the server's rejects valid input, and one looser
 * produces a 422 the form claimed would not happen.
 */

/** Matches the API's `Field(min_length=8)` on sign-up. */
export const PASSWORD_MIN_LENGTH = 8;

/** Matches the API's `Field(max_length=128)` on both sign-up and sign-in. */
export const PASSWORD_MAX_LENGTH = 128;

/** Field-keyed validation messages. An empty object means the form is valid. */
export type FieldErrors = Partial<Record<"email" | "password", string>>;

/**
 * Whether a string is plausibly an email address.
 *
 * Deliberately permissive: one `@`, something either side, no whitespace, and a
 * dot in the domain. A stricter regex is a well-known way to reject addresses
 * that are actually valid, and the API's `EmailStr` is the real check.
 */
function looksLikeEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

/**
 * Validate sign-up input.
 *
 * The password floor is enforced here because it is a rule the user can fix
 * before submitting, and telling them so immediately is better than spending a
 * request on it.
 */
export function validateSignUp(email: string, password: string): FieldErrors {
  const errors: FieldErrors = {};

  if (email.trim() === "") {
    errors.email = "Enter your email address.";
  } else if (!looksLikeEmail(email)) {
    errors.email = "Enter a valid email address.";
  }

  if (password === "") {
    errors.password = "Enter a password.";
  } else if (password.length < PASSWORD_MIN_LENGTH) {
    errors.password = `Use at least ${PASSWORD_MIN_LENGTH} characters.`;
  } else if (password.length > PASSWORD_MAX_LENGTH) {
    errors.password = `Use no more than ${PASSWORD_MAX_LENGTH} characters.`;
  }

  return errors;
}

/**
 * Validate sign-in input.
 *
 * Deliberately weaker than {@link validateSignUp}: presence only, no minimum
 * length. The API makes the same distinction and for the same reason — a length
 * rule on sign-in rejects a short legacy password with a message that differs
 * from a wrong-password message, telling an attacker their guess was the wrong
 * *shape* rather than merely wrong.
 */
export function validateSignIn(email: string, password: string): FieldErrors {
  const errors: FieldErrors = {};

  if (email.trim() === "") {
    errors.email = "Enter your email address.";
  } else if (!looksLikeEmail(email)) {
    errors.email = "Enter a valid email address.";
  }

  if (password === "") {
    errors.password = "Enter your password.";
  }

  return errors;
}

/** Whether a validation result holds any error. */
export function hasErrors(errors: FieldErrors): boolean {
  return Object.keys(errors).length > 0;
}
