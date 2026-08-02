import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, ApiUnreachableError, apiRequest } from "@/lib/api";

/**
 * `env` reads NEXT_PUBLIC_* at first access and memoizes, so the variables must
 * be present before the module under test resolves them.
 */
beforeEach(() => {
  process.env.NEXT_PUBLIC_PROJECTONE_ENVIRONMENT = "development";
  process.env.NEXT_PUBLIC_PROJECTONE_API_URL = "http://127.0.0.1:8000";
});

afterEach(() => {
  vi.restoreAllMocks();
});

function respondWith(status: number, body: unknown): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Promise.resolve({
        ok: status >= 200 && status < 300,
        status,
        json: async () => Promise.resolve(body),
      } as Response),
    ),
  );
}

describe("apiRequest", () => {
  it("returns the decoded payload on success", async () => {
    respondWith(200, { message: "Signed out" });

    await expect(apiRequest({ path: "/auth/sign-out", method: "POST" })).resolves.toEqual({
      message: "Signed out",
    });
  });

  it("raises ApiError carrying the envelope's detail and request id", async () => {
    respondWith(401, { detail: "Invalid credentials", request_id: "req-123" });

    const error = await apiRequest({ path: "/auth/sign-in", method: "POST" }).catch(
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(401);
    expect((error as ApiError).message).toBe("Invalid credentials");
    expect((error as ApiError).requestId).toBe("req-123");
  });

  it("falls back to a generic message when the body is not an envelope", async () => {
    // Starlette can emit a non-JSON body on some failures; the client must not
    // crash rendering `undefined` at the user.
    respondWith(502, null);

    const error = await apiRequest({ path: "/auth/me", method: "GET" }).catch(
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe("The request could not be completed");
    expect((error as ApiError).requestId).toBeNull();
  });

  it("raises ApiUnreachableError when the request never completes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Promise.reject(new TypeError("fetch failed"))),
    );

    await expect(apiRequest({ path: "/auth/me", method: "GET" })).rejects.toBeInstanceOf(
      ApiUnreachableError,
    );
  });

  it("sends the bearer credential only when one is supplied", async () => {
    respondWith(200, {});
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;

    await apiRequest({ path: "/auth/me", method: "GET", accessToken: "token-abc" });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer token-abc");

    fetchMock.mockClear();
    await apiRequest({ path: "/auth/sign-in", method: "POST", body: {} });

    const [, anonymous] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((anonymous.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it("never caches an authentication response", async () => {
    respondWith(200, {});
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;

    await apiRequest({ path: "/auth/me", method: "GET", accessToken: "token-abc" });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.cache).toBe("no-store");
  });

  it("forwards the client address when one is supplied", async () => {
    // Public endpoints can only be limited by network address, and behind this
    // proxy the API would otherwise see one address for the whole platform
    // (ADR-002).
    respondWith(200, {});
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;

    await apiRequest({
      path: "/auth/sign-in",
      method: "POST",
      body: {},
      clientAddress: "203.0.113.5",
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)["X-Forwarded-For"]).toBe("203.0.113.5");
  });

  it("omits the forwarding header when no address is known", async () => {
    // Undefined is a normal outcome — nothing sits in front of this process, so
    // the API sees the real peer. Sending a placeholder would be worse.
    respondWith(200, {});
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;

    await apiRequest({ path: "/auth/sign-in", method: "POST", body: {} });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)["X-Forwarded-For"]).toBeUndefined();
  });

  it("sets the forwarding header rather than appending to it", async () => {
    // This process is the first trusted hop. Appending would splice whatever a
    // browser sent into a chain the API is about to trust — the exact failure
    // the API's allowlist exists to prevent.
    respondWith(200, {});
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;

    await apiRequest({
      path: "/auth/sign-in",
      method: "POST",
      body: {},
      clientAddress: "203.0.113.5",
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const forwarded = (init.headers as Record<string, string>)["X-Forwarded-For"];

    expect(forwarded).toBe("203.0.113.5");
    expect(forwarded).not.toContain(",");
  });
});
