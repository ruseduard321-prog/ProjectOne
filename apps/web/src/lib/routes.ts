/**
 * Well-known application routes.
 *
 * Plain string constants with no imports, so they are usable from every runtime
 * the application has: Server Components, Server Actions, Client Components and
 * the Edge proxy. `auth.ts` cannot serve this purpose — it reaches the cookie
 * store through `next/headers`, which the Edge runtime does not provide.
 */

/** Where an unauthenticated visitor is sent. */
export const SIGN_IN_PATH = "/sign-in";

/** Where a signed-in user lands. */
export const POST_SIGN_IN_PATH = "/dashboard";

/**
 * Route Handler that clears an unusable session, then redirects to sign-in.
 *
 * A render cannot delete a cookie, so the gate sends a request carrying a
 * rejected session here rather than straight to sign-in — see
 * `app/session/expired/route.ts`.
 */
export const SESSION_EXPIRED_PATH = "/session/expired";
