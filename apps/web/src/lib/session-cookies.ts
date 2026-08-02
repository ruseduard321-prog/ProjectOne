/**
 * The names and lifetimes of the session cookies.
 *
 * Separated from `session.ts` because the proxy needs them and runs in the Edge
 * runtime, where `next/headers` is unavailable. Three modules now read or write
 * these cookies — the session layer, the proxy and the expiry Route Handler —
 * and they must agree on the names. The way that agreement breaks is a string
 * literal typed more than once.
 *
 * The reasoning behind cookie storage — and why it is not `localStorage` — is
 * documented in `session.ts`.
 */

/** Cookie holding the short-lived access token presented to the API. */
export const ACCESS_TOKEN_COOKIE = "projectone_access_token";

/** Cookie holding the long-lived refresh token used to mint new sessions. */
export const REFRESH_TOKEN_COOKIE = "projectone_refresh_token";

/**
 * How long the refresh cookie survives, in seconds.
 *
 * The access cookie expires with the token itself; this one outlives it
 * deliberately, because a refresh cookie that died alongside the access token
 * could never refresh anything. Thirty days bounds how long a stolen cookie
 * remains useful — a session that never expires is a credential with no end.
 */
export const REFRESH_MAX_AGE_SECONDS = 60 * 60 * 24 * 30;
