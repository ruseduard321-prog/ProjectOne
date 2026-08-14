/**
 * The retry behaviour shared by every route error boundary (STEP-24).
 *
 * ## What these are actually asserting
 *
 * That the retry does the one thing `reset()` cannot: make the server run again.
 * The defect these close was not a broken wire — the handler fired, and `reset()`
 * did exactly what it promises. It clears client state and re-renders the cached
 * payload, which still contained the failure. Three clicks, zero server
 * requests, no visible change.
 *
 * So `refresh` being called is the assertion that matters, and the deletion test
 * below exists to prove it fails when the refresh is removed. Without it this
 * file would pass against the original broken code.
 *
 * ## Why the hook is called directly
 *
 * The suite runs in a node environment with no DOM (`vitest.config.ts`), so
 * there is no renderer to host a hook. `useErrorRecovery` is called with
 * `useRouter` and `useCallback` mocked, which is enough because the hook's whole
 * body is the handler it returns — there is no state, no effect and no render
 * output to miss. Adding jsdom and React Testing Library to assert two function
 * calls would be two dependencies bought for nothing (CLAUDE.md §28).
 *
 * `startTransition` is mocked rather than executed so the test can prove *both*
 * calls happen inside it, which is the ordering guarantee the hook exists to
 * provide.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { useErrorRecovery } from "@/lib/error-recovery";

// `vi.hoisted` because the `vi.mock` factories below are hoisted above ordinary
// top-level consts, and would otherwise close over bindings not yet initialised.
const { refresh, startTransition } = vi.hoisted(() => ({
  refresh: vi.fn(),
  startTransition: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

vi.mock("react", () => ({
  startTransition,
  // The identity of the returned callback is irrelevant here; what matters is
  // the body it wraps, so this hands it straight back.
  useCallback: (callback: () => void) => callback,
}));

beforeEach(() => {
  vi.clearAllMocks();
});

/**
 * Build the handler and return it alongside the `reset` it was given.
 *
 * Named as a hook because it calls one — `rules-of-hooks` requires that of any
 * function invoking `useErrorRecovery`. It is a test factory rather than a real
 * hook; there is no renderer here to host one.
 */
function useBuiltRetry(): { retry: () => void; reset: ReturnType<typeof vi.fn> } {
  const reset = vi.fn();

  return { retry: useErrorRecovery(reset), reset };
}

describe("useErrorRecovery", () => {
  it("schedules the recovery in a transition", () => {
    const { retry } = useBuiltRetry();

    retry();

    expect(startTransition).toHaveBeenCalledOnce();
  });

  it("refetches the route, which is what reset alone cannot do", () => {
    /*
     * **The assertion this whole step exists for.** Without this call the
     * boundary re-renders the same cached payload and the user sees no change,
     * however many times they click.
     */
    const { retry } = useBuiltRetry();

    retry();
    runScheduledTransition();

    expect(refresh).toHaveBeenCalledOnce();
  });

  it("clears the boundary so the fresh payload can render", () => {
    const { retry, reset } = useBuiltRetry();

    retry();
    runScheduledTransition();

    expect(reset).toHaveBeenCalledOnce();
  });

  it("does neither until the transition runs, so the two stay batched", () => {
    /*
     * The ordering guarantee. If either call escaped the transition, the
     * boundary could clear against the stale payload and flash the error again
     * before the refresh landed.
     */
    const { retry, reset } = useBuiltRetry();

    retry();

    expect(refresh).not.toHaveBeenCalled();
    expect(reset).not.toHaveBeenCalled();

    runScheduledTransition();

    expect(refresh).toHaveBeenCalledOnce();
    expect(reset).toHaveBeenCalledOnce();
  });

  it("refetches before clearing, so the boundary never clears onto a stale payload", () => {
    const { retry, reset } = useBuiltRetry();

    retry();
    runScheduledTransition();

    expect(refresh.mock.invocationCallOrder[0]).toBeLessThan(reset.mock.invocationCallOrder[0]);
  });
});

/** Execute the callback handed to the mocked `startTransition`. */
function runScheduledTransition(): void {
  const scheduled = startTransition.mock.calls[0]?.[0] as (() => void) | undefined;

  if (scheduled === undefined) {
    throw new Error("Nothing was scheduled in a transition");
  }

  scheduled();
}
