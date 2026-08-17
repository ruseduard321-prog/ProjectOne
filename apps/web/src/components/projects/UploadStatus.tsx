/**
 * What an upload is doing, rendered from state alone.
 *
 * ## Why this is separate from the control that owns the upload
 *
 * `AssetUpload` holds an `XMLHttpRequest`, a progress counter and three
 * outcomes. None of that can be exercised by this repository's test suite: it
 * runs in a **node environment with no DOM** (`vitest.config.ts`), rendering
 * through `renderToStaticMarkup`, which cannot drive hook state or dispatch an
 * event. A component that both owns the request and draws the result would
 * therefore have four required states ([[Design System]] §10) and no way to
 * prove any of them.
 *
 * Split this way, every state is a value. `upload-status.test.tsx` renders each
 * one directly and asserts what a user would see, with no DOM and no new test
 * dependency ([[CLAUDE|CLAUDE.md]] §28). That the split is also plain
 * presentation-from-logic separation (§11) is the reason it costs nothing.
 *
 * A Server Component by default — nothing here needs the browser.
 */

/** Where an upload is. Exhaustive: every state the control can be in is here. */
export type UploadPhase =
  /** Nothing has been attempted yet, or the last attempt was cleared. */
  | { readonly kind: "idle" }
  /**
   * The request has been opened but no byte count has arrived.
   *
   * A real state rather than a rounding of "0%": until the first progress event
   * the browser has not said how much there is to send, and a determinate bar
   * showing zero would claim knowledge that does not exist yet.
   */
  | { readonly kind: "starting" }
  | { readonly kind: "sending"; readonly percent: number }
  | {
      readonly kind: "failed";
      readonly message: string;
      readonly requestId: string | null;
    }
  | { readonly kind: "done"; readonly name: string };

export interface UploadStatusProps {
  readonly phase: UploadPhase;
}

export function UploadStatus({ phase }: UploadStatusProps) {
  if (phase.kind === "idle") {
    return null;
  }

  if (phase.kind === "failed") {
    /*
     * `role="alert"` because this appears after load and the user must know the
     * upload did not happen — the §9.1 rule 6 case, and the same treatment
     * `SettingsForm` gives a form-level failure.
     *
     * The message is the API's own. Its refusals name the rule that was broken
     * and are written never to echo the filename, so nothing is prepended,
     * appended, or substituted here.
     */
    return (
      <div
        role="alert"
        className="rounded-md border border-danger px-4 py-3 text-sm text-danger"
      >
        <p>{phase.message}</p>
        {phase.requestId !== null ? (
          <p className="mt-1 text-text-muted">Reference: {phase.requestId}</p>
        ) : null}
      </div>
    );
  }

  if (phase.kind === "done") {
    // `role="status"` rather than `alert`: a completed upload is polite
    // information, and interrupting a screen reader to announce success is
    // worse than announcing it at the next pause.
    return (
      <p role="status" className="text-sm text-text-muted">
        Uploaded {phase.name}.
      </p>
    );
  }

  const determinate = phase.kind === "sending";
  const percent = determinate ? phase.percent : 0;

  return (
    <div className="flex flex-col gap-2">
      {/*
       * A native progress element: it is announced as a progress bar, exposes
       * its value to assistive technology, and needs no ARIA of its own.
       * Omitting `value` is what makes it indeterminate, which is exactly the
       * `starting` state — the platform already models the distinction this
       * component needs to draw.
       */}
      <progress
        aria-label="Upload progress"
        value={determinate ? percent : undefined}
        max={100}
        className="h-2 w-full overflow-hidden rounded-full"
      />

      <p role="status" className="text-sm text-text-muted">
        {determinate ? `Uploading — ${percent}%` : "Starting upload…"}
      </p>
    </div>
  );
}
