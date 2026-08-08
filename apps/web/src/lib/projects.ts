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
