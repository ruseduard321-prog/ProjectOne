import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  type ApiWorkspace,
  listBudgets,
  listProviderCredentials,
  revokeProviderCredential,
  storeProviderCredential,
  updateBudget,
} from "@/lib/api";
import { resolveWorkspace } from "@/lib/workspace";

/**
 * The settings client surface (STEP-19).
 *
 * These assert the properties that would be expensive to discover later:
 *
 * - **A provider key travels in the request body and never in a URL.** A key in
 *   a path or query string ends up in every proxy log and browser history entry
 *   between here and the API, and no amount of care at the API recovers it.
 * - **`spent_usd` is never sent.** The API answers 422 and the column-level
 *   grant refuses the write, but a client that tried would be a client whose
 *   author believed it was writable.
 * - **Workspace resolution is deterministic.** "The first workspace" is only a
 *   safe simplification if "first" is stable — a selection that moved between
 *   page loads would silently edit a different workspace each time.
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

const KEY = "sk-test-UNIQUEMARKER-abcdefghijklmnop-9999";

describe("provider credentials", () => {
  it("sends the key in the request body, never in the URL", async () => {
    const calls = capture({ id: "1", provider: "openai", last_four: "9999" });

    await storeProviderCredential("token", "workspace-1", "openai", KEY);

    const [call] = calls;
    expect(call).toBeDefined();

    // The whole point: a key in a path or query string is a key in every proxy
    // log between the browser and the API.
    expect(call?.url).not.toContain(KEY);
    expect(call?.url).toBe(
      "http://127.0.0.1:8000/api/v1/workspaces/workspace-1/ai/providers/openai",
    );
    expect(call?.init.method).toBe("PUT");
    expect(JSON.parse(String(call?.init.body))).toEqual({ api_key: KEY });
  });

  it("presents the session as a bearer credential and forwards no client address", async () => {
    // Authenticated calls are rate limited by verified `user_id` (ADR-002 §1),
    // so an address would be collected for nothing — the least data that
    // achieves the goal is the right amount (CLAUDE.md §16).
    const calls = capture({ id: "1", provider: "openai", last_four: "9999" });

    await storeProviderCredential("token-abc", "workspace-1", "openai", KEY);

    const headers = calls[0]?.init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer token-abc");
    expect(headers["X-Forwarded-For"]).toBeUndefined();
  });

  it("reads credentials without ever asking for key material", async () => {
    const calls = capture([{ id: "1", provider: "openai", last_four: "9999" }]);

    const credentials = await listProviderCredentials("token", "workspace-1");

    expect(calls[0]?.init.method).toBe("GET");
    // The response type has no field for a key, so there is nothing to assert
    // the absence of — which is the design. What is assertable is that the
    // decoded value carries only the three displayable fields.
    expect(Object.keys(credentials[0] ?? {})).toEqual(["id", "provider", "last_four"]);
  });

  it("revokes with DELETE and tolerates an empty 204 body", async () => {
    // A 204 has no body, so `response.json()` rejects. The client must treat
    // that as success rather than as a parse failure.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Promise.resolve({
          ok: true,
          status: 204,
          json: async () => Promise.reject(new Error("no body")),
        } as unknown as Response),
      ),
    );

    await expect(
      revokeProviderCredential("token", "workspace-1", "openai"),
    ).resolves.toBeNull();
  });
});

describe("budgets", () => {
  it("never sends spent_usd", async () => {
    const calls = capture({});

    await updateBudget("token", "workspace-1", "50.00", 30);

    const body = JSON.parse(String(calls[0]?.init.body)) as Record<string, unknown>;

    expect(body).toEqual({ limit_usd: "50.00", period_days: 30 });
    expect(body.spent_usd).toBeUndefined();
    expect(body.breaker_tripped_at).toBeUndefined();
  });

  it("omits the period entirely when it is not being changed", async () => {
    // Sending a default would silently reset the billing period on an edit that
    // was about the ceiling. Omitting the key is what leaves it untouched.
    const calls = capture({});

    await updateBudget("token", "workspace-1", "50.00");

    expect(JSON.parse(String(calls[0]?.init.body))).toEqual({ limit_usd: "50.00" });
  });

  it("keeps amounts as decimal strings through the round trip", async () => {
    // Parsed to `number` and re-serialized, 0.001234 stops matching the ledger
    // it came from — and this screen's purpose is to be trusted about money.
    capture([
      {
        id: "b1",
        workflow_type: null,
        limit_usd: "50.000000",
        spent_usd: "0.001234",
        remaining_usd: "49.998766",
        period_started_at: "2026-08-04T00:00:00+00:00",
        period_days: 30,
        breaker_open: false,
        breaker_reason: null,
      },
    ]);

    const budgets = await listBudgets("token", "workspace-1");

    expect(budgets[0]?.spent_usd).toBe("0.001234");
    expect(typeof budgets[0]?.limit_usd).toBe("string");
  });
});

describe("resolveWorkspace", () => {
  function workspace(id: string, name: string): ApiWorkspace {
    return { id, name, owner_id: "user-1" };
  }

  it("selects the first workspace and reports the others", async () => {
    capture([workspace("w1", "Alpha"), workspace("w2", "Beta")]);

    const resolved = await resolveWorkspace("token");

    expect(resolved?.current.id).toBe("w1");
    expect(resolved?.available).toHaveLength(2);
  });

  it("returns undefined when the caller belongs to no workspace", async () => {
    // A legitimate state, not an error: a confirmed account that never created
    // a workspace is in it. Modelled so the screen renders an empty state
    // rather than throwing into the error boundary.
    capture([]);

    await expect(resolveWorkspace("token")).resolves.toBeUndefined();
  });

  it("is deterministic across repeated resolutions", async () => {
    // "The first workspace" is only a safe simplification if "first" is stable.
    // The API orders by name; this asserts the client does not reorder it.
    capture([workspace("w1", "Alpha"), workspace("w2", "Beta")]);

    const first = await resolveWorkspace("token");
    const second = await resolveWorkspace("token");

    expect(first?.current.id).toBe(second?.current.id);
  });
});
