/**
 * The retry behaviour shared by every route error boundary.
 *
 * ## Why this exists
 *
 * Every boundary shipped with `onClick={reset}`, and three of them documented
 * that `reset()` "genuinely recovers" from an unreachable API. It does not.
 * Next.js's `reset()` is client state and nothing more:
 *
 * ```js
 * this.reset = () => { this.setState({ error: null }); };
 * ```
 *
 * It clears the boundary and re-renders the *cached* RSC payload — which still
 * contains the failure, so the boundary immediately renders again. Observed
 * directly during STEP-24: with a fault injected into one dashboard fetch, three
 * clicks produced zero server requests and no visible change. The control looked
 * real and recovered nothing, which is the failure mode CLAUDE.md §24 exists to
 * prevent — a user told to try again by a button that cannot succeed.
 *
 * Recovery needs the server to re-run. `router.refresh()` refetches the Server
 * Component; `reset()` then clears the boundary so the fresh payload can render.
 * Both must happen, and in one transition, or the boundary clears against the
 * stale payload and flashes the error again before the refresh lands.
 *
 * ## Why not `unstable_retry`
 *
 * Next.js has exactly this built in, and it is where the shape below comes
 * from — but it is prefixed `unstable_` and reached through the boundary's
 * internal context. `useRouter().refresh()` and `startTransition` are the stable
 * public equivalents, so this depends on the supported API rather than an
 * internal one that can change without a major version (CLAUDE.md §28).
 *
 * ## Why only the behaviour is shared
 *
 * Each boundary keeps its own markup, heading, message and digest handling. The
 * copy is deliberately different per screen — "your projects are safe" versus
 * "your conversations are safe" — and a shared visual component would either
 * flatten that into one generic message or grow a prop for every difference.
 * What was actually duplicated, and actually wrong in all four copies, is the
 * recovery. That is what this shares (CLAUDE.md §29).
 */

"use client";

import { useRouter } from "next/navigation";
import { startTransition, useCallback } from "react";

/**
 * Build the retry handler for an error boundary.
 *
 * @param reset - The `reset` prop Next.js passes to an `error.tsx` boundary.
 * @returns A handler that refetches the route, then clears the boundary.
 *
 * @example
 * ```tsx
 * export default function DashboardError({ error, reset }) {
 *   const retry = useErrorRecovery(reset);
 *   return <button type="button" onClick={retry}>Try again</button>;
 * }
 * ```
 */
export function useErrorRecovery(reset: () => void): () => void {
  const router = useRouter();

  return useCallback(() => {
    // One transition, both updates. Refresh first so the new payload is already
    // in flight when the boundary clears — reversing these, or splitting them
    // across two renders, shows the stale error again in between.
    startTransition(() => {
      router.refresh();
      reset();
    });
  }, [router, reset]);
}
