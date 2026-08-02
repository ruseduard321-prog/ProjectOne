/**
 * Facts about the running session, for the developer inspection page.
 *
 * **Server-only, and development-only.** Nothing here may be imported from a
 * production code path — see `app/dev/session/page.tsx` for the two mechanisms
 * that keep the page itself out of a production build.
 *
 * ## What this module will not do
 *
 * It reports **derived facts, never secret material**. No token value, no
 * cookie value, no prefix and no truncation — a truncated token is still token
 * material, and a page that shows the first eight characters of a JWT has
 * leaked the header and part of the payload for no diagnostic gain
 * (CLAUDE.md §16).
 *
 * Where a value's presence matters, presence is what it reports. Where an
 * expiry matters, the expiry is computed and the token discarded.
 *
 * ## Why the JWT is decoded rather than verified
 *
 * This is a diagnostic view of what the *browser is holding*, not an
 * authentication decision. The API verifies signatures against Supabase's JWKS
 * (`app/services/token_service.py`) and is the only thing entitled to say a
 * token is valid. Verifying here would duplicate that logic into a second
 * place, and a second place is where the two answers drift apart.
 *
 * So: decoded for display, never trusted. `GET /auth/me` is what actually
 * proves the session works, and this page calls it.
 */

import { ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE } from "@/lib/session-cookies";

/** Claims this page reads, when a token carries them. */
interface TokenClaims {
  readonly exp?: number;
  readonly iat?: number;
  readonly sid?: string;
  readonly sub?: string;
}

/** What can be said about a token without revealing any of it. */
export interface TokenFacts {
  /** Whether a token was present at all. */
  readonly present: boolean;
  /** Expiry as an ISO instant, or undefined when the token carries no `exp`. */
  readonly expiresAt?: string;
  /** Seconds until expiry; negative when already expired. */
  readonly expiresInSeconds?: number;
  /** Whether the expiry has already passed. */
  readonly expired?: boolean;
  /** Session identifier from the `sid` claim, when the issuer supplies one. */
  readonly sessionId?: string;
  /** Why no expiry could be reported, when none could. */
  readonly note?: string;
}

/**
 * Decode a JWT payload without verifying it.
 *
 * Returns undefined for anything that is not a readable JWT — including an
 * opaque token, which is a normal outcome rather than an error. Supabase
 * refresh tokens are opaque strings, not JWTs, and reporting "not exposed" for
 * one is more honest than inferring an expiry that was never in the token.
 */
function decodeClaims(token: string): TokenClaims | undefined {
  const segments = token.split(".");

  if (segments.length !== 3) {
    return undefined;
  }

  const payload = segments[1];

  if (payload === undefined) {
    return undefined;
  }

  try {
    // base64url → base64. `Buffer` is available because this only ever runs on
    // the server; the page importing it is a Server Component.
    const normalized = payload.replaceAll("-", "+").replaceAll("_", "/");
    const decoded = Buffer.from(normalized, "base64").toString("utf8");
    const parsed: unknown = JSON.parse(decoded);

    if (typeof parsed !== "object" || parsed === null) {
      return undefined;
    }

    return parsed as TokenClaims;
  } catch {
    return undefined;
  }
}

/**
 * Describe a token without revealing it.
 *
 * @param token The raw token, used only to compute the facts below and never
 *   returned in any form.
 * @param now Reference instant, injectable so the countdown is testable.
 */
export function describeToken(token: string | undefined, now: Date = new Date()): TokenFacts {
  if (token === undefined) {
    return { present: false };
  }

  const claims = decodeClaims(token);

  if (claims === undefined) {
    return {
      present: true,
      note: "Opaque token — not a JWT, so no expiry is exposed in the token itself.",
    };
  }

  const sessionId = typeof claims.sid === "string" ? claims.sid : undefined;

  if (typeof claims.exp !== "number") {
    return {
      present: true,
      sessionId,
      note: "Token carries no `exp` claim.",
    };
  }

  const expiresAt = new Date(claims.exp * 1000);
  const expiresInSeconds = Math.round((expiresAt.getTime() - now.getTime()) / 1000);

  return {
    present: true,
    expiresAt: expiresAt.toISOString(),
    expiresInSeconds,
    expired: expiresInSeconds <= 0,
    sessionId,
  };
}

/** Header names this page reports on, all of them proxy-related. */
export const INSPECTED_HEADERS = [
  "x-forwarded-for",
  "x-real-ip",
  "x-forwarded-host",
  "x-forwarded-proto",
  "cf-connecting-ip",
  "host",
] as const;

/** Cookie names the session layer owns. Values are never read. */
export const SESSION_COOKIE_NAMES = [ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE] as const;

/**
 * Describe which rate limit bucket this request would land in.
 *
 * A *description* of the scheme, not a reconstruction of the API's key. The API
 * owns that decision (`app/core/client_address.py`), and a client-side
 * recomputation that drifts from it would be worse than no panel at all —
 * it would state confidently what the API is doing while being wrong.
 */
export function describeRateLimitIdentity(signedIn: boolean, userId?: string): string {
  if (signedIn && userId !== undefined) {
    return `user:${userId} — authenticated routes are limited per verified user (ADR-002 §1)`;
  }

  return "ip:<resolved client address> — public routes are limited per client address, resolved from trusted proxies only";
}
