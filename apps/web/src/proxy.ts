import { type NextRequest, NextResponse } from "next/server";

import { devRoutesEnabled, isDevOnlyPath } from "@/lib/dev-only";
import { SIGN_IN_PATH } from "@/lib/routes";
import { ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE } from "@/lib/session-cookies";

/**
 * Refuses unauthenticated requests to the application shell before any
 * rendering begins.
 *
 * ## Why this exists in addition to the layout gate
 *
 * `requireProfile()` in `app/(app)/layout.tsx` is the authoritative check — it
 * asks the API whether the token is actually valid. But it runs *inside* the
 * `loading.tsx` Suspense boundary, so by the time it redirects, Next.js has
 * already flushed a 200 and can only finish with a `<meta http-equiv="refresh">`
 * fallback. Verified by requesting `/dashboard` with no session and observing
 * `HTTP/1.1 200` with `NEXT_REDIRECT` embedded in the streamed body.
 *
 * No shell markup or user data leaked in that response — the gate did hold. But
 * a 200 carrying a meta-refresh is a weaker answer than a redirect status: it
 * relies on the client honouring the refresh, and any client that does not
 * receives a success code for a request that was refused.
 *
 * A proxy runs before rendering starts, so it can return a real **307**.
 *
 * (Next.js 16 renamed this file convention from `middleware` to `proxy`; the
 * exported function name follows it. Behaviour is unchanged.)
 *
 * ## What this does NOT do
 *
 * **This is not the authentication control, and it must never become one.** It
 * checks only that a session cookie is *present*. It does not verify the token,
 * cannot know whether it was revoked, and a forged cookie of any value would
 * pass it. Verification requires asking the API, which is what the layout does
 * on every request.
 *
 * Splitting it this way is deliberate: this answers "is this request even
 * plausibly authenticated" cheaply and with the right status code, and the
 * layout answers "is this session real" authoritatively. Removing the layout
 * check and trusting this file would reduce authentication to the presence of a
 * cookie the user controls.
 */
export function proxy(request: NextRequest): NextResponse {
  /*
   * Development-only routes are refused here, before rendering begins.
   *
   * This is the *enforcing* half of the `/dev/session` exclusion, and it lives
   * here for a reason discovered by testing rather than assumed: a
   * `notFound()` call inside the page cannot set a 404 status, because the
   * root `loading.tsx` Suspense boundary has already flushed a 200 by the time
   * the page body runs. Observed directly — `GET /dev/session` against a
   * production build returned `HTTP 200` with the not-found body inside it.
   *
   * That is the same failure STEP-16 hit with `redirect()`, one level up: a
   * render that has already started streaming can no longer choose its status
   * code. The proxy runs before any of that.
   *
   * 404 rather than 403: a 403 confirms the route exists.
   */
  if (isDevOnlyPath(request.nextUrl.pathname)) {
    if (!devRoutesEnabled()) {
      return new NextResponse(null, { status: 404 }) as NextResponse;
    }

    // Served without the session check below, deliberately. The inspector must
    // render for a signed-out visitor — "why am I signed out" is one of the
    // questions it exists to answer, and a gate that redirected to sign-in
    // would hide exactly the state worth inspecting.
    return NextResponse.next();
  }

  const hasSession =
    request.cookies.has(ACCESS_TOKEN_COOKIE) || request.cookies.has(REFRESH_TOKEN_COOKIE);

  if (hasSession) {
    return NextResponse.next();
  }

  const signIn = new URL(SIGN_IN_PATH, request.url);
  const response = NextResponse.redirect(signIn, 307);

  /*
   * Clear the session cookies on the way out.
   *
   * Redundant when there were none, and load-bearing when there were stale
   * ones: the layout can discover mid-render that a refresh token is spent, but
   * a render may not write cookies, so it cannot clear them itself
   * (`session.ts`). Middleware runs in a context that may. Without this the
   * dead cookie survives, passes the presence check above on the next request,
   * and the user loops through a layout that can only ever redirect them again.
   */
  response.cookies.delete(ACCESS_TOKEN_COOKIE);
  response.cookies.delete(REFRESH_TOKEN_COOKIE);

  return response;
}

/**
 * The routes this runs on.
 *
 * Listed explicitly rather than as a negative pattern excluding `/sign-in`,
 * `/_next` and the rest. A negative matcher silently starts gating any new
 * public route that does not happen to be in the exclusion list, and the
 * failure mode — a sign-up page that redirects to sign-in — is one nobody finds
 * until a user reports it.
 *
 * Every route inside the `(app)` group belongs here. A feature step adding one
 * adds it to this list; the layout gate covers it regardless, so forgetting
 * costs the correct status code rather than the protection itself.
 */
export const config = {
  matcher: [
    "/dashboard/:path*",
    "/projects/:path*",
    "/chat/:path*",
    "/settings/:path*",
    // Not an application route and deliberately *not* session-gated — the
    // inspector must render signed out, since "why am I signed out" is one of
    // the questions it exists to answer. It is matched here only so the
    // production refusal above can run before rendering.
    "/dev/:path*",
  ],
};
