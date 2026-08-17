import { revalidatePath } from "next/cache";
import { type NextRequest, NextResponse } from "next/server";

import { ApiError, ApiUnreachableError, uploadAsset } from "@/lib/api";
import { resolveAccessToken } from "@/lib/auth";

/**
 * Forwards a browser's file upload to the API, carrying the session for it.
 *
 * ## Why a Route Handler rather than a Server Action
 *
 * Every other write in this application is a Server Action, and this one cannot
 * be — for two independent reasons, either of which would be sufficient
 * ([[STEP-29 Asset Management UI]] D1):
 *
 *  1. **Size.** Next.js caps a Server Action body at 1 MB by default
 *     (`next/dist/server/app-render/action-handler.js`, which applies the same
 *     ceiling to multipart parsing as `fieldSize`). The API accepts 100 MB. The
 *     established pattern cannot carry the established payload.
 *  2. **Progress.** `useActionState` exposes pending or not-pending and nothing
 *     between, so a Server Action can render a spinner but never a percentage.
 *     A 60 MB video behind a spinner is indistinguishable from a hang.
 *
 * An `XMLHttpRequest` against this route has `upload.onprogress`, which is the
 * only place a real byte count is available in a browser. `fetch` has no
 * equivalent that is safe to depend on.
 *
 * ## The token never reaches the browser
 *
 * This is the whole reason the browser does not post to the API directly. The
 * access token lives in an httpOnly cookie (`session.ts`), so client code cannot
 * read it and could not attach it; the API also registers no CORS middleware, so
 * a cross-origin request would be refused before reaching a route. This handler
 * runs on the server, reads the cookie exactly as a Server Action does, and is
 * the second leg of browser → Next.js → API.
 *
 * **It grants no access that did not already exist.** The same cookie, the same
 * helper, the same bearer token, against a route whose authorization
 * (`VIEW_WORKSPACE`) the API enforces regardless of who asks.
 *
 * ## Why this is not in the proxy's matcher
 *
 * `proxy.ts` redirects a request with no session cookie to sign-in with a 307.
 * That is right for a page and wrong for this: an `XMLHttpRequest` follows the
 * redirect transparently and reports success carrying a sign-in page, so the
 * upload appears to have worked. A 401 with the error envelope is an answer the
 * caller can act on. The gate is not weakened by the omission — this handler
 * refuses an absent session itself, below, and the API refuses an invalid one.
 *
 * ## Nothing here inspects the bytes
 *
 * The body is streamed straight through. Size, declared type, extension and the
 * file's own magic bytes are all checked by `app/services/asset_content.py`,
 * where the rules are testable without HTTP and where they cannot be bypassed by
 * a client that skips this route. Re-implementing any of them here would be a
 * second copy of a security boundary — the failure mode ADR-004 exists to
 * prevent.
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ workspaceId: string; projectId: string }> },
): Promise<NextResponse> {
  const { workspaceId, projectId } = await params;

  const contentType = request.headers.get("content-type");

  // The boundary lives in this header, so it is forwarded verbatim rather than
  // regenerated — a rebuilt header would no longer describe the body it labels.
  if (contentType === null || !contentType.startsWith("multipart/form-data")) {
    return NextResponse.json(
      { detail: "This endpoint accepts a file upload only.", request_id: null },
      { status: 415 },
    );
  }

  if (request.body === null) {
    return NextResponse.json(
      { detail: "The upload carried no data.", request_id: null },
      { status: 400 },
    );
  }

  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return NextResponse.json(
      {
        detail: "Your session has expired. Sign in again to upload this file.",
        request_id: null,
      },
      { status: 401 },
    );
  }

  try {
    const asset = await uploadAsset(
      accessToken,
      workspaceId,
      projectId,
      request.body,
      contentType,
    );

    // The project page renders its asset list on the server, so its cache must
    // be dropped here. The client also calls `router.refresh()` after a
    // successful upload: this clears the cached render, that re-requests it.
    revalidatePath(`/projects/${projectId}`);

    return NextResponse.json(asset, { status: 201 });
  } catch (error) {
    /*
     * The API's refusals are passed through with their own status and message.
     *
     * 413, 415, 429 and 404 each arrive carrying a `public_message` the backend
     * wrote to be shown to a person, and — deliberately — one that never echoes
     * the filename, because a filename is caller-controlled input and
     * reflecting it into an error is how one injection becomes two. Replacing
     * them with a generic failure here would discard the only text that tells
     * the user which rule they broke; appending the filename would undo the
     * rule the backend is keeping.
     */
    if (error instanceof ApiError) {
      return NextResponse.json(
        { detail: error.message, request_id: error.requestId },
        { status: error.status },
      );
    }

    if (error instanceof ApiUnreachableError) {
      return NextResponse.json({ detail: error.message, request_id: null }, { status: 503 });
    }

    throw error;
  }
}
