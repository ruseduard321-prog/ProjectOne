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

import { revalidatePath } from "next/cache";

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
 * An absent `conversation_id` starts a new conversation — the server derives its
 * title from this first message, so nothing here needs to name it.
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
  const conversationId = field(data, "conversation_id");
  const projectId = field(data, "project_id");
  const content = field(data, "content").trim();

  if (content === "") {
    return { fieldErrors: { content: "Type a message to send." } };
  }

  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return SESSION_LOST;
  }

  try {
    await sendChatMessage(
      accessToken,
      workspaceId,
      content,
      conversationId === "" ? undefined : conversationId,
      projectId === "" ? undefined : projectId,
    );
  } catch (error) {
    return toFormState(error);
  }

  revalidatePath(CHAT_PATH);

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
