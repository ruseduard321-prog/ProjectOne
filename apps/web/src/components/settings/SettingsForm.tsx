"use client";

/**
 * The shared shell for every settings form.
 *
 * A Client Component because each form needs three things the server cannot
 * give it: the pending state of an in-flight submission, the action-state hook
 * that carries errors back without a page reload, and focus management after a
 * failure. The boundary is kept to the form — every section heading, every
 * rendered value and the page around them stay on the server (CLAUDE.md §11).
 *
 * Defined once rather than per section for the reason `CredentialsForm` gives:
 * near-identical form components drift the moment one of them gains an
 * accessibility fix the other does not. Four settings forms is four chances to
 * forget the error announcement.
 *
 * ## What this owns, and what the caller owns
 *
 * This owns the `<form>`, the submit button, the error region, the success
 * confirmation, and the focus behaviour. The caller supplies the fields, because
 * they differ entirely between a display name and a spend ceiling — and a
 * component that tried to own both would be a schema-driven form builder, which
 * is a great deal more machinery than four forms justify.
 *
 * The fields arrive as plain JSX and read their error and disabled state from
 * `form-context.ts`. They cannot be handed down as a render prop, because every
 * page that renders one of these forms is a Server Component and a function
 * cannot cross that boundary.
 */

import { type ReactNode, useActionState, useEffect, useRef } from "react";

import { SettingsFormProvider } from "@/components/settings/form-context";
import { EMPTY_FORM_STATE, type FormState } from "@/lib/form-state";

export interface SettingsFormProps {
  /** The Server Action this form posts to. */
  readonly action: (previous: FormState, data: FormData) => Promise<FormState>;
  readonly submitLabel: string;
  readonly pendingLabel: string;
  /** Confirmation shown after a successful save. */
  readonly savedLabel?: string;
  /**
   * Hidden values the action needs — the workspace id, the provider name.
   *
   * Passed as props rather than read from a context: a Server Action receives
   * only what the form submits, so these have to be in the payload, and putting
   * them here keeps every caller's hidden inputs in one visible place.
   */
  readonly hidden?: Readonly<Record<string, string>>;
  /**
   * Rendered when the caller's role does not permit this change.
   *
   * The form still renders its fields, disabled, rather than vanishing: a
   * control that is absent tells a member nothing, while one that is present and
   * disabled with a reason tells them the setting exists and who can change it.
   */
  readonly disabledReason?: string;
  /** Styling variant for the submit button. `danger` for destructive actions. */
  readonly intent?: "primary" | "danger";
  /**
   * The fields.
   *
   * Plain JSX rather than a render prop, so a **Server Component** can pass it:
   * a function child is not serializable across the server/client boundary and
   * React rejects it outright. Fields read the current state and pending flag
   * from {@link SettingsFormProvider} instead — see `form-context.ts`.
   */
  readonly children: ReactNode;
}

export function SettingsForm({
  action,
  submitLabel,
  pendingLabel,
  savedLabel = "Saved",
  hidden,
  disabledReason,
  intent = "primary",
  children,
}: SettingsFormProps) {
  const [state, formAction, pending] = useActionState(action, EMPTY_FORM_STATE);

  const statusRef = useRef<HTMLDivElement>(null);

  /*
   * Move focus to the form-level error after a failed submit.
   *
   * Without it a keyboard or screen reader user submits, focus stays on the
   * button, and the message is rendered but unreachable without hunting for it
   * ([[Design System]] §9). Field-level errors are announced by their own
   * `aria-describedby` wiring in `FormField`, so only the form-level case needs
   * an explicit focus target.
   */
  useEffect(() => {
    if (!pending && state.formError !== undefined) {
      statusRef.current?.focus();
    }
  }, [state, pending]);

  const locked = disabledReason !== undefined;

  return (
    <form action={formAction} noValidate className="flex flex-col gap-4">
      {Object.entries(hidden ?? {}).map(([name, value]) => (
        <input key={name} type="hidden" name={name} value={value} />
      ))}

      {state.formError !== undefined ? (
        <div
          ref={statusRef}
          role="alert"
          tabIndex={-1}
          className="rounded-md border border-danger px-4 py-3 text-sm text-danger"
        >
          <p>{state.formError}</p>
          {state.requestId != null ? (
            <p className="mt-1 text-text-muted">Reference: {state.requestId}</p>
          ) : null}
        </div>
      ) : null}

      <SettingsFormProvider value={{ state, pending: pending || locked }}>
        {children}
      </SettingsFormProvider>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={pending || locked}
          className={[
            "rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:opacity-60",
            intent === "danger"
              ? "border border-danger text-danger hover:bg-danger hover:text-accent-contrast"
              : "bg-accent text-accent-contrast hover:bg-accent-hover",
          ].join(" ")}
        >
          {pending ? pendingLabel : submitLabel}
        </button>

        {/*
         * role="status" rather than role="alert": a save confirmation is
         * polite information, and interrupting a screen reader mid-sentence to
         * announce success is worse than announcing it when they pause.
         */}
        {state.saved === true && !pending ? (
          <p role="status" className="text-sm text-text-muted">
            {savedLabel}
          </p>
        ) : null}

        {locked ? <p className="text-sm text-text-muted">{disabledReason}</p> : null}
      </div>
    </form>
  );
}
