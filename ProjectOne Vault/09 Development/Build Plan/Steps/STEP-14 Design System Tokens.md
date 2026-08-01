---
title: STEP-14 Design System Tokens
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-02
tags: [engineering, workflow, build-step, frontend,design]
step_id: STEP-14
step_status: Not Started
detail_level: full
---

# STEP-14 — Design System Tokens

**Status:** Not Started
**Detail level:** full — expanded by [[STEP-13 Auth Users Workspaces Endpoints]], per [[Execution Protocol]].

## Goal

Typography scale, color system and spacing grid implemented as the single source of styling truth — before any screen exists.

## Scope

Tokens only, no components and no screens. Order matters: every later screen inherits consistency instead of improvising it ([[Design System]] §4–6).

## Prerequisites

- [[STEP-13 Auth Users Workspaces Endpoints]] — `Done`

## Required Documentation

- [[Design System]] §4–6
- [[CLAUDE|CLAUDE.md]] Design Rules

## Inherited from earlier steps

Recorded during synchronization, not expansion.

Added by [[STEP-13 Auth Users Workspaces Endpoints]]:

- **The frontend is still a skeleton and has not moved since STEP-05.** `apps/web/src/app` holds `layout.tsx`, `page.tsx`, `loading.tsx`, `not-found.tsx`, a `/health` route and `globals.css`. Nothing consumes the API yet; that begins at [[STEP-16 Sign Up and Sign In UI]].
- **`globals.css` currently holds `create-next-app` defaults**, not ProjectOne tokens: two colors (`--background`, `--foreground`), a `prefers-color-scheme` block, and a `body` rule hardcoding `Arial, Helvetica, sans-serif` while `@theme inline` declares `--font-sans: var(--font-geist-sans)`. **Those two disagree with each other** — the body rule wins, so the declared font variable is dead. This step replaces that file's contents; it should not build on top of them.
- **Tailwind v4 is in use, configured through CSS rather than `tailwind.config.js`.** Tokens belong in `@theme`, which is what makes them available as utility classes. There is no config file to add, and adding one would be the wrong shape for v4.
- **The backend contract is settled and versioned** ([[API Endpoints]]), so nothing in this step is waiting on it. A token layer has no API dependency in any case — it is deliberately sequenced before any screen so later screens inherit consistency rather than improvising it.

> [!warning] This step is blocked on an owner decision before implementation
> [[Design System]] is `status: draft` at v0.1 and states **principles, not values**. §5 says "a modern sans-serif typeface with a defined type scale" without naming one; §6 says "one primary accent color and limited semantic colors" without giving a hex. §4 says "consistent grid, generous whitespace" without a base unit.
>
> A token layer is by definition the concrete values, so this step cannot be implemented from the document as written. Inventing a brand palette would be exactly the fabrication [[CLAUDE|CLAUDE.md]] §34 forbids — and unlike a wrong internal API, a wrong palette propagates into every screen built after it.
>
> **Do not start by guessing.** Put the specific choices to the project owner (typeface, primary accent, semantic colors, base spacing unit, type scale ratio, radius scale, dark mode yes/no for v1), record the answers in [[Design System]], then implement. If the owner prefers Claude to propose a palette, that proposal is still their decision to accept — and it is recorded in the document before code, not after.

## Tasks

1. **Resolve the missing values with the project owner** — see the warning above. This is task 1 because every other task depends on its output. Record the answers in [[Design System]] §4–6, moving those sections from principle to specification.
2. **Implement the tokens in `globals.css` under `@theme`** — color, typography, spacing, radius, and any elevation scale. Tailwind v4 reads `@theme`, which is what turns a token into a utility class; a token defined outside it is a CSS variable no component can reach idiomatically.
3. **Remove the `create-next-app` defaults**, including the `body` font rule that contradicts `--font-sans`. Leaving one hardcoded font declaration in place is how a design system acquires its first exception on day one.
4. **Decide dark mode explicitly.** The skeleton has a `prefers-color-scheme` block inherited from the template. Either implement it properly as part of the token layer or remove it — an unmaintained half-implementation is worse than neither, because it looks supported and is not.
5. **Document the token set** in [[Design System]] so a component author reads the vault rather than the stylesheet, and so the two cannot silently diverge.

## Validation

- Every token is reachable as a Tailwind utility class in a real component, observed rather than assumed — a token that compiles but produces no class is not implemented.
- No hardcoded color, font family, or spacing value remains in `globals.css`, `layout.tsx` or `page.tsx`.
- The existing pages still render, and `apps/web` builds clean with zero client JavaScript added.
- Lint, type-check, tests and build pass for `apps/web` in CI.

## Definition of Done

The typography scale, color system and spacing grid exist as tokens that every later screen consumes; [[Design System]] §4–6 state concrete values rather than principles; no template default or hardcoded style survives in the app shell; and the dark-mode question is answered deliberately rather than inherited.

---

## Navigation

- **Previous:** [[STEP-13 Auth Users Workspaces Endpoints]]
- **Next:** [[STEP-15 App Shell and Routing]]
- **Parent:** [[Build Plan]]
