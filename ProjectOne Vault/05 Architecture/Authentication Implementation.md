---
title: Authentication Implementation
category: Architecture
status: stable
version: "1.0"
last_updated: 2026-08-01
tags: [backend, security, authentication, multi-tenancy, standards]
aliases: ["Auth Implementation", "Authentication Backend"]
---

# Authentication Implementation

**What was actually built**, as opposed to the intended model in [[Authentication and Authorization]]. Established by [[STEP-10 Authentication Backend]] and binding from that point on.

[[RLS Policy Pattern]] is the companion note: it owns the database side (policies, the two connections, grants). This note owns the request side — how a token becomes a verified identity, and how that identity reaches the database.

## The Shape

```
request → HTTPBearer → TokenService.verify (ES256, JWKS)
                            ↓ AuthenticatedUser
                     RequestSessionFactory.authenticated_as(user.id)
                            ↓ SET LOCAL ROLE + set_config (per transaction)
                     RLS policies decide which rows exist
```

Identity is verified once, at the edge, and then carried into the database rather than re-checked in application code. No route filters by user id in a `WHERE` clause: filtering is the policies' job, and an application-side copy of that rule is a second, weaker implementation that silently stops matching when one of the two is edited.

## Token Verification

Supabase signs this project's access tokens with **`ES256`** — verified against the live project, not assumed. That is asymmetric, so the API verifies with the **public** key from the project's JWKS endpoint and holds no signing secret at all. A read-only copy of this service cannot mint a token, only check one. (The legacy Supabase model used a shared `HS256` secret, where anything able to verify a token can also forge one.)

Five things are checked, and each one is a check that must pass:

| Check | Why it is not optional |
|---|---|
| Signature | The base guarantee. |
| **Algorithm allow-list** (`["ES256"]`) | Reading `alg` from the token's own header is the classic JWT vulnerability — a token claiming `HS256` makes the verifier use the *public* key as a shared secret, and that key is public. |
| **`iss`** | A signature check alone accepts a correctly-signed token from a *different* Supabase project. Anyone with a free project could otherwise authenticate here. |
| **`aud`** (`authenticated`) | Distinguishes a user access token from other tokens the project issues. |
| **`require`** on `exp`, `iat`, `sub`, `aud`, `iss` | Verifying a claim's *value* is not the same as requiring it to *exist*. A forged minimal token walks through the gap. |

`sub` is then parsed as a uuid. It is set as the session variable `auth.uid()` casts, so a non-uuid would otherwise surface as a database error deep inside a query rather than as an authentication failure at the edge.

The JWKS client is built once per process and caches the key set, with a bounded lifespan so a Supabase key rotation is picked up without a redeploy.

### Failures are indistinguishable to the caller

Every rejection returns **401 with the same body**, whether the token was missing, malformed, expired, tampered with, or from the wrong issuer. Distinguishing them hands an attacker an oracle: whether a token was ever valid, whether it has merely expired, whether the signing key is right. The specific cause is preserved in the exception for logs, which is where it is useful and not exploitable ([[CLAUDE|CLAUDE.md]] §24).

One deliberate exception: `SigningKeyUnavailableError` is a distinct type, because a JWKS outage is *our* fault rather than the caller's — the token may well be valid and merely unverifiable. It still returns 401, because an unverifiable token must never be honoured, but conflating it in logs would hide a Supabase outage behind what looks like a wave of bad credentials.

`IdentityProviderError` returns **503**, not 401. Supabase being unreachable means the credentials were never actually judged; returning 401 would tell a user their password is wrong during an outage and hide the outage in the one metric that should reveal it.

## Layering

Router → service → repository, per [[CLAUDE|CLAUDE.md]] §12:

| Layer | Module | Owns |
|---|---|---|
| Router | `app/routers/auth.py` | HTTP only — request/response shapes |
| Service | `app/services/auth_service.py` | Registration, sign-in, provisioning decisions |
| Service | `app/services/token_service.py` | **Token verification is business logic**, not routing |
| Repository | `app/repositories/supabase_auth.py` | The only module that talks to Supabase Auth |
| Repository | `app/repositories/session.py` | Request-scoped, RLS-subject connections |
| Repository | `app/repositories/users.py` | `public.users` rows |

Token verification living in a service rather than a router is the load-bearing part of this split: a router's job is to accept a request and return a response, not to decide what makes a token valid.

**Status-code translation left the routers in [[STEP-12 API Conventions and Middleware]].** `AuthError` and its subclasses are now mapped by application-wide exception handlers ([[API Conventions]]), so a router raises or propagates and never maps. The reasoning is there rather than restated here.

## Endpoints

Paths are shown with the `/api/v1` prefix STEP-12 introduced. They were unversioned when STEP-10 built them, and were migrated — not duplicated — onto the prefix; the unversioned paths no longer answer.

| Endpoint | Auth | Notes |
|---|---|---|
| `POST /api/v1/auth/sign-up` | — | 201. Returns `email_confirmation_required` when the project issues no session. Rate limited. |
| `POST /api/v1/auth/sign-in` | — | Returns access + refresh tokens. Rate limited. |
| `POST /api/v1/auth/sign-out` | Bearer | Revokes **upstream**, using the user's own token. |
| `POST /api/v1/auth/refresh` | — | Exchanges a refresh token. Rate limited. |
| `GET /api/v1/auth/me` | Bearer | The caller's profile; provisions it if absent. |
| `GET /api/v1/workspaces` | Bearer | Read-only. Exists to prove RLS reaches the API. |

Sign-out deliberately calls Supabase rather than discarding the token client-side. A local discard leaves the token valid until it expires, so a "signed out" user still holds working credentials — which is not what signing out means.

> [!warning] What sign-out revokes, and what it does not
> Measured during [[STEP-16 Sign Up and Sign In UI]] validation against the live project, because the sentence above is easy to read as more than it claims.
>
> - **The refresh token is revoked immediately.** Exchanging it after sign-out returns 401. The session really is terminated upstream, so no *new* access token can be minted.
> - **An access token already issued keeps working until it expires** — up to **one hour** on this project. `GET /auth/me` returned 200 for a token captured before sign-out. This is not a defect in sign-out: access tokens are stateless JWTs verified locally against JWKS (see [[#Token Verification]]), so honouring one requires no call to Supabase and revocation cannot reach it.
>
> The practical exposure is bounded and specific: an attacker who *already captured* an access token keeps it for the remainder of its hour, and signing out does not shorten that. It does stop them holding the session indefinitely, which is what the refresh token would have given them.
>
> Closing the gap entirely would require checking a revocation list on every request — a stateful check on the hot path, which is precisely the cost the stateless design was chosen to avoid. It is recorded here as a known, measured property rather than resolved silently; shortening the access token lifetime is the cheap lever if the window is judged too wide.

No endpoint accepts a user id in its body. Identity always comes from the verified token; a `user_id` field on a sign-in request is an impersonation endpoint with extra steps.

## Errors Are Typed

`app/core/security.py` defines `AuthError` and its subclasses. Every subclass carries a `public_message` safe to return, separate from the detail that goes to logs, and nothing inspects message strings to decide a status code.

Translation is owned by the handlers in `app/core/errors.py`, registered once for the application ([[API Conventions]]). The identical-401-body property this note depends on is unchanged and still guarded by `test_rejections_do_not_reveal_why` — moving the mapping did not move the rule.

## What This Step Did Not Build

Stated so the next reader does not assume otherwise:

- **MFA and OAuth providers are deferred.** [[Authentication and Authorization]] puts both in scope for the platform. The email/password path plus the RLS connection is already the Critical surface; adding two more identity flows on top of an unreviewed foundation widens the blast radius of a mistake in it. Both belong with [[STEP-16 Sign Up and Sign In UI]] or a step of their own, and the token verification path above is provider-agnostic — an OAuth-issued Supabase token verifies identically.
- **Roles and permissions.** ~~`workspace_members.role` exists and nothing reads it.~~ Delivered by [[STEP-11 Authorization and RBAC]] — see [[Authorization Model]].
- **Workspace creation.** The INSERT policies deliberately cannot bootstrap a workspace from a client ([[RLS Policy Pattern]]), so it needs an audited service path — [[STEP-13 Auth Users Workspaces Endpoints]].
- **Rate limiting on auth endpoints.** [[STEP-12 API Conventions and Middleware]] owns middleware. Supabase applies its own limits upstream in the meantime.

---

## Navigation

- **Previous:** [[RLS Policy Pattern]]
- **Next:** [[Authorization Model]]
- **Parent:** [[Architecture MOC]]
- **Related Notes:** [[RLS Policy Pattern]] · [[Authentication and Authorization]] · [[Security Architecture]] · [[Table - users]] · [[Chapter 09 - Security Standards]]
