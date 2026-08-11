import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * The chat Server Actions (STEP-23).
 *
 * These assert the behaviour a user meets when a turn fails, which is the part
 * of this screen nobody exercises by hand and the part CLAUDE.md §15 governs
 * most directly:
 *
 * - **A failed turn never returns a reply.** No fabricated text, no empty
 *   assistant message, no "sorry, something went wrong" stored as though the
 *   model said it. The action returns an error state and the transcript keeps
 *   only what genuinely happened.
 * - **A provider outage is distinguishable from an exhausted budget.** One is
 *   temporary and worth retrying; the other needs an owner to change a setting.
 *   Telling a user to retry a call that a ceiling will refuse again is worse
 *   than saying nothing.
 * - **The user's question is never presented as lost.** The API persists it
 *   before calling a provider, so the failure message says so.
 *
 * The API client is mocked rather than the network, so these assert the action's
 * own decisions rather than re-testing `api.ts`.
 */

const sendChatMessage = vi.fn();
const deleteConversation = vi.fn();
const resolveAccessToken = vi.fn();
const revalidatePath = vi.fn();

class MockApiError extends Error {
  constructor(
    readonly status: number,
    detail: string,
    readonly requestId: string | null = "req-1",
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

class MockApiUnreachableError extends Error {}

vi.mock("@/lib/api", () => ({
  ApiError: MockApiError,
  ApiUnreachableError: MockApiUnreachableError,
  sendChatMessage,
  deleteConversation,
}));

vi.mock("@/lib/auth", () => ({ resolveAccessToken }));
vi.mock("next/cache", () => ({ revalidatePath }));

const { deleteConversationAction, sendMessageAction } = await import(
  "@/app/(app)/chat/actions"
);

const WORKSPACE = "22222222-2222-2222-2222-222222222222";
const CONVERSATION = "11111111-1111-1111-1111-111111111111";

/** Build the form payload the composer submits. */
function form(fields: Readonly<Record<string, string>>): FormData {
  const data = new FormData();

  for (const [name, value] of Object.entries(fields)) {
    data.set(name, value);
  }

  return data;
}

beforeEach(() => {
  resolveAccessToken.mockResolvedValue("token");
  sendChatMessage.mockResolvedValue({});
  deleteConversation.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("a failed turn is reported honestly, never fabricated", () => {
  it("returns an error state rather than a reply when the provider fails", async () => {
    sendChatMessage.mockRejectedValue(
      new MockApiError(502, "The AI provider could not be reached"),
    );

    const state = await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: "", content: "Hello" }),
    );

    // The whole point: an error, and nothing resembling an answer.
    expect(state.formError).toContain("The AI provider could not be reached");
    expect(state.saved).toBeUndefined();
  });

  it("tells the user their question survived a provider failure", async () => {
    sendChatMessage.mockRejectedValue(new MockApiError(503, "No provider is available"));

    const state = await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: "", content: "Hello" }),
    );

    // The API persists the user's message before calling a provider, so the
    // honest message says the question is safe rather than implying it is gone.
    expect(state.formError).toContain("saved");
  });

  it("does not revalidate the page when the turn failed", async () => {
    sendChatMessage.mockRejectedValue(new MockApiError(502, "Provider failed"));

    await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: "", content: "Hello" }),
    );

    // Nothing changed that a re-render would show, and revalidating on failure
    // would imply the transcript had moved on.
    expect(revalidatePath).not.toHaveBeenCalled();
  });
});

describe("a budget refusal is not a provider outage", () => {
  it("points at the budget setting rather than suggesting a retry", async () => {
    sendChatMessage.mockRejectedValue(
      new MockApiError(402, "This workspace has reached its AI spend limit"),
    );

    const state = await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: "", content: "Hello" }),
    );

    expect(state.formError).toContain("budget");
    // Retrying would meet the same ceiling, so the message must not imply it.
    expect(state.formError).not.toContain("try again");
  });

  it("distinguishes a rate limit, which is requests rather than cost", async () => {
    sendChatMessage.mockRejectedValue(new MockApiError(429, "Too many requests"));

    const state = await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: "", content: "Hello" }),
    );

    expect(state.formError).toContain("Wait a minute");
    expect(state.formError).not.toContain("budget");
  });
});

describe("what never reaches the API", () => {
  it("refuses an empty message without spending a request", async () => {
    const state = await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: "", content: "   " }),
    );

    expect(state.fieldErrors.content).toBe("Type a message to send.");
    expect(sendChatMessage).not.toHaveBeenCalled();
  });

  it("reports a lost session rather than calling with no token", async () => {
    resolveAccessToken.mockResolvedValue(undefined);

    const state = await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: "", content: "Hello" }),
    );

    expect(state.formError).toContain("session has expired");
    expect(sendChatMessage).not.toHaveBeenCalled();
  });
});

describe("a successful turn", () => {
  it("passes an empty conversation id as undefined, starting a new conversation", async () => {
    await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: "", content: "Hello" }),
    );

    expect(sendChatMessage).toHaveBeenCalledWith(
      "token",
      WORKSPACE,
      "Hello",
      undefined,
      undefined,
    );
  });

  it("continues an existing conversation when one is open", async () => {
    await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: CONVERSATION, content: "More" }),
    );

    expect(sendChatMessage).toHaveBeenCalledWith(
      "token",
      WORKSPACE,
      "More",
      CONVERSATION,
      undefined,
    );
  });

  it("revalidates the screen so the new turn renders", async () => {
    await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: "", content: "Hello" }),
    );

    expect(revalidatePath).toHaveBeenCalledWith("/chat");
  });
});

describe("deleting a conversation", () => {
  it("reports a conversation that is already gone", async () => {
    deleteConversation.mockRejectedValue(new MockApiError(404, "Conversation not found"));

    const state = await deleteConversationAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: CONVERSATION }),
    );

    expect(state.formError).toContain("no longer exists");
  });

  it("revalidates the screen after a successful delete", async () => {
    const state = await deleteConversationAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: CONVERSATION }),
    );

    expect(state.saved).toBe(true);
    expect(revalidatePath).toHaveBeenCalledWith("/chat");
  });
});
