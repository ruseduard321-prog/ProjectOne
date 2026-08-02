"use server";

/**
 * Server Actions backing the authentication forms.
 *
 * A Server Action rather than a client `fetch` for the reason the whole session
 * design rests on: the credential never enters client JavaScript, and the
 * resulting httpOnly cookie is written by the server that received the token.
 * A client-side sign-in could not write that cookie, and would have to keep the
 * token somewhere script can read — which is the outcome `session.ts` exists to
 * avoid.
 *
 * Every action returns a {@link FormState} rather than throwing. A thrown error
 * in an action surfaces as the generic error boundary, which is the wrong
 * treatment for "your password was incorrect".
 *
 * **Only async functions are exported from this module.** Next.js enforces it —
 * every export of a `"use server"` file becomes a remotely-callable endpoint, so
 * a constant exported here fails the build. `FormState` and its empty value live
 * in `lib/form-state.ts` for that reason.
 */

import { redirect } from "next/navigation";

import { ApiError, ApiUnreachableError, signIn, signOut, signUp } from "@/lib/api";
import { resolveAccessToken } from "@/lib/auth";
import { hasErrors, validateSignIn, validateSignUp } from "@/lib/credentials";
import type { FormState } from "@/lib/form-state";
import { POST_SIGN_IN_PATH, SIGN_IN_PATH } from "@/lib/routes";
import { clearSession, writeSession } from "@/lib/session";

/** Read a required text field from submitted form data. */
function field(data: FormData, name: string): string {
  const value = data.get(name);

  return typeof value === "string" ? value : "";
}

/**
 * Render a thrown API failure into form state.
 *
 * The API's `detail` is shown verbatim — its error contract already guarantees
 * these messages are safe to display, and rewriting them client-side is how a
 * deliberately generic sign-up rejection becomes an enumeration oracle.
 *
 * A 429 is special-cased because the envelope's message alone does not tell a
 * user what to do about it. Anything else keeps the server's wording.
 */
function toFormState(error: unknown): FormState {
  if (error instanceof ApiError) {
    if (error.status === 429) {
      return {
        fieldErrors: {},
        formError: "Too many attempts. Wait a minute and try again.",
        requestId: error.requestId,
      };
    }

    return { fieldErrors: {}, formError: error.message, requestId: error.requestId };
  }

  if (error instanceof ApiUnreachableError) {
    return { fieldErrors: {}, formError: error.message };
  }

  throw error;
}

/**
 * Register an account and sign the new user in.
 *
 * When the Supabase project requires email confirmation no session is issued,
 * which is a normal outcome rather than a failure — the form says so and stays
 * put instead of redirecting into a shell the user cannot yet reach.
 */
export async function signUpAction(_previous: FormState, data: FormData): Promise<FormState> {
  const email = field(data, "email");
  const password = field(data, "password");

  const fieldErrors = validateSignUp(email, password);

  if (hasErrors(fieldErrors)) {
    return { fieldErrors };
  }

  let result;

  try {
    result = await signUp(email, password);
  } catch (error) {
    return toFormState(error);
  }

  if (result.session === null) {
    return { fieldErrors: {}, confirmationRequired: true };
  }

  await writeSession(
    {
      accessToken: result.session.access_token,
      refreshToken: result.session.refresh_token,
    },
    result.session.expires_in,
  );

  // Outside the try: `redirect` works by throwing, so catching around it would
  // swallow the navigation and render the error branch on a successful sign-up.
  redirect(POST_SIGN_IN_PATH);
}

/** Exchange credentials for a session and enter the application. */
export async function signInAction(_previous: FormState, data: FormData): Promise<FormState> {
  const email = field(data, "email");
  const password = field(data, "password");

  const fieldErrors = validateSignIn(email, password);

  if (hasErrors(fieldErrors)) {
    return { fieldErrors };
  }

  let session;

  try {
    session = await signIn(email, password);
  } catch (error) {
    return toFormState(error);
  }

  await writeSession(
    { accessToken: session.access_token, refreshToken: session.refresh_token },
    session.expires_in,
  );

  redirect(POST_SIGN_IN_PATH);
}

/**
 * Revoke the session upstream, then discard it locally.
 *
 * The order matters and the upstream call is not optional: deleting the cookies
 * alone leaves the access token valid until it expires, so a copy taken before
 * sign-out would still work. That is not what signing out means.
 *
 * The local session is cleared even when revocation fails. A user who clicked
 * sign out must end up signed out of *this* browser regardless of whether the
 * identity provider was reachable — leaving them holding a live cookie because
 * an upstream call failed is the worse of the two outcomes.
 */
export async function signOutAction(): Promise<void> {
  const accessToken = await resolveAccessToken();

  if (accessToken !== undefined) {
    try {
      await signOut(accessToken);
    } catch {
      // Swallowed deliberately — see above. Not logged: the token is the one
      // value that must never reach a log (CLAUDE.md §16).
    }
  }

  await clearSession();

  redirect(SIGN_IN_PATH);
}
