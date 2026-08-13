import { retryTurnAction } from "@/app/(app)/chat/actions";
import { SettingsForm } from "@/components/settings/SettingsForm";
import type { ApiChatMessage } from "@/lib/api";

/**
 * A conversation's messages, oldest first.
 *
 * Presentational only, and a **Server Component**: the transcript is rendered
 * from data the page already fetched server-side, and nothing in it needs the
 * browser. The only client code on the chat screen is the composer's form shell
 * (CLAUDE.md §11).
 *
 * ## Attribution is shown, not implied
 *
 * An assistant message carries the provider and model that produced it. That is
 * not decoration: a reply served after a provider fallback came from a provider
 * the workspace did not choose, and a transcript that does not say which is one
 * the reader cannot honestly attribute (CLAUDE.md §15). The same line carries the
 * token count, which is what the reply cost against the workspace's budget.
 *
 * ## An unanswered question says so
 *
 * A user message whose `turn_status` is not `completed` is rendered as
 * unanswered, with a Retry control when it is `pending`. This is the fix for the
 * defect manual testing found: the status existed in the database throughout,
 * but nothing rendered it, so three questions whose provider call had failed sat
 * in a transcript looking exactly like answered ones. A turn that is retryable
 * by contract and invisible on screen is not retryable in any sense the user can
 * use.
 */
export interface TranscriptProps {
  readonly messages: readonly ApiChatMessage[];
  /** The workspace and conversation a Retry names. */
  readonly workspaceId: string;
  readonly conversationId: string;
}

export function Transcript({ messages, workspaceId, conversationId }: TranscriptProps) {
  return (
    <ol className="flex flex-col gap-4">
      {messages.map((message) => (
        <li key={message.id}>
          <MessageBubble
            message={message}
            workspaceId={workspaceId}
            conversationId={conversationId}
          />
        </li>
      ))}
    </ol>
  );
}

/** What a message's turn state means for what the transcript shows. */
export interface TurnDisplay {
  /** Whether to say this question has no reply. */
  readonly isUnanswered: boolean;
  /** Whether to offer Retry, which only a `pending` turn may be. */
  readonly isRetryable: boolean;
}

/**
 * Decide how one message's turn state is rendered.
 *
 * Exported and pure so it can be tested directly. That is deliberate rather
 * than incidental: this suite runs in a node environment with no DOM and no
 * React Testing Library — a decision `vitest.config.ts` documents, and one this
 * step does not overturn to add a component test (CLAUDE.md §28). The branching
 * *is* the part that failed, so the branching is what gets asserted.
 *
 * The rules, and why each is what it is:
 *
 *  - **Only a question can be unanswered.** An assistant reply carries a null
 *    status by constraint, so testing the role as well keeps this readable as "a
 *    question nobody answered" rather than "a row with a null column".
 *  - **`completed` renders nothing extra.** Annotating every answered question
 *    would make the exceptional state harder to spot, not easier.
 *  - **Only `pending` may be retried.** An `in_progress` turn is either in
 *    flight or was abandoned by a dead process, and STEP-23 has no lease to
 *    tell them apart. Offering Retry there would return 409 at best and risk a
 *    second provider charge at worst.
 *  - **A null status on a question is not unanswered.** Rows written before the
 *    turn-state migration carry one, and they were all completed exchanges —
 *    the migration backfills them, but a client reading an older cached
 *    response must not be told its answered questions are broken.
 */
export function turnDisplay(message: ApiChatMessage): TurnDisplay {
  const isQuestion = message.role === "user";
  const status = message.turn_status;

  return {
    isUnanswered: isQuestion && status !== null && status !== "completed",
    isRetryable: isQuestion && status === "pending",
  };
}

/**
 * One message.
 *
 * The two roles are distinguished by alignment and surface rather than by colour
 * alone — colour alone would carry no meaning for a reader who cannot
 * distinguish the two surfaces ([[Design System]] §9). The role is also stated
 * in text for assistive technology, which cannot see the alignment at all.
 */
function MessageBubble({
  message,
  workspaceId,
  conversationId,
}: {
  readonly message: ApiChatMessage;
  readonly workspaceId: string;
  readonly conversationId: string;
}) {
  const isUser = message.role === "user";
  const { isUnanswered, isRetryable } = turnDisplay(message);

  return (
    <article
      className={[
        "flex max-w-prose flex-col gap-2 rounded-lg border px-5 py-4",
        isUser
          ? "ml-auto border-border bg-surface-raised"
          : "mr-auto border-border bg-surface",
      ].join(" ")}
    >
      <h3 className="text-xs font-medium uppercase tracking-wide text-text-muted">
        {isUser ? "You" : "Assistant"}
      </h3>

      {/*
       * `whitespace-pre-wrap` so the newlines a user typed survive rendering.
       * The content is interpolated as text, never as HTML — a model's reply is
       * untrusted input like any other, and rendering it as markup would be an
       * injection vector on the one surface guaranteed to carry model output.
       */}
      <p className="whitespace-pre-wrap text-sm text-text">{message.content}</p>

      {!isUser && message.provider !== null ? (
        <p className="text-xs text-text-muted">
          {message.provider}
          {message.model === null ? "" : ` · ${message.model}`}
          {message.token_count > 0 ? ` · ${message.token_count} tokens` : ""}
        </p>
      ) : null}

      {isUnanswered ? (
        <UnansweredNotice
          isRetryable={isRetryable}
          workspaceId={workspaceId}
          conversationId={conversationId}
          userMessageId={message.id}
        />
      ) : null}
    </article>
  );
}

/**
 * What is shown beneath a question nothing has answered.
 *
 * The two states are worded differently because they are not the same
 * situation, and telling a user to retry something they cannot retry is worse
 * than saying nothing:
 *
 *  - **`pending`** — no provider holds this turn. Retrying answers *this*
 *    question, so the control is offered.
 *  - **`in_progress`** — a call is in flight, or a process died holding the
 *    claim. STEP-23 has no lease, so the two are indistinguishable here and
 *    neither may be retried: re-invoking a provider that has already accepted
 *    the request risks a second charge. The honest answer is to say it is being
 *    answered and, if it stays that way, that it needs support — not to offer a
 *    button that would return 409 every time.
 *
 * `role="status"` rather than `role="alert"`: this renders on page load beside
 * the question, not in response to an action the user just took, and an alert
 * would interrupt a screen reader mid-transcript for every stale turn.
 */
function UnansweredNotice({
  isRetryable,
  workspaceId,
  conversationId,
  userMessageId,
}: {
  readonly isRetryable: boolean;
  readonly workspaceId: string;
  readonly conversationId: string;
  readonly userMessageId: string;
}) {
  if (!isRetryable) {
    return (
      <p role="status" className="text-xs text-text-muted">
        This message is being answered. If it stays this way, contact support — it cannot be
        retried automatically without risking a second charge.
      </p>
    );
  }

  return (
    <div className="border-t border-border pt-3">
      {/*
       * `SettingsForm` again rather than a bespoke button: it already owns the
       * pending state, the disabled-while-submitting behaviour, the error region
       * and the focus move after a failure — all of which this needs
       * identically. The hidden fields carry the ids that make this a retry of
       * *this* turn rather than a new question, which is the whole reason the
       * action is separate from `sendMessageAction`.
       */}
      <SettingsForm
        action={retryTurnAction}
        submitLabel="Retry"
        pendingLabel="Retrying…"
        savedLabel="Answered"
        hidden={{
          workspace_id: workspaceId,
          conversation_id: conversationId,
          user_message_id: userMessageId,
        }}
      >
        <p role="status" className="text-xs text-danger">
          No reply yet — the assistant could not answer this message.
        </p>
      </SettingsForm>
    </div>
  );
}
