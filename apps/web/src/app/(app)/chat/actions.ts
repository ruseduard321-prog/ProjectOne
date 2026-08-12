"use server";

/**
 * Server Actions backing the chat screen.
 *
 * The same reasoning as the project actions: the access token lives in an
 * httpOnly cookie the browser cannot read, so every call is made server-side.
 *
 * Every action returns a {@link FormState} rather than throwing. That matters
 * more here than anywhere else in the application, because **the failures this
 * screen must survive are ordinary, not exceptional**: a provider outage, a
 * tripped breaker, an exhausted budget. Routing those to the route's error
 * boundary would replace the whole conversation with a crash page and lose the
 * transcript the user is reading — when the honest answer is a message beside
 * their question saying what happened.
 *
 * **Only async functions are exported.** Next.js makes every export of a
 * `"use server"` module a remotely-callable endpoint, so a constant here fails
 * the build — the defect STEP-16 hit. Shared types live in `lib/form-state.ts`.
 */

import { randomUUID } from "node:crypto";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import {
  ApiError,
  ApiUnreachableError,
  deleteConversation,
  sendChatMessage,
} from "@/lib/api";
import { resolveAccessToken } from "@/lib/auth";
import type { FormState } from "@/lib/form-state";

/** Where the chat screen lives, for cache revalidation after a write. */
const CHAT_PATH = "/chat";

/** Read a text field from submitted form data. */
function field(data: FormData, name: string): string {
  const value = data.get(name);

  return typeof value === "string" ? value : "";
}

/**
 * Render a thrown API failure into form state.
 *
 * **This is where CLAUDE.md §15 is enforced in the UI.** Every branch below
 * tells the user what actually happened. None of them invents a reply, and none
 * of them silently swallows the failure into an empty assistant message — a
 * chat screen that answers a failed call with a blank bubble is the "confident
 * empty answer" the step's validation explicitly forbids.
 *
 * The statuses that get their own wording, and why the envelope's own message is
 * not enough on its own:
 *
 *  - **502 / 503** — the provider failed or none was available. The user's
 *    question is already saved, so the actionable part is that retrying is
 *    worthwhile and nothing was lost.
 *  - **402** — a spend ceiling refused the call before any provider was
 *    contacted. Nothing is broken; the workspace is out of budget, and the
 *    remedy is an owner changing it in Settings.
 *  - **429** — rate limited. Distinct from 402: this is requests, not cost.
 *  - **404** — the conversation is gone, most likely deleted in another tab.
 *  - **403** — the caller's role does not permit this.
 */
function toFormState(error: unknown): FormState {
  if (error instanceof ApiError) {
    if (error.status === 502 || error.status === 503) {
      return {
        fieldErrors: {},
        formError: `${error.message}. Your message was saved — try sending it again in a moment.`,
        requestId: error.requestId,
      };
    }

    if (error.status === 402) {
      return {
        fieldErrors: {},
        formError: `${error.message}. An owner can adjust the workspace's AI budget in Settings.`,
        requestId: error.requestId,
      };
    }

    if (error.status === 429) {
      return {
        fieldErrors: {},
        formError: "Too many messages in a short time. Wait a minute and try again.",
        requestId: error.requestId,
      };
    }

    if (error.status === 404) {
      return {
        fieldErrors: {},
        formError: "This conversation no longer exists. It may have been deleted.",
        requestId: error.requestId,
      };
    }

    if (error.status === 403) {
      return {
        fieldErrors: {},
        formError: "Your role in this workspace does not permit this.",
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

/** The state returned when the session has gone while the screen was open. */
const SESSION_LOST: FormState = {
  fieldErrors: {},
  formError: "Your session has expired. Sign in again to continue this conversation.",
};

/**
 * Send one message, and receive the reply.
 *
 * ## The conversation id is chosen here, not discovered from the response
 *
 * A first message carries an id this action generates. That looks redundant —
 * the server could name the conversation itself — but it is what makes the
 * first turn survive a failure.
 *
 * When the server named it, the id existed **only inside a successful
 * response**. A provider outage on a first message therefore persisted the
 * conversation and the user's question under an id nothing on this side ever
 * learned. The screen said "your message was saved" while showing no
 * conversation open, and retrying started a *second* conversation holding a
 * *second* copy of the same question. The message was saved; the user simply had
 * no way to reach it.
 *
 * Generating the id up front fixes all three symptoms with one change: the
 * success path knows where to navigate, the failure path knows what to open, and
 * the retry names the conversation that already exists, so the server continues
 * it instead of creating another.
 *
 * `randomUUID` rather than a counter or a timestamp: this value becomes a
 * primary key, and the server refuses a collision rather than merging into
 * whatever holds it.
 *
 * ## Both outcomes navigate
 *
 * Success and provider failure both end at `?conversation=<id>`, because in both
 * cases that conversation now exists and holds the user's question. The
 * difference is what is shown there — a reply, or an honest error and the
 * unanswered question still in the transcript. Navigating only on success is
 * what stranded the failed turn.
 *
 * `project_id` is only meaningful when starting one: an existing conversation's
 * project is fixed, because its earlier turns were already answered against it.
 * The server enforces that; this simply passes what the form carried.
 */
export async function sendMessageAction(
  _previous: FormState,
  data: FormData,
): Promise<FormState> {
  const workspaceId = field(data, "workspace_id");
  const openConversationId = field(data, "conversation_id");
  const projectId = field(data, "project_id");
  const content = field(data, "content").trim();

  if (content === "") {
    return { fieldErrors: { content: "Type a message to send." } };
  }

  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return SESSION_LOST;
  }

  /*
   * Continuing an open conversation reuses its id; starting one mints an id the
   * server has not seen. Either way the id is known before the call, which is
   * the whole point — see the docstring.
   */
  const conversationId = openConversationId === "" ? randomUUID() : openConversationId;
  const isNewConversation = openConversationId === "";

  try {
    await sendChatMessage(
      accessToken,
      workspaceId,
      content,
      conversationId,
      projectId === "" ? undefined : projectId,
    );
  } catch (error) {
    const state = toFormState(error);

    /*
     * A failed *first* turn still created the conversation and saved the
     * question — the API persists both before it calls a provider. Leaving the
     * screen where it is would show "your message was saved" beside no
     * conversation at all, which is the contradiction this branch exists to
     * remove.
     *
     * The error travels in the URL rather than in the returned state, because
     * `redirect` throws and the state is discarded. The alternative — staying
     * put and returning the id — keeps the message but strands the conversation,
     * which is the defect itself. Navigating with the reason attached is the
     * only option that preserves both.
     *
     * Only for a new conversation. Continuing an open one is already at the
     * right URL, and redirecting would discard the error for no gain.
     *
     * `SESSION_LOST` and an empty message return earlier, so neither reaches
     * here — nothing was created in those cases and there is nothing to open.
     */
    if (isNewConversation && state.formError !== undefined) {
      revalidatePath(CHAT_PATH);
      redirect(
        `${CHAT_PATH}?conversation=${conversationId}&error=${encodeURIComponent(state.formError)}`,
      );
    }

    return state;
  }

  revalidatePath(CHAT_PATH);

  /*
   * `redirect` throws, so nothing after it runs. Only for a new conversation:
   * replying inside an open one is already at the right URL, and redirecting
   * there would discard the form's "Sent" state for no benefit.
   */
  if (isNewConversation) {
    redirect(`${CHAT_PATH}?conversation=${conversationId}`);
  }

  return { fieldErrors: {}, saved: true };
}

/**
 * Delete a conversation.
 *
 * Soft on the server — from the caller's side it is gone, which is what
 * `DELETE` means to them. A workspace erasure clears the message rows
 * themselves, through the registered stores.
 */
export async function deleteConversationAction(
  _previous: FormState,
  data: FormData,
): Promise<FormState> {
  const workspaceId = field(data, "workspace_id");
  const conversationId = field(data, "conversation_id");

  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return SESSION_LOST;
  }

  try {
    await deleteConversation(accessToken, workspaceId, conversationId);
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath(CHAT_PATH);

  return { fieldErrors: {}, saved: true };
}
