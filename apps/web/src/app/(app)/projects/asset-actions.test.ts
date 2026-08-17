import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * The asset Server Actions (STEP-29).
 *
 * What these prove is the behaviour nobody exercises by hand:
 *
 * - **A signed URL is minted only when asked for.** The action exists precisely
 *   so nothing mints one while a list renders; that it is a plain function
 *   rather than a form action is what keeps it off the render path.
 * - **A 404 says the same thing whichever cause produced it.** The API answers
 *   "this asset has no bytes" and "this asset belongs to another workspace"
 *   identically on purpose, so an asset id cannot be used to probe across
 *   tenants. A client that distinguished them would rebuild the oracle the API
 *   declines to be.
 * - **A lost session is a result, not a thrown error.** A failed preview must
 *   not replace a working screen with an error page.
 */

const assetDownloadUrl = vi.fn();
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

class MockUnreachable extends Error {
  constructor() {
    super("The service is temporarily unavailable. Please try again.");
  }
}

vi.mock("@/lib/api", () => ({
  ApiError: MockApiError,
  ApiUnreachableError: MockUnreachable,
  assetDownloadUrl,
  createAsset: vi.fn(),
  createProject: vi.fn(),
  deleteAsset: vi.fn(),
  deleteProject: vi.fn(),
  renameProject: vi.fn(),
  transitionProject: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({ resolveAccessToken }));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));

const { assetDownloadUrlAction } = await import("@/app/(app)/projects/actions");

const WORKSPACE = "11111111-1111-1111-1111-111111111111";
const PROJECT = "22222222-2222-2222-2222-222222222222";
const ASSET = "33333333-3333-3333-3333-333333333333";

beforeEach(() => {
  resolveAccessToken.mockResolvedValue("token-abc");
  assetDownloadUrl.mockResolvedValue({
    url: "https://bucket.test/o?X-Amz-Signature=deadbeef",
    expires_in_seconds: 900,
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("assetDownloadUrlAction", () => {
  it("returns the minted URL and its lifetime", async () => {
    const result = await assetDownloadUrlAction(WORKSPACE, PROJECT, ASSET);

    expect(result).toEqual({
      ok: true,
      url: "https://bucket.test/o?X-Amz-Signature=deadbeef",
      expiresInSeconds: 900,
    });
  });

  it("mints exactly one URL per call", async () => {
    await assetDownloadUrlAction(WORKSPACE, PROJECT, ASSET);

    expect(assetDownloadUrl).toHaveBeenCalledTimes(1);
    expect(assetDownloadUrl).toHaveBeenCalledWith("token-abc", WORKSPACE, PROJECT, ASSET);
  });

  it("gives one answer for a missing file and for another tenant's asset", async () => {
    // Both are 404 at the API, deliberately. Two different messages here would
    // reintroduce the distinction the backend refuses to make.
    assetDownloadUrl.mockRejectedValue(new MockApiError(404, "Asset not found."));

    const missing = await assetDownloadUrlAction(WORKSPACE, PROJECT, ASSET);

    assetDownloadUrl.mockRejectedValue(new MockApiError(404, "Project not found."));

    const foreign = await assetDownloadUrlAction(WORKSPACE, PROJECT, ASSET);

    expect(missing).toEqual(foreign);
    expect(missing).toEqual({ ok: false, error: "This file is no longer available." });
  });

  it("reports a lost session without throwing", async () => {
    resolveAccessToken.mockResolvedValue(undefined);

    const result = await assetDownloadUrlAction(WORKSPACE, PROJECT, ASSET);

    expect(result.ok).toBe(false);
    expect(assetDownloadUrl).not.toHaveBeenCalled();
  });

  it("reports an outage as itself rather than as a missing file", async () => {
    assetDownloadUrl.mockRejectedValue(new MockUnreachable());

    const result = await assetDownloadUrlAction(WORKSPACE, PROJECT, ASSET);

    expect(result).toEqual({
      ok: false,
      error: "The service is temporarily unavailable. Please try again.",
    });
  });

  it("passes an unexpected status through with the API's own message", async () => {
    assetDownloadUrl.mockRejectedValue(new MockApiError(403, "Storage is not configured."));

    const result = await assetDownloadUrlAction(WORKSPACE, PROJECT, ASSET);

    expect(result).toEqual({ ok: false, error: "Storage is not configured." });
  });
});
