import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * The settings Server Actions (STEP-19).
 *
 * What these prove is the behaviour a user meets when something goes wrong,
 * which is the part of a form nobody exercises by hand:
 *
 * - **A rejected value never reaches the API.** A malformed ceiling is caught
 *   here, so a typo does not consume a rate-limit slot or produce a 422 the
 *   form claimed would not happen.
 * - **An error never carries the submitted key.** The one value that must not
 *   appear in a returned state, a log, or a rendered message.
 * - **A 402 and a 403 are distinguishable to the user.** A budget refusal is
 *   actionable ("raise the limit"); a role refusal is not, and telling someone
 *   to raise a limit they cannot change is worse than saying nothing.
 *
 * The API client is mocked rather than the network, so these assert the action's
 * own decisions rather than re-testing `api.ts`.
 */

const storeProviderCredential = vi.fn();
const updateBudget = vi.fn();
const revokeProviderCredential = vi.fn();
const updateProfile = vi.fn();
const renameWorkspace = vi.fn();
const resolveAccessToken = vi.fn();

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

vi.mock("@/lib/api", () => ({
  ApiError: MockApiError,
  ApiUnreachableError: class extends Error {},
  storeProviderCredential,
  updateBudget,
  revokeProviderCredential,
  updateProfile,
  renameWorkspace,
}));

vi.mock("@/lib/auth", () => ({ resolveAccessToken }));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));

const KEY = "sk-test-UNIQUEMARKER-abcdefghijklmnop-9999";

/** Build FormData from a plain object, as a submitted form would. */
function form(values: Record<string, string>): FormData {
  const data = new FormData();

  for (const [name, value] of Object.entries(values)) {
    data.set(name, value);
  }

  return data;
}

const EMPTY = { fieldErrors: {} };

beforeEach(() => {
  resolveAccessToken.mockResolvedValue("token-abc");
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("updateBudgetAction", () => {
  it("refuses a non-numeric ceiling without calling the API", async () => {
    const { updateBudgetAction } = await import("./actions");

    const state = await updateBudgetAction(EMPTY, form({ workspace_id: "w1", limit_usd: "abc" }));

    expect(state.fieldErrors.limit_usd).toBeDefined();
    expect(updateBudget).not.toHaveBeenCalled();
  });

  it("refuses a zero ceiling", async () => {
    // A zero ceiling refuses every call, which nobody setting a spending limit
    // means — disabling AI is what the shutdown switch is for.
    const { updateBudgetAction } = await import("./actions");

    const state = await updateBudgetAction(EMPTY, form({ workspace_id: "w1", limit_usd: "0" }));

    expect(state.fieldErrors.limit_usd).toBeDefined();
    expect(updateBudget).not.toHaveBeenCalled();
  });

  it("refuses a fractional period", async () => {
    const { updateBudgetAction } = await import("./actions");

    const state = await updateBudgetAction(
      EMPTY,
      form({ workspace_id: "w1", limit_usd: "10.00", period_days: "2.5" }),
    );

    expect(state.fieldErrors.period_days).toBeDefined();
    expect(updateBudget).not.toHaveBeenCalled();
  });

  it("passes a valid ceiling through as the string the user typed", async () => {
    // Not parsed and re-serialized: `Number("0.10")` back to a string is how a
    // typed ceiling becomes a slightly different one.
    const { updateBudgetAction } = await import("./actions");

    updateBudget.mockResolvedValue({});

    const state = await updateBudgetAction(
      EMPTY,
      form({ workspace_id: "w1", limit_usd: "0.10", period_days: "30" }),
    );

    expect(state.saved).toBe(true);
    expect(updateBudget).toHaveBeenCalledWith("token-abc", "w1", "0.10", 30);
  });

  it("renders a budget refusal as the API's own actionable message", async () => {
    const { updateBudgetAction } = await import("./actions");

    updateBudget.mockRejectedValue(
      new MockApiError(402, "This workspace has reached its AI spending limit"),
    );

    const state = await updateBudgetAction(
      EMPTY,
      form({ workspace_id: "w1", limit_usd: "10.00" }),
    );

    expect(state.formError).toBe("This workspace has reached its AI spending limit");
    expect(state.requestId).toBe("req-1");
  });

  it("renders a role refusal differently from a budget one", async () => {
    // Telling a member to raise a limit they cannot change is worse than saying
    // nothing. The two refusals must not collapse into one message.
    const { updateBudgetAction } = await import("./actions");

    updateBudget.mockRejectedValue(new MockApiError(403, "Permission denied"));

    const state = await updateBudgetAction(
      EMPTY,
      form({ workspace_id: "w1", limit_usd: "10.00" }),
    );

    expect(state.formError).toContain("role");
  });
});

describe("storeProviderKeyAction", () => {
  it("refuses an empty key without calling the API", async () => {
    const { storeProviderKeyAction } = await import("./actions");

    const state = await storeProviderKeyAction(
      EMPTY,
      form({ workspace_id: "w1", provider: "openai", api_key: "   " }),
    );

    expect(state.fieldErrors.api_key).toBeDefined();
    expect(storeProviderCredential).not.toHaveBeenCalled();
  });

  it("never echoes the key back in the returned state", async () => {
    const { storeProviderKeyAction } = await import("./actions");

    storeProviderCredential.mockResolvedValue({
      id: "1",
      provider: "openai",
      last_four: "9999",
    });

    const state = await storeProviderKeyAction(
      EMPTY,
      form({ workspace_id: "w1", provider: "openai", api_key: KEY }),
    );

    expect(state.saved).toBe(true);
    // Serialized whole rather than field by field: a key leaking through any
    // property, nested or not, fails this and would pass a per-field check.
    expect(JSON.stringify(state)).not.toContain(KEY);
  });

  it("never carries the key into an error state either", async () => {
    // The failure path is where a well-meaning implementation adds "we could
    // not save <value>" — which puts the credential straight into rendered HTML.
    const { storeProviderKeyAction } = await import("./actions");

    storeProviderCredential.mockRejectedValue(
      new MockApiError(422, "The API key is too short to be valid"),
    );

    const state = await storeProviderKeyAction(
      EMPTY,
      form({ workspace_id: "w1", provider: "openai", api_key: KEY }),
    );

    expect(state.formError).toBe("The API key is too short to be valid");
    expect(JSON.stringify(state)).not.toContain(KEY);
  });

  it("reports an expired session rather than silently doing nothing", async () => {
    const { storeProviderKeyAction } = await import("./actions");

    resolveAccessToken.mockResolvedValue(undefined);

    const state = await storeProviderKeyAction(
      EMPTY,
      form({ workspace_id: "w1", provider: "openai", api_key: KEY }),
    );

    expect(state.formError).toContain("expired");
    expect(storeProviderCredential).not.toHaveBeenCalled();
  });
});

describe("updateProfileAction", () => {
  it("refuses a whitespace-only display name", async () => {
    const { updateProfileAction } = await import("./actions");

    const state = await updateProfileAction(EMPTY, form({ display_name: "   " }));

    expect(state.fieldErrors.display_name).toBeDefined();
    expect(updateProfile).not.toHaveBeenCalled();
  });

  it("trims before sending", async () => {
    const { updateProfileAction } = await import("./actions");

    updateProfile.mockResolvedValue({});

    await updateProfileAction(EMPTY, form({ display_name: "  Ada  " }));

    expect(updateProfile).toHaveBeenCalledWith("token-abc", "Ada");
  });
});

describe("renameWorkspaceAction", () => {
  it("surfaces a 403 as a role message", async () => {
    const { renameWorkspaceAction } = await import("./actions");

    renameWorkspace.mockRejectedValue(new MockApiError(403, "Permission denied"));

    const state = await renameWorkspaceAction(
      EMPTY,
      form({ workspace_id: "w1", name: "Renamed" }),
    );

    expect(state.formError).toContain("role");
  });
});
