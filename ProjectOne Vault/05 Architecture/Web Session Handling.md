---
title: Web Session Handling
category: Architecture
status: stable
version: "1.0"
last_updated: 2026-08-02
tags: [frontend, security, authentication, standards]
aliases: ["Session Handling", "Token Storage", "Web Auth"]
---

# Web Session Handling

**How a session is stored and enforced in `apps/web`**, established by [[STEP-16 Sign Up and Sign In UI]] and binding from that point on.

[[Authentication Implementation]] is the companion note: it owns the request side inside the API — how a token becomes a verified identity. This note owns everything before that, in the browser and the Next.js server.

## The Decision: httpOnly Cookies, Written Server-Side

Tokens live in **httpOnly cookies set by the server**. They are never in `localStorage`, never in `sessionStorage`, and never reachable by JavaScript.

[[Authentication and Authorization]] requires "session management and token security" and specifies no mechanism, so this choice extends that document rather than diverging from it — checked before implementing, per [[CLAUDE|CLAUDE.md]] §33–34.

### Why not `localStorage`

`localStorage` is readable by any script on the origin. A single XSS anywhere in the application exfiltrates a live session, and a stolen **refresh** token outlives the access token it came with — turning a momentary script injection into indefinite account access.

An httpOnly cookie does not remove XSS as a threat: a script running on the page can still *act* as the user while that page is open. What it removes is the attacker's ability to **walk away with the credential**. That distinction is the whole of the trade.

### Two consequences, both deliberate

1. **Every API call is server-side.** The browser cannot read the token, so it cannot attach it. Traffic is browser → Next.js → API. This also sidesteps CORS, which matters concretely: the API registers **no CORS middleware**, so a direct browser call would be refused regardless.
2. **`sameSite: "lax"` is the CSRF control.** The cookie is not sent on cross-site POSTs, so a third-party form cannot drive an authenticated state change. `lax` rather than `strict` so following an inbound link does not present as signed-out.

`secure` is set everywhere except local development, where a `secure` cookie over plain HTTP is silently dropped — which would look like signing in and being immediately forgotten.

## The Two-Layer Gate

Enforcement is server-side, and it is split across two layers that answer different questions.

| Layer | File | Question | Authoritative? |
|---|---|---|---|
| Proxy | `src/proxy.ts` | Is a session cookie even present? | **No** |
| Layout | `src/app/(app)/layout.tsx` | Is this session real? | **Yes** |

**The proxy is not the authentication control and must never become one.** It checks cookie *presence* only: it does not verify the token, cannot know whether it was revoked, and any forged cookie value passes it. It exists for one reason — see below.

**The layout is the control.** `requireProfile()` calls `GET /auth/me`, so a session is only accepted if the API verified the token against JWKS and the row came back. Placing it in the layout rather than each page means a feature step adding a route inside `(app)` inherits the gate instead of having to remember it.

### Why the proxy exists at all

A `redirect()` from the layout runs *inside* the `loading.tsx` Suspense boundary, so Next.js has already flushed a **200** and can only finish with a `<meta http-equiv="refresh">`. Observed directly: requesting `/dashboard` with no session returned `HTTP/1.1 200` with `NEXT_REDIRECT` embedded in the streamed body.

No shell markup or user data leaked in that response — the gate held. But a 200 carrying a meta-refresh is a weaker answer than a redirect status, because it depends on the client honouring the refresh. The proxy runs before rendering begins, so it returns a real **307**.

Its matcher lists shell routes explicitly rather than excluding public ones. A negative matcher silently starts gating each new public route that is not in the exclusion list, and "sign-up redirects to sign-in" is a bug nobody finds until a user reports it. `proxy.test.ts` asserts every navigable route is covered.

> [!note] Next.js 16 renamed this file convention from `middleware` to `proxy`. Behaviour is unchanged.

## Cookies Cannot Be Written During a Render

**Next.js permits cookie mutation only in a Server Action or Route Handler.** A Server Component rendering a page may read cookies but not write them.

This constraint bites precisely where it hurts most. The layout is where an unusable session is *discovered* — it asks the API and learns the refresh token is spent. But the layout is a render, so it cannot delete the cookie that carried it. Worse, the attempt **throws**, and the throw aborts the render, killing the `redirect()` that was about to run.

Observed during validation as an endless "Loading…" skeleton with no way out:

```
Error: Cookies can only be modified in a Server Action or Route Handler.
    at clearSession (src/lib/session.ts)
    at requireProfile (src/lib/auth.ts)
    at AppLayout (src/app/(app)/layout.tsx)
```

Two mechanisms resolve it together:

- **`writeSession` and `clearSession` report failure rather than throwing** (`"read-only-context"`). A caller that could not clear the cookie still knows the session is unusable and redirects anyway.
- **`/session/expired` is a Route Handler that can write.** The gate sends a request carrying a *rejected* session there instead of straight to sign-in; it deletes both cookies and 307s onward.

Without the second mechanism the dead cookie survives every request: the proxy sees it present, passes the request through, the gate rejects it again, and the user loops forever. The distinction the gate draws — cookie present versus absent — is what routes those two cases apart.

## Token Refresh

The access cookie's lifetime tracks the token's own `expires_in`, so its **absence with a refresh cookie still present** is the signal that a refresh is due. `resolveAccessToken()` refreshes on that signal rather than by calling the API and being rejected, so a user whose token expires mid-session continues silently instead of being bounced to sign-in.

A refresh the provider refuses is treated as spent — the session is cleared rather than retried, because a rotated or revoked refresh token is never going to work again.

## What Is Not Built

Stated so the next reader does not assume otherwise:

- **Password reset, email confirmation handling, OAuth/social sign-in, and workspace creation UI** are all out of scope for [[STEP-16 Sign Up and Sign In UI]] and remain unscheduled.
- **This project has email confirmation enabled.** Sign-up therefore returns `email_confirmation_required` with no session, and the UI renders a "check your email" state. The confirmation link itself lands nowhere in this application yet.
- **The API's rate limiter now sees one IP.** With every call proxied through Next.js, the limiter keys on the web server's address rather than the end user's, so per-user limiting is no longer what it measures. Recorded here rather than left to be discovered — it needs a forwarded-client-address scheme before this reaches real traffic.

---

## Navigation

- **Previous:** [[API Endpoints]]
- **Next:** [[Schema Overview]]
- **Parent:** [[Architecture MOC]]
- **Related Notes:** [[Authentication Implementation]] · [[Authentication and Authorization]] · [[API Endpoints]] · [[Design System]] · [[Security Architecture]]
