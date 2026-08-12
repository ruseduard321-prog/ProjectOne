import type { Metadata } from "next";
import Link from "next/link";

import { Transcript } from "@/components/chat/Transcript";
import { FormField } from "@/components/auth/FormField";
import { SettingsForm } from "@/components/settings/SettingsForm";
import { SettingsSection } from "@/components/settings/SettingsSection";
import { EmptyState } from "@/components/shell/EmptyState";
import {
  type ApiConversation,
  type ApiConversationDetail,
  listConversations,
  readConversation,
} from "@/lib/api";
import { requireProfile, resolveAccessToken } from "@/lib/auth";
import { resolveWorkspace } from "@/lib/workspace";

import { deleteConversationAction, sendMessageAction } from "./actions";

export const metadata: Metadata = {
  title: "AI Chat — ProjectOne",
};

/**
 * The chat screen: a workspace's conversations, and the open one's transcript.
 *
 * A **Server Component**. Every value here is fetched and rendered server-side;
 * the only client code beneath it is the composer's form shell. The access token
 * lives in an httpOnly cookie the browser cannot read, so a client component
 * could not fetch any of this even if it wanted to (CLAUDE.md §11).
 *
 * ## Which conversation is open is a URL parameter
 *
 * `?conversation=<id>` rather than client state, so a conversation is
 * linkable, survives a reload, and renders on the server with its transcript
 * already in the HTML. It also means the composer posts to a Server Action and
 * the page simply re-renders — no client-side message list to keep in sync with
 * the server's, which is where a chat UI usually accumulates its bugs.
 *
 * ## Non-streaming, deliberately
 *
 * The reply arrives whole, as the API returns it ([[STEP-23 AI Chat End to End]]
 * task 6). Streaming would change the response contract, move where spend is
 * settled, and complicate a mid-stream failure — the composer's pending state
 * carries the wait instead. This is stated rather than defaulted.
 */
export default async function ChatPage({
  searchParams,
}: {
  readonly searchParams: Promise<{
    readonly conversation?: string;
    readonly error?: string;
  }>;
}) {
  await requireProfile();

  const accessToken = await resolveAccessToken();
  const workspace = accessToken === undefined ? undefined : await resolveWorkspace(accessToken);

  if (accessToken === undefined || workspace === undefined) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-semibold tracking-tight text-text">AI Chat</h1>
        <EmptyState
          title="No workspace yet"
          description="Conversations live inside a workspace. Once you belong to one, your chats appear here."
        />
      </div>
    );
  }

  const workspaceId = workspace.current.id;
  const { conversation: requestedId, error: turnError } = await searchParams;

  const conversations = await listConversations(accessToken, workspaceId);

  /*
   * A requested conversation that no longer exists renders the screen with none
   * open, rather than failing the page. The likeliest cause is a link followed
   * after the conversation was deleted in another tab, and losing the whole
   * screen — including the list showing what *does* exist — would be a worse
   * answer than simply showing no transcript.
   */
  const open =
    requestedId === undefined || !conversations.some((item) => item.id === requestedId)
      ? undefined
      : await readConversation(accessToken, workspaceId, requestedId);

  return (
    <ChatScreen
      workspaceId={workspaceId}
      workspaceName={workspace.current.name}
      conversations={conversations}
      open={open}
      turnError={turnError}
    />
  );
}

interface ChatScreenProps {
  readonly workspaceId: string;
  readonly workspaceName: string;
  readonly conversations: readonly ApiConversation[];
  readonly open: ApiConversationDetail | undefined;
  /**
   * Why the turn that opened this conversation failed, when one did.
   *
   * Carried in the URL because the action that knows it ends in a `redirect`,
   * which discards the returned form state. See `sendMessageAction`.
   */
  readonly turnError: string | undefined;
}

/**
 * The rendered screen, separated from the data fetching above it.
 *
 * The same split the projects and settings screens use: the layout is readable
 * without the awaits, and a future test can render it against fixed props.
 */
function ChatScreen({
  workspaceId,
  workspaceName,
  conversations,
  open,
  turnError,
}: ChatScreenProps) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight text-text">AI Chat</h1>
        <p className="text-sm text-text-muted">
          Ask the assistant about the work in {workspaceName}. Conversations stay inside this
          workspace.
        </p>
      </div>

      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        <ConversationList
          conversations={conversations}
          openId={open?.conversation.id}
          workspaceId={workspaceId}
        />

        <section
          aria-labelledby="conversation-heading"
          className="flex min-w-0 flex-1 flex-col gap-4"
        >
          <h2 id="conversation-heading" className="sr-only">
            Conversation
          </h2>

          {open === undefined ? (
            <EmptyState
              title={conversations.length === 0 ? "No conversations yet" : "No conversation open"}
              description={
                conversations.length === 0
                  ? "Ask a question below to start your first conversation."
                  : "Choose a conversation from the list, or ask something below to start a new one."
              }
            />
          ) : (
            <Transcript messages={open.messages} />
          )}

          {/*
           * The reason a first turn failed, shown beside the question it saved
           * rather than in place of it.
           *
           * `role="alert"` so it is announced on arrival: the user navigated
           * here rather than submitting in place, so nothing else would tell a
           * screen reader that the turn did not complete ([[Design System]] §9).
           *
           * Rendered after the transcript, so the reading order is what was
           * asked, then what happened to it.
           */}
          {turnError === undefined ? null : (
            <div
              role="alert"
              className="rounded-md border border-danger px-4 py-3 text-sm text-danger"
            >
              <p>{turnError}</p>
            </div>
          )}

          <Composer workspaceId={workspaceId} openConversationId={open?.conversation.id} />
        </section>
      </div>
    </div>
  );
}

/**
 * The conversation list.
 *
 * Each entry is a link carrying the conversation id in the query string, so
 * navigation is a server round trip that renders the transcript directly —
 * no client-side fetch, and a working browser back button for free.
 */
function ConversationList({
  conversations,
  openId,
  workspaceId,
}: {
  readonly conversations: readonly ApiConversation[];
  readonly openId: string | undefined;
  readonly workspaceId: string;
}) {
  if (conversations.length === 0) {
    return null;
  }

  return (
    <nav aria-labelledby="conversations-heading" className="flex w-full flex-col gap-3 lg:w-72">
      <h2 id="conversations-heading" className="text-lg font-medium text-text">
        Conversations
      </h2>

      <ul className="flex flex-col gap-2">
        {conversations.map((conversation) => {
          const isOpen = conversation.id === openId;

          return (
            <li key={conversation.id} className="flex flex-col gap-1">
              <Link
                href={`/chat?conversation=${conversation.id}`}
                aria-current={isOpen ? "page" : undefined}
                className={[
                  "rounded-lg border px-4 py-3 text-sm transition-colors",
                  isOpen
                    ? "border-accent bg-surface-raised text-text"
                    : "border-border bg-surface text-text-muted hover:bg-surface-raised",
                ].join(" ")}
              >
                {conversation.title}
              </Link>

              {isOpen ? (
                <SettingsForm
                  action={deleteConversationAction}
                  submitLabel="Delete conversation"
                  pendingLabel="Deleting…"
                  savedLabel="Deleted"
                  intent="danger"
                  hidden={{ workspace_id: workspaceId, conversation_id: conversation.id }}
                >
                  <p className="text-sm text-text-muted">
                    This removes the conversation and its messages from the workspace.
                  </p>
                </SettingsForm>
              ) : null}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/**
 * The message composer.
 *
 * Reuses `SettingsForm` rather than introducing a second form shell: it already
 * owns the pending state, the error region, the focus move after a failure and
 * the disabled-while-submitting behaviour — all of which this form needs
 * identically. Inventing a chat-specific one would be the fourth near-identical
 * form component the settings shell exists to prevent.
 *
 * **The pending state is the loading state for the AI call.** A non-streaming
 * turn takes as long as the provider does, so "Sending…" on a disabled button is
 * what tells the user the request is in flight ([[Design System]] §10).
 *
 * A failed turn renders its reason in the form's error region — a provider
 * outage, an exhausted budget, a rate limit — never an empty assistant bubble
 * (CLAUDE.md §15).
 */
function Composer({
  workspaceId,
  openConversationId,
}: {
  readonly workspaceId: string;
  readonly openConversationId: string | undefined;
}) {
  return (
    <SettingsSection
      title={openConversationId === undefined ? "Start a conversation" : "Reply"}
      description={
        openConversationId === undefined
          ? "Your first message becomes the conversation's title."
          : "Replies continue the conversation above."
      }
    >
      <SettingsForm
        action={sendMessageAction}
        submitLabel="Send"
        pendingLabel="Sending…"
        savedLabel="Sent"
        hidden={{
          workspace_id: workspaceId,
          // An empty string means "start a new conversation" — the action
          // converts it to an omitted field, which is what the API reads as new.
          conversation_id: openConversationId ?? "",
        }}
      >
        <FormField
          id="chat-content"
          name="content"
          label="Message"
          type="text"
          autoComplete="off"
          placeholder="Ask about your projects, scripts or plans"
        />
      </SettingsForm>
    </SettingsSection>
  );
}
