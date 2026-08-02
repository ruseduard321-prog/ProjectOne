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
 */
export interface UserMenuProps {
  /** The signed-in user's email, shown as their identity. */
  readonly email: string;
}

export function UserMenu({ email }: UserMenuProps) {
  return (
    <div className="flex items-center gap-4">
      <span className="text-sm text-text-muted" title={email}>
        {email}
      </span>

      <form action={signOutAction}>
        <button
          type="submit"
          className="rounded-md px-3 py-1.5 text-sm font-medium text-text-muted transition-colors hover:bg-surface-raised hover:text-text"
        >
          Sign out
        </button>
      </form>
    </div>
  );
}
