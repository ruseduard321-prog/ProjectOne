import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * The asset upload Route Handler (STEP-29).
 *
 * This is the only endpoint in the web application that a browser posts to
 * directly, which makes it the only place these properties can be established:
 *
 * - **An absent session is answered 401, never redirected.** `proxy.ts`
 *   redirects a page request to sign-in with a 307, which is right for a page
 *   and wrong here: an `XMLHttpRequest` follows a redirect transparently and
 *   would report success carrying a sign-in page, so a failed upload would look
 *   like a completed one. That is why this route is deliberately outside the
 *   proxy's matcher, and why the refusal has to live here instead.
 * - **The token never reaches the browser.** It is read from the httpOnly
 *   cookie on this side and attached here.
 * - **The API's refusals pass through with their own status and wording.**
 *   Replacing them with a generic failure would discard the only text naming
 *   the rule that was broken.
 * - **The multipart content type is forwarded verbatim**, boundary included.
 */

const uploadAsset = vi.fn();
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

class MockUnreachable extends Error {
  constructor() {
    super("The service is temporarily unavailable. Please try again.");
  }
}

vi.mock("@/lib/api", () => ({
  ApiError: MockApiError,
  ApiUnreachableError: MockUnreachable,
  uploadAsset,
}));

vi.mock("@/lib/auth", () => ({ resolveAccessToken }));
vi.mock("next/cache", () => ({ revalidatePath }));

const { POST } = await import(
  "@/app/api/workspaces/[workspaceId]/projects/[projectId]/assets/upload/route"
);

const WORKSPACE = "11111111-1111-1111-1111-111111111111";
const PROJECT = "22222222-2222-2222-2222-222222222222";
const MULTIPART = "multipart/form-data; boundary=----WebKitFormBoundaryAbC123";

const params = Promise.resolve({ workspaceId: WORKSPACE, projectId: PROJECT });

/** A request of the shape a browser's `XMLHttpRequest` produces. */
function upload(contentType: string | null = MULTIPART, withBody = true): Request {
  return new Request("http://localhost/api/upload", {
    method: "POST",
    headers: contentType === null ? {} : { "content-type": contentType },
    body: withBody ? new Uint8Array([1, 2, 3]) : null,
  });
}

const CREATED = {
  id: "33333333-3333-3333-3333-333333333333",
  project_id: PROJECT,
  name: "Cover art",
  kind: "image",
  storage_path: "abc.png",
  created_by: "44444444-4444-4444-4444-444444444444",
  created_at: "2026-08-17T10:00:00+00:00",
};

beforeEach(() => {
  resolveAccessToken.mockResolvedValue("token-abc");
  uploadAsset.mockResolvedValue(CREATED);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("asset upload route", () => {
  it("stores the file and answers 201 with the created asset", async () => {
    const response = await POST(upload() as never, { params });

    expect(response.status).toBe(201);
    await expect(response.json()).resolves.toMatchObject({ name: "Cover art" });
  });

  it("attaches the session token the browser cannot read", async () => {
    await POST(upload() as never, { params });

    expect(uploadAsset).toHaveBeenCalledWith(
      "token-abc",
      WORKSPACE,
      PROJECT,
      expect.anything(),
      MULTIPART,
    );
  });

  it("forwards the multipart boundary verbatim", async () => {
    const unusual = "multipart/form-data; boundary=--------------------------998877";

    await POST(upload(unusual) as never, { params });

    expect(uploadAsset.mock.calls[0]?.[4]).toBe(unusual);
  });

  it("drops the project page's cached render so the new asset appears", async () => {
    await POST(upload() as never, { params });

    expect(revalidatePath).toHaveBeenCalledWith(`/projects/${PROJECT}`);
  });

  it("answers an absent session with 401 rather than a redirect", async () => {
    resolveAccessToken.mockResolvedValue(undefined);

    const response = await POST(upload() as never, { params });

    // A 3xx here would be followed by XHR and reported as success carrying a
    // sign-in page — a failed upload that looks like a completed one.
    expect(response.status).toBe(401);
    expect(response.headers.get("location")).toBeNull();

    const body = (await response.json()) as { detail: string };

    expect(body.detail).toContain("session has expired");
    expect(uploadAsset).not.toHaveBeenCalled();
  });

  it("refuses a request that is not a file upload", async () => {
    const response = await POST(upload("application/json") as never, { params });

    expect(response.status).toBe(415);
    expect(uploadAsset).not.toHaveBeenCalled();
  });

  it("refuses a request with no content type at all", async () => {
    const response = await POST(upload(null) as never, { params });

    expect(response.status).toBe(415);
    expect(uploadAsset).not.toHaveBeenCalled();
  });

  it.each([
    [413, "The file is larger than the 100 MB limit for one asset."],
    [415, "The file's contents do not match its declared type."],
    [429, "Too many requests."],
    [404, "Project not found."],
  ])("passes a %i refusal through with the API's wording", async (status, detail) => {
    uploadAsset.mockRejectedValue(new MockApiError(status, detail, "req-5"));

    const response = await POST(upload() as never, { params });

    expect(response.status).toBe(status);
    await expect(response.json()).resolves.toEqual({ detail, request_id: "req-5" });
  });

  it("never adds a filename to a refusal the API left out", async () => {
    uploadAsset.mockRejectedValue(
      new MockApiError(415, "The file's extension does not match its declared type.", null),
    );

    const response = await POST(upload() as never, { params });
    const body = (await response.json()) as { detail: string };

    // The backend withholds the filename because it is caller-controlled input.
    // This layer must not put it back.
    expect(body.detail).not.toMatch(/\.\w{2,4}\b/);
  });

  it("reports an unreachable API as 503, not as a rejected file", async () => {
    uploadAsset.mockRejectedValue(new MockUnreachable());

    const response = await POST(upload() as never, { params });

    expect(response.status).toBe(503);
  });
});
