"use client";

import { type ReactNode, useCallback, useEffect, useRef } from "react";

import { NavLinks } from "@/components/shell/NavLinks";
import { ShellIdentity } from "@/components/shell/ShellIdentity";

/**
 * Navigation below the `md` breakpoint, where the rail is not persistent.
 *
 * ## Why this exists
 *
 * [[Design System]] §9a rule 2 has required a drawer since it was written, and
 * the shell never had one: below `md` the four rail destinations simply
 * stacked above the content, so every page on a phone opened with the
 * navigation instead of with the page.
 *
 * It carries the **same three regions as the rail** — product identity,
 * destinations, signed-in user — because they are the same navigation plane at
 * a different width, not a reduced version of it. In particular the signed-in
 * address and the sign-out control live here rather than in the mobile header,
 * where a real address had to be compressed into an unreadable fragment to fit
 * beside a trigger and a wordmark.
 *
 * ## Why a native `<dialog>`
 *
 * The same reasoning `ConfirmDialog` records, and deliberately the same
 * mechanism rather than a second one. `showModal()` supplies the focus trap,
 * the `Escape` handler, the inert background and the top-layer stacking that a
 * hand-built drawer must otherwise reimplement — and reimplement correctly,
 * because a drawer whose focus escapes is a drawer a keyboard user can lose
 * inside a page they cannot see.
 *
 * §9a rule 2's three requirements map onto it exactly:
 *
 *  - focus is trapped while open — `showModal()`,
 *  - `Escape` closes it — native, observed through the `close` event so React
 *    can never disagree with what the browser actually did,
 *  - focus returns to the trigger — done explicitly on `close`, rather than
 *    relying on the browser's own restoration, because that behaviour varies
 *    between engines and the rule does not.
 *
 * Choosing a destination closes the drawer as well. A drawer left open over
 * the page it just navigated to is a drawer the user has to dismiss twice.
 */
export interface MobileNavProps {
  /**
   * The signed-in user's identity and sign-out control, for the foot of the
   * drawer.
   *
   * Rendered JSX rather than an email string, so `UserMenu` stays a **Server
   * Component**: importing it here would pull it — and the server action it
   * posts to — into the client bundle. This is the same constraint
   * `ConfirmDialog` records for its confirming control.
   */
  readonly identity: ReactNode;
}

export function MobileNav({ identity }: MobileNavProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const open = useCallback(() => {
    dialogRef.current?.showModal();
  }, []);

  const close = useCallback(() => {
    dialogRef.current?.close();
  }, []);

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
    <div className="md:hidden">
      <button
        ref={triggerRef}
        type="button"
        onClick={open}
        /*
         * `aria-haspopup="dialog"` rather than `aria-expanded`: this opens a
         * modal in the top layer, not a disclosure that expands in place, and
         * announcing it as the latter would promise a relationship the DOM
         * does not have once `showModal()` moves it.
         */
        aria-haspopup="dialog"
        className="flex min-h-11 min-w-11 items-center justify-center rounded-md px-3 text-sm font-medium text-text-muted transition-colors duration-(--duration-fast) ease-(--ease-standard) hover:bg-surface-raised hover:text-text"
      >
        Menu
      </button>

      <dialog
        ref={dialogRef}
        /*
         * Named directly rather than by a visible heading. The drawer's visible
         * top is the product wordmark, which names the product rather than the
         * region — so labelling the dialog with it would announce "ProjectOne
         * dialog" and tell a screen-reader user nothing about what they opened.
         */
        aria-label="Navigation"
        /*
         * Pinned to the inline start and full height: a drawer, not a centred
         * modal. `max-w-none`/`max-h-none` override the user-agent defaults
         * that would otherwise cap a `<dialog>` at 80% of the viewport, and
         * `p-0` replaces its default padding with the regions' own.
         */
        className="m-0 h-full max-h-none w-72 max-w-none bg-nav-surface p-0 text-text-on-nav backdrop:bg-overlay"
      >
        <div className="flex h-full flex-col">
          <div className="flex h-16 shrink-0 items-center justify-between gap-3 px-5">
            <ShellIdentity />

            <button
              type="button"
              onClick={close}
              className="-mr-2 flex min-h-11 min-w-11 items-center justify-center rounded-md px-3 text-sm font-medium text-text-on-nav-muted transition-colors duration-(--duration-fast) ease-(--ease-standard) hover:bg-nav-surface-raised hover:text-text-on-nav"
            >
              Close
            </button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
            <nav aria-label="Main">
              <NavLinks onNavigate={close} />
            </nav>
          </div>

          <div className="shrink-0 px-3 pb-5">{identity}</div>
        </div>
      </dialog>
    </div>
  );
}
