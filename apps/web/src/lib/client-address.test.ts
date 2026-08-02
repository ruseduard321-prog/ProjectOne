import { afterEach, describe, expect, it, vi } from "vitest";

import { readClientAddress } from "@/lib/client-address";

/**
 * `readClientAddress` reads `next/headers`, which only resolves inside a
 * request scope. Mocking it is what lets the header-selection rules be tested
 * as the pure decision they are.
 */
function withHeaders(entries: Record<string, string>): void {
  vi.doMock("next/headers", () => ({
    headers: async () =>
      Promise.resolve({
        get: (name: string) => entries[name.toLowerCase()] ?? null,
      }),
  }));
}

/** Re-import after mocking, so the mock is in place when the module resolves. */
async function readWith(entries: Record<string, string>): Promise<string | undefined> {
  vi.resetModules();
  withHeaders(entries);

  const loaded = await import("@/lib/client-address");

  return loaded.readClientAddress();
}

afterEach(() => {
  vi.resetModules();
  vi.doUnmock("next/headers");
});

describe("readClientAddress", () => {
  it("prefers x-real-ip, which platforms set as a single resolved address", async () => {
    await expect(
      readWith({ "x-real-ip": "203.0.113.5", "x-forwarded-for": "198.51.100.9" }),
    ).resolves.toBe("203.0.113.5");
  });

  it("falls back to x-forwarded-for when x-real-ip is absent", async () => {
    await expect(readWith({ "x-forwarded-for": "203.0.113.5" })).resolves.toBe("203.0.113.5");
  });

  it("takes the leftmost entry of a forwarded chain", async () => {
    // Leftmost is correct *here* and wrong in the API. The asymmetry is the
    // point: this process reads what the platform in front of it recorded,
    // where the head is the original client. The API reads a chain that may
    // include a client-supplied prefix, so it walks from the right.
    await expect(
      readWith({ "x-forwarded-for": "203.0.113.5, 10.0.0.1, 10.0.0.2" }),
    ).resolves.toBe("203.0.113.5");
  });

  it("trims surrounding whitespace", async () => {
    await expect(readWith({ "x-forwarded-for": "  203.0.113.5  , 10.0.0.1" })).resolves.toBe(
      "203.0.113.5",
    );
  });

  it("returns undefined when no platform header is present", async () => {
    // Correct rather than a failure: nothing sits in front of this process, so
    // the API sees the real peer and needs no forwarding. Fabricating a value
    // would be worse than sending none.
    await expect(readWith({})).resolves.toBeUndefined();
  });

  it("skips an empty header value rather than forwarding a blank address", async () => {
    await expect(readWith({ "x-real-ip": "", "x-forwarded-for": "203.0.113.5" })).resolves.toBe(
      "203.0.113.5",
    );
  });

  it("returns undefined when every candidate header is blank", async () => {
    await expect(readWith({ "x-real-ip": "", "x-forwarded-for": "  " })).resolves.toBeUndefined();
  });
});

describe("readClientAddress export", () => {
  it("is a function", () => {
    // Guards the import path itself: the actions module calls this by name, and
    // a rename would otherwise only surface at runtime in a Server Action.
    expect(typeof readClientAddress).toBe("function");
  });
});
