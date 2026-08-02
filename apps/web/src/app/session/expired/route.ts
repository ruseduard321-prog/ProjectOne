import { type NextRequest, NextResponse } from "next/server";

import { SIGN_IN_PATH } from "@/lib/routes";
import { ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE } from "@/lib/session-cookies";

/**
 * Clears a session that turned out to be unusable, then sends the user to
 * sign-in.
 *
 * ## Why a Route Handler exists for this
 *
 * The application layout is where an unusable session is *discovered*: it asks
 * the API who the caller is, and learns there that the refresh token is spent
 * or the access token was revoked. But a layout is a render, and **Next.js
 * forbids writing cookies during a render** — so the one place that knows the
 * cookie is dead is the one place that cannot delete it.
 *
 * Without somewhere to hand that off to, the dead cookie survives every
 * request: the proxy sees a cookie present and lets the request through,
 * the layout re-discovers it is worthless and redirects, and the user loops.
 * Observed during STEP-16 validation as an endless "Loading…" skeleton.
 *
 * A Route Handler may write cookies. So the layout redirects here, this deletes
 * them, and the redirect it returns arrives at sign-in with no session attached
 * — which the proxy then treats as an ordinary signed-out visitor.
 *
 * ## Why this is not an open redirect
 *
 * It takes no parameters and always sends the user to {@link SIGN_IN_PATH}.
 * A `?next=` parameter would be the obvious convenience and is deliberately
 * absent: a redirect target read from the URL is an open redirect unless every
 * caller validates it, and "unless every caller validates it" is not a security
 * control.
 */
export function GET(request: NextRequest): NextResponse {
  // The base comes from the request's own URL, which is why no origin needs
  // configuring. Only the path is ours — `SIGN_IN_PATH` is a constant, so
  // nothing user-supplied reaches the destination.
  const response = NextResponse.redirect(new URL(SIGN_IN_PATH, request.url), 307);

  response.cookies.delete(ACCESS_TOKEN_COOKIE);
  response.cookies.delete(REFRESH_TOKEN_COOKIE);

  return response;
}
