/**
 * Shared vocabulary and presentation rules for the project lifecycle.
 *
 * Lives here rather than beside the actions that use it for a hard framework
 * reason, the same one `lib/form-state.ts` records: a `"use server"` module may
 * export **only async functions**, because every export becomes a
 * remotely-callable endpoint. A constant exported from one fails the build.
 *
 * ## What this file deliberately does not contain
 *
 * **The transition rules.** Which states a project may move to is decided by the
 * server and arrives per project in `legal_transitions` — see [[Project
 * Lifecycle]]. A map from state to allowed next states here would be a second
 * copy of the state machine, and two copies diverge the first time the rules
 * change. What lives here is only the *vocabulary* (which states exist) and how
 * to *label* them, neither of which is a rule about movement.
 */

import type { ApiAssetKind, ApiProjectStatus } from "@/lib/api";

/**
 * Every lifecycle state, in the order [[Projects]] states the pipeline.
 *
 * Used to narrow a submitted string and to sort states for display. Order is
 * pipeline order rather than alphabetical, so a list of states reads as the
 * lifecycle rather than as an index.
 */
export const PROJECT_STATUSES: readonly ApiProjectStatus[] = [
  "idea",
  "planning",
  "generation",
  "review",
  "editing",
  "approval",
  "publishing",
  "analytics",
  "archive",
];

/** Narrow a submitted string to the API's status vocabulary. */
export function isProjectStatus(value: string): value is ApiProjectStatus {
  return (PROJECT_STATUSES as readonly string[]).includes(value);
}

/**
 * How each state is written in the interface.
 *
 * Capitalized labels rather than raw values, because `idea` in a status badge
 * reads as a database value leaking into the product. The keys are exhaustive by
 * type: adding a state to `ApiProjectStatus` without a label here is a compile
 * error, which is the point.
 */
const STATUS_LABELS: Record<ApiProjectStatus, string> = {
  idea: "Idea",
  planning: "Planning",
  generation: "Generation",
  review: "Review",
  editing: "Editing",
  approval: "Approval",
  publishing: "Publishing",
  analytics: "Analytics",
  archive: "Archived",
};

/** The label shown for a lifecycle state. */
export function statusLabel(status: ApiProjectStatus): string {
  return STATUS_LABELS[status];
}

/**
 * The verb shown on the control that moves a project into a state.
 *
 * Distinct from {@link statusLabel} because a button and a badge want different
 * words: the badge says where the project *is*, the button says what will
 * *happen*. "Archive" and "Archived" are the clearest case.
 *
 * Archiving is deliberately worded as an action on the project rather than as
 * the next pipeline step, because it is reachable from every state and is
 * terminal — presenting it identically to "Move to Planning" would suggest it is
 * just the next stage.
 */
export function transitionLabel(status: ApiProjectStatus): string {
  return status === "archive" ? "Archive project" : `Move to ${STATUS_LABELS[status]}`;
}

/**
 * Every kind of asset a project may hold.
 *
 * **A closed vocabulary**, matching the database's `ck_assets_kind_valid`. The
 * UI presents these as a fixed choice rather than a text field for a concrete
 * reason: a free-text input would let a user type "script", which the API
 * refuses — an interface that accepts input the server cannot store is one that
 * teaches the user to guess.
 */
export const ASSET_KINDS: readonly ApiAssetKind[] = ["document", "image", "video", "audio"];

/** Narrow a submitted string to the asset-kind vocabulary. */
export function isAssetKind(value: string): value is ApiAssetKind {
  return (ASSET_KINDS as readonly string[]).includes(value);
}

/** How each asset kind is written in the interface. */
const ASSET_KIND_LABELS: Record<ApiAssetKind, string> = {
  document: "Document",
  image: "Image",
  video: "Video",
  audio: "Audio",
};

/** The label shown for an asset kind. */
export function assetKindLabel(kind: ApiAssetKind): string {
  return ASSET_KIND_LABELS[kind];
}

/**
 * The largest single upload the API accepts, in bytes.
 *
 * Mirrors `MAX_UPLOAD_BYTES` in `app/services/asset_content.py`, set by the
 * project owner as STEP-28 D2. **A second copy of a server rule, and bounded
 * deliberately**: it is used to tell the user the limit before they choose a
 * file and to refuse an oversized one without spending a minute uploading it.
 * The server remains the only authority — a client that skipped this check
 * still receives a 413, so drift costs a slightly wrong hint rather than a
 * wrong outcome.
 */
export const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;

/** The ceiling written the way it is shown to a person. */
export const MAX_UPLOAD_LABEL = `${MAX_UPLOAD_BYTES / (1024 * 1024)} MB`;

/**
 * What the file picker offers for each kind.
 *
 * **A hint, never a control.** These mirror the extensions in `ALLOWED_TYPES`
 * (`app/services/asset_content.py`) so the dialog is not a list of every file on
 * the machine, and that is the entire job: the server checks the declared type,
 * the extension *and* the file's magic bytes, and refuses anything that fails
 * any of them. A user who defeats this attribute — by dragging a file, or by
 * switching the picker to "All Files" — reaches exactly the same validation.
 *
 * Written as extensions rather than MIME types because a browser matches
 * extensions reliably and matches MIME types according to its own guess.
 */
const ACCEPT_BY_KIND: Record<ApiAssetKind, string> = {
  image: ".png,.jpg,.jpeg,.gif,.webp",
  document: ".pdf",
  video: ".mp4,.m4v,.webm",
  audio: ".mp3,.wav",
};

/** The `accept` attribute for a file input offering one kind of asset. */
export function acceptForKind(kind: ApiAssetKind): string {
  return ACCEPT_BY_KIND[kind];
}

/**
 * How an asset of a given kind can be shown in the browser.
 *
 * **Decided by `kind` alone**, because that is all the API returns —
 * `AssetResponse` carries no MIME type and no size ([[STEP-29 Asset Management
 * UI]] D2). Adding one would be a public API contract change, which is Critical
 * under [[CLAUDE|CLAUDE.md]] §21 and outside a step whose surfaces are frontend
 * only.
 *
 * `none` is an honest answer, not a missing case: a PDF is the only document
 * format accepted, and embedding a cross-origin signed URL in an `<iframe>`
 * renders inconsistently across browsers and depends on response headers this
 * application does not set. A download link that works beats a preview pane
 * that sometimes does.
 */
export type AssetPreviewMode = "image" | "video" | "audio" | "none";

/** How to render a preview of this kind of asset, if at all. */
export function previewModeForKind(kind: ApiAssetKind): AssetPreviewMode {
  return kind === "document" ? "none" : kind;
}

/**
 * The outcome of minting a signed URL.
 *
 * A result rather than a thrown error, for the reason the project actions give:
 * a failure to load one preview is not a page failure, and routing it to the
 * route's error boundary would replace a working screen with an error page.
 *
 * Lives here rather than beside the action that returns it because a
 * `"use server"` module may export only async functions.
 */
export type AssetUrlResult =
  | { readonly ok: true; readonly url: string; readonly expiresInSeconds: number }
  | { readonly ok: false; readonly error: string };

/**
 * Where the browser posts a file for one project.
 *
 * A same-origin Next.js Route Handler, not the API — the access token is in an
 * httpOnly cookie the browser cannot read, and the API registers no CORS
 * middleware, so this is the only address a browser upload can reach. See that
 * handler for the full reasoning.
 */
export function assetUploadPath(workspaceId: string, projectId: string): string {
  return `/api/workspaces/${workspaceId}/projects/${projectId}/assets/upload`;
}
