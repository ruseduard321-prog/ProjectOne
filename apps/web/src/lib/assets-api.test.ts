/**
 * The asset upload and download client surface (STEP-29).
 *
 * These assert the properties that would be expensive to discover later:
 *
 * - **The multipart body is forwarded, not rebuilt.** The boundary lives in the
 *   `Content-Type` header the browser wrote; regenerating either half would
 *   produce a header that no longer describes the body.
 * - **The body is streamed, not buffered.** A 100 MB upload held in full by this
 *   process before being sent again doubles what a single request costs, for no
 *   gain — nothing here inspects the bytes.
 * - **A refusal keeps the API's own wording.** The backend writes messages that
 *   name the rule broken and deliberately never name the file; a client that
 *   substituted its own would discard the only actionable part.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, ApiUnreachableError, assetDownloadUrl, uploadAsset } from "@/lib/api";

const WORKSPACE = "11111111-1111-1111-1111-111111111111";
const PROJECT = "22222222-2222-2222-2222-222222222222";
const ASSET = "33333333-3333-3333-3333-333333333333";
const TOKEN = "access-token";

/** The header a browser writes for a multipart form, boundary and all. */
const MULTIPART = "multipart/form-data; boundary=----WebKitFormBoundaryAbC123";

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

/** A body of the shape a route handler forwards. */
function stream(): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new Uint8Array([1, 2, 3]));
      controller.close();
    },
  });
}

function headerOf(init: RequestInit, name: string): string | undefined {
  return (init.headers as Record<string, string> | undefined)?.[name];
}

const CREATED = {
  id: ASSET,
  project_id: PROJECT,
  name: "Cover art",
  kind: "image",
  storage_path: "abc.png",
  created_by: "44444444-4444-4444-4444-444444444444",
  created_at: "2026-08-17T10:00:00+00:00",
};

describe("uploadAsset", () => {
  it("posts to the project's upload route", async () => {
    const calls = capture(CREATED, 201);

    await uploadAsset(TOKEN, WORKSPACE, PROJECT, stream(), MULTIPART);

    expect(calls[0]?.url).toBe(
      `http://127.0.0.1:8000/api/v1/workspaces/${WORKSPACE}/projects/${PROJECT}/assets/upload`,
    );
    expect(calls[0]?.init.method).toBe("POST");
  });

  it("forwards the multipart content type with its boundary intact", async () => {
    const calls = capture(CREATED, 201);

    await uploadAsset(TOKEN, WORKSPACE, PROJECT, stream(), MULTIPART);

    // Verbatim: a boundary this side invented would not match the one dividing
    // the parts of the body it labels.
    expect(headerOf(calls[0]!.init, "Content-Type")).toBe(MULTIPART);
    expect(headerOf(calls[0]!.init, "Authorization")).toBe(`Bearer ${TOKEN}`);
  });

  it("passes the body through as a stream rather than reading it", async () => {
    const calls = capture(CREATED, 201);
    const body = stream();

    await uploadAsset(TOKEN, WORKSPACE, PROJECT, body, MULTIPART);

    // The identical object, still unread. Buffering it here would double the
    // memory a 100 MB upload costs and would gain nothing — validation is the
    // API's, where it cannot be bypassed.
    expect(calls[0]?.init.body).toBe(body);
    expect(body.locked).toBe(false);
  });

  it("declares half duplex, without which a streamed body is refused", async () => {
    const calls = capture(CREATED, 201);

    await uploadAsset(TOKEN, WORKSPACE, PROJECT, stream(), MULTIPART);

    expect((calls[0]?.init as { duplex?: string }).duplex).toBe("half");
  });

  it("never caches an upload response", async () => {
    const calls = capture(CREATED, 201);

    await uploadAsset(TOKEN, WORKSPACE, PROJECT, stream(), MULTIPART);

    expect(calls[0]?.init.cache).toBe("no-store");
  });

  it.each([
    [413, "The file is larger than the 100 MB limit for one asset."],
    [415, "The file's contents do not match its declared type."],
    [415, "That file type is not supported for this kind of asset."],
    [429, "Too many requests."],
    [404, "Project not found."],
  ])("surfaces a %i refusal with the API's own message", async (status, detail) => {
    capture({ detail, request_id: "req-9" }, status);

    await expect(uploadAsset(TOKEN, WORKSPACE, PROJECT, stream(), MULTIPART)).rejects.toThrow(
      ApiError,
    );

    await expect(
      uploadAsset(TOKEN, WORKSPACE, PROJECT, stream(), MULTIPART),
    ).rejects.toMatchObject({ status, message: detail, requestId: "req-9" });
  });

  it("reports an unreachable API as an outage, not a rejected file", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("ECONNREFUSED"))),
    );

    // Collapsing the two would tell a user their file was refused during an
    // outage, which is the wrong thing to act on.
    await expect(uploadAsset(TOKEN, WORKSPACE, PROJECT, stream(), MULTIPART)).rejects.toThrow(
      ApiUnreachableError,
    );
  });
});

describe("assetDownloadUrl", () => {
  it("asks the download route for one asset", async () => {
    const calls = capture({ url: "https://example.test/o", expires_in_seconds: 900 });

    await assetDownloadUrl(TOKEN, WORKSPACE, PROJECT, ASSET);

    expect(calls[0]?.url).toBe(
      `http://127.0.0.1:8000/api/v1/workspaces/${WORKSPACE}/projects/${PROJECT}/assets/${ASSET}/download`,
    );
    expect(calls[0]?.init.method).toBe("GET");
  });

  it("returns the URL and the lifetime it was signed for", async () => {
    capture({ url: "https://example.test/o?sig=x", expires_in_seconds: 900 });

    const download = await assetDownloadUrl(TOKEN, WORKSPACE, PROJECT, ASSET);

    expect(download.url).toBe("https://example.test/o?sig=x");
    // 15 minutes, the value STEP-28 D3 chose to bound what a leaked URL is
    // worth. Asserted so a client cannot be told one lifetime while the URL
    // carries another.
    expect(download.expires_in_seconds).toBe(900);
  });

  it("sends no body, so no capability is requested in a loggable payload", async () => {
    const calls = capture({ url: "https://example.test/o", expires_in_seconds: 900 });

    await assetDownloadUrl(TOKEN, WORKSPACE, PROJECT, ASSET);

    expect(calls[0]?.init.body).toBeUndefined();
  });

  it("surfaces a 404 for an asset with no bytes", async () => {
    capture({ detail: "Asset not found.", request_id: null }, 404);

    await expect(assetDownloadUrl(TOKEN, WORKSPACE, PROJECT, ASSET)).rejects.toMatchObject({
      status: 404,
    });
  });
});
