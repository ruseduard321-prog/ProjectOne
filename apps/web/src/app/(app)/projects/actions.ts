"use server";

/**
 * Server Actions backing the project screens.
 *
 * The same reasoning as the settings actions: the access token lives in an
 * httpOnly cookie the browser cannot read, so every call is made server-side.
 *
 * Every action returns a {@link FormState} rather than throwing. A thrown error
 * surfaces as the route's error boundary, which is the wrong treatment for
 * "enter a project name" — and, more importantly here, for the **409 a refused
 * lifecycle transition produces**, which is a meaningful answer the user should
 * read rather than a page failure.
 *
 * **Only async functions are exported.** Next.js makes every export of a
 * `"use server"` module a remotely-callable endpoint, so a constant here fails
 * the build — the defect STEP-16 hit. Shared types live in `lib/form-state.ts`.
 */

import { revalidatePath } from "next/cache";

import {
  ApiError,
  ApiUnreachableError,
  assetDownloadUrl,
  createAsset,
  createProject,
  deleteAsset,
  deleteProject,
  renameProject,
  transitionProject,
} from "@/lib/api";
import { resolveAccessToken } from "@/lib/auth";
import type { FormState } from "@/lib/form-state";
import { type AssetUrlResult, isAssetKind, isProjectStatus } from "@/lib/projects";

/** Where the project screens live, for cache revalidation after a write. */
const PROJECTS_PATH = "/projects";

/** Read a text field from submitted form data. */
function field(data: FormData, name: string): string {
  const value = data.get(name);

  return typeof value === "string" ? value : "";
}

/**
 * Render a thrown API failure into form state.
 *
 * The API's `detail` is shown verbatim — its error contract guarantees these
 * messages are user-facing and leak neither credentials nor internal state.
 *
 * Four statuses get their own wording because the envelope's message alone does
 * not tell a user what to do:
 *
 *  - **404** — the project is gone, most likely deleted in another tab.
 *  - **409** — the lifecycle refused the move. The API's own message names both
 *    states and is more useful than anything this layer could substitute, so it
 *    is passed through; only the reason it happened is added.
 *  - **403** — the caller's role does not permit this. The screen should not
 *    have offered it, so this also signals the UI drifted from the server.
 *  - **429** — rate limited.
 *
 * **413 and 415 are deliberately absent from that list.** They are the upload
 * refusals, and the API's own message already names the rule that was broken —
 * which file types are accepted, or which limit was exceeded — in wording
 * written to be shown and chosen never to echo the filename back. Substituting
 * a generic sentence would replace the only text that tells the user what to do
 * differently. They fall through to the pass-through below.
 */
function toFormState(error: unknown): FormState {
  if (error instanceof ApiError) {
    if (error.status === 429) {
      return {
        fieldErrors: {},
        formError: "Too many attempts. Wait a minute and try again.",
        requestId: error.requestId,
      };
    }

    if (error.status === 404) {
      return {
        fieldErrors: {},
        formError: "This project no longer exists. It may have been deleted.",
        requestId: error.requestId,
      };
    }

    if (error.status === 409) {
      // The API's message names the current and requested states, which is
      // exactly what makes this actionable. Reaching a 409 at all means the
      // project moved since the page rendered, so the reload hint is the real
      // remedy rather than filler.
      return {
        fieldErrors: {},
        formError: `${error.message}. Reload to see its current state.`,
        requestId: error.requestId,
      };
    }

    if (error.status === 403) {
      return {
        fieldErrors: {},
        formError: "Your role in this workspace does not permit this change.",
        requestId: error.requestId,
      };
    }

    return { fieldErrors: {}, formError: error.message, requestId: error.requestId };
  }

  if (error instanceof ApiUnreachableError) {
    return { fieldErrors: {}, formError: error.message };
  }

  throw error;
}

/** The state returned when the session has gone while a form was open. */
const SESSION_LOST: FormState = {
  fieldErrors: {},
  formError: "Your session has expired. Sign in again to save this change.",
};

/** Create a project in the current workspace. */
export async function createProjectAction(
  _previous: FormState,
  data: FormData,
): Promise<FormState> {
  const workspaceId = field(data, "workspace_id");
  const name = field(data, "name").trim();
  const description = field(data, "description").trim();

  if (name === "") {
    return { fieldErrors: { name: "Enter a project name." } };
  }

  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return SESSION_LOST;
  }

  try {
    await createProject(
      accessToken,
      workspaceId,
      name,
      description === "" ? undefined : description,
    );
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath(PROJECTS_PATH);

  return { fieldErrors: {}, saved: true };
}

/** Rename a project, and update its description. */
export async function renameProjectAction(
  _previous: FormState,
  data: FormData,
): Promise<FormState> {
  const workspaceId = field(data, "workspace_id");
  const projectId = field(data, "project_id");
  const name = field(data, "name").trim();
  const description = field(data, "description").trim();

  if (name === "") {
    return { fieldErrors: { name: "Enter a project name." } };
  }

  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return SESSION_LOST;
  }

  try {
    // An empty description is sent as `null` rather than `""`, so clearing the
    // field genuinely clears the column instead of storing a blank string that
    // renders identically but is not absent.
    await renameProject(
      accessToken,
      workspaceId,
      projectId,
      name,
      description === "" ? null : description,
    );
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath(PROJECTS_PATH);
  revalidatePath(`${PROJECTS_PATH}/${projectId}`);

  return { fieldErrors: {}, saved: true };
}

/**
 * Move a project to a new lifecycle state.
 *
 * The requested status is validated against the API's vocabulary before being
 * sent — not as a security control (the API types it as an enum and answers 422
 * regardless), but so a malformed submission produces a field message rather
 * than a round trip that fails.
 *
 * **Whether the move is legal is not checked here.** That is the server's
 * decision, and duplicating it would be the second copy of the state machine
 * this step exists to avoid. A refused move comes back as a 409 and is rendered.
 */
export async function transitionProjectAction(
  _previous: FormState,
  data: FormData,
): Promise<FormState> {
  const workspaceId = field(data, "workspace_id");
  const projectId = field(data, "project_id");
  const status = field(data, "status");

  if (!isProjectStatus(status)) {
    return { fieldErrors: { status: "Choose a state to move this project to." } };
  }

  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return SESSION_LOST;
  }

  try {
    await transitionProject(accessToken, workspaceId, projectId, status);
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath(PROJECTS_PATH);
  revalidatePath(`${PROJECTS_PATH}/${projectId}`);

  return { fieldErrors: {}, saved: true };
}

/**
 * Delete a project.
 *
 * **Not the same as archiving.** Archiving is a lifecycle transition handled by
 * `transitionProjectAction`; this removes the project from the workspace. The UI
 * presents them as separate actions with separate wording, because presenting
 * one as the other would misrepresent what the user just did.
 */
export async function deleteProjectAction(
  _previous: FormState,
  data: FormData,
): Promise<FormState> {
  const workspaceId = field(data, "workspace_id");
  const projectId = field(data, "project_id");

  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return SESSION_LOST;
  }

  try {
    await deleteProject(accessToken, workspaceId, projectId);
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath(PROJECTS_PATH);

  return { fieldErrors: {}, saved: true };
}

/** Record an asset against a project. */
export async function createAssetAction(
  _previous: FormState,
  data: FormData,
): Promise<FormState> {
  const workspaceId = field(data, "workspace_id");
  const projectId = field(data, "project_id");
  const name = field(data, "name").trim();
  const kind = field(data, "kind").trim();

  if (name === "") {
    return { fieldErrors: { name: "Enter a name for this asset." } };
  }

  // Checked against the closed vocabulary rather than for non-emptiness: the
  // database's `ck_assets_kind_valid` refuses anything else, so an unchecked
  // value would reach the API only to come back as a 422 the user cannot act on.
  if (!isAssetKind(kind)) {
    return { fieldErrors: { kind: "Choose what kind of asset this is." } };
  }

  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return SESSION_LOST;
  }

  try {
    await createAsset(accessToken, workspaceId, projectId, name, kind);
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath(`${PROJECTS_PATH}/${projectId}`);

  return { fieldErrors: {}, saved: true };
}

/**
 * Mint a time-limited URL for one asset's bytes.
 *
 * **Not a form action.** It takes arguments rather than `FormData` and returns a
 * result rather than a {@link FormState}, because it is called imperatively from
 * a preview control the moment a user asks to see a file — there is no form and
 * nothing is being saved.
 *
 * Called **on user action only, never while rendering a list**. The URL is a
 * bearer capability with a 15-minute life (STEP-28 D3): minting one per asset at
 * render time would spend that lifetime while the page was merely being read,
 * issue an API call per row, and place capabilities into markup Next.js may
 * cache ([[STEP-29 Asset Management UI]] D3).
 */
export async function assetDownloadUrlAction(
  workspaceId: string,
  projectId: string,
  assetId: string,
): Promise<AssetUrlResult> {
  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return { ok: false, error: "Your session has expired. Sign in again to open this file." };
  }

  try {
    const download = await assetDownloadUrl(accessToken, workspaceId, projectId, assetId);

    return {
      ok: true,
      url: download.url,
      expiresInSeconds: download.expires_in_seconds,
    };
  } catch (error) {
    if (error instanceof ApiError) {
      // 404 covers both "this asset has no file" and "this asset is not yours".
      // The API answers them identically on purpose, so an asset id cannot be
      // used to probe across workspaces, and this message must not distinguish
      // them either.
      if (error.status === 404) {
        return { ok: false, error: "This file is no longer available." };
      }

      return { ok: false, error: error.message };
    }

    if (error instanceof ApiUnreachableError) {
      return { ok: false, error: error.message };
    }

    throw error;
  }
}

/** Remove an asset from a project. */
export async function deleteAssetAction(
  _previous: FormState,
  data: FormData,
): Promise<FormState> {
  const workspaceId = field(data, "workspace_id");
  const projectId = field(data, "project_id");
  const assetId = field(data, "asset_id");

  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return SESSION_LOST;
  }

  try {
    await deleteAsset(accessToken, workspaceId, projectId, assetId);
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath(`${PROJECTS_PATH}/${projectId}`);

  return { fieldErrors: {}, saved: true };
}
