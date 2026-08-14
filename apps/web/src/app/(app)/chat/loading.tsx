/**
 * Loading state for the chat screen.
 *
 * The shape mirrors what the page renders — a heading, the conversation list
 * beside a transcript, then the composer — because a skeleton with a different
 * shape to its content causes the reflow it exists to prevent
 * ([[Design System]] §10).
 *
 * The transcript placeholders alternate alignment, matching how user and
 * assistant messages actually render. A column of identical centred blocks would
 * imply a different screen to the one that arrives.
 */
function ConversationSkeleton() {
  return <div className="h-11 w-full animate-pulse rounded-lg bg-skeleton" />;
}

function MessageSkeleton({ align }: { readonly align: "start" | "end" }) {
  return (
    <div
      className={[
        "flex max-w-prose flex-col gap-2 rounded-lg border border-border px-5 py-4",
        align === "end" ? "ml-auto" : "mr-auto",
      ].join(" ")}
    >
      <div className="h-3 w-16 animate-pulse rounded-sm bg-skeleton" />
      <div className="h-4 w-64 animate-pulse rounded-sm bg-skeleton" />
      <div className="h-4 w-48 animate-pulse rounded-sm bg-skeleton" />
    </div>
  );
}

export default function Loading() {
  return (
    <div className="flex flex-col gap-6" role="status" aria-busy="true">
      <span className="sr-only">Loading conversations</span>

      <div className="flex flex-col gap-2">
        <div className="h-8 w-32 animate-pulse rounded-md bg-skeleton" />
        <div className="h-4 w-80 animate-pulse rounded-sm bg-skeleton" />
      </div>

      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        <div className="flex w-full flex-col gap-2 lg:w-72">
          <div className="h-6 w-36 animate-pulse rounded-md bg-skeleton" />
          <ConversationSkeleton />
          <ConversationSkeleton />
          <ConversationSkeleton />
        </div>

        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <MessageSkeleton align="end" />
          <MessageSkeleton align="start" />

          <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface px-6 py-5">
            <div className="h-5 w-32 animate-pulse rounded-md bg-skeleton" />
            <div className="h-10 w-full animate-pulse rounded-md bg-skeleton" />
            <div className="h-9 w-24 animate-pulse rounded-md bg-skeleton" />
          </div>
        </div>
      </div>
    </div>
  );
}
