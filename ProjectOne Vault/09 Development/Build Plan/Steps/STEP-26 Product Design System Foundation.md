---
title: STEP-26 Product Design System Foundation
category: Development/Build Step
status: stable
version: "1.3"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, design, frontend]
step_id: STEP-26
step_status: Done
detail_level: full
phase: "Design Foundation"
---

# STEP-26 — Product Design System Foundation

**Status:** Done — approved by the owner on 2026-08-15, [[ADR-003 Product Visual Language and Token Semantics]] `Accepted`
**Phase:** Design Foundation — The shared visual and interaction system, established once against the surfaces that actually exist.
**Detail level:** full — this is the next step and is written at full detail.

## Objective

Decide the product's visual and interaction language once, and record it in [[Design System]] as tokens, rules and component contracts.

## Why This Step Exists Now

Every screen built from here inherits it. Deciding it once, now, is what stops each new domain inventing its own spacing scale and its own error state. It is also the only design work that can be done honestly today: the surfaces it covers all exist.

## Dependencies

- [[STEP-25a Foundation Remediation]]

## Scope

- **Visual direction** — the owner-approved ivory canvas, matte-black navigation, vermilion accent and editorial typography, written as rules rather than adjectives.
- **Design tokens** — colour, type scale, weight, radius, elevation as token values.
- **Typography** — families, scale and hierarchy.
- **Spacing and layout rules** — one scale, applied consistently.
- **Navigation conventions** — structure, states and behaviour.
- **Shared component contracts** — the reusable set, each with a defined public interface.
- **Accessibility rules** — contrast, focus, keyboard order and semantics as system-level rules, carrying forward the accessibility findings in [[Foundation Audit Findings]].
- **Responsive behaviour** — breakpoints and collapse rules, stated rather than improvised per screen.
- **Loading, empty, error and success states** — defined as a system, since [[CLAUDE|CLAUDE.md]] 11 requires them of every async surface and a per-screen answer produces per-screen drift.
- **The common runtime design-system infrastructure** the approved foundation requires in order to exist at all — see the owner clarification below. Specifically and exhaustively: the primitive and semantic token definitions and their mappings in `apps/web/src/app/globals.css`; the global font wiring in `apps/web/src/app/layout.tsx`; and the design-system validation tooling and CI wiring directly required to enforce those tokens.

> [!important] Owner scope clarification — recorded 2026-08-15 at the approval gate
> **This step's original wording said "No application styling is implemented" (Out of Scope) and "No application code changes." (Definition of Done).** That wording is preserved below with its correction rather than deleted, because the change is a real narrowing of an earlier decision and hiding it would misrepresent what was agreed.
>
> **The conflict.** A design foundation whose tokens exist only as a table in a document is not a foundation — no later surface can consume it, and the first screen to need it would have to invent the runtime layer itself, which is precisely the per-screen drift this step exists to prevent. The original wording, read literally, forbade the token layer from existing.
>
> **The owner's clarification.** STEP-26 **may** change the *common runtime design-system infrastructure* listed in Scope above — the token layer, the global font wiring, and the tooling that enforces them. It **may not** touch anything screen-specific.
>
> **The distinction is between the shared substrate and any individual surface.** The substrate is what every screen consumes; a surface is what one screen looks like. This step builds the first and never the second.
>
> This clarification narrows *how* the step's goal is achieved. It does not widen the goal, and it does not lower a quality or safety bar ([[CLAUDE|CLAUDE.md]] 39).

## Out of Scope

- **No screen blueprints for domains that do not exist.** Video Generation, Analytics, Publishing, Billing and every other future domain are excluded by owner decision — each domain's surface is designed in its own phase, once its behaviour is known.
- **No individual component is restyled, no screen is rebuilt, and no screen layout is changed.** The product-wide rebuild is [[STEP-80 Product-wide UI Rebuild]], and no part of it is done early here.
- **No future-domain UI**, and no new shared component for a screen that does not exist yet.
- **No STEP-80 work of any kind.**

> [!note] What this replaced
> This list previously read *"No application styling is implemented and no page is rebuilt."* The first clause was too broad: it excluded the runtime token layer, which is shared infrastructure rather than styling of any particular surface. Corrected by the owner clarification above on 2026-08-15. **The second clause is unchanged and still binding** — no page is rebuilt.

## Surfaces Affected

**Frontend:** [[Design System]], the runtime token layer (`globals.css`), global font wiring (`layout.tsx`), shared component contracts as documentation. **Infrastructure:** the contrast check and its CI wiring. **Backend / database:** none.

## Required Tests and Proofs

- Token set is internally consistent — no colour, spacing or type value appears in a rule without being a token.
- Contrast ratios meet WCAG AA, measured rather than asserted.
- Every shared component contract states its loading, empty and error states.
- Accessibility findings carried forward from [[Foundation Audit Findings]] are addressed at system level.

## Definition of Done

[[Design System]] carries the complete approved visual language — tokens, typography, spacing, navigation, component contracts, accessibility and responsive rules, and the four async states — with the owner's approval recorded, **and that language exists at runtime as the token layer later surfaces consume.**

**Application code changes are limited to the common runtime design-system infrastructure** named in Scope: `globals.css`, `layout.tsx`, and the token-enforcement tooling. **No individual component is restyled, no screen is rebuilt and no screen layout is changed** — verified, not asserted.

> [!note] What this replaced
> This previously ended *"No application code changes."* That was corrected by the owner clarification on 2026-08-15, recorded in Scope above: it would have forbidden the token layer from existing, leaving an approved design language no surface could consume. The replacement is a narrower and checkable statement, not a looser one — it names exactly which three things may change and requires the rest to be verified untouched.

## Risks and Governance Gates

**Owner approval gate** — the visual direction is the owner's decision, not Claude's. **ADR checkpoint:** if this changes foundational token values or shared component contracts that other code is built against, an ADR must reach `Accepted` before any step consumes it ([[CLAUDE|CLAUDE.md]] 7/39).

## Outcome — 2026-08-15

**Implemented, validated and approved.** The owner approved all six decisions on 2026-08-15 and required two documentation corrections, both of which were made — see [[#Owner approval — granted 2026-08-15]]. [[ADR-003 Product Visual Language and Token Semantics]] is `Accepted`.

### What was built

| | |
|---|---|
| Visual language, as rules | [[Design System]] §0 |
| Design tokens | [[Design System]] §6.1–6.2, implemented in `apps/web/src/app/globals.css` |
| Typography | [[Design System]] §5.1a (display face), §5.1–5.3 unchanged |
| Spacing / radius / elevation | [[Design System]] §4.1–4.3 — **unchanged**, see below |
| Navigation conventions | [[Design System]] §7.2 |
| Shared component contracts | [[Design System]] §7.1 |
| Accessibility rules | [[Design System]] §9.1–9.2 |
| Responsive rules | [[Design System]] §9a |
| Loading / empty / error / success | [[Design System]] §10 |
| Contrast enforcement | `scripts/check-contrast.py`, wired into the `web` CI job |

**The spacing, radius and elevation scales were deliberately not changed.** [[STEP-14 Design System Tokens]] established a 4px scale, four radii and three elevation levels with reasoning that the new direction does not contradict. Changing them would have been a change for its own sake, and §29/§35 forbid exactly that. This step re-states them as the system's scales; it does not re-decide them.

### The ADR checkpoint triggered

The step's checkpoint reads: *if this changes foundational token values or shared component contracts that other code is built against, an ADR must reach `Accepted` before any step consumes it.* **It triggered**, and [[ADR-003 Product Visual Language and Token Semantics]] was raised — currently `Review`.

The reason is specific, and it is **not** merely that the values changed. [[Design System#6.5 How to change a token]] documents a revalue as a routine, supported procedure, and [[STEP-14 Design System Tokens]] proved it with a swap test. A pure repointing would have been operational, not architectural.

**What triggered it is that the semantic layer gained five new roles**, forced by four measured WCAG failures that no existing token could be repointed to fix. Adding a role changes the contract every component is built against, which is architectural under [[CLAUDE|CLAUDE.md]] §7 — and §39's ambiguity rule resolves toward the ADR in any case.

### Validation

All observed, not assumed:

- **Contrast: 90 pairings, 0 failures**, both themes, every foreground against every surface it can appear on. Four failures were found by measurement during the work and corrected before anything was committed — recorded in [[Design System#6.3]].
- **Two negative controls** confirm the check is not vacuously passing: lightening `ink-500` in the stylesheet alone trips the palette-drift guard; changing it in both the script and the stylesheet produces three genuine contrast failures. Both reverted.
- **The swap test passes** — reassigning `--color-accent` to green changed the accent everywhere with **no component file edited**, then reverted. The §3a layering survives this palette.
- **Every new token generates a real utility class**, verified by compiling a probe component and reading the built CSS — `bg-nav-surface`, `bg-nav-surface-raised`, `text-text-on-nav`, `text-text-on-nav-muted`, `text-accent-on-nav`, `bg-accent-fill` and `font-display` all present. Probe removed afterwards.
- **Zero token-layer leaks in the codebase**: no hex, no primitive reference, no Tailwind default palette class, no `dark:` variant outside a comment.
- Web lint (zero-warning), `tsc --noEmit`, **261 tests passing**, and the production build all clean. Both fonts self-hosted by `next/font`.
- Governance docs sync check green; wiki-links in every touched note resolve.

### No application code was restyled

`globals.css` and `layout.tsx` are the only application files changed — the token layer and the font wiring. **No component and no screen was touched**, as this step's Out of Scope requires. The `nav-*` family therefore has no consumer yet: it is defined and verified but unused until [[STEP-80 Product-wide UI Rebuild]], which is deliberate.

## Owner approval — granted 2026-08-15

All six decisions were **approved as implemented**. No value was changed to obtain approval.

| # | Decision | Outcome |
|---|---|---|
| 1 | [[ADR-003 Product Visual Language and Token Semantics]] | **Accepted** |
| 2 | The exact palette values (§6.1) | **Approved as implemented** |
| 3 | `--color-accent` / `--color-accent-fill` as separate semantic roles | **Approved** |
| 4 | Instrument Serif, display-only at `--text-2xl` and above | **Approved** |
| 5 | The dedicated `nav-*` token family | **Approved** |
| 6 | Cinematic cues structural only | **Approved** |

### Two corrections required at the gate

The owner approved the work and required two documentation corrections before completion. Both were made; neither changed a token value.

**1. Scope clarification.** The step's original wording (*"No application styling is implemented"*, *"No application code changes."*) forbade the runtime token layer from existing, which contradicts what a design foundation is for. Corrected in [[#Scope]], [[#Out of Scope]] and [[#Definition of Done]], with the superseded wording preserved beside each correction rather than deleted.

**2. Accent wording.** The prose overstated the split — ADR-003 claimed the two roles held *"different values in light mode"* while parenthetically contradicting itself, and [[Design System]] led with the divergence rather than the reason for it. Corrected in both: they are **two separate semantic roles** that **currently resolve to the same value in light mode (`#C84016`) and diverge in dark mode** (`#F0663A` foreground, `#E2511F` fill). They are separate for semantic correctness and independent accessibility/theme evolution — **not** because they must always resolve to different primitives. The values themselves were not touched.

## Audit Gaps Closed

Design system (tokens) — *Foundation / Partial*

---

## Navigation

- **Previous:** [[STEP-25a Foundation Remediation]]
- **Next:** [[STEP-27 Storage Provider Abstraction]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
