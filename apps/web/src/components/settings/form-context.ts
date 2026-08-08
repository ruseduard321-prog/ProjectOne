"use client";

/**
 * The state of the enclosing form, read by the fields inside it.
 *
 * ## Why this exists
 *
 * A field needs two things from the form around it: the current {@link FormState}
 * so it can render its own validation error, and whether a submission is in
 * flight so it can disable itself. `SettingsForm` owns both, because both come
 * from `useActionState`.
 *
 * The obvious way to hand them down is a render prop — `children` as a function
 * of `(state, pending)`. That is exactly what this replaces, and the reason is a
 * hard constraint rather than a preference: **every page rendering a settings
 * form is a Server Component**, and a function is not serializable across the
 * server/client boundary. React refuses it with *"Functions are not valid as a
 * child of Client Components"*. Passing plain JSX and letting the fields read
 * this context keeps the pages on the server, which is where CLAUDE.md §11 wants
 * them and where the httpOnly access token requires them to stay.
 *
 * ## Why a context rather than cloned props
 *
 * The alternative — `SettingsForm` walking `children` and injecting props — only
 * reaches direct descendants, so it breaks the moment a field is nested inside a
 * layout `<div>`, which every current caller does. A context reaches any depth
 * and needs no cooperation from the markup in between.
 *
 * The default is a non-pending empty state, so a field rendered outside a form
 * degrades to "no error, enabled" rather than throwing. That is deliberate: a
 * missing provider is a caller mistake worth surviving, not worth crashing a
 * page over.
 */

import { createContext, useContext } from "react";

import { EMPTY_FORM_STATE, type FormState } from "@/lib/form-state";

/** What a field may read from the form enclosing it. */
export interface SettingsFormContextValue {
  /** The most recent action result, carrying any per-field errors. */
  readonly state: FormState;
  /**
   * Whether inputs should be disabled.
   *
   * Combines an in-flight submission with the caller's `disabledReason`, so a
   * field asks one question rather than reproducing that rule per call site.
   */
  readonly pending: boolean;
}

const SettingsFormContext = createContext<SettingsFormContextValue>({
  state: EMPTY_FORM_STATE,
  pending: false,
});

export const SettingsFormProvider = SettingsFormContext.Provider;

/** Read the enclosing form's state. Safe outside a form: reports idle and clean. */
export function useSettingsFormContext(): SettingsFormContextValue {
  return useContext(SettingsFormContext);
}

/**
 * The error recorded for one field, if any.
 *
 * A helper rather than each field indexing `state.fieldErrors` itself, so the
 * shape of that lookup lives in one place.
 */
export function useFieldError(name: string): string | undefined {
  return useSettingsFormContext().state.fieldErrors[name];
}
