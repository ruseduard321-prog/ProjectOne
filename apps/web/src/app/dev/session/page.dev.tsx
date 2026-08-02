/**
 * `/dev/session` — the developer session inspector.
 *
 * **Development only.** See `lib/dev-only.ts` for the two mechanisms that keep
 * this out of production, and why the exclusion is the feature rather than a
 * detail of it.
 *
 * ## Why this page exists
 *
 * STEP-16 moved the entire session into httpOnly cookies written server-side.
 * That is the correct security posture and it has a deliberate consequence:
 * **the running session became invisible to the developer building against
 * it.** The browser cannot read the cookies, DevTools shows opaque values, and
 * every API call happens server-side where no network tab observes it.
 *
 * Three of STEP-16's defects were each found by running the flow and reasoning
 * backwards from a symptom. A page that simply states the session's condition
 * would have shortened all three.
 *
 * ## What it will not show
 *
 * No token value, no cookie value, no API key, no password, no connection
 * string — not even a prefix, since a truncated JWT still leaks its header and
 * part of its payload. Presence, expiry and identity are computed; the secrets
 * that produced them are discarded (CLAUDE.md §16).
 *
 * ## What it will not do
 *
 * It observes. It never refreshes, revokes, or repairs a session, and it never
 * deletes a cookie — including one it discovers is dead. That last restraint is
 * exactly the STEP-16 defect that stranded users forever: the place that
 * discovers a credential is dead is not always a place permitted to delete it.
 */

import { headers } from "next/headers";

import { ApiError, ApiUnreachableError, apiRequest, readProfile } from "@/lib/api";
import { notFoundInProduction } from "@/lib/dev-only";
import {
  INSPECTED_HEADERS,
  SESSION_COOKIE_NAMES,
  describeRateLimitIdentity,
  describeToken,
} from "@/lib/dev-session";
import { readAccessToken, readRefreshToken } from "@/lib/session";

/**
 * Never prerendered, and never cached.
 *
 * A static literal because Next.js parses this at compile time and rejects any
 * indirection — an imported constant fails the build outright, which is how
 * this was discovered rather than assumed.
 *
 * Load-bearing for the exclusion: without it the route could be answered from
 * a prerendered artifact, meaning session state baked into a build and the
 * runtime production check never running at all.
 */
export const dynamic = "force-dynamic";

/** The API's `/health` payload — a readiness check, not a liveness ping. */
interface HealthPayload {
  readonly status: string;
  readonly service: string;
  readonly version: string;
  readonly environment: string;
  readonly dependencies: readonly { readonly name: string; readonly healthy: boolean }[];
}

/** What the API reported, or why it could not be reached. */
interface HealthResult {
  readonly payload?: HealthPayload;
  readonly error?: string;
}

async function readHealth(): Promise<HealthResult> {
  try {
    // `/health` is mounted unversioned, deliberately — it is infrastructure
    // rather than product surface (API Conventions). It already reports real
    // database connectivity, which is why this page adds no endpoint of its
    // own: new production surface for a development page is a bad trade.
    return { payload: await apiRequest<HealthPayload>({ path: "/health", method: "GET" }) };
  } catch (error) {
    if (error instanceof ApiUnreachableError) {
      return { error: "Unreachable — the API did not answer." };
    }

    if (error instanceof ApiError) {
      // A 503 is a *successful* diagnostic: the API answered and told us a
      // dependency is down. Reporting it as an error would hide the answer.
      return { error: `Answered ${String(error.status)}: ${error.message}` };
    }

    return { error: "Unknown failure." };
  }
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-1 border-b border-border py-3 sm:grid-cols-[16rem_1fr] sm:gap-4">
      <dt className="text-sm font-medium text-text-muted">{label}</dt>
      <dd className="text-sm break-words text-text">{value}</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="mb-2 text-lg font-semibold text-text">{title}</h2>
      <dl className="rounded-lg border border-border bg-surface px-4">{children}</dl>
    </section>
  );
}

function Absent({ children }: { children: React.ReactNode }) {
  return <span className="text-text-muted italic">{children}</span>;
}

export default async function DevSessionPage() {
  // Second line of defence, before any work. The proxy already refused this
  // request with a real 404 in production; this ensures a page reached some
  // other way still never reads a session or calls the API.
  await notFoundInProduction();

  const [accessToken, refreshToken, requestHeaders, health] = await Promise.all([
    readAccessToken(),
    readRefreshToken(),
    headers(),
    readHealth(),
  ]);

  const access = describeToken(accessToken);
  const refresh = describeToken(refreshToken);

  let profile: Awaited<ReturnType<typeof readProfile>> | undefined;
  let profileError: string | undefined;

  if (accessToken !== undefined) {
    try {
      profile = await readProfile(accessToken);
    } catch (error) {
      profileError =
        error instanceof ApiError
          ? `${String(error.status)} — ${error.message}`
          : "The API could not be reached.";
    }
  }

  const signedIn = profile !== undefined;
  const authStatus = signedIn
    ? "Signed in — verified by GET /auth/me"
    : accessToken === undefined && refreshToken === undefined
      ? "Signed out — no session cookies present"
      : access.expired === true
        ? "Session expired — the access token's exp has passed"
        : "Cookies present, but /auth/me did not confirm the session";

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-text">Session Inspector</h1>
        <p className="mt-2 text-sm text-text-muted">
          Development only. This page is absent from a production build and returns 404 if one
          somehow includes it. It shows no token, cookie or key values — only facts derived from
          them.
        </p>
      </header>

      <Section title="Authentication">
        <Row label="Status" value={authStatus} />
        <Row
          label="User ID"
          value={profile?.id ?? <Absent>Not signed in</Absent>}
        />
        <Row label="Email" value={profile?.email ?? <Absent>Not signed in</Absent>} />
        <Row
          label="Display name"
          value={profile?.display_name ?? <Absent>Not set</Absent>}
        />
        {profileError !== undefined && <Row label="/auth/me said" value={profileError} />}
      </Section>

      <Section title="Tokens">
        <Row label="Access token present" value={access.present ? "Yes" : "No"} />
        <Row
          label="Access token expires"
          value={
            access.expiresAt !== undefined ? (
              <>
                {access.expiresAt}{" "}
                <span className="text-text-muted">
                  ({access.expiresInSeconds ?? 0}s
                  {access.expired === true ? ", expired" : " remaining"})
                </span>
              </>
            ) : (
              <Absent>{access.note ?? "No token"}</Absent>
            )
          }
        />
        <Row label="Refresh token present" value={refresh.present ? "Yes" : "No"} />
        <Row
          label="Refresh token expires"
          value={
            refresh.expiresAt ?? (
              <Absent>
                {refresh.note ??
                  "Not exposed — Supabase refresh tokens are opaque, so no expiry is readable here."}
              </Absent>
            )
          }
        />
        <Row
          label="Session ID"
          value={
            access.sessionId ?? (
              <Absent>Not present — the access token carries no `sid` claim.</Absent>
            )
          }
        />
      </Section>

      <Section title="Cookies">
        {SESSION_COOKIE_NAMES.map((name) => (
          <Row
            key={name}
            label={name}
            value={
              (name === SESSION_COOKIE_NAMES[0] ? access.present : refresh.present)
                ? "Present (httpOnly — value never read or shown)"
                : "Absent"
            }
          />
        ))}
      </Section>

      <Section title="Rate limit identity">
        <Row label="This request counts against" value={describeRateLimitIdentity(signedIn, profile?.id)} />
        <Row
          label="How the address is resolved"
          value="X-Forwarded-For is honoured only from a peer in the API's trusted allowlist, walked right-to-left. See ADR-002."
        />
      </Section>

      <Section title="Proxy headers received by Next.js">
        <Row
          label="Note"
          value="What THIS server received. The API resolves the client address from its own view of the chain, which may differ."
        />
        {INSPECTED_HEADERS.map((name) => (
          <Row
            key={name}
            label={name}
            value={requestHeaders.get(name) ?? <Absent>Not sent</Absent>}
          />
        ))}
      </Section>

      <Section title="API and database">
        {health.payload !== undefined ? (
          <>
            <Row label="API status" value={health.payload.status} />
            <Row label="Service" value={`${health.payload.service} v${health.payload.version}`} />
            <Row label="API environment" value={health.payload.environment} />
            {health.payload.dependencies.length > 0 ? (
              health.payload.dependencies.map((dependency) => (
                <Row
                  key={dependency.name}
                  label={`Dependency: ${dependency.name}`}
                  value={dependency.healthy ? "Healthy" : "Unreachable"}
                />
              ))
            ) : (
              <Row label="Dependencies" value={<Absent>None reported</Absent>} />
            )}
          </>
        ) : (
          <Row label="API status" value={health.error ?? "Unknown"} />
        )}
      </Section>
    </main>
  );
}
