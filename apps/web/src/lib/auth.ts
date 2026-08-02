/**
 * Session resolution for the authenticated application.
 *
 * Sits between the cookie store (`session.ts`) and the API client (`api.ts`),
 * and owns the one piece of logic neither of them can: what to do when the
 * access token has expired but the refresh token has not.
 *
 * Server-only by construction — everything here reaches the cookie store
 * through `next/headers`, which Next.js refuses to bundle into client code.
 */

import { redirect } from "next/navigation";

import { ApiError, type ApiProfile, readProfile, refreshSession } from "@/lib/api";
import { readClientAddress } from "@/lib/client-address";
import { SESSION_EXPIRED_PATH, SIGN_IN_PATH } from "@/lib/routes";
import { clearSession, readAccessToken, readRefreshToken, writeSession } from "@/lib/session";

/**
 * Return a usable access token, refreshing it if the current one has expired.
 *
 * The access cookie's lifetime tracks the token's own, so its *absence* — with
 * a refresh cookie still present — is the signal that a refresh is due. That is
 * why the refresh path is reached without ever calling the API and being
 * rejected: a user whose token expired mid-session continues silently rather
 * than being bounced to sign-in (STEP-16 task 6).
 *
 * @returns The token, or `undefined` when there is no recoverable session.
 */
export async function resolveAccessToken(): Promise<string | undefined> {
  const accessToken = await readAccessToken();

  if (accessToken !== undefined) {
    return accessToken;
  }

  const refreshToken = await readRefreshToken();

  if (refreshToken === undefined) {
    return undefined;
  }

  try {
    const session = await refreshSession(refreshToken, await readClientAddress());

    await writeSession(
      { accessToken: session.access_token, refreshToken: session.refresh_token },
      session.expires_in,
    );

    return session.access_token;
  } catch {
    // A refresh token the provider will not honour is spent: it has been
    // revoked, rotated, or has expired. Clearing it here stops every subsequent
    // request retrying a credential that is never going to work again.
    await clearSession();

    return undefined;
  }
}

/**
 * The signed-in user's profile, or `undefined` when there is no session.
 *
 * Does not redirect — callers that must have a user use {@link requireProfile}.
 * This exists for the surfaces that render differently when signed out rather
 * than refusing outright.
 */
export async function currentProfile(): Promise<ApiProfile | undefined> {
  const accessToken = await resolveAccessToken();

  if (accessToken === undefined) {
    return undefined;
  }

  try {
    return await readProfile(accessToken);
  } catch (error) {
    // A 401 here means the token was rejected despite being unexpired — revoked
    // upstream, most likely by a sign-out on another device. That is a real
    // signed-out state, so the local cookies must go with it.
    if (error instanceof ApiError && error.status === 401) {
      await clearSession();

      return undefined;
    }

    throw error;
  }
}

/**
 * The signed-in user's profile, refusing the request when there is none.
 *
 * **This is the authentication gate**, and it runs on the server. A client-side
 * redirect is a convenience for the user, never the control: the markup and any
 * data it embedded would already have been sent before the redirect ran
 * ([[Chapter 05 - NextJS Architecture]] §5.10).
 *
 * The destination depends on whether a cookie was there to begin with, and the
 * distinction is not cosmetic. Reaching here *with* a cookie means the session
 * was presented and rejected — and a render cannot delete the cookie that
 * carried it (`session.ts`). Sending those requests through
 * `/session/expired`, a Route Handler that can, is what stops a dead cookie
 * looping forever: the proxy sees it present, passes the request through, this
 * gate rejects it again, and nothing ever clears it.
 */
export async function requireProfile(): Promise<ApiProfile> {
  const hadCookie =
    (await readAccessToken()) !== undefined || (await readRefreshToken()) !== undefined;

  const profile = await currentProfile();

  if (profile === undefined) {
    redirect(hadCookie ? SESSION_EXPIRED_PATH : SIGN_IN_PATH);
  }

  return profile;
}
