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

const startChatTurn = vi.fn();
const completeChatTurn = vi.fn();
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
  startChatTurn,
  completeChatTurn,
  deleteConversation,
}));

vi.mock("@/lib/auth", () => ({ resolveAccessToken }));
vi.mock("next/cache", () => ({ revalidatePath }));

/*
 * `redirect` throws in Next.js, and the action depends on that: it is how a
 * first turn ends without falling through to the return below it. The mock
 * throws a tagged error so a test can assert *where* the action navigated,
 * which a silent no-op mock would hide.
 */
class RedirectSignal extends Error {
  constructor(readonly url: string) {
    super(`NEXT_REDIRECT:${url}`);
  }
}

const redirect = vi.fn((url: string) => {
  throw new RedirectSignal(url);
});

vi.mock("next/navigation", () => ({ redirect }));

/** Run an action that is expected to redirect, and return where it went. */
async function redirectedTo(run: () => Promise<unknown>): Promise<string> {
  try {
    await run();
  } catch (error) {
    if (error instanceof RedirectSignal) {
      return error.url;
    }

    throw error;
  }

  throw new Error("expected the action to redirect, but it returned normally");
}

const { deleteConversationAction, sendMessageAction } = await import(
  "@/app/(app)/chat/actions"
);

const WORKSPACE = "22222222-2222-2222-2222-222222222222";
const CONVERSATION = "11111111-1111-1111-1111-111111111111";
const USER_MESSAGE = "33333333-3333-3333-3333-333333333333";

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
  // Step 1 succeeds by default: the question is stored, and the id it returns
  // is what step 2 and every navigation assertion below key on.
  startChatTurn.mockImplementation(
    (_token: string, _ws: string, _content: string, conversationId?: string) =>
      Promise.resolve({
        conversation: { id: conversationId ?? "generated" },
        user_message: { id: USER_MESSAGE },
      }),
  );
  completeChatTurn.mockResolvedValue({});
  deleteConversation.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("a failed turn is reported honestly, never fabricated", () => {
  it("reports the provider failure rather than a reply, when replying in place", async () => {
    completeChatTurn.mockRejectedValue(
      new MockApiError(502, "The AI provider could not be reached"),
    );

    // An *open* conversation, so the action returns rather than navigating —
    // the screen is already showing the right transcript.
    const state = await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: CONVERSATION, content: "More" }),
    );

    // The whole point: an error, and nothing resembling an answer.
    expect(state.formError).toContain("The AI provider could not be reached");
    expect(state.saved).toBeUndefined();
  });

  it("tells the user their question survived a provider failure", async () => {
    completeChatTurn.mockRejectedValue(new MockApiError(503, "No provider is available"));

    const state = await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: CONVERSATION, content: "More" }),
    );

    // The API persists the user's message before calling a provider, so the
    // honest message says the question is safe rather than implying it is gone.
    expect(state.formError).toContain("saved");
  });

  it("revalidates even when the reply failed, because the question is stored", async () => {
    completeChatTurn.mockRejectedValue(new MockApiError(502, "Provider failed"));

    await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: CONVERSATION, content: "More" }),
    );

    // **This assertion is the inverse of what it used to be, and the inversion
    // is the fix.** Under the single-request design a failed turn stored
    // nothing, so revalidating would have implied a transcript change that had
    // not happened. Now step 1 commits the question before any provider is
    // called, so the transcript genuinely has a new unanswered message in it
    // and the screen must re-render to show it.
    expect(revalidatePath).toHaveBeenCalledWith("/chat");
  });

  it("stores nothing and does not revalidate when the question itself fails", async () => {
    startChatTurn.mockRejectedValue(new MockApiError(503, "Database unavailable"));

    const state = await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: CONVERSATION, content: "More" }),
    );

    // Step 1 failing is the one case where nothing was saved, so there is
    // nothing to show and no completion to attempt.
    expect(completeChatTurn).not.toHaveBeenCalled();
    expect(revalidatePath).not.toHaveBeenCalled();
    expect(state.formError).toBeDefined();
  });
});

describe("a first turn is reachable whether it succeeds or fails", () => {
  /*
   * The defect these cover, in one sentence: the conversation id used to exist
   * only inside a successful response, so a first turn that failed saved the
   * user's question somewhere the UI could never name — and the retry made a
   * second conversation holding a second copy of it.
   */

  it("opens the new conversation after a successful first turn", async () => {
    const url = await redirectedTo(() =>
      sendMessageAction(
        { fieldErrors: {} },
        form({ workspace_id: WORKSPACE, conversation_id: "", content: "Hello" }),
      ),
    );

    // Navigated to the conversation the turn just created, so the reply is on
    // screen rather than waiting for the user to find it in the list.
    const sentId = startChatTurn.mock.calls[0][3];

    expect(sentId).toBeTypeOf("string");
    expect(url).toBe(`/chat?conversation=${sentId}`);
  });

  it("opens the conversation holding the saved question when a first turn fails", async () => {
    completeChatTurn.mockRejectedValue(
      new MockApiError(502, "The AI provider could not be reached"),
    );

    const url = await redirectedTo(() =>
      sendMessageAction(
        { fieldErrors: {} },
        form({ workspace_id: WORKSPACE, conversation_id: "", content: "Hello" }),
      ),
    );

    const sentId = startChatTurn.mock.calls[0][3];

    // The conversation exists — the API persisted it and the question before
    // calling the provider — so the screen must open it rather than claiming
    // the message was saved while showing nothing.
    expect(url).toContain(`/chat?conversation=${sentId}`);

    // And it must carry the reason, or the user arrives at their unanswered
    // question with no explanation for why it is unanswered.
    expect(decodeURIComponent(url)).toContain("The AI provider could not be reached");
  });

  it("revalidates after a failed first turn, because a conversation now exists", async () => {
    completeChatTurn.mockRejectedValue(new MockApiError(502, "Provider failed"));

    await redirectedTo(() =>
      sendMessageAction(
        { fieldErrors: {} },
        form({ workspace_id: WORKSPACE, conversation_id: "", content: "Hello" }),
      ),
    );

    // The conversation list gained an entry even though the turn failed.
    expect(revalidatePath).toHaveBeenCalledWith("/chat");
  });

  it("sends a fresh id per new conversation, never a reused one", async () => {
    await redirectedTo(() =>
      sendMessageAction(
        { fieldErrors: {} },
        form({ workspace_id: WORKSPACE, conversation_id: "", content: "One" }),
      ),
    );

    await redirectedTo(() =>
      sendMessageAction(
        { fieldErrors: {} },
        form({ workspace_id: WORKSPACE, conversation_id: "", content: "Two" }),
      ),
    );

    // Two separate conversations. Reusing an id would make the second message
    // land in the first conversation, which is the opposite failure to the one
    // being fixed and just as wrong.
    expect(startChatTurn.mock.calls[0][3]).not.toBe(startChatTurn.mock.calls[1][3]);
  });
});

describe("retrying a failed first turn continues it rather than duplicating it", () => {
  it("sends the same conversation id the failed attempt created", async () => {
    completeChatTurn.mockRejectedValue(new MockApiError(502, "Provider failed"));

    const url = await redirectedTo(() =>
      sendMessageAction(
        { fieldErrors: {} },
        form({ workspace_id: WORKSPACE, conversation_id: "", content: "Hello" }),
      ),
    );

    // The redirect above put the id in the URL, so the composer on the screen
    // the user lands on now carries it as its open conversation. The retry is
    // therefore a reply, not a new conversation.
    const created = new URL(url, "http://localhost").searchParams.get("conversation");

    expect(created).not.toBeNull();

    completeChatTurn.mockResolvedValue({});

    const state = await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: created ?? "", content: "Hello" }),
    );

    // Same conversation, so the question is not stored a second time and the
    // user does not end up with two conversations asking the same thing.
    expect(startChatTurn.mock.calls[1][3]).toBe(created);

    // A reply inside an open conversation returns rather than navigating.
    expect(state.saved).toBe(true);
  });
});

describe("a budget refusal is not a provider outage", () => {
  it("points at the budget setting rather than suggesting a retry", async () => {
    completeChatTurn.mockRejectedValue(
      new MockApiError(402, "This workspace has reached its AI spend limit"),
    );

    const state = await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: CONVERSATION, content: "More" }),
    );

    expect(state.formError).toContain("budget");
    // Retrying would meet the same ceiling, so the message must not imply it.
    expect(state.formError).not.toContain("try again");
  });

  it("distinguishes a rate limit, which is requests rather than cost", async () => {
    completeChatTurn.mockRejectedValue(new MockApiError(429, "Too many requests"));

    const state = await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: CONVERSATION, content: "More" }),
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
    expect(startChatTurn).not.toHaveBeenCalled();
  });

  it("reports a lost session rather than calling with no token", async () => {
    resolveAccessToken.mockResolvedValue(undefined);

    const state = await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: "", content: "Hello" }),
    );

    expect(state.formError).toContain("session has expired");
    expect(startChatTurn).not.toHaveBeenCalled();
  });
});

describe("a successful turn", () => {
  it("names the new conversation itself rather than letting the server choose", async () => {
    await redirectedTo(() =>
      sendMessageAction(
        { fieldErrors: {} },
        form({ workspace_id: WORKSPACE, conversation_id: "", content: "Hello" }),
      ),
    );

    const [token, workspace, content, conversationId, projectId] =
      startChatTurn.mock.calls[0];

    expect(token).toBe("token");
    expect(workspace).toBe(WORKSPACE);
    expect(content).toBe("Hello");
    expect(projectId).toBeUndefined();

    // A real id, not undefined: the action must know where the conversation
    // will be before it calls, which is what makes the failure path work.
    expect(conversationId).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );
  });

  it("continues an existing conversation when one is open", async () => {
    await sendMessageAction(
      { fieldErrors: {} },
      form({ workspace_id: WORKSPACE, conversation_id: CONVERSATION, content: "More" }),
    );

    expect(startChatTurn).toHaveBeenCalledWith(
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
      form({ workspace_id: WORKSPACE, conversation_id: CONVERSATION, content: "More" }),
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
