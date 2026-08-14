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
  completeChatTurn,
  deleteConversation,
  startChatTurn,
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
 *  - **409** — the turn is already claimed, by a concurrent Retry or by a call
 *    still in flight. Not a failure of the user's action: the answer is coming,
 *    or another click is fetching it. Saying "try again" here would invite the
 *    user to pile up requests against a turn that already has an owner.
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

    if (error.status === 409) {
      return {
        fieldErrors: {},
        formError:
          "This message is already being answered. Reload in a moment to see the reply.",
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
 * ## Two calls, because one transaction could not keep the promise
 *
 * Sending is `startChatTurn` then `completeChatTurn`. The split is not
 * cosmetic: the API runs each request inside one transaction, so when a single
 * request persisted the question *and* called the provider, a provider failure
 * rolled the question back with it. This screen said "your message was saved"
 * while nothing had been — found in manual testing, after every unit test on
 * both sides passed.
 *
 * Step 1 contacts no provider, so it commits. By the time step 2 can fail, the
 * question is durable.
 *
 * ## Both outcomes keep the question visible
 *
 * Success and provider failure both end with the conversation open at
 * `?conversation=<id>`, because in both cases it exists and holds what the user
 * typed. The difference is what sits beside it — a reply, or an honest error
 * above the unanswered question.
 *
 * Retrying re-sends the same text, which stores a *new* question and answers
 * that one. The turn key makes the server side idempotent per question, so a
 * double-submitted completion cannot bill twice for the same one.
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

  /*
   * Step 1 — store the question. No provider is contacted, so this commits and
   * what it saves is durable. A failure here means nothing was stored, which is
   * why it returns rather than navigating: there is no conversation to open.
   */
  let pending;

  try {
    pending = await startChatTurn(
      accessToken,
      workspaceId,
      content,
      conversationId,
      projectId === "" ? undefined : projectId,
    );
  } catch (error) {
    return toFormState(error);
  }

  /*
   * Step 2 — answer it. This is the call that can fail for reasons outside the
   * user's control, and by now their question is already saved, so every exit
   * below leaves it visible and retryable.
   */
  try {
    await completeChatTurn(
      accessToken,
      workspaceId,
      pending.conversation.id,
      pending.user_message.id,
    );
  } catch (error) {
    const state = toFormState(error);

    /*
     * The question is stored — step 1 committed before any provider was
     * contacted — so the screen must show it whatever went wrong here. That is
     * now true for a reply as well as a first message, which it was not when
     * the turn was a single request: back then a failure rolled the question
     * back, and the promise "your message was saved" was false.
     *
     * Revalidate so the transcript re-renders with the unanswered question in
     * it, and carry the reason in the URL because `redirect` throws and the
     * returned state would be discarded.
     *
     * A *new* conversation must navigate — nothing on screen points at it yet.
     * An open one is already at the right URL, so it revalidates in place and
     * returns the error for the form to render, keeping focus where the user
     * left it.
     *
     * `SESSION_LOST`, an empty message and a failed step 1 all return earlier:
     * in those cases nothing was stored and there is nothing to open.
     */
    revalidatePath(CHAT_PATH);

    if (isNewConversation && state.formError !== undefined) {
      redirect(
        `${CHAT_PATH}?conversation=${pending.conversation.id}` +
          `&error=${encodeURIComponent(state.formError)}`,
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
 * Answer a question that is already stored, without asking it again.
 *
 * ## Why this exists as a separate action
 *
 * `sendMessageAction` always starts with `startChatTurn`, so every resend mints
 * a *new* user message. That is correct for sending — a resend is a new send —
 * but it made a failed turn unrecoverable: manual testing produced three
 * identical `pending` questions in one conversation, none of which anything
 * would ever answer, because nothing on the screen could name an existing turn.
 *
 * This action names one. It calls **only** `completeChatTurn`, for a
 * `user_message_id` the transcript already rendered, so:
 *
 *  - no second user message is written — there is no `startChatTurn` here;
 *  - the conversation id and the user message id are both unchanged, because
 *    both are read from the stored question rather than generated;
 *  - the turn that failed is the turn that gets answered.
 *
 * ## Concurrency is the server's, not this action's
 *
 * Two Retry clicks race to the same endpoint, and nothing here serialises them.
 * They do not need to: the API claims the turn with a conditional UPDATE
 * committed before any network call, so exactly one caller reaches a provider
 * and the loser gets 409 — one invocation, one reply, one charge. Adding a
 * client-side guard would only hide the second click; the guarantee has to hold
 * against two browsers anyway.
 *
 * A 409 is therefore not a failure to report as one. It means the turn is
 * already being answered — by the other click, or by a call still in flight —
 * and the honest message says exactly that rather than implying the retry broke
 * something.
 *
 * ## Failure leaves it retryable
 *
 * An ordinary provider failure releases the claim server-side, so the turn
 * returns to `pending` and the button the user just pressed is still the right
 * button. Nothing is written, nothing is lost, and the reason renders in the
 * form's error region beside the question it belongs to.
 */
export async function retryTurnAction(
  _previous: FormState,
  data: FormData,
): Promise<FormState> {
  const workspaceId = field(data, "workspace_id");
  const conversationId = field(data, "conversation_id");
  const userMessageId = field(data, "user_message_id");

  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return SESSION_LOST;
  }

  try {
    await completeChatTurn(accessToken, workspaceId, conversationId, userMessageId);
  } catch (error) {
    return toFormState(error);
  }

  /*
   * No redirect: the conversation is already open at the right URL, and this
   * turn is one of several in it. Revalidating re-renders the transcript with
   * the reply in place and the Retry control gone, because the question is now
   * `completed`.
   */
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
