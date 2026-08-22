"use client";

/**
 * Asks before something irreversible happens.
 *
 * ## Why this component exists
 *
 * [[Design System]] §7.1 defined no dialog when this was written, while the
 * token layer named one in three places — `--radius-lg` as "Dialogs, panels",
 * `--shadow-lg` as "Dialogs", `--color-surface-raised` as "Dropdowns, dialogs".
 * STEP-26 shipped the tokens and no components at all, so the gap was a missing
 * component rather than a deliberate absence. [[STEP-29 Asset Management UI]]
 * D4 closed it, and §7.1 now carries this contract.
 *
 * A Client Component: it holds open/closed state and drives an imperative
 * browser API. That is the whole client boundary — the confirming control
 * arrives as {@link ConfirmDialogProps.children} already rendered on the server.
 *
 * ## Why a native `<dialog>`
 *
 * `showModal()` brings the focus trap, the `Escape` handler, the inert
 * background and the top-layer stacking that a hand-built modal has to
 * reimplement — and reimplement correctly, since a modal whose focus escapes is
 * a modal a keyboard user can lose. Adding a dependency to restate what the
 * platform already does would be surface area for no gain
 * ([[CLAUDE|CLAUDE.md]] §28).
 *
 * Behaviour required by [[Design System]] §9a rule 2, which is the nearest
 * binding precedent (the navigation drawer):
 *
 *  - focus is trapped while open — `showModal()`,
 *  - `Escape` closes it — native, observed through the `close` event so React
 *    state cannot drift from what the browser did,
 *  - focus returns to the control that opened it — done explicitly below rather
 *    than relying on the browser's own restoration, because that behaviour
 *    varies and the rule does not.
 *
 * **Cancel is focused first and confirm is never the default.** A destructive
 * action reached by pressing Enter on a dialog the user has not read is the
 * failure this component exists to prevent.
 *
 * ## Why there is no backdrop-click close
 *
 * Deliberate. A stray click dismissing a confirmation is harmless; the same
 * gesture landing on a confirm button is not, and the two are one misplaced
 * `stopPropagation` apart. `Escape` and the Cancel button are the two ways out,
 * both keyboard-reachable, and both announced.
 */

import { type ReactNode, useCallback, useEffect, useId, useRef } from "react";

export interface ConfirmDialogProps {
  /** The control that opens the dialog. Names the action, not the object. */
  readonly triggerLabel: string;
  /** The question, as a question. Rendered as the dialog's accessible name. */
  readonly title: string;
  /** What will happen, in one sentence. Names the thing being acted on. */
  readonly description: string;
  /** The Cancel control's label. */
  readonly cancelLabel?: string;
  /**
   * The confirming control — normally a form that performs the action.
   *
   * Plain JSX rather than a callback, so a **Server Component** can supply it: a
   * function child is not serializable across the server/client boundary and
   * React rejects it outright. This is the same constraint `SettingsForm`
   * records, and for the same reason.
   */
  readonly children: ReactNode;
}

export function ConfirmDialog({
  triggerLabel,
  title,
  description,
  cancelLabel = "Cancel",
  children,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const titleId = useId();
  const descriptionId = useId();

  const open = useCallback(() => {
    dialogRef.current?.showModal();
  }, []);

  const close = useCallback(() => {
    dialogRef.current?.close();
  }, []);

  /*
   * Return focus to the trigger however the dialog was dismissed.
   *
   * Listening for `close` rather than handling each exit path separately is
   * what makes `Escape` behave identically to the Cancel button — the browser
   * fires it for both, and for a `dialog.close()` from anywhere else.
   */
  useEffect(() => {
    const dialog = dialogRef.current;

    if (dialog === null) {
      return;
    }

    const onClose = () => {
      triggerRef.current?.focus();
    };

    dialog.addEventListener("close", onClose);

    return () => {
      dialog.removeEventListener("close", onClose);
    };
  }, []);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={open}
        className="rounded-md border border-danger px-4 py-2 text-sm font-medium text-danger transition-colors hover:bg-danger hover:text-danger-contrast"
      >
        {triggerLabel}
      </button>

      <dialog
        ref={dialogRef}
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="max-w-prose rounded-lg border border-border bg-surface-raised p-6 text-text shadow-lg backdrop:bg-overlay"
      >
        <div className="flex flex-col gap-4">
          <h2 id={titleId} className="text-lg font-medium text-text">
            {title}
          </h2>

          <p id={descriptionId} className="text-sm text-text-muted">
            {description}
          </p>

          <div className="flex flex-wrap items-center gap-3">
            {/*
             * First in the DOM and explicitly autofocused, so the destructive
             * control is never what Enter reaches. Tab order follows visual
             * order, which §9.1 rule 4 requires.
             */}
            <button
              type="button"
              autoFocus
              onClick={close}
              className="rounded-md border border-border-strong px-4 py-2 text-sm font-medium text-text transition-colors hover:bg-surface"
            >
              {cancelLabel}
            </button>

            {children}
          </div>
        </div>
      </dialog>
    </>
  );
}
