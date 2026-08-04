/**
 * The shape a form submission returns.
 *
 * Lives here rather than beside the actions that produce it for a hard
 * framework reason: a `"use server"` module may export **only async functions**,
 * because every export becomes a remotely-callable endpoint. A constant exported
 * from one fails the build. Types are erased and would survive, but keeping the
 * type and its empty value together is what stops the two drifting.
 */

/**
 * Per-input validation messages, keyed by the field's `name` attribute.
 *
 * Widened from the auth-only `FieldErrors` when STEP-19 added the settings
 * forms. A `Record<string, string>` rather than a union of every field name in
 * the application: enumerating them here would mean this shared type had to
 * change every time a form gained an input, which is coupling with no benefit —
 * the key is only ever used to look up a message for an input the same component
 * rendered.
 */
export type FormFieldErrors = Partial<Record<string, string>>;

export interface FormState {
  /** Per-input validation messages, rendered beside their field. */
  readonly fieldErrors: FormFieldErrors;
  /** A form-level failure — the API's own message, rendered above the form. */
  readonly formError?: string;
  /** Correlation id from the API's error envelope, so a report is traceable. */
  readonly requestId?: string | null;
  /** Set when registration succeeded but the account needs email confirmation. */
  readonly confirmationRequired?: boolean;
  /**
   * Set when a settings write succeeded, so the form can confirm it.
   *
   * A form that saves and says nothing leaves the user unsure whether it did —
   * and on a settings screen the usual reassurance (the value visibly changing)
   * is absent, because the value they typed is already on screen.
   */
  readonly saved?: boolean;
}

/** The state a form starts in, before any submission. */
export const EMPTY_FORM_STATE: FormState = { fieldErrors: {} };
