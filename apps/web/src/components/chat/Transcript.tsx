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
 */
export interface TranscriptProps {
  readonly messages: readonly ApiChatMessage[];
}

export function Transcript({ messages }: TranscriptProps) {
  return (
    <ol className="flex flex-col gap-4">
      {messages.map((message) => (
        <li key={message.id}>
          <MessageBubble message={message} />
        </li>
      ))}
    </ol>
  );
}

/**
 * One message.
 *
 * The two roles are distinguished by alignment and surface rather than by colour
 * alone — colour alone would carry no meaning for a reader who cannot
 * distinguish the two surfaces ([[Design System]] §9). The role is also stated
 * in text for assistive technology, which cannot see the alignment at all.
 */
function MessageBubble({ message }: { readonly message: ApiChatMessage }) {
  const isUser = message.role === "user";

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
    </article>
  );
}
