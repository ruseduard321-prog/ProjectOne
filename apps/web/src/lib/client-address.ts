/**
 * Reading the browser's address, to forward to the API.
 *
 * **Server-only**, like everything that touches `next/headers`.
 *
 * ## Why this exists
 *
 * Every browser call reaches the API through this process (STEP-16), so the
 * peer address the API observes is *this server's*, not the user's. Public
 * endpoints — sign-in, sign-up, refresh — can only be limited by network
 * address, so without forwarding, the whole platform shares one bucket and ten
 * sign-in attempts lock every user out (ADR-002).
 *
 * ## What makes this safe
 *
 * This process is the **first trusted hop**. The value it forwards is *set*,
 * never appended to, and any `X-Forwarded-For` a browser sent is discarded here
 * rather than carried onward — appending would splice an attacker-chosen entry
 * into a chain the API is about to trust, which is the exact failure the API's
 * allowlist exists to prevent.
 *
 * The address itself is read from the platform's own headers. Those are set by
 * whatever sits in front of *this* server (Vercel, a load balancer, an ingress),
 * so they carry the same trust question one layer up — see `PLATFORM_HEADERS`.
 */

import { headers } from "next/headers";

/**
 * Headers a hosting platform sets to identify the browser, most specific first.
 *
 * `x-real-ip` is checked before `x-forwarded-for` deliberately: platforms that
 * set it write a single address they resolved themselves, whereas
 * `x-forwarded-for` is a chain whose leftmost entry may have come from the
 * client. When only the chain is available, the leftmost entry is what the
 * platform received — trusted here **only** because a platform that terminates
 * TLS in front of this process is inside the deployment's trust boundary, the
 * same assumption every Next.js deployment already makes to know its own
 * hostname.
 *
 * If ProjectOne is ever deployed with nothing in front of it, none of these are
 * present and this returns undefined — which is correct: there is no proxy, so
 * the API sees the real peer and needs no forwarding.
 */
const PLATFORM_HEADERS = ["x-real-ip", "x-forwarded-for"] as const;

/**
 * Return the browser's address, or undefined when it cannot be determined.
 *
 * Undefined is a normal outcome, not an error: it means no platform header was
 * present, so there is nothing to forward and the API's own fallback (limit by
 * peer address) is already correct. Fabricating a value here would be worse
 * than sending none.
 */
export async function readClientAddress(): Promise<string | undefined> {
  const incoming = await headers();

  for (const name of PLATFORM_HEADERS) {
    const value = incoming.get(name);

    if (value === null) {
      continue;
    }

    // A chain arrives leftmost-first; a single address is the same expression
    // with one entry, so both shapes are handled by taking the head.
    const first = value.split(",")[0]?.trim();

    if (first !== undefined && first.length > 0) {
      return first;
    }
  }

  return undefined;
}
