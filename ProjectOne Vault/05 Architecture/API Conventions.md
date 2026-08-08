---
title: API Conventions
category: Architecture
status: stable
version: "1.2"
last_updated: 2026-08-08
tags: [backend, api, standards, security, observability]
aliases: ["API Contract", "Error Envelope", "API Middleware"]
---

# API Conventions

**What every ProjectOne endpoint inherits without asking for it**: a versioned path, one response envelope, one error contract, a correlation id, and — on the routes that need it — a rate limit. Established by [[STEP-12 API Conventions and Middleware]] and binding from that point on; the rate limiting identity and trust boundary were revised by [[STEP-12a Trusted Proxy and Per-User Rate Limiting]].

[[API Architecture]] states the *principles* (REST-first, versioned, standardized responses, comprehensive error handling). This note records the *decisions* that implement them, so the next endpoint does not re-decide any of it. Where the two differ in detail, this note describes what exists and [[API Architecture]] describes what was intended.

Companion notes: [[Authentication Implementation]] owns how a token becomes an identity; [[Authorization Model]] owns who may do what. This note owns the layer both of them surface through.

## Versioning

**URL prefix: `/api/v1`.** Every product route is mounted under it. The choice, and the alternative rejected:

| | Chosen | Rejected |
|---|---|---|
| Shape | `/api/v1/workspaces` | `Accept: application/vnd.projectone.v1+json` |
| Visible in | logs, `curl`, browsers, edge routing rules | none of those |
| Forgotten by a client | 404 — loud | served whatever the default is — silent |

The cost is that the version appears in every URL. That is precisely the property that makes it hard to get wrong, and it is why header negotiation was declined: a versioning scheme whose absence is invisible fails in the one direction that matters.

**`/health` is deliberately unversioned.** It is consumed by orchestrators and uptime checks, and its contract is "this process is ready", not a product interface. Versioning it would turn every API version bump into a deploy-configuration change.

**The existing endpoints were migrated, not duplicated.** `/auth/*` and `/workspaces` shipped unversioned in [[STEP-10 Authentication Backend]] and [[STEP-11 Authorization and RBAC]]; the unversioned paths now return 404. A convention with pre-existing exceptions is not a convention ([[CLAUDE|CLAUDE.md]] §14), and leaving both live would mean clients kept using the unversioned route until v2 broke them exactly as if versioning had never been introduced.

`API_VERSION` and `API_PREFIX` live in `app/core/api.py`. No route hardcodes the string, so v2 can be mounted *alongside* v1 rather than replacing it — which is the entire point of versioning.

## The Error Envelope

```json
{ "detail": "A message safe to show a user", "request_id": "0f8c…" }
```

`detail` is FastAPI's own field name, kept rather than replaced. Every `HTTPException` and every framework-generated 422 already produces it; a bespoke key would mean re-rendering validation errors to fight the framework, and would break every existing client for a cosmetic difference.

`request_id` sits **beside** `detail`, never inside it. That placement is load-bearing — see [[#The Two Properties That Must Not Break]].

A 422 carries a third key, `errors`, listing `field` / `message` / `type`. Field-level detail is safe here in a way it is not for auth failures: telling a caller that `email` is malformed reveals nothing they did not just send, and withholding it makes every client integration a guessing game. The `input` value pydantic echoes by default is **stripped** — on `/auth/sign-up` that value is the submitted password.

### Status codes

| Cause | Status | Why |
|---|---|---|
| `AuthError` and subclasses | 401 | Identity unknown or unverifiable. |
| `IdentityProviderError` | 503 | Ours, not the caller's — Supabase was unreachable, so the credentials were never judged. |
| `AuthorizationError` / `WorkspaceAccessError` | 403 | Identity known; the answer is still no. |
| `ProjectNotFoundError` | **404** | The named resource is absent *or* hidden by RLS — deliberately one answer. |
| `LastOwnerError` | 409 | Permission held; the workspace's *state* refuses. |
| `IllegalTransitionError` | **409** | Permission held; the *resource's* state refuses. |
| `BudgetExceededError` / `ExecutionLimitExceededError` | **402** | Well-formed and authorized; the workspace has spent its allowance. |
| `AIShutdownError` / `SpendBreakerOpenError` | **503** + `Retry-After` | Operational and temporary; nothing about the caller is at fault. |
| Validation failure | 422 | The request never formed a valid operation. |
| Unhandled exception | 500 | Fixed message; the traceback goes to the log. |

The 401/403 split must never be collapsed. `AuthorizationError` is deliberately not an `AuthError` subclass ([[Authorization Model]]) so a permission failure cannot be mistaken for a credential failure — which would send a correct client into a token-refresh loop over a settled "no".

**402 rather than 403 for a spend ceiling**, and the distinction matters to the reader of the response: 403 says *"you may never do this"* and sends someone to the permission model, while a budget refusal succeeds again next period or once the limit is raised. See [[AI Cost Governance]].

Registered by [[STEP-18 AI Cost Governance Controls]] **before any route can raise one**. Without the handler a deliberate, correct cost control would reach the client as a **500** — a control reported as a crash, sending a user to support and an engineer to a stack trace that does not exist. `ExecutionLimitExceededError` shares the 402 with the budget deliberately: from the caller's side both mean "this workflow consumed its allowance", and splitting them would leak how runs are bounded internally.

**404 for a resource, 403 for a tenant** ([[STEP-21 Projects UI]]), and the two look inconsistent until the question each answers is named. A **workspace** id answers 403 whether the caller is a non-member or under-privileged, because they supplied that id as the thing they claim access to and a 404 would confirm which ids exist. A resource id *inside* a workspace they do belong to answers 404, because an invisible resource and an absent one are the same fact from their side and the tenant gate has already refused outsiders. The rule underneath both: **one answer per question, regardless of cause.**

**409 and 422 are different refusals**, and the projects lifecycle is where the distinction first becomes routine. 422 says *the value is not a member of the vocabulary*; 409 says *the value is valid but the resource's current state refuses it*. `LastOwnerError` and `IllegalTransitionError` are the same shape — permission held, state says no — differing only in whose state refuses. Collapsing either into 422 would send a client debugging a typo through a state diagram; collapsing into 403 would send them to the permission model.

### Translation lives in handlers, not routers

All of it is registered once, from a table in `app/core/errors.py`. Routers raise; they do not map.

This finishes what [[STEP-11 Authorization and RBAC]] started — the 403 handler was already registered centrally, while `AuthError` was still mapped by a `_reject` helper inside `app/routers/auth.py`. Two translation sites is how two answers drift apart, and a *difference* between them is an oracle. A service can also raise without the route above it knowing (`DataOwnershipService` does exactly that), so a mapping that depends on each router remembering to catch something is a mapping that eventually surfaces as a 500.

One deliberate exception remains in the router: sign-up catches `CredentialsRejectedError` and returns a generic **400**, because the same exception from sign-in correctly means 401 and a handler cannot tell the two apart. It is an endpoint decision, not a type-to-status mapping.

## The Two Properties That Must Not Break

Inherited from [[STEP-10 Authentication Backend]] and [[STEP-11 Authorization and RBAC]], and re-proven against the new envelope:

1. **Every authentication failure returns an identical `detail`** — absent token, expired, forged signature, wrong issuer, JWKS outage. Distinguishing them tells an attacker whether a token was ever valid and whether the signing key is right. Guarded by `test_rejections_do_not_reveal_why` and `test_authentication_failures_share_one_identical_detail`.
2. **Every authorization refusal returns an identical `detail`** — whether the caller's role was too low or they were not a member at all. This is what stops a workspace id becoming an existence oracle.

**This is why `request_id` is a sibling of `detail` rather than nested inside it.** The id necessarily varies per request; folding it into the compared value would make two otherwise-identical bodies differ, and the tests asserting the properties would either break or be weakened to accommodate it. Tests compare `detail`; the id sits beside it. The reason a rejection happened stays in the log, where it is a debugging aid rather than an oracle ([[CLAUDE|CLAUDE.md]] §24).

## Correlation Id

Header `X-Request-ID`, in and out.

- **Read** from the request when a caller or upstream proxy supplies one, so a trace survives a hop.
- **Generated** (uuid4) when they do not.
- **Echoed** on every response, and included in every error body, so a user reporting a failure can quote an id that is actually findable.
- **Carried** through the request in a `ContextVar` — not a module global, which under concurrency would be shared across every request a worker is handling at once, so a log line would carry whichever id was set last.

A supplied id is **untrusted input** and is validated before use: alphanumerics, hyphen and underscore, 128 characters maximum. Anything else is replaced with a generated one. An unvalidated id lands in every log line the request produces, which makes a newline a log-forgery vector and an unbounded string a log flood ([[CLAUDE|CLAUDE.md]] §16).

Errors that never reach an exception handler — Starlette's 404 for an unmatched route, and the rate limiter's own 429 — are stamped by the context middleware on the way out. Without that, "every error body carries a request id" would be true of most errors while failing on exactly the two a confused caller is most likely to ask about.

## Logging, and the Credential Rule

Every request produces one line: method, path, status, duration, correlation id.

**The query string is not logged, and neither are headers.** Query strings carry personal data and headers carry `Authorization` ([[CLAUDE|CLAUDE.md]] §16, §25).

**No credential ever reaches a log**, and this is enforced structurally rather than by convention. A `RedactingFilter` on the log handler removes credential-shaped values — bearer tokens, `Authorization` values of any scheme, `access_token`, `refresh_token`, `api_key`, `password`, `secret` — from every record passing through, including records emitted by `httpx` and `uvicorn`, which know nothing about ProjectOne's rules.

The reasoning matters more than the mechanism. "Do not log the `Authorization` header" holds exactly until someone debugging an auth problem logs the request headers — at which point the token is in the log file and *nothing turns red*. It is the rule most easily broken by a later convenience change, and its failure is silent and permanent. Enforcing it in the pipeline means that change produces a redacted line instead of a leaked credential.

Redaction **keeps the label and replaces the value** (`Bearer [REDACTED]`), so a redacted line still says that a credential was present. Silently deleting the evidence is harder to debug than saying "there was a token here" — and a redaction nobody can interpret is one someone eventually turns off. The filter censors; it never drops a record, because losing the event as well as the credential loses the interesting half of an auth failure.

The rule is asserted directly (`redact` is tested against known credential shapes) *and* through the request path (no log line from a real request contains a token). The direct test is the one that will still be meaningful after the pipeline is refactored.

## Rate Limiting

Applied to the endpoints reachable **without** a credential, which are the ones an attacker can attempt in volume:

| Endpoint | Limit | Window | Protects against |
|---|---|---|---|
| `POST /api/v1/auth/sign-in` | 10 | 60s | Credential stuffing |
| `POST /api/v1/auth/sign-up` | 5 | 60s | Account spam |
| `POST /api/v1/auth/refresh` | 30 | 60s | Refresh-token guessing |

And, since [[STEP-12a Trusted Proxy and Per-User Rate Limiting]], to the authenticated routes where the caller's own volume is the risk:

| Endpoint | Limit | Window | Scope | Protects against |
|---|---|---|---|---|
| `POST /api/v1/workspaces` | 10 | 60s | `workspace-create` | Unbounded creation — nothing else caps it, and each one bootstraps two rows through the privileged service path |
| `GET /api/v1/workspaces/{id}/export` | 5 | 60s | `workspace-export` | The most expensive read the API serves, and the shape a stolen token would reach for |

Scopes, not paths: routes sharing a scope share an allowance, so "20 AI calls a minute across every AI route" is expressible without one bucket per endpoint.

Counted **per path**, so exhausting sign-in does not also lock a caller out of sign-up — they protect different things, and a shared counter would make one attack a denial of service against the other endpoint. A refusal is a 429 in the standard envelope with `Retry-After`. `/health` is never limited: an unreachable health check reports an outage the check itself caused.

### Identity: what a limit is counted against

Revised by [[STEP-12a Trusted Proxy and Per-User Rate Limiting]], implementing [[ADR-002 Trusted Proxy and Client Address Resolution]]. Two namespaced key classes:

| Request | Key | Source |
|---|---|---|
| Authenticated | `user:<user_id>` | The **validated** auth context — the same ES256/JWKS verification the rest of the request uses |
| Unauthenticated | `ip:<client_address>` | Resolved from trusted proxies only, below |

**The `user_id` is never read from a header, a body field, or an unverified claim.** A caller who can influence their own key is not being limited.

**Two mechanisms, and the reason is structural.** ASGI middleware runs *before* FastAPI resolves dependencies, so the middleware limiter cannot know who is calling. Public paths are therefore limited in middleware (refusing before any work happens, which is the point of limiting an uncredentialed endpoint); authenticated paths are limited by `limit_by_user`, a route-level dependency that runs after authentication. The two refusals are deliberately **identical in shape** — same status, message, `Retry-After` and envelope — so a caller cannot tell which limiter refused them, since that difference would reveal whether the endpoint considered them authenticated.

### The trust boundary

**`X-Forwarded-For` is honoured only from a peer in the configured allowlist** (`PROJECTONE_TRUSTED_PROXIES`, CIDR-aware). Otherwise it is ignored and the peer address is used. The peer address is the only value in a request an attacker cannot forge without controlling the network path, so every trust decision anchors to it.

The chain is walked **right to left**, discarding entries that are themselves trusted proxies; the first untrusted address is the client. **Never the leftmost entry** — honest proxies append rather than replace and a client may send the header itself, so the leftmost value is attacker-chosen. Taking it is the classic vulnerability here, and it fails silently.

**Failure is closed.** A malformed header, an unparseable chain or an absent allowlist falls back to the peer address — a weaker limit, never no limit. No configuration value disables limiting. An empty allowlist warns at startup, because behind a proxy it silently restores the platform-wide-bucket defect.

An optional single-hop platform header (`PROJECTONE_CLIENT_ADDRESS_HEADER`, e.g. Cloudflare's `CF-Connecting-IP`) is preferred when configured, under the same trust gate — such a header is trustworthy only *because* the platform overwrites it.

> [!warning] Deployment requirement
> Any reverse proxy in front of the API must be in the allowlist **and must strip or overwrite an inbound `X-Forwarded-For` from the internet rather than appending to it.** A trusted proxy that blindly appends splices attacker-supplied entries into a chain the API is about to trust. Recorded in [[Infrastructure]].

**One limitation, stated rather than hidden:**

- **In-process and per-worker.** N workers permit up to N times each configured allowance — for per-user keys as much as address keys. Exact global limits need shared state (Redis/Valkey), which is new infrastructure and therefore its own ADR ([[CLAUDE|CLAUDE.md]] §10, §28). STEP-12a fixed *what is counted*, not *where counts live*; the migration path and the **Availability First** posture Foundation adopts are [[ADR-002 Trusted Proxy and Client Address Resolution]] §Future Evolution. Supabase applies its own limits upstream regardless.

**Still not a cost control.** Per-workspace AI spend quotas answer a different question ([[CLAUDE|CLAUDE.md]] §15a) and belong to [[STEP-18 AI Cost Governance Controls]]. `limit_by_user` is the mechanism they can build on, not a substitute for them.

## Where It Lives

| Module | Owns |
|---|---|
| `app/core/api.py` | Version prefix, request-id header name, the correlation-id context variable |
| `app/core/errors.py` | The envelope, every exception handler, the handler table |
| `app/core/logging.py` | The logging pipeline, the redaction rule |
| `app/core/middleware.py` | Correlation id, request logging, public-path rate limiting |
| `app/core/client_address.py` | Trusted-proxy resolution — pure, framework-free, exhaustively tested |
| `app/core/user_rate_limit.py` | Per-user rate limiting (`limit_by_user`) for authenticated routes |
| `app/ai/` | The provider-agnostic AI layer — see [[AI Router Implementation]]. Imports no FastAPI, so its failures reach HTTP only through the handler table above |
| `app/main.py` | Registers the above; defines no mapping itself |

> [!note] AI provider failures have no handler entry yet
> [[STEP-17 AI Router and Provider Abstraction]] deliberately shipped no HTTP routes, so nothing raises a `ProviderError` into the handler chain. The exception classes already carry `public_message` in the established shape, so the step that adds the first AI endpoint adds **one row to `EXCEPTION_HANDLERS`** — never a `try/except` in a route.

## What This Step Did Not Build

Stated so the next reader does not assume otherwise:

- ~~**Audit logging.**~~ **Built by [[STEP-13 Auth Users Workspaces Endpoints]]** — see [[Table - audit_log]]. The distinction this section drew still holds and is worth keeping: request logging records that a request happened, audit logging records *who changed what*. They are separate mechanisms with separate retention rules, and the presence of one is not the presence of the other.
- **Distributed/global rate limiting.** See the limitation above; it needs an ADR. **Per-user identity was fixed by [[STEP-12a Trusted Proxy and Per-User Rate Limiting]]** — the remaining gap is the shared store, not the key.
- **Idempotency keys.** [[API Architecture]] calls for idempotent operations where appropriate. Nothing built so far creates a resource from a client-supplied request, so there is nothing yet to make idempotent. It belongs with the first `POST` that does.
- **Pagination and filtering conventions.** `GET /api/v1/workspaces` returns a caller's own workspaces, which is bounded by construction. The first genuinely unbounded collection is the right place to settle this, not an imagined one.

---

## Navigation

- **Previous:** [[Authorization Model]]
- **Next:** [[API Endpoints]]
- **Parent:** [[Architecture MOC]]
- **Related Notes:** [[API Architecture]] · [[Authentication Implementation]] · [[Authorization Model]] · [[Chapter 06 - FastAPI Architecture]] · [[Security Architecture]] · [[API Endpoint Template]]
