---
title: STEP-15 App Shell and Routing
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-02
tags: [engineering, workflow, build-step, frontend]
step_id: STEP-15
step_status: Done
detail_level: full
---

# STEP-15 — App Shell and Routing

**Status:** Done
**Detail level:** full — expanded by [[STEP-14 Design System Tokens]], per [[Execution Protocol]].

## Goal

Base layout, navigation shell and routing structure — Server Components by default.

## Scope

The authenticated shell users land in. No feature screens. Loading, empty and error states defined from this first surface onward ([[CLAUDE|CLAUDE.md]] §11).

**Inherited from [[STEP-03 Web App Skeleton]]:** the root `error.tsx` boundary is still owed. STEP-03 established `loading` and `not-found` but could not add an error boundary — Next.js requires it to be a Client Component, which that step's validation forbade. This is the first step where client components are legitimate, so the error boundary lands here ([[Chapter 05 - NextJS Architecture]] §5.9).

## Prerequisites

- [[STEP-14 Design System Tokens]] — `Done`

## Required Documentation

- [[Frontend Architecture]]
- [[Chapter 05 - NextJS Architecture]]
- [[Design System]] §10

## Inherited from earlier steps

Recorded during synchronization, not expansion.

Added by [[STEP-14 Design System Tokens]]:

- **The token layer is live and is the only styling vocabulary available.** `apps/web/src/app/globals.css` holds primitives and semantic tokens; components reference the semantic layer exclusively. Every surface built in this step uses `bg-surface`, `text-text-muted`, `border-border-strong` and the rest — never a Tailwind default palette class, never a hex, never an arbitrary pixel value ([[Design System]] §3a). The token names are in §6.2.
- **Primitives are deliberately not utility classes.** They live outside `@theme`, so `bg-neutral-900` does not exist and will fail at build rather than silently working. If a surface needs a color with no semantic name, add the token per §6.5 — do not reach past the layer.
- **No component may be theme-aware.** Dark mode is a remapping of the semantic layer; a `dark:` variant in a component is the same defect as a hardcoded hex ([[Design System]] §6.4). The shell inherits both themes for free by using tokens.
- **`--color-surface-raised` is the surface with the least contrast headroom** in both themes (§6.3). Anything floating — dropdowns, dialogs, popovers, the navigation menu — sits on it, so foregrounds there are the first thing to re-check if any token moves.
- **The app shell files are already on tokens**: `layout.tsx`, `page.tsx`, `loading.tsx`, `not-found.tsx` and `health/page.tsx` carry no hardcoded styling. This step extends them rather than cleaning them up.
- **`layout.tsx` owns the Inter font variable** via `next/font`, applied to `<html>`. A nested layout must not re-declare it.
- **Zero client JavaScript exists in `apps/web` today.** That changes in this step for the error boundary specifically (below), and the bundle impact of anything else marked `use client` should be justified rather than assumed.

## Tasks

1. **Build the authenticated shell layout** — a route group (e.g. `app/(app)/layout.tsx`) holding the persistent navigation chrome, with the page area rendering `children`. Server Component; nothing here needs browser APIs.
2. **Implement the navigation shell** using semantic tokens only. Keyboard reachable, with a visible focus indicator — the global `:focus-visible` rule in `globals.css` already provides one, so do not override it per-component without reason ([[CLAUDE|CLAUDE.md]] §11, [[Design System]] §9).
3. **Add the root `error.tsx` boundary** owed since [[STEP-03 Web App Skeleton]]. This is necessarily a Client Component — Next.js requires it — and is the one legitimate `use client` in this step ([[Chapter 05 - NextJS Architecture]] §5.9). It shows an actionable message and a recovery affordance, never a raw stack trace ([[CLAUDE|CLAUDE.md]] §24).
4. **Define loading, empty and error states for the shell surfaces** as part of this step, not as follow-up polish ([[CLAUDE|CLAUDE.md]] §11, [[Design System]] §10). Loading states are skeletons built from tokens, not spinners with hardcoded colors.
5. **Establish the routing structure** for the authenticated area, with route segments that later feature steps slot into without restructuring.

**Explicitly out of scope:** feature screens, any API call, and authentication itself. Sign-up and sign-in UI is [[STEP-16 Sign Up and Sign In UI]]; wiring the shell to real session state follows it. A shell that renders for an unauthenticated user is acceptable at this step, because there is nothing to protect yet.

## Validation

- Every surface uses semantic tokens only — **no hex, no Tailwind default palette class, no `dark:` variant, no arbitrary pixel value** in any file this step touches. Grep for them rather than trusting review.
- Both themes render correctly and **switching them changes no component markup** — the same check STEP-14 used: compare rendered markup length across themes.
- **Contrast re-verified for any new foreground/surface combination** this step introduces, particularly anything landing on `--color-surface-raised` (§6.3). Reuse STEP-14's method: enumerate, do not hand-pick.
- The error boundary actually catches a thrown error and renders the fallback — **observed by throwing deliberately**, not inferred from the file existing.
- Keyboard navigation reaches every interactive element in the shell, with a visible focus indicator on each.
- `use client` appears **only** in `error.tsx`. Any other occurrence is justified in the step outcome or removed.
- Existing routes (`/`, `/health`) still render.
- Lint, type-check, tests and build pass for `apps/web` in CI.

## Definition of Done

The authenticated shell renders with navigation, routing structure and the loading/empty/error states every later feature screen inherits; the root error boundary owed since STEP-03 exists and is demonstrated to catch a real error; every surface is built from semantic tokens with no theme-aware component and no hardcoded style; and both themes render correctly with contrast verified for any new pairing.

**Not a Critical change** ([[CLAUDE|CLAUDE.md]] §21) as scoped above: it touches no schema, auth, API contract, infrastructure or tenant boundary. **If this step ends up gating routes on authentication, that scope is Critical** and requires an owner approval gate — surface it rather than absorbing it.

## Outcome — Done (2026-08-02)

All five tasks implemented, all validation observed.

### What was built

`app/(app)/layout.tsx` is the shell — a **route group**, so it wraps every
application screen without adding a segment to any URL. Header, sidebar and page
area; a Server Component. Four route segments live inside it (`/dashboard`,
`/projects`, `/chat`, `/settings`), each a placeholder that later feature steps
fill in rather than restructure.

**Nav destinations are the ones with a scheduled build step.** Analytics,
Billing and Video Generation are specified in the Project Bible but have no step
in the [[Build Plan]], and a nav item pointing at a route that does not exist is
a dead end rather than a roadmap. Structure lives in `lib/navigation.ts` as
data, so the sidebar and the active-route logic read one list instead of two.

The root `error.tsx` owed since [[STEP-03 Web App Skeleton]] now exists. It shows
an actionable message and a reset affordance and **never renders the error
message or stack trace** — an unexpected failure's message is written for an
engineer and can carry internal detail ([[CLAUDE|CLAUDE.md]] §24). Next.js's
`digest` is surfaced as a reference so a user report ties to a server log.

### Client boundaries

**Two, both justified.** `error.tsx` must be a Client Component — Next.js
requires it, which is exactly why STEP-03 could not deliver it. `SidebarNav`
needs `usePathname` to mark the active route, and is deliberately the smallest
possible boundary: the layout, header, page content and empty states all stay on
the server. Everything still prerenders static.

### A missing token, found by building the first skeleton

The loading skeleton was written against `--color-surface-raised` and turned out
to be **invisible in light mode** — that token is `#ffffff` against a `#f8fafc`
canvas, a ratio of **1.05**, measured in the browser rather than reasoned about.

Per [[Design System]] §6.5 the fix is to name the missing role, not reach for a
primitive, so `--color-skeleton` was added (`neutral-200` light, `neutral-700`
dark) and recorded in §6.2 before use. A skeleton is *informational* — it is not
operable, so the 3:1 non-text bar does not apply — but it must be
distinguishable, which at 1.05 it was not. Now 1.18 light / 1.95 dark.

This is the second time in two steps that a surface reused for a foreground fill
produced an invisible result. The pattern is worth naming: **a token that names
a surface is not automatically safe as a fill *on* that surface.**

### Validation observed

- **Error boundary demonstrated**, not inferred — a temporary route threw
  deliberately; the fallback rendered with its recovery button, and the response
  leaked neither the stack trace nor the raw message. Route removed before
  commit.
- **All 7 routes return 200** and prerender static; the route group adds no URL
  segment.
- **Exactly one nav item is active** on each route, marked with `aria-current`
  rather than color alone — color is invisible to assistive technology.
- **Both themes verified by computed style**, every value resolving to its token
  (`#818cf8` accent, `#1e293b` raised, `#94a3b8` muted, `#334155` border).
  **Markup length identical at 12653 in both themes** — the theme change touches
  no component markup.
- **Shell contrast pairings verified**, including the tightest one this step
  introduces: active nav label is `accent` on `surface-raised`, **4.90** in dark.
  The full 58-pairing token check still passes after adding `--color-skeleton`.
- **Keyboard order correct**: skip link first, then brand, then all four nav
  items; no negative `tabindex`. The skip link targets a real `#main-content`.
- `use client` appears only in `error.tsx` and `SidebarNav.tsx`.
- 14 tests pass (7 new, covering `isActiveRoute` — including the
  `/projects-archive` prefix case a plain `startsWith` would get wrong). Lint,
  type-check and build pass.

### Deliberately not built

**Authentication is not enforced here.** Session handling arrives with
[[STEP-16 Sign Up and Sign In UI]]; gating routes before that contract exists
would be a guess. Nothing inside the shell is protected because nothing inside
it holds data yet — every screen is a placeholder. This keeps the step
non-Critical, as its Definition of Done anticipated.

---

## Navigation

- **Previous:** [[STEP-14 Design System Tokens]]
- **Next:** [[STEP-16 Sign Up and Sign In UI]]
- **Parent:** [[Build Plan]]
