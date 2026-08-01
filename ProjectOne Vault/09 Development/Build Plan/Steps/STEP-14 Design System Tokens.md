---
title: STEP-14 Design System Tokens
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-02
tags: [engineering, workflow, build-step, frontend,design]
step_id: STEP-14
step_status: Done
detail_level: full
---

# STEP-14 — Design System Tokens

**Status:** Done
**Detail level:** full — expanded by [[STEP-13 Auth Users Workspaces Endpoints]], per [[Execution Protocol]].

## Goal

Typography scale, color system and spacing grid implemented as the single source of styling truth — before any screen exists.

## Scope

Tokens only, no components and no screens. Order matters: every later screen inherits consistency instead of improvising it ([[Design System]] §4–6).

## Prerequisites

- [[STEP-13 Auth Users Workspaces Endpoints]] — `Done`

## Required Documentation

- [[Design System]] §3a (token architecture — the binding constraint) and §4–6 (the v1 values)
- [[CLAUDE|CLAUDE.md]] Design Rules

## Inherited from earlier steps

Recorded during synchronization, not expansion.

Added by [[STEP-13 Auth Users Workspaces Endpoints]]:

- **The frontend is still a skeleton and has not moved since STEP-05.** `apps/web/src/app` holds `layout.tsx`, `page.tsx`, `loading.tsx`, `not-found.tsx`, a `/health` route and `globals.css`. Nothing consumes the API yet; that begins at [[STEP-16 Sign Up and Sign In UI]].
- **`globals.css` currently holds `create-next-app` defaults**, not ProjectOne tokens: two colors (`--background`, `--foreground`), a `prefers-color-scheme` block, and a `body` rule hardcoding `Arial, Helvetica, sans-serif` while `@theme inline` declares `--font-sans: var(--font-geist-sans)`. **Those two disagree with each other** — the body rule wins, so the declared font variable is dead. This step replaces that file's contents; it should not build on top of them.
- **Tailwind v4 is in use, configured through CSS rather than `tailwind.config.js`.** Tokens belong in `@theme`, which is what makes them available as utility classes. There is no config file to add, and adding one would be the wrong shape for v4.
- **The backend contract is settled and versioned** ([[API Endpoints]]), so nothing in this step is waiting on it. A token layer has no API dependency in any case — it is deliberately sequenced before any screen so later screens inherit consistency rather than improvising it.

> [!note] The blocker is resolved — values were supplied on 2026-08-02
> This step was previously blocked: [[Design System]] stated principles without values, and a token layer *is* the concrete values. The project owner supplied them on 2026-08-02 as **v1 initial values, explicitly not permanent branding**, with a binding architectural constraint: *all tokens are expected to change without requiring component rewrites*.
>
> [[Design System]] §3a–§6 now hold the specification — the two-layer token architecture, the 4px spacing scale, Inter with a 1.25 type scale, the slate/indigo palette, and dark mode confirmed in scope for v1. **This step implements that specification; it does not re-decide it.**
>
> The constraint is the load-bearing part, and §3a is where it lives: components reference **semantic** tokens (`--color-accent`) and never primitives (`--color-accent-600`), so a rebrand is one edit to §6.2's mapping rather than a change to every component that ever shipped. An implementation that satisfies the values but breaks that layering has failed this step, because it produces exactly the rewrite-on-rebrand the owner ruled out.
>
> §6.5 documents the change procedure, and §6.3 records that all 28 contrast pairings were computed and verified when the values were set — two of them were corrected as a result. Re-run that check if any value moves.

## Tasks

1. **Implement the two-layer token architecture in `globals.css`** per [[Design System]] §3a — primitives first, then semantic tokens mapped onto them. Both layers go under Tailwind v4's `@theme`, which is what turns a token into a utility class; a token defined outside it is a CSS variable no component can reach idiomatically. The layering is the deliverable as much as the values are.
2. **Implement the v1 values**: spacing (§4.1), radius (§4.2), elevation (§4.3), type scale and weights (§5.2–5.3), color primitives and semantic tokens (§6.1–6.2).
3. **Load Inter through `next/font`**, self-hosted — never a CDN link, which is a render-blocking dependency on a third party and leaks every visitor's IP to them. Wire it to `--font-sans` so the variable is live rather than declared and unused.
4. **Remove the `create-next-app` defaults.** Specifically the `body` rule hardcoding `Arial, Helvetica, sans-serif`, which currently overrides `--font-sans` and makes that variable dead. Leaving one hardcoded declaration is how a design system acquires its first exception on day one.
5. **Implement dark mode as a semantic remapping** (§6.4), not a second set of components. The existing `prefers-color-scheme` block is replaced by a proper mapping of the semantic layer onto dark-mode primitives.
6. **Verify contrast against WCAG AA** (§6.3) for every pairing in §6.2, in both themes. A failing pairing is a broken interface, not a style disagreement — and `--color-text-muted` is the one most likely to fail, by construction.

## Validation

- Every semantic token is reachable as a Tailwind utility class in a real component, **observed rather than assumed** — a token that compiles but produces no class is not implemented.
- **The swap test, and this is the one that proves the constraint:** reassign `--color-accent` in §6.2's mapping from indigo to a visibly different hue, rebuild, and confirm the accent changes everywhere **with no component file edited**. Revert afterwards. If any component needs touching, the layering is broken and the step is not done — whatever the rendered output looks like.
- No hardcoded color, font family, pixel value or `dark:` variant remains in `globals.css`, `layout.tsx`, `page.tsx`, `loading.tsx` or `not-found.tsx`.
- Inter actually loads and renders — verified in a browser, not inferred from the config. The fallback stack is what renders on failure, so a silently failing font looks like a working page.
- Contrast checked for every §6.2 pairing in **both** themes against WCAG AA (§6.3).
- Both themes render correctly, and switching between them changes no component's markup.
- The existing pages still render, and `apps/web` builds clean with **zero client JavaScript added** — a token layer is CSS and must not introduce a Client Component.
- Lint, type-check, tests and build pass for `apps/web` in CI.

## Definition of Done

The spacing, radius, elevation, typography and color scales from [[Design System]] §4–6 exist as tokens every later screen consumes, implemented as the two-layer architecture §3a requires; the entire brand can be replaced by editing the semantic mapping alone, demonstrated by the swap test rather than asserted; dark mode works as a remapping with no theme-aware components; every pairing meets WCAG AA; and no `create-next-app` default or hardcoded style survives in the app shell.

**Not a Critical change** ([[CLAUDE|CLAUDE.md]] §21): it touches no schema, auth, API contract, infrastructure or tenant boundary. It does not need an owner approval gate — the design decisions it implements were already made by the owner on 2026-08-02 and recorded in [[Design System]].

## Outcome — Done (2026-08-02)

All six tasks implemented, all validation observed. The step ran in two passes:
the first was `Blocked` by a contrast failure, and the owner directed a minimal
refinement rather than a redesign.

### What was built

`apps/web/src/app/globals.css` holds the whole token layer. Primitives sit
**outside** `@theme` deliberately — a primitive registered as a theme value
becomes a utility class, which would hand components the `bg-neutral-900` escape
hatch §3a forbids. Verified: the compiled CSS contains no primitive utility.

`@theme inline` is load-bearing for the color tokens. `inline` makes the
generated utilities emit `var(--color-accent)` rather than baking the hex in at
build time, which is what lets the dark-mode block remap the semantic layer at
runtime with no `dark:` variant anywhere.

Inter is self-hosted through `next/font` and exposed as `--font-inter`, which
`--font-sans` composes with the fallback stack — so the token layer owns the
font and components only ever see the semantic name.

### The contrast failure and its correction

The first pass found two dark-mode pairings below AA: `--color-text-muted` on
`--color-surface-raised` (4.04) and `--color-accent` on `--color-surface`
(4.00). The cause was a **gap in the specification's verification, not in the
implementation** — §6.3's original check covered `--color-background` and
`--color-surface` but never `--color-surface-raised`.

Extending the check to all three surfaces exposed a third failure the original
set could not have caught: `--color-danger` at 3.89 on the raised surface.

Four values moved, all one step within an existing ramp, no hue changed:

| Token | Was | Now |
|---|---|---|
| `--color-surface-raised` (dark) | `neutral-700` | `neutral-800` |
| `--color-accent` (dark) | `accent-500` | `accent-400` |
| `--color-accent-hover` (dark) | `accent-400` | `accent-200` |
| `--color-danger` (dark) | `danger-500` | `danger-400` |

`accent-hover` moved only because `accent` did — the two would otherwise
collapse onto the same value. Two primitives were added to support this
(`neutral-800`, `danger-400`); no new semantic token was needed, so the
architecture is unchanged.

**Verification now enumerates every foreground against every surface** rather
than a hand-picked list, because a hand-picked list is what produced this. 58
pairings, both themes, all pass.

### Validation observed

- **Swap test passed** — `--color-accent` reassigned to amber, rebuilt, accent
  changed throughout; all five component files byte-identical by `git
  hash-object`. Reverted. This is the evidence the §3a constraint holds.
- **58/58 contrast pairings pass** across both themes and all three surfaces.
- **Inter genuinely renders** — `document.fonts.check('16px Inter')` true with a
  `loaded` font entry in a real browser, not inferred from config. No
  `fonts.googleapis`/`gstatic` request in the build output.
- **Both themes verified in-browser** by computed style: light resolves to
  `#f8fafc`/`#0f172a`/`#4f46e5`, dark to `#020617`/`#f1f5f9`. Markup length
  identical in both — the theme change touches no component markup.
- **Zero client JavaScript added**; no `use client` anywhere in `src/`.
- No hardcoded color, `dark:` variant, arbitrary pixel value or `opacity-*`
  workaround remains in the app shell.
- Lint, type-check, 7 tests and build all pass; no console errors.

### Also corrected

`health/page.tsx` carried `border-emerald-600/30`, `text-black/60` and two
`dark:` variants — the exact defects §3a and §6.4 name, in the app shell this
step's validation covers. Now on semantic tokens.

[[Design System]] was updated to v1.2 (§6.1–6.3): the corrected values, the two
added primitives, a rewritten §6.3 recording why the original check missed them,
and a refreshed margin table. Light mode now carries the tightest margins.

---

## Navigation

- **Previous:** [[STEP-13 Auth Users Workspaces Endpoints]]
- **Next:** [[STEP-15 App Shell and Routing]]
- **Parent:** [[Build Plan]]
