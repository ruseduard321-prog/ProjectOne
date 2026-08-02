/**
 * The shape a form submission returns.
 *
 * Lives here rather than beside the actions that produce it for a hard
 * framework reason: a `"use server"` module may export **only async functions**,
 * because every export becomes a remotely-callable endpoint. A constant exported
 * from one fails the build. Types are erased and would survive, but keeping the
 * type and its empty value together is what stops the two drifting.
 */

import type { FieldErrors } from "@/lib/credentials";

export interface FormState {
  /** Per-input validation messages, rendered beside their field. */
  readonly fieldErrors: FieldErrors;
  /** A form-level failure — the API's own message, rendered above the form. */
  readonly formError?: string;
  /** Correlation id from the API's error envelope, so a report is traceable. */
  readonly requestId?: string | null;
  /** Set when registration succeeded but the account needs email confirmation. */
  readonly confirmationRequired?: boolean;
}

/** The state a form starts in, before any submission. */
export const EMPTY_FORM_STATE: FormState = { fieldErrors: {} };
