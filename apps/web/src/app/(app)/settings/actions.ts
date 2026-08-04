"use server";

/**
 * Server Actions backing the settings forms.
 *
 * The same reasoning as the authentication actions: the access token lives in an
 * httpOnly cookie the browser cannot read, so every call is made server-side.
 * For the BYOK form that is not merely consistency — **a provider key must never
 * enter client JavaScript**, and a client-side `fetch` could not attach the
 * bearer token anyway.
 *
 * Every action returns a {@link FormState} rather than throwing. A thrown error
 * surfaces as the generic error boundary, which is the wrong treatment for "that
 * key looks too short".
 *
 * **Only async functions are exported.** Next.js makes every export of a
 * `"use server"` module a remotely-callable endpoint, so a constant here fails
 * the build — the defect STEP-16 hit. Shared types live in `lib/form-state.ts`.
 */

import { revalidatePath } from "next/cache";

import {
  ApiError,
  ApiUnreachableError,
  renameWorkspace,
  revokeProviderCredential,
  storeProviderCredential,
  updateBudget,
  updateProfile,
} from "@/lib/api";
import { resolveAccessToken } from "@/lib/auth";
import type { FormState } from "@/lib/form-state";

/** Where the settings screens live, for cache revalidation after a write. */
const SETTINGS_PATH = "/settings";

/** Read a required text field from submitted form data. */
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
 * Three statuses get their own wording because the envelope's message alone does
 * not tell a user what to do:
 *
 *  - **402** — a spend ceiling was reached. Actionable: raise it or wait.
 *  - **403** — the caller's role does not permit the change. The screen should
 *    not have offered it, so this is also a signal the UI drifted from the
 *    server's rules.
 *  - **429** — rate limited.
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

/** Update the signed-in user's display name. */
export async function updateProfileAction(
  _previous: FormState,
  data: FormData,
): Promise<FormState> {
  const displayName = field(data, "display_name").trim();

  if (displayName === "") {
    return { fieldErrors: { display_name: "Enter a display name." } };
  }

  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return SESSION_LOST;
  }

  try {
    await updateProfile(accessToken, displayName);
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath(SETTINGS_PATH);

  return { fieldErrors: {}, saved: true };
}

/** Rename the current workspace. Owner and admin only, enforced by the API. */
export async function renameWorkspaceAction(
  _previous: FormState,
  data: FormData,
): Promise<FormState> {
  const workspaceId = field(data, "workspace_id");
  const name = field(data, "name").trim();

  if (name === "") {
    return { fieldErrors: { name: "Enter a workspace name." } };
  }

  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return SESSION_LOST;
  }

  try {
    await renameWorkspace(accessToken, workspaceId, name);
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath(SETTINGS_PATH);

  return { fieldErrors: {}, saved: true };
}

/**
 * Store or replace a provider API key.
 *
 * The key reaches this function, is handed to the API, and is never returned,
 * logged, or written into the returned state. The success state deliberately
 * carries no echo of it — not even `last_four`, which the screen re-reads from
 * the server on revalidation rather than trusting a value round-tripped through
 * a form result.
 */
export async function storeProviderKeyAction(
  _previous: FormState,
  data: FormData,
): Promise<FormState> {
  const workspaceId = field(data, "workspace_id");
  const provider = field(data, "provider");
  const apiKey = field(data, "api_key").trim();

  if (apiKey === "") {
    return { fieldErrors: { api_key: "Paste an API key." } };
  }

  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return SESSION_LOST;
  }

  try {
    await storeProviderCredential(accessToken, workspaceId, provider, apiKey);
  } catch (error) {
    // Not logged, and the error is not enriched with the submitted value. An
    // error message quoting a rejected key would defeat the point of the route
    // that refuses to return one (CLAUDE.md §16).
    return toFormState(error);
  }

  revalidatePath(SETTINGS_PATH);

  return { fieldErrors: {}, saved: true };
}

/** Revoke a stored provider key. */
export async function revokeProviderKeyAction(
  _previous: FormState,
  data: FormData,
): Promise<FormState> {
  const workspaceId = field(data, "workspace_id");
  const provider = field(data, "provider");

  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return SESSION_LOST;
  }

  try {
    await revokeProviderCredential(accessToken, workspaceId, provider);
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath(SETTINGS_PATH);

  return { fieldErrors: {}, saved: true };
}

/**
 * Set the workspace's AI spend ceiling.
 *
 * `spent_usd` is never submitted. The API would answer 422 if it were, and the
 * column-level grant added by migration `c9d3b71e08af` would refuse the write
 * even then — three independent gates on one value, which is what a running
 * total that every ceiling is enforced against deserves.
 */
export async function updateBudgetAction(
  _previous: FormState,
  data: FormData,
): Promise<FormState> {
  const workspaceId = field(data, "workspace_id");
  const limitUsd = field(data, "limit_usd").trim();
  const periodDaysRaw = field(data, "period_days").trim();

  // Validated as a decimal string rather than parsed to a number: parsing to
  // `number` and re-serializing is what silently turns a typed ceiling into a
  // slightly different one.
  if (!/^\d+(\.\d{1,6})?$/.test(limitUsd) || Number(limitUsd) <= 0) {
    return { fieldErrors: { limit_usd: "Enter an amount greater than zero, e.g. 50.00" } };
  }

  let periodDays: number | undefined;

  if (periodDaysRaw !== "") {
    periodDays = Number(periodDaysRaw);

    if (!Number.isInteger(periodDays) || periodDays < 1 || periodDays > 365) {
      return { fieldErrors: { period_days: "Enter a whole number of days between 1 and 365." } };
    }
  }

  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return SESSION_LOST;
  }

  try {
    await updateBudget(accessToken, workspaceId, limitUsd, periodDays);
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath(SETTINGS_PATH);

  return { fieldErrors: {}, saved: true };
}
