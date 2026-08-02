import { describe, expect, it } from "vitest";

import { describeRateLimitIdentity, describeToken } from "@/lib/dev-session";

/**
 * Facts derived from a token, without revealing any of it.
 *
 * The central property under test is negative: whatever these functions
 * return, **no part of the token appears in it**. A truncated JWT still leaks
 * its header and part of its payload, so "shows only a prefix" is not a
 * mitigation.
 */
function makeJwt(claims: Record<string, unknown>, signature = "SIGNATURE-MUST-NOT-LEAK"): string {
  const header = Buffer.from(JSON.stringify({ alg: "ES256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(JSON.stringify(claims)).toString("base64url");

  return `${header}.${payload}.${signature}`;
}

const NOW = new Date("2026-08-03T12:00:00.000Z");

describe("describeToken", () => {
  it("reports absence when there is no token", () => {
    expect(describeToken(undefined)).toEqual({ present: false });
  });

  it("computes the expiry and a countdown from the exp claim", () => {
    const token = makeJwt({ exp: Math.floor(NOW.getTime() / 1000) + 1800 });
    const facts = describeToken(token, NOW);

    expect(facts.present).toBe(true);
    expect(facts.expiresAt).toBe("2026-08-03T12:30:00.000Z");
    expect(facts.expiresInSeconds).toBe(1800);
    expect(facts.expired).toBe(false);
  });

  it("reports an already-expired token as expired", () => {
    const token = makeJwt({ exp: Math.floor(NOW.getTime() / 1000) - 60 });
    const facts = describeToken(token, NOW);

    expect(facts.expired).toBe(true);
    expect(facts.expiresInSeconds).toBe(-60);
  });

  it("surfaces the session id when the issuer supplies one", () => {
    const token = makeJwt({ exp: Math.floor(NOW.getTime() / 1000) + 60, sid: "session-abc" });

    expect(describeToken(token, NOW).sessionId).toBe("session-abc");
  });

  it("says so plainly when a token carries no exp", () => {
    // Better than inferring a value that was never in the token.
    const facts = describeToken(makeJwt({ sub: "user" }), NOW);

    expect(facts.present).toBe(true);
    expect(facts.expiresAt).toBeUndefined();
    expect(facts.note).toContain("no `exp`");
  });

  it("treats an opaque token as opaque rather than as an error", () => {
    // Supabase refresh tokens are opaque strings, not JWTs. Reporting "not
    // exposed" is honest; inventing an expiry would not be.
    const facts = describeToken("an-opaque-refresh-token", NOW);

    expect(facts.present).toBe(true);
    expect(facts.expiresAt).toBeUndefined();
    expect(facts.note).toContain("Opaque");
  });

  it("does not throw on a malformed payload", () => {
    expect(() => describeToken("aaa.!!!not-base64!!!.ccc", NOW)).not.toThrow();
    expect(describeToken("aaa.!!!not-base64!!!.ccc", NOW).present).toBe(true);
  });

  it("never returns any part of the token", () => {
    // The assertion this whole module exists to satisfy.
    const signature = "SIGNATURE-MUST-NOT-LEAK";
    const token = makeJwt({ exp: Math.floor(NOW.getTime() / 1000) + 60, sub: "user" }, signature);
    const serialized = JSON.stringify(describeToken(token, NOW));

    expect(serialized).not.toContain(signature);
    expect(serialized).not.toContain(token);
    // The header and payload segments individually, not just the whole token —
    // a partial leak is still a leak.
    for (const segment of token.split(".")) {
      expect(serialized).not.toContain(segment);
    }
  });
});

describe("describeRateLimitIdentity", () => {
  it("names the user bucket for an authenticated caller", () => {
    const described = describeRateLimitIdentity(true, "user-123");

    expect(described).toContain("user:user-123");
  });

  it("names the address bucket for an anonymous caller", () => {
    const described = describeRateLimitIdentity(false);

    expect(described).toContain("ip:");
    expect(described).toContain("trusted proxies");
  });

  it("falls back to the address bucket when no user id is known", () => {
    // Signed in but without an id is a contradiction; the safer description
    // wins rather than rendering `user:undefined`.
    expect(describeRateLimitIdentity(true)).toContain("ip:");
  });
});
