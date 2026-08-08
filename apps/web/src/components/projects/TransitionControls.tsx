"use client";

/**
 * The controls that move a project through its lifecycle.
 *
 * ## The one rule this component exists to enforce
 *
 * **It renders exactly the states the server said were legal, and nothing
 * else.** `legalTransitions` comes from the API's `legal_transitions` field,
 * which the backend derives from `legal_transitions_from` per project. There is
 * no map from state to allowed states anywhere in this file — or anywhere else
 * in the frontend — because a second copy of the state machine diverges from the
 * first the moment the rules change ([[Project Lifecycle]]).
 *
 * The consequence worth stating: a screen can never offer a move the server will
 * refuse, and a rules change reaches every client without a frontend deploy.
 *
 * ## Why a Client Component
 *
 * One button per legal state, each submitting a different value through the same
 * Server Action, and each needing its own pending state — a user who clicks
 * "Move to Review" should see *that* button working, not every button. That
 * needs `useActionState` and `useFormStatus`, which are client-only.
 *
 * The boundary stays here: the surrounding page, the project data and every
 * label are rendered on the server.
 */

import { useActionState } from "react";
import { useFormStatus } from "react-dom";

import type { ApiProjectStatus } from "@/lib/api";
import { EMPTY_FORM_STATE, type FormState } from "@/lib/form-state";
import { transitionLabel } from "@/lib/projects";

export interface TransitionControlsProps {
  readonly workspaceId: string;
  readonly projectId: string;
  /** Exactly the states the server will accept, in the order to show them. */
  readonly legalTransitions: readonly ApiProjectStatus[];
  readonly action: (previous: FormState, data: FormData) => Promise<FormState>;
}

/**
 * One transition button, aware of whether *it* is the one submitting.
 *
 * `useFormStatus` reads the enclosing form's pending state, so this has to be a
 * child of the form rather than the form itself — which is why it is a separate
 * component rather than an inline element.
 */
function TransitionButton({ status }: { readonly status: ApiProjectStatus }) {
  const { pending } = useFormStatus();

  const archiving = status === "archive";

  return (
    <button
      type="submit"
      name="status"
      value={status}
      disabled={pending}
      className={[
        "rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:opacity-60",
        archiving
          ? "border border-border text-text-muted hover:bg-surface-raised"
          : "bg-accent text-accent-contrast hover:bg-accent-hover",
      ].join(" ")}
    >
      {pending ? "Working…" : transitionLabel(status)}
    </button>
  );
}

export function TransitionControls({
  workspaceId,
  projectId,
  legalTransitions,
  action,
}: TransitionControlsProps) {
  const [state, formAction] = useActionState(action, EMPTY_FORM_STATE);

  /*
   * The terminal state, rendered honestly rather than as an absence.
   *
   * An archived project has no legal moves, so with no branch here the section
   * would render as an empty div and read as a loading failure. Saying so is
   * also where the archive/delete distinction gets stated to the user.
   */
  if (legalTransitions.length === 0) {
    return (
      <p className="text-sm text-text-muted">
        This project is archived. Archived projects stay in the workspace as a record — deleting
        one is a separate action.
      </p>
    );
  }

  return (
    <form action={formAction} className="flex flex-col gap-3">
      <input type="hidden" name="workspace_id" value={workspaceId} />
      <input type="hidden" name="project_id" value={projectId} />

      {state.formError !== undefined ? (
        <div role="alert" className="rounded-md border border-danger px-4 py-3 text-sm text-danger">
          <p>{state.formError}</p>
          {state.requestId != null ? (
            <p className="mt-1 text-text-muted">Reference: {state.requestId}</p>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-3">
        {legalTransitions.map((status) => (
          <TransitionButton key={status} status={status} />
        ))}
      </div>
    </form>
  );
}
