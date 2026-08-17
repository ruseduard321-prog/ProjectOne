"use client";

/**
 * Shows an asset's contents, having first asked for a URL to reach them by.
 *
 * ## Why the URL is not already here
 *
 * A signed URL is a **bearer capability**: anyone holding it reads the object
 * with no further authentication, and it lives fifteen minutes (STEP-28 D3).
 * Minting one for every asset while the list renders would spend that lifetime
 * while the page was merely being read, issue an API call per row, and — the
 * decisive objection — place capabilities into server-rendered HTML that Next.js
 * may cache and serve to whoever asks next.
 *
 * So the URL is minted **on user action only** ([[STEP-29 Asset Management UI]]
 * D3), which is what makes this a Client Component: it needs a click, and it
 * needs somewhere to hold the answer.
 *
 * ## Why the preview is chosen by kind
 *
 * `AssetResponse` carries no MIME type and no size — only `kind` — so per-kind
 * is the granularity the API actually offers, and adding a field to it would be
 * a public API contract change outside this step (D2). `document` therefore has
 * no inline preview: PDF is the only document format accepted, and embedding a
 * cross-origin signed URL in an `<iframe>` depends on response headers this
 * application does not set. A link that works beats a pane that sometimes does,
 * and saying so plainly is the honest fallback the step requires.
 */

import { useCallback, useState } from "react";

import type { ApiAssetKind } from "@/lib/api";
import { type AssetUrlResult, previewModeForKind } from "@/lib/projects";

export interface AssetPreviewProps {
  readonly workspaceId: string;
  readonly projectId: string;
  readonly assetId: string;
  /** The asset's own name, used as the accessible name of the media element. */
  readonly assetName: string;
  readonly kind: ApiAssetKind;
  /**
   * Mints the URL.
   *
   * Injected rather than imported so this component can be rendered in a test
   * without a server. The page passes `assetDownloadUrlAction`.
   */
  readonly mint: (
    workspaceId: string,
    projectId: string,
    assetId: string,
  ) => Promise<AssetUrlResult>;
}

/** What the control is doing. */
type PreviewState =
  | { readonly kind: "idle" }
  | { readonly kind: "loading" }
  | { readonly kind: "failed"; readonly message: string }
  | { readonly kind: "ready"; readonly url: string };

export function AssetPreview({
  workspaceId,
  projectId,
  assetId,
  assetName,
  kind,
  mint,
}: AssetPreviewProps) {
  const [state, setState] = useState<PreviewState>({ kind: "idle" });

  const mode = previewModeForKind(kind);

  const load = useCallback(() => {
    setState({ kind: "loading" });

    void mint(workspaceId, projectId, assetId).then((result) => {
      setState(
        result.ok
          ? { kind: "ready", url: result.url }
          : { kind: "failed", message: result.error },
      );
    });
  }, [assetId, mint, projectId, workspaceId]);

  if (state.kind === "idle") {
    return (
      <button
        type="button"
        onClick={load}
        className="rounded-md border border-border-strong px-3 py-1.5 text-sm font-medium text-text transition-colors hover:bg-surface"
      >
        {mode === "none" ? "Get link" : "Preview"}
      </button>
    );
  }

  if (state.kind === "loading") {
    return (
      <p role="status" className="text-sm text-text-muted">
        Preparing…
      </p>
    );
  }

  if (state.kind === "failed") {
    /*
     * A retry that genuinely re-runs the operation, which [[Design System]] §10
     * rule 4 makes a rule rather than a nicety — a retry that does not re-mint
     * would manufacture confidence in a failure. This is also the fifteen-minute
     * expiry path: a preview left open past its TTL fails here, and this button
     * is what recovers it.
     */
    return (
      <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-danger">
        <span>{state.message}</span>
        <button
          type="button"
          onClick={load}
          className="rounded-md border border-danger px-3 py-1.5 font-medium text-danger transition-colors hover:bg-danger hover:text-danger-contrast"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="flex w-full flex-col gap-2">
      {mode === "image" ? (
        // Named by the asset's own name: an empty `alt` on content the user
        // asked to see is a defect, not a decoration (§9.1 rule 3).
        // eslint-disable-next-line @next/next/no-img-element
        <img src={state.url} alt={assetName} className="max-h-96 max-w-full rounded-md" />
      ) : null}

      {mode === "video" ? (
        <video src={state.url} controls className="max-h-96 max-w-full rounded-md">
          <track kind="captions" />
        </video>
      ) : null}

      {mode === "audio" ? <audio src={state.url} controls className="w-full" /> : null}

      {mode === "none" ? (
        <p className="text-sm text-text-muted">
          A preview is not available for this file type. Open it to view the file.
        </p>
      ) : null}

      {/*
       * Always offered, including beside a working preview: a preview is a
       * look, and downloading is what a user came for often enough that hiding
       * it behind the preview would be the wrong default.
       *
       * `rel="noreferrer"` matters more than usual here — the URL is a
       * capability, and a referrer header is one of the ways one leaks.
       */}
      <a
        href={state.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-sm text-text-muted underline underline-offset-4"
      >
        Open {assetName} in a new tab
      </a>
    </div>
  );
}
