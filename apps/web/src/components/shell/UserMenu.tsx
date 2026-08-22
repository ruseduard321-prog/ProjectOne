import { signOutAction } from "@/app/(auth)/actions";

/**
 * The signed-in user's identity and the sign-out control.
 *
 * A Server Component with no client JavaScript at all: the sign-out button is a
 * plain form posting to a Server Action, which works without hydration and
 * therefore before it — and continues to work with JavaScript disabled.
 *
 * A form rather than a link, deliberately. Sign-out revokes the session
 * upstream, which is a state change, and a GET that changes state can be
 * triggered by anything that prefetches a URL — including the browser itself.
 *
 * ## Why it is stacked, and why that is not cosmetic
 *
 * It renders at the foot of the navigation plane — the rail on desktop, the
 * drawer on mobile — so it has a column's width rather than a header's
 * leftovers. Laid out beside the sign-out control in a top bar, a real address
 * was compressed to an unreadable fragment on any narrow viewport; stacked, the
 * address gets the full width of the plane and truncates only when it genuinely
 * exceeds it. The full value stays available as the title either way.
 *
 * ## Tokens
 *
 * `nav-*` exclusively. This renders **inside the navigation plane**, and
 * [[ADR-003 Product Visual Language and Token Semantics]] Decision 3 is
 * explicit: a component rendering there references the `nav-*` family, and a
 * component rendering on the canvas never does. It used canvas tokens while it
 * lived in a canvas-coloured header; moving it onto the plane moves its tokens.
 */
export interface UserMenuProps {
  /** The signed-in user's email, shown as their identity. */
  readonly email: string;
}

export function UserMenu({ email }: UserMenuProps) {
  return (
    <div className="flex flex-col gap-1">
      <span className="truncate px-3 text-sm text-text-on-nav-muted" title={email}>
        {email}
      </span>

      <form action={signOutAction}>
        <button
          type="submit"
          // min-h-11 is the 44px coarse-pointer target §9.1 rule 9 requires.
          className="flex min-h-11 w-full items-center rounded-md px-3 text-sm font-medium text-text-on-nav-muted transition-colors duration-(--duration-fast) ease-(--ease-standard) hover:bg-nav-surface-raised hover:text-text-on-nav"
        >
          Sign out
        </button>
      </form>
    </div>
  );
}
