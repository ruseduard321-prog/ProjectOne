"use client";

/**
 * The shared sign-up / sign-in form.
 *
 * A Client Component because it needs three things the server cannot give it:
 * the pending state of an in-flight submission, focus management after a failed
 * one, and the action-state hook that carries errors back without a page
 * reload. The boundary is kept to the form itself — the page around it, its
 * heading and its links all stay on the server (CLAUDE.md §11).
 *
 * Both screens share it because they differ only in labels, autocomplete hints
 * and which action they post to. Two near-identical form components would drift
 * the moment one of them gained an accessibility fix the other did not.
 */

import { useActionState, useEffect, useId, useRef } from "react";

import { FormField } from "@/components/auth/FormField";
import { EMPTY_FORM_STATE, type FormState } from "@/lib/form-state";

export interface CredentialsFormProps {
  /** The Server Action this form posts to. */
  readonly action: (previous: FormState, data: FormData) => Promise<FormState>;
  /** Label on the submit button when idle. */
  readonly submitLabel: string;
  /** Label while the submission is in flight. */
  readonly pendingLabel: string;
  /** `new-password` on sign-up, `current-password` on sign-in. */
  readonly passwordAutoComplete: "new-password" | "current-password";
  /** Hint under the password field, when the screen has one. */
  readonly passwordHint?: string;
}

export function CredentialsForm({
  action,
  submitLabel,
  pendingLabel,
  passwordAutoComplete,
  passwordHint,
}: CredentialsFormProps) {
  const [state, formAction, pending] = useActionState(action, EMPTY_FORM_STATE);

  // useId rather than a hardcoded string: the ids wire labels and error
  // messages to inputs, and two forms on one page would otherwise collide and
  // silently mislabel each other's fields.
  const baseId = useId();
  const emailId = `${baseId}-email`;
  const passwordId = `${baseId}-password`;

  const emailRef = useRef<HTMLDivElement>(null);
  const passwordRef = useRef<HTMLDivElement>(null);
  const formErrorRef = useRef<HTMLDivElement>(null);

  /*
   * Move focus to the first problem after a failed submit.
   *
   * Without this a keyboard or screen reader user submits, focus stays on the
   * button, and nothing announces that anything went wrong — the error is
   * rendered but unreachable without hunting for it ([[Design System]] §9).
   */
  useEffect(() => {
    if (pending) {
      return;
    }

    if (state.fieldErrors.email !== undefined) {
      emailRef.current?.querySelector("input")?.focus();
    } else if (state.fieldErrors.password !== undefined) {
      passwordRef.current?.querySelector("input")?.focus();
    } else if (state.formError !== undefined) {
      formErrorRef.current?.focus();
    }
  }, [state, pending]);

  if (state.confirmationRequired === true) {
    return (
      <div
        role="status"
        className="rounded-md border border-border bg-surface-raised px-4 py-3 text-sm text-text"
      >
        <p className="font-medium">Check your email</p>
        <p className="mt-1 text-text-muted">
          Your account was created. Confirm your email address to finish signing in.
        </p>
      </div>
    );
  }

  return (
    <form action={formAction} noValidate className="flex flex-col gap-6">
      {/*
       * role="alert" so the server's message is announced when it appears.
       * tabIndex makes it focusable as the fallback focus target above — a
       * form-level error belongs to no single field.
       */}
      {state.formError !== undefined ? (
        <div
          ref={formErrorRef}
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

      <div ref={emailRef}>
        <FormField
          id={emailId}
          name="email"
          label="Email"
          type="email"
          autoComplete="email"
          error={state.fieldErrors.email}
          disabled={pending}
        />
      </div>

      <div ref={passwordRef}>
        <FormField
          id={passwordId}
          name="password"
          label="Password"
          type="password"
          autoComplete={passwordAutoComplete}
          error={state.fieldErrors.password}
          hint={passwordHint}
          disabled={pending}
        />
      </div>

      <button
        type="submit"
        disabled={pending}
        className={[
          "rounded-md bg-accent-fill px-4 py-2 text-sm font-medium text-accent-contrast",
          "transition-colors hover:bg-accent-hover disabled:opacity-60",
        ].join(" ")}
      >
        {pending ? pendingLabel : submitLabel}
      </button>
    </form>
  );
}
