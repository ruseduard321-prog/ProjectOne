import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  type ApiChatMessage,
  type ApiConversation,
  deleteConversation,
  listConversations,
  readConversation,
  completeChatTurn,
  startChatTurn,
} from "@/lib/api";

/**
 * The chat client surface (STEP-23).
 *
 * These assert the properties that would be expensive to discover later:
 *
 * - **A role is never sent.** The server writes the assistant role from what a
 *   provider actually returned. A client that could supply one could forge a
 *   reply into its own transcript and have it replayed to the model on every
 *   later turn as though the assistant had said it.
 * - **A new conversation omits `conversation_id` rather than sending null.** The
 *   request model forbids unexpected fields, and "absent" is what the API reads
 *   as "start a new one".
 * - **The workspace is always in the path, never the body.** Every route is
 *   authorized against the path parameter, so a body-supplied workspace would be
 *   a second, unauthorized answer to which tenant this is.
 */

beforeEach(() => {
  process.env.NEXT_PUBLIC_PROJECTONE_ENVIRONMENT = "development";
  process.env.NEXT_PUBLIC_PROJECTONE_API_URL = "http://127.0.0.1:8000";
});

afterEach(() => {
  vi.restoreAllMocks();
});

interface Captured {
  readonly url: string;
  readonly init: RequestInit;
}

/** Stub fetch, returning `body`, and capture what was sent. */
function capture(body: unknown, status = 200): Captured[] {
  const calls: Captured[] = [];

  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit) => {
      calls.push({ url, init });

      return Promise.resolve({
        ok: status >= 200 && status < 300,
        status,
        json: async () => Promise.resolve(body),
      } as Response);
    }),
  );

  return calls;
}

const WORKSPACE = "22222222-2222-2222-2222-222222222222";
const CONVERSATION = "11111111-1111-1111-1111-111111111111";

/** A conversation as the API returns it. */
function conversation(): ApiConversation {
  return {
    id: CONVERSATION,
    workspace_id: WORKSPACE,
    title: "A conversation",
    project_id: null,
    created_by: "33333333-3333-3333-3333-333333333333",
    created_at: "2026-08-11T10:00:00+00:00",
    updated_at: "2026-08-11T10:00:00+00:00",
    version: 1,
  };
}

/** A message as the API returns it. */
function message(role: "user" | "assistant"): ApiChatMessage {
  return {
    id: "44444444-4444-4444-4444-444444444444",
    conversation_id: CONVERSATION,
    role,
    content: role === "user" ? "Hello" : "Hello back",
    provider: role === "assistant" ? "openai" : null,
    model: role === "assistant" ? "gpt-4o-mini" : null,
    token_count: role === "assistant" ? 42 : 0,
    created_at: "2026-08-11T10:00:00+00:00",
  };
}

describe("a client may only ever send a user message", () => {
  it("sends no role, so a reply cannot be forged into the transcript", async () => {
    const calls = capture({
      conversation: conversation(),
      user_message: message("user"),
      assistant_message: message("assistant"),
    });

    await startChatTurn("token", WORKSPACE, "Hello");

    const body = JSON.parse(String(calls[0]?.init.body)) as Record<string, unknown>;

    expect(body).not.toHaveProperty("role");
  });

  it("sends no workspace_id in the body — the path is what is authorized", async () => {
    const calls = capture({
      conversation: conversation(),
      user_message: message("user"),
      assistant_message: message("assistant"),
    });

    await startChatTurn("token", WORKSPACE, "Hello");

    const body = JSON.parse(String(calls[0]?.init.body)) as Record<string, unknown>;

    expect(body).not.toHaveProperty("workspace_id");
    expect(calls[0]?.url).toContain(`/workspaces/${WORKSPACE}/chat/conversations`);
  });
});

describe("starting a conversation versus continuing one", () => {
  it("omits conversation_id entirely when starting a new conversation", async () => {
    const calls = capture({
      conversation: conversation(),
      user_message: message("user"),
      assistant_message: message("assistant"),
    });

    await startChatTurn("token", WORKSPACE, "Hello");

    const body = JSON.parse(String(calls[0]?.init.body)) as Record<string, unknown>;

    // Absent, not null: the API reads an omitted id as "start a new one", and
    // an explicit null would be the same intent expressed less clearly.
    expect(body).not.toHaveProperty("conversation_id");
    expect(body).not.toHaveProperty("project_id");
    expect(body.content).toBe("Hello");
  });

  it("carries conversation_id when continuing", async () => {
    const calls = capture({
      conversation: conversation(),
      user_message: message("user"),
      assistant_message: message("assistant"),
    });

    await startChatTurn("token", WORKSPACE, "Hello", CONVERSATION);

    const body = JSON.parse(String(calls[0]?.init.body)) as Record<string, unknown>;

    expect(body.conversation_id).toBe(CONVERSATION);
  });

  it("carries project_id when a new conversation is about a project", async () => {
    const calls = capture({
      conversation: conversation(),
      user_message: message("user"),
      assistant_message: message("assistant"),
    });

    await startChatTurn("token", WORKSPACE, "Hello", undefined, "99999999-9999-9999-9999-999999999999");

    const body = JSON.parse(String(calls[0]?.init.body)) as Record<string, unknown>;

    expect(body.project_id).toBe("99999999-9999-9999-9999-999999999999");
    expect(body).not.toHaveProperty("conversation_id");
  });
});

describe("completing a stored turn", () => {
  it("names the user message, not the conversation, as the turn key", async () => {
    const calls = capture({
      conversation: conversation(),
      user_message: message("user"),
      assistant_message: message("assistant"),
    });

    await completeChatTurn("token", WORKSPACE, CONVERSATION, "abc-123");

    const body = JSON.parse(String(calls[0]?.init.body)) as Record<string, unknown>;

    // A conversation holds many turns. Keying on the conversation would make a
    // second question look like a retry of the first, and idempotency would
    // then refuse a legitimate follow-up.
    expect(body.user_message_id).toBe("abc-123");
    expect(calls[0]?.url).toContain(
      `/workspaces/${WORKSPACE}/chat/conversations/${CONVERSATION}/completion`,
    );
  });

  it("sends no content — the question is already stored", async () => {
    const calls = capture({
      conversation: conversation(),
      user_message: message("user"),
      assistant_message: message("assistant"),
    });

    await completeChatTurn("token", WORKSPACE, CONVERSATION, "abc-123");

    const body = JSON.parse(String(calls[0]?.init.body)) as Record<string, unknown>;

    // Re-sending the text would make the completion capable of storing a
    // *different* question than the one it claims to answer.
    expect(body).not.toHaveProperty("content");
  });
});

describe("reads and deletes", () => {
  it("lists conversations from the workspace path", async () => {
    const calls = capture([conversation()]);

    const listed = await listConversations("token", WORKSPACE);

    expect(calls[0]?.url).toContain(`/workspaces/${WORKSPACE}/chat/conversations`);
    expect(calls[0]?.init.method).toBe("GET");
    expect(listed).toHaveLength(1);
  });

  it("reads one conversation with its transcript in a single call", async () => {
    const calls = capture({
      conversation: conversation(),
      messages: [message("user"), message("assistant")],
    });

    const detail = await readConversation("token", WORKSPACE, CONVERSATION);

    // One request, not two: a client opening a conversation always needs both,
    // and splitting them would render the screen in two stages for no benefit.
    expect(calls).toHaveLength(1);
    expect(detail.messages).toHaveLength(2);
  });

  it("deletes by id, through DELETE", async () => {
    const calls = capture(undefined, 204);

    await deleteConversation("token", WORKSPACE, CONVERSATION);

    expect(calls[0]?.init.method).toBe("DELETE");
    expect(calls[0]?.url).toContain(
      `/workspaces/${WORKSPACE}/chat/conversations/${CONVERSATION}`,
    );
  });
});

describe("an assistant message carries its attribution", () => {
  it("preserves the provider and model that answered", async () => {
    capture({
      conversation: conversation(),
      messages: [message("assistant")],
    });

    const detail = await readConversation("token", WORKSPACE, CONVERSATION);
    const reply = detail.messages[0];

    // A reply served after a fallback came from a provider the workspace did
    // not choose. A transcript that drops this cannot honestly attribute it.
    expect(reply?.provider).toBe("openai");
    expect(reply?.model).toBe("gpt-4o-mini");
    expect(reply?.token_count).toBe(42);
  });

  it("leaves a user message unattributed, because no provider produced it", async () => {
    capture({
      conversation: conversation(),
      messages: [message("user")],
    });

    const detail = await readConversation("token", WORKSPACE, CONVERSATION);

    expect(detail.messages[0]?.provider).toBeNull();
    expect(detail.messages[0]?.model).toBeNull();
  });
});
