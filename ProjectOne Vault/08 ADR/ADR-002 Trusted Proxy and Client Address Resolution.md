---
title: "ADR-002: Trusted Proxy and Client Address Resolution"
category: ADR
status: accepted
version: "1.1"
last_updated: 2026-08-03
tags: [adr, decision, architecture, security, api, infrastructure]
adr_number: "0002"
---

# ADR-002: Trusted Proxy and Client Address Resolution

## Status

**Accepted** — approved by the project owner on 2026-08-03.

This decision is now binding, and [[STEP-12a Trusted Proxy and Per-User Rate Limiting]] is unblocked ([[CLAUDE|CLAUDE.md]] §7). Changing the trust boundary requires a new ADR that supersedes this one — this note is not amended in place.

## Context

[[STEP-16 Sign Up and Sign In UI]] put a Next.js proxy in front of the API. Every browser call is now browser → Next.js → API, which is what makes an httpOnly cookie the browser cannot read workable at all. It also broke a security control, observed directly during that step's validation:

> With every call proxied through Next.js, the API's rate limiter keys on the web server's address, so it no longer limits per user and one user can lock out others.

`RateLimitMiddleware._client_key()` returns `request.client.host`. Behind the proxy that value is **always the Next.js server**, so every user on the platform shares one bucket on every limited path. The sign-in rule of 10 requests per minute is now a *platform-wide* limit of 10 sign-ins per minute. Any single user triggers it accidentally; any attacker triggers it deliberately, locking out every other user with ten requests. A control intended to stop credential stuffing has become a denial-of-service amplifier.

The naive fix — read `X-Forwarded-For` — is the vulnerability, not the remedy. The existing implementation already says so:

> The peer address, never a header. `X-Forwarded-For` is caller-supplied and trivially spoofed, so counting against it would let an attacker reset their own allowance by changing one header — a rate limiter that the attacker controls.

That reasoning is correct and this ADR does not overturn it. A forwarded header is attacker-controlled **when it arrives from an attacker**. It is trustworthy **when it arrives from a peer we have deliberately decided to trust to have written it.** The decision below is about drawing that line explicitly, because it is currently undrawn and the fix cannot be built without it.

The forces at play:

- **Zero Trust and untrusted external input are binding** ([[CLAUDE|CLAUDE.md]] §16). A header from the internet is input, not fact.
- **Per-user limiting requires identity**, and the only trustworthy identity for an authenticated request is the one the JWT verification already produced. Anything else is a claim the caller made about themselves.
- **Public endpoints have no user.** Sign-in, sign-up, password reset and email confirmation are reachable precisely *because* no credential exists yet, which is what makes them the credential-stuffing targets. They can only be limited by network address.
- **Real deployments have real proxy chains.** Cloudflare, an Nginx or Caddy sidecar, and the Next.js proxy may all sit in the path. A scheme that assumes exactly one hop breaks on contact with production ([[Infrastructure]]).
- **Failing open is unacceptable.** A misconfiguration must degrade to a weaker-but-present limit, never to no limit.

## Decision

### 1. Rate limit identity is resolved by class, and namespaced

Every limited request counts against exactly one key:

| Request class | Key | Source of the identity |
|---|---|---|
| Authenticated | `user:<user_id>` | The validated auth context — the same ES256/JWKS verification the rest of the request relies on |
| Unauthenticated | `ip:<client_address>` | The resolved client address, per §3 below |

The `user:` / `ip:` namespace is load-bearing, not cosmetic: without it a user whose identifier happened to collide with an address string would silently share a bucket with that address.

**The `user_id` is never read from a header, a body field, or an unverified claim.** It comes from the verified token's subject or the request is not treated as authenticated. This is the rule the whole decision rests on — a caller who can influence their own limiting key is not being limited.

### 2. Public and authenticated limiting use different mechanisms

This follows from an ordering constraint rather than from preference. `RateLimitMiddleware` runs as ASGI middleware, which executes *before* FastAPI resolves dependencies — so at the moment the limiter runs today, no verified identity exists yet.

**Decided:** the two classes are limited by two mechanisms.

- **Public paths** stay in middleware, keyed on the resolved client address. They must refuse *before* any work happens, which is the entire point of limiting an unauthenticated endpoint.
- **Authenticated paths** are limited by a dependency that runs after authentication, keyed on the verified `user_id` — declarative per route, matching how `requires(<permission>)` already works ([[Authorization Model]]).

Two alternatives were rejected. **Verifying the token inside the limiter** would duplicate verification, double JWKS work, and create two places where auth logic can drift apart — the second place being one nobody would think to audit. **Moving all limiting into dependencies** does not work either: an unauthenticated request has no dependency-resolved identity to key on, so public paths would need middleware regardless, and the "single mechanism" this was meant to buy does not actually exist.

The cost is honest: two mechanisms mean two places to look. It is accepted because the classes genuinely differ in *when they can possibly know who is calling*, and a single mechanism would have to paper over that difference rather than resolve it.

### 3. The trust boundary

**`X-Forwarded-For` is honoured only when the immediate peer address is in a configured allowlist of trusted proxies. Otherwise it is ignored entirely and the peer address is used.**

The peer address — the TCP source — is the only value in the request an attacker cannot forge without controlling the network path. Every trust decision anchors to it.

**Parsing rule.** `X-Forwarded-For` is a comma-separated list appended to by each hop: `client, proxy1, proxy2`.

- **Never take the leftmost entry.** This is the standard vulnerability in this area: a client may send the header itself, and honest proxies *append* rather than replace, so the leftmost value is whatever the attacker chose to put there.
- **Walk right-to-left, discarding entries that are themselves trusted proxies. The first untrusted address encountered is the client.**
- **If every entry is trusted**, fall back to the peer address.
- **Malformed entries** invalidate the header; fall back to the peer address and log it.

**Failure is closed.** A malformed header, an absent allowlist, or an unparseable chain results in limiting against the peer address — a weaker limit, never an absent one. There is no configuration value that disables limiting.

**Platform headers are an override, not a default.** Where a platform sets a single-hop, non-appendable header — Cloudflare's `CF-Connecting-IP` is the canonical example — it may be preferred, **under the same trust gate**. Such a header is trustworthy only because the platform overwrites it, which holds only if the request genuinely came from that platform. It is configuration, never an unconditional default.

### 4. Configuration, not code branching

The allowlist is **CIDR-aware** — real deployments need ranges (Cloudflare's published ranges, a loopback sidecar, a private subnet), not bare addresses. It is supplied through the existing `Settings` system ([[Environment and Secrets]]) with `.env.example` entries, per environment.

No environment-conditional branching in application code ([[CLAUDE|CLAUDE.md]] §28a): local, staging and production differ by *configuration value*, not by code path. Local development typically trusts loopback; production trusts the CDN ranges and the Next.js origin.

### 5. The proxy's obligation

`apps/web` currently forwards no client address — `apps/web/src/lib/api.ts` sends `Accept`, `Content-Type` and `Authorization` only. For public endpoints to be limited by real client address, the Next.js proxy must read the client address from its own incoming request and forward it. Next.js thereby becomes a trusted proxy and must appear in the API's allowlist.

**This creates a deployment obligation that is part of the decision, not a footnote:** any reverse proxy placed in front of the API must be in the allowlist, **and must strip or overwrite inbound `X-Forwarded-For` from the internet rather than appending to it.** A trusted proxy that blindly appends passes attacker-supplied entries into a chain the API is about to trust. Recorded in [[Infrastructure]].

## Alternatives Considered

### Option A — Keep keying on the peer address

Change nothing; accept that limiting is per-proxy.

**Rejected because** it is the live defect. It is not a weaker limit, it is an inverted one: the control now provides an attacker a cheap way to lock every user out of sign-in. A security control that reliably harms the people it protects is worse than its absence, because its presence implies coverage that does not exist.

### Option B — Trust `X-Forwarded-For` unconditionally

Read the header, take the leftmost entry, key on it.

**Rejected because** it hands the limiter's key to the caller. Any client resets its own allowance by varying one header value, so credential stuffing becomes unlimited — while the logs show a limiter working normally against thousands of distinct "clients". This is the failure the current code comment explicitly warns against, and it is worse than Option A because it fails silently rather than visibly.

### Option C — Limit at the edge only (Cloudflare / Nginx rules)

Delegate rate limiting entirely to the CDN or reverse proxy.

**Rejected as a *replacement*, valuable as a *layer*.** The edge cannot key on `user_id` — it does not verify ProjectOne's tokens, so per-user limiting is impossible there, and per-user limiting is the requirement. It also makes a security control depend on infrastructure configuration that lives outside the repository, untested by CI and invisible in review, and it leaves the API unprotected on any path that does not traverse the edge (staging, direct access, a future internal client). Edge limiting remains welcome as defence in depth ([[CLAUDE|CLAUDE.md]] §16), which is the same posture already taken toward Supabase's own upstream limits.

### Option D — Introduce Redis/Valkey now and solve distribution at the same time

Fix the identity problem and replace the in-process store in one change.

**Rejected because it conflates two independent problems.** *What is counted* (this ADR) and *where counts live* (§Future Evolution) are separable, and the first is a live vulnerability while the second is a scaling limitation that does not yet bind — the deployment is single-instance. Bundling them would also make a security fix depend on a new infrastructure dependency requiring its own ADR ([[CLAUDE|CLAUDE.md]] §10, §28), delaying the fix behind an infrastructure decision. Fixing the key first is strictly ordered: correct keys are a prerequisite for a distributed limiter regardless, since a distributed store keyed on the wrong identity distributes the wrong answer.

## Consequences

### Easier

- Per-user limiting becomes possible at all, which is the requirement.
- A user exhausting their allowance no longer affects anyone else.
- The trust boundary is written down, so a future deployment change (adding a CDN, moving the proxy) has a documented rule to satisfy instead of an assumption to rediscover.
- Public and authenticated limits can be tuned independently, because they are now separate mechanisms with separate rules.

### Harder

- **Two mechanisms to understand and maintain**, accepted deliberately in §2.
- **Correctness now depends on configuration.** A wrong allowlist is a real misconfiguration class that did not exist before: too narrow and limiting silently falls back to the proxy address (the current defect, restored); too wide and forged headers are honoured. This is why [[STEP-16a Developer Session Inspector]] renders the resolved address and identity — a misconfiguration that is invisible is a misconfiguration that ships.
- **A new deployment requirement** binds anyone standing up an environment (§5). It is documented in [[Infrastructure]] rather than left as operational folklore.
- **Rate limit logs change shape.** The `rate_limit_exceeded` line gains an identity class. Logging a raw client address alongside a user id is a data-protection question, not a debugging convenience — checked against [[Privacy and Data Protection]] before it ships.

### Explicitly not changed

**The limiter remains in-process and per-worker.** [[STEP-12 API Conventions and Middleware]] stated that approximation openly and it stands. Per-user keys make it *more* visible rather than less: N workers permit up to N times each user's configured allowance. That is a bounded, stated over-permission, not a silent one — and it is a scaling limitation, not the security defect this ADR closes. See §Future Evolution.

## Future Evolution

**Documentation only. Nothing here is scheduled, and no step implements it.** Recorded so the migration path is a known route rather than a rediscovery, per the owner's request on 2026-08-03.

### What forces the change

The in-process store is sufficient while the API runs as a single instance, and stops being sufficient at a specific, observable point: **more than one API instance serving traffic.** Counters live in one worker's memory, so N instances permit up to N times each configured allowance, and a client's requests land on whichever instance the load balancer picks. Horizontal scaling is an explicit platform goal ([[CLAUDE|CLAUDE.md]] §7, §12), so this is a matter of when, not whether.

Three triggers should prompt the move, any one of them sufficient:

1. **Multi-instance deployment** of `apps/api`, including autoscaling that can transiently exceed one instance.
2. **A limit that must be exact** rather than approximate — the clearest case being AI spend, where [[CLAUDE|CLAUDE.md]] §15a budget ceilings are financial commitments and an N-times over-permission is real money.
3. **Limits needing to survive a restart.** In-process counters reset on deploy, so a rolling deploy currently clears every allowance — a free reset for an attacker who notices.

### Why this ADR's work is a prerequisite, not throwaway

The migration is deliberately narrow because the identity scheme decided above is the part that survives. `user:<user_id>` and `ip:<client_address>` are already the correct keys for a shared store; the trusted-proxy resolution is already the correct way to derive the second. **A distributed limiter keyed on the wrong identity would distribute the wrong answer more efficiently.** What changes is only *where the counter for a key lives*.

### The migration path

1. **An ADR first.** Redis/Valkey is a new infrastructure dependency outside the [[CLAUDE|CLAUDE.md]] §10 stack table, so it requires its own ADR ([[CLAUDE|CLAUDE.md]] §28) covering the engine, hosting, failure posture and operational ownership. It supersedes this section rather than being governed by it.
2. **Extract the counter behind an interface.** The rate limit decision — *given this key and this rule, is the request allowed?* — becomes a small port with the current in-process implementation as its first adapter. This is the only change worth making *before* the move, and it is worth making only when the move is actually scheduled: extracting an interface for a single implementation ahead of a second one is the speculative abstraction [[CLAUDE|CLAUDE.md]] §29/§35 forbids.
3. **Add a shared-store adapter** implementing the same port, using an atomic server-side operation. A sliding window needs the read-modify-write to be atomic — a naive `GET` then `SET` from multiple instances undercounts precisely under the concurrent load the limiter exists to handle.
4. **Adopt one of the two operating modes below**, explicitly. This is the decision that matters most and the one most often left implicit until a cache outage answers it by accident.
5. **Migrate both classes together.** Public and authenticated limiting share the port, so neither is left behind on a different substrate.

### Backend-unavailable operating modes

When the distributed limiter backend is unreachable — a Redis/Valkey outage, a network partition, a failover — the limiter must do *something*, and there are exactly two defensible answers. Both are legitimate; they optimize for different failures.

| Mode | Behaviour when the backend is unavailable | Optimizes for | Cost |
|---|---|---|---|
| **Availability First** | Fall back to the in-process limiter — today's per-worker approximation | Keeping the platform serving | Limits become approximate (N workers permit N× the allowance) for the duration of the outage |
| **Security First** | Fail closed — refuse limited requests while the backend is unreachable | Never permitting an unlimited request | A backend outage becomes a platform outage; sign-in stops working for everyone |

**Availability First is adopted for Foundation.**

The reasoning is about what each failure actually costs at this stage. Under Security First, a cache outage takes down authentication for every user — a dependency failure escalated into a total outage, and one where the blast radius is *larger* than the risk being managed. Under Availability First the fallback is not "no limiting": it is the in-process limiter, which is exactly the protection in place today and which STEP-12a leaves working. The degradation is bounded, well understood, and strictly better than the alternative's failure mode.

**The production decision is deliberately left open.** Foundation is single-instance and pre-revenue; the calculus changes when the platform is multi-instance, when limits guard AI spend (where an N× over-permission is real money, [[CLAUDE|CLAUDE.md]] §15a), or when a compliance obligation makes an approximate limit unacceptable. A future ADR — the same one that introduces the shared store — makes the production call, and may reasonably choose Security First for specific high-value paths while keeping Availability First for authentication. **A mixed posture is a legitimate outcome** and should not be foreclosed here.

What is *not* open: the mode must be a stated, configured decision with an observable signal when the fallback engages. A limiter silently degrading with nothing in the logs is indistinguishable from a limiter working, which is the observability gap [[CLAUDE|CLAUDE.md]] §26 exists to prevent.

### What must not be assumed

- **A shared store does not remove the trust boundary.** Client address resolution is unchanged by where counters live; §3 remains binding.
- **A shared store is not automatically exact.** Clock skew across instances, window boundaries and non-atomic operations each reintroduce approximation. Exactness is a property of the algorithm and the operations used, not of the storage engine.
- **Adding Redis for rate limiting does not license using it for anything else.** A cache introduced for one purpose becomes a session store, then a queue, then an undocumented dependency with data in it that nobody planned to persist. Scope belongs in its ADR.

## Related

- Governing rules: [[CLAUDE|CLAUDE.md]] §7 (ADR lifecycle) · §14 (API security) · §16 (Zero Trust, untrusted input) · §28 (dependency rules) · §28a (environment configuration)
- Architecture: [[Security Architecture]] · [[API Architecture]] · [[Infrastructure]] · [[Web Session Handling]]
- Conventions this amends: [[API Conventions]] (STEP-12's middleware contract)
- Build steps: [[STEP-12a Trusted Proxy and Per-User Rate Limiting]] (implements this) · [[STEP-16 Sign Up and Sign In UI]] (introduced the regression) · [[STEP-16a Developer Session Inspector]] (makes misconfiguration visible)
- Prior decision: [[ADR-001 Technology Stack]]

---

## Navigation

- **Previous:** [[ADR-001 Technology Stack]]
- **Next:** —
- **Parent:** [[Global Index]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[Security Architecture]] · [[Infrastructure]]
