/**
 * Session storage for the web application.
 *
 * ## The decision this module encodes
 *
 * Tokens are held in **httpOnly cookies written by the server**, never in
 * `localStorage`, `sessionStorage`, or any JavaScript-reachable place.
 *
 * The alternative — storing the access token in `localStorage` and attaching it
 * to browser fetches — was rejected. `localStorage` is readable by any script
 * running on the origin, so a single XSS anywhere in the application exfiltrates
 * a live session, and a refresh token stolen that way outlives the access token
 * it came with. An httpOnly cookie is not reachable by script at all: the same
 * XSS can still *act* as the user while the page is open, but it cannot walk
 * away with the credential.
 *
 * Two consequences follow, and both are deliberate:
 *
 *  1. **Every API call is made server-side.** The browser cannot read the token,
 *     so it cannot attach it. Requests go browser → Next.js Route Handler or
 *     Server Component → API. This also sidesteps CORS entirely, which matters
 *     because the API registers no CORS middleware.
 *  2. **`sameSite: "lax"` is the CSRF control.** The cookie is not sent on
 *     cross-site POSTs, so a third-party form cannot drive an authenticated
 *     state change. `lax` rather than `strict` so that following a link into the
 *     application from elsewhere does not appear as a signed-out session.
 *
 * Checked against [[Authentication and Authorization]] before implementing: that
 * document requires "session management and token security" and specifies no
 * mechanism, so this choice extends it rather than diverging from it
 * (CLAUDE.md §33–34).
 */

import { cookies } from "next/headers";

import {
  ACCESS_TOKEN_COOKIE,
  REFRESH_MAX_AGE_SECONDS,
  REFRESH_TOKEN_COOKIE,
} from "@/lib/session-cookies";

/** A session as this application stores it. */
export interface StoredSession {
  readonly accessToken: string;
  readonly refreshToken: string;
}

/**
 * Cookie attributes shared by both tokens.
 *
 * `secure` is conditional on the environment for one reason: a `secure` cookie
 * is silently dropped over plain HTTP, which would make local development
 * appear to sign in and then immediately forget. It is unconditional anywhere
 * that is not local development.
 */
function cookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge,
  };
}

/**
 * Whether a cookie write succeeded.
 *
 * Next.js permits cookie mutation **only** in a Server Action or Route Handler.
 * A Server Component rendering a page may read cookies but not write them, and
 * attempting it throws.
 *
 * That constraint is load-bearing here, because the session layer legitimately
 * wants to write from both contexts: an action signing a user in, and a layout
 * discovering mid-render that a refresh token is spent. The second is a render,
 * so it cannot write — and the throw is not catchable at a useful distance: it
 * aborts the render, which kills the `redirect()` that was about to send the
 * user to sign-in and leaves them on a loading skeleton forever.
 *
 * Observed exactly that way during STEP-16 validation, with a stale cookie:
 * `Cookies can only be modified in a Server Action or Route Handler`, thrown
 * from `clearSession`, producing an endless "Loading…" instead of a redirect.
 *
 * So the write is attempted and its failure reported rather than propagated.
 * A caller that could not clear the cookie still knows the session is unusable
 * and redirects; the stale cookie is cleared by `app/session/expired/route.ts`,
 * a Route Handler, which runs in a context that *may* write.
 */
type WriteOutcome = "written" | "read-only-context";

/**
 * Persist a session, replacing whatever was there.
 *
 * The access cookie's lifetime tracks the token's own `expires_in`, so a stale
 * cookie is never presented to the API — the absence of the cookie is what
 * triggers a refresh, and a cookie that outlived its token would instead
 * produce a 401 on a route that could have recovered silently.
 */
export async function writeSession(
  session: StoredSession,
  accessTokenLifetimeSeconds: number,
): Promise<WriteOutcome> {
  const store = await cookies();

  try {
    store.set(
      ACCESS_TOKEN_COOKIE,
      session.accessToken,
      cookieOptions(accessTokenLifetimeSeconds),
    );
    store.set(
      REFRESH_TOKEN_COOKIE,
      session.refreshToken,
      cookieOptions(REFRESH_MAX_AGE_SECONDS),
    );
  } catch {
    return "read-only-context";
  }

  return "written";
}

/**
 * Discard the local session. Does not revoke anything upstream.
 *
 * Returns rather than throws when called during a render — see
 * {@link WriteOutcome}. The caller's decision does not depend on the cookie
 * actually being gone: a session it just found unusable is unusable either way.
 */
export async function clearSession(): Promise<WriteOutcome> {
  const store = await cookies();

  try {
    store.delete(ACCESS_TOKEN_COOKIE);
    store.delete(REFRESH_TOKEN_COOKIE);
  } catch {
    return "read-only-context";
  }

  return "written";
}

/** The access token, if one is present and unexpired. */
export async function readAccessToken(): Promise<string | undefined> {
  const store = await cookies();

  return store.get(ACCESS_TOKEN_COOKIE)?.value;
}

/** The refresh token, if one is present. */
export async function readRefreshToken(): Promise<string | undefined> {
  const store = await cookies();

  return store.get(REFRESH_TOKEN_COOKIE)?.value;
}
