/**
 * Session resolution when the API is unreachable (STEP-16b).
 *
 * `resolveAccessToken` owns one decision: what to do when the access cookie has
 * expired but the refresh cookie has not. Its failure path originally caught
 * every error identically and cleared the session — which is correct for a
 * refresh token the provider *rejected*, and wrong for one it never saw.
 *
 * The distinction is not cosmetic, and `api.ts` already draws it: `ApiError`
 * carries a status because a request was judged, `ApiUnreachableError` carries
 * none because no request completed. Collapsing them destroys a still-valid
 * credential during an outage and reports the outage as a signed-out session —
 * two `CLAUDE.md` §24 failures from one discarded distinction.
 *
 * These assert the branch that decides which of those happens. The API client
 * is mocked rather than the network, so what is under test is the decision, not
 * `apiRequest`'s own error mapping.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const refreshSession = vi.fn();
const readProfile = vi.fn();
const clearSession = vi.fn();
const writeSession = vi.fn();
const readAccessToken = vi.fn();
const readRefreshToken = vi.fn();
const redirect = vi.fn();

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

/** Mirrors `api.ts`: no status, no correlation id — no request was judged. */
class MockApiUnreachableError extends Error {
  constructor() {
    super("The service is temporarily unavailable. Please try again.");
    this.name = "ApiUnreachableError";
  }
}

vi.mock("@/lib/api", () => ({
  ApiError: MockApiError,
  ApiUnreachableError: MockApiUnreachableError,
  refreshSession,
  readProfile,
}));

vi.mock("@/lib/session", () => ({
  clearSession,
  writeSession,
  readAccessToken,
  readRefreshToken,
}));

vi.mock("@/lib/client-address", () => ({ readClientAddress: vi.fn(async () => "127.0.0.1") }));
vi.mock("next/navigation", () => ({ redirect }));

beforeEach(() => {
  vi.resetAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

/**
 * The state this whole suite is about: the access cookie has expired (so a
 * refresh is due) and the refresh cookie is still present and, as far as anyone
 * knows, still good.
 */
function expiredAccessValidRefresh(): void {
  readAccessToken.mockResolvedValue(undefined);
  readRefreshToken.mockResolvedValue("refresh-token-still-valid");
}

describe("resolveAccessToken when the API is unreachable", () => {
  it("propagates ApiUnreachableError rather than reporting a signed-out session", async () => {
    /*
     * **The defect this step exists for.** An outage during refresh was caught
     * by a bare `catch {}` and turned into `undefined`, which the gate above
     * reads as "no session" and redirects to sign-in. The error must escape so
     * the failure surfaces as what it is: the service being down.
     */
    const { resolveAccessToken } = await import("@/lib/auth");

    expiredAccessValidRefresh();
    refreshSession.mockRejectedValue(new MockApiUnreachableError());

    await expect(resolveAccessToken()).rejects.toBeInstanceOf(MockApiUnreachableError);
  });

  it("does not delete the refresh cookie, because the outage says nothing about it", async () => {
    /*
     * The most damaging half. Clearing here destroys a credential the provider
     * never rejected — so a user is signed out by an outage and must
     * re-authenticate even after the service returns.
     */
    const { resolveAccessToken } = await import("@/lib/auth");

    expiredAccessValidRefresh();
    refreshSession.mockRejectedValue(new MockApiUnreachableError());

    await resolveAccessToken().catch(() => undefined);

    expect(clearSession).not.toHaveBeenCalled();
  });

  it("does not write a session it never received", async () => {
    const { resolveAccessToken } = await import("@/lib/auth");

    expiredAccessValidRefresh();
    refreshSession.mockRejectedValue(new MockApiUnreachableError());

    await resolveAccessToken().catch(() => undefined);

    expect(writeSession).not.toHaveBeenCalled();
  });
});

describe("resolveAccessToken when the refresh credential is genuinely rejected", () => {
  it("clears the session on a 401, because that token is spent", async () => {
    // The behaviour STEP-16 built and this step must not regress: a refresh
    // token the provider refuses is revoked, rotated or expired, and retrying
    // it forever is worse than clearing it.
    const { resolveAccessToken } = await import("@/lib/auth");

    expiredAccessValidRefresh();
    refreshSession.mockRejectedValue(new MockApiError(401, "Invalid refresh token"));

    expect(await resolveAccessToken()).toBeUndefined();
    expect(clearSession).toHaveBeenCalledOnce();
  });

  it("clears the session on any other judged rejection", async () => {
    const { resolveAccessToken } = await import("@/lib/auth");

    expiredAccessValidRefresh();
    refreshSession.mockRejectedValue(new MockApiError(403, "Refresh not permitted"));

    expect(await resolveAccessToken()).toBeUndefined();
    expect(clearSession).toHaveBeenCalledOnce();
  });
});

describe("resolveAccessToken on the paths that do not refresh", () => {
  it("returns the access token unchanged when it has not expired", async () => {
    const { resolveAccessToken } = await import("@/lib/auth");

    readAccessToken.mockResolvedValue("access-token-live");
    readRefreshToken.mockResolvedValue("refresh-token");

    expect(await resolveAccessToken()).toBe("access-token-live");
    expect(refreshSession).not.toHaveBeenCalled();
  });

  it("returns undefined when there is no session at all", async () => {
    // A visitor with no cookies is not an outage and not a rejection — there is
    // simply nothing to resolve, and no API call should be attempted.
    const { resolveAccessToken } = await import("@/lib/auth");

    readAccessToken.mockResolvedValue(undefined);
    readRefreshToken.mockResolvedValue(undefined);

    expect(await resolveAccessToken()).toBeUndefined();
    expect(refreshSession).not.toHaveBeenCalled();
    expect(clearSession).not.toHaveBeenCalled();
  });

  it("stores the refreshed pair and returns the new token on success", async () => {
    const { resolveAccessToken } = await import("@/lib/auth");

    expiredAccessValidRefresh();
    refreshSession.mockResolvedValue({
      access_token: "access-new",
      refresh_token: "refresh-new",
      expires_in: 3600,
    });

    expect(await resolveAccessToken()).toBe("access-new");
    expect(writeSession).toHaveBeenCalledWith(
      { accessToken: "access-new", refreshToken: "refresh-new" },
      3600,
    );
  });
});

describe("requireProfile during an outage", () => {
  it("does not redirect to sign-in when the API is unreachable", async () => {
    /*
     * The user-visible symptom that opened this step: an outage bounced the
     * user to `/sign-in`, which claims their session ended. The error must
     * reach an error boundary instead, so the page can say the service is
     * unavailable and offer a retry.
     */
    const { requireProfile } = await import("@/lib/auth");

    expiredAccessValidRefresh();
    refreshSession.mockRejectedValue(new MockApiUnreachableError());

    await expect(requireProfile()).rejects.toBeInstanceOf(MockApiUnreachableError);
    expect(redirect).not.toHaveBeenCalled();
  });

  it("propagates an outage that happens while reading the profile", async () => {
    // The second call the gate makes. A live access cookie skips the refresh
    // entirely, so this is the path an outage takes for a user whose token has
    // not yet expired.
    const { requireProfile } = await import("@/lib/auth");

    readAccessToken.mockResolvedValue("access-token-live");
    readRefreshToken.mockResolvedValue("refresh-token");
    readProfile.mockRejectedValue(new MockApiUnreachableError());

    await expect(requireProfile()).rejects.toBeInstanceOf(MockApiUnreachableError);
    expect(redirect).not.toHaveBeenCalled();
    expect(clearSession).not.toHaveBeenCalled();
  });

  it("still clears and redirects when the profile call is genuinely rejected", async () => {
    // Unchanged STEP-16 behaviour: a 401 on `/auth/me` means the token was
    // revoked upstream, which is a real signed-out state.
    const { requireProfile } = await import("@/lib/auth");

    readAccessToken.mockResolvedValue("access-token-live");
    readRefreshToken.mockResolvedValue("refresh-token");
    readProfile.mockRejectedValue(new MockApiError(401, "Invalid token"));

    await requireProfile();

    expect(clearSession).toHaveBeenCalledOnce();
    expect(redirect).toHaveBeenCalledOnce();
  });
});
