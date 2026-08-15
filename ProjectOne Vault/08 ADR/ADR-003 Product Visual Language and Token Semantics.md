---
title: "ADR-003: Product Visual Language and Token Semantics"
category: ADR
status: review
version: "1.0"
last_updated: 2026-08-15
tags: [adr, decision, design, frontend, accessibility]
adr_number: "0003"
---

# ADR-003: Product Visual Language and Token Semantics

## Status

**Review** — proposed by [[STEP-26 Product Design System Foundation]] on 2026-08-15, awaiting the project owner's decision.

**Not binding, and nothing may be built against it yet.** [[CLAUDE|CLAUDE.md]] §7 permits implementation only once an ADR reaches `Accepted`, and the approver is the project owner — Claude drafts and recommends, and does not self-approve its own architectural proposals. Until that happens, [[Design System]]'s existing slate/indigo tokens remain the only ones a component may be built against.

## Context

The project owner approved a new visual direction on 2026-08-14: a warm ivory/cream canvas, matte-black navigation, burnt-orange/vermilion accent, editorial typography and cinematic production cues — explicitly *not* a dark interface, *not* blue/purple AI gradients, *not* glassmorphism-heavy, and *not* a generic KPI-card dashboard. That decision superseded the dark direction in [[Design Backlog and UI Vision]] and is recorded, with its concept reference `ProjectOne_Product_Design_Direction_v1.0.png`, in [[STEP-26 Product Design System Foundation]].

**An approved adjective is not a token value.** [[Design System#14. Long-Term Vision]] states the gap precisely: the direction is approved but not yet expressed as token values, and *a component cannot be built against an adjective*. STEP-26 exists to close that gap. This ADR exists because closing it turns out to require more than repointing a mapping.

### Why this needs an ADR at all

[[STEP-26 Product Design System Foundation]] carries an explicit checkpoint: *if this changes foundational token values or shared component contracts that other code is built against, an ADR must reach `Accepted` before any step consumes it.* Both halves of that condition are met, and the second is the one that matters.

**The token values change, but that alone would not trigger it.** [[Design System#6.5 How to change a token]] documents rebranding as a routine, supported procedure: edit the primitives, repoint the semantic mapping, re-run contrast, touch no component. [[STEP-14 Design System Tokens]] proved that property with a swap test, and the owner's own framing at the time was that *all tokens are expected to change without requiring component rewrites*. A pure revalue is therefore **operational**, not architectural — exactly what §3a was built to absorb.

**What triggers the checkpoint is that the semantic layer itself gains new roles.** Verifying this palette against WCAG AA (§6.3) produced four measured failures that cannot be fixed by repointing an existing token, because the roles they represent do not exist yet:

| Measured failure | Ratio | Bar | Why no existing token fixes it |
|---|---|---|---|
| `--color-accent` as text on the ivory canvas | 4.39 | 4.5 | Darkening the accent until it passes as text makes the *fill* darker than the approved vermilion. Text and fill are two roles with two different bars. |
| `--color-accent` as text on matte-black navigation | 3.99 | 4.5 | The accent tuned against ivory is too dark on near-black. This is the same one-step-lighter rule §6.2 already states for dark mode — but navigation is dark *inside the light theme*, where that rule does not currently reach. |
| Navigation muted text on raised navigation | 4.49 | 4.5 | Navigation foregrounds sit on a dark surface in both themes, so they cannot share the canvas text tokens. |
| `--color-border-strong` on the ivory canvas | 2.87 | 3.0 | The single value that satisfies navigation's muted-text bar fails the interactive-boundary bar on ivory. One token, two irreconcilable requirements. |

Each is the same shape of problem [[Design System#6.2 Semantic tokens (v1)]] already solved twice — once by splitting `--color-border` from `--color-border-strong`, once by adding `--color-skeleton` when a skeleton built on `surface-raised` turned out to be invisible at 1.05:1. In both cases the fix was a **new named role**, and the note records why: *a missing semantic token is a design decision, not a licence to use a primitive.*

**Adding roles to the semantic layer is a change to the contract components are built against.** Every component in `apps/web` references that layer and nothing else — verified, not assumed: an inventory of the 19 semantic utility classes in use found **zero** hex codes, zero primitive references, zero Tailwind default palette classes and zero `dark:` variants outside a comment. That layer is the shared interface, so extending it is an architectural decision under [[CLAUDE|CLAUDE.md]] §7, and §39's ambiguity rule resolves toward the ADR in any case.

### The forces

- **The owner's approved direction is binding input, not a proposal to re-litigate.** This ADR decides how to express it in tokens, never whether to adopt it.
- **WCAG AA is a constraint on the palette, not a review step** ([[Design System#6.3]]). A palette that fails contrast is a broken interface, and "it looks fine in the mockup" is exactly how the two live failures found during STEP-14 were originally missed.
- **The concept reference is direction, not specification.** It illustrates one dashboard containing surfaces that do not exist today. Treating it literally would produce blueprints for domains STEP-26 explicitly excludes.
- **Components must not need editing.** The rebrandability §3a guarantees is the property most worth protecting; a change that breaks it costs more than the palette is worth.
- **The vermilion in the reference is a fill colour.** Measured, it is around 3.6:1 against white — below the 4.5 text bar by construction. Any honest expression of it must separate where it fills from where it writes.

## Decision

### 1. The visual direction becomes token values, in the existing two-layer architecture

The direction is expressed entirely within [[Design System#3a. Token Architecture]] — primitives repointed, semantic layer remapped. **No third layer, no theme-aware components, no `dark:` variants.** The exact values are specified in [[Design System]] §4–6 as amended by STEP-26.

The identity in one line: **an ivory canvas the interface sits on, a matte-black navigation rail it hangs from, and a single vermilion accent used sparingly enough to still mean something.**

### 2. Four semantic roles are added, each because a measurement forced it

This is the substantive half of the decision and the reason an ADR is required.

| New token | Light | Dark | The role it names |
|---|---|---|---|
| `--color-accent-fill` | `verm-600` `#C84016` | `verm-500` `#E2511F` | The accent as a **background** carrying text on top. Bar: 4.5 for its `*-contrast` foreground, 3:1 against surfaces. |
| `--color-nav-surface` | `ink-900` `#121110` | `ink-950` `#0F0E0D` | The matte-black navigation plane — a dark surface **inside the light theme**, which the existing surface tokens cannot describe. |
| `--color-nav-surface-raised` | `ink-800` `#232120` | `char-800` `#1A1816` | The active/hovered navigation item. |
| `--color-text-on-nav` / `--color-text-on-nav-muted` | `ivory-100` / `ink-400` | `ivory-200` / `ink-400` | Navigation foregrounds. They sit on a dark plane in **both** themes, so they cannot share the canvas text tokens. |
| `--color-accent-on-nav` | `verm-400` `#F0663A` | `verm-400` `#F0663A` | The accent **on** the navigation plane. Identical in both themes, because the plane it sits on is dark in both. |

`--color-accent` and `--color-accent-fill` are deliberately **different values in light mode** (`#C84016` vs the same primitive) and deliberately **diverge in dark mode**. That split is the honest expression of the owner's vermilion: bright enough to fill, dark enough to read.

`--color-border-strong` is repointed to a new `ink-450` primitive, distinct from the `ink-400` that navigation's muted text needs. One value could not satisfy both bars.

### 3. Navigation is a first-class surface family, not a styled sidebar

The matte-black rail is dark in the light theme. Every existing surface/text/border token assumes foreground and background move together with the theme; navigation breaks that assumption, and painting it with canvas tokens plus overrides is how components become theme-aware.

**Consequence, stated as a rule:** a component rendering inside the navigation plane references the `nav-*` family, and a component rendering on the canvas never does.

### 4. Contrast is verified by an executable check, not by inspection

The verification that produced this ADR's four corrections is committed as `scripts/check-contrast.py` and enumerates **every** foreground against **every** surface it can appear on, in both themes — 90 pairings. Not a hand-picked list: [[Design System#6.3]] records that a hand-picked list is precisely how `--color-surface-raised` went unverified and shipped two live failures.

It is wired into the `web` CI job, so a future token change that breaks a pairing fails the build rather than reaching review. This converts §6.3's rule — *any future token change must be re-checked the same way* — from an instruction someone must remember into a check that runs.

**Skeleton fills are checked at a 1.2:1 visibility floor, not 3:1.** A skeleton is informational, not operable, so WCAG's non-text bar does not apply — but it must be distinguishable, which is the defect that created `--color-skeleton` in the first place.

### 5. Editorial typography is a display/body split, and the body face does not change

**Inter is retained for UI and body text.** It was chosen for legibility at small sizes and a neutral tone that does not date; nothing in the new direction argues against it, and replacing a working body face is cost with no benefit.

**A serif display face is added for editorial moments only** — page titles and the few large headings where the direction's "editorial" quality actually lives. Bounded deliberately: `--font-display` applies at `--text-2xl` and above, never to body copy, labels, table cells or controls.

The recommended face is **Instrument Serif** (SIL Open Font License, self-hosted via `next/font`, one weight). Rationale: a high-contrast, tight-fitting display serif that reads as editorial rather than institutional, and one weight keeps the added payload to a single file. **This is the choice most open to owner substitution** and the cheapest to change — it is one primitive and one `next/font` import.

`--font-mono` is unchanged.

### 6. Weights remain three, and no weight above 600 is introduced

The direction's "editorial" quality comes from the display face, the type scale and generous spacing — not from heavier weights. [[Design System#5.3]]'s reasoning stands: bold headings in a calm interface read as shouting.

## Alternatives Considered

- **Repoint the existing tokens only; add nothing.** The smallest change and the one §6.5 describes as routine. **Rejected on measurement:** it leaves four pairings failing WCAG AA. The only way to satisfy them within the existing token set is to darken the accent until the fill is no longer the approved vermilion, and to paint navigation with canvas tokens — which forces per-component overrides and breaks §3a's no-theme-aware-components rule. Rejecting the accessible expression of the owner's direction in order to avoid an ADR would be the wrong trade.

- **Give navigation its own local CSS scope** (a `.nav { --color-surface: ... }` block remapping the canvas tokens inside the rail). Genuinely tempting: it adds no token names and navigation components would keep saying `bg-surface`. **Rejected** because it makes a token's meaning depend on where in the tree it is read. A reader of `bg-surface` could no longer know what colour it produces without knowing its ancestors, and the scope would silently capture any component that ever renders inside navigation. Explicit `nav-*` names cost five tokens and keep every reference unambiguous.

- **One accent value used for both fill and text.** What the concept reference literally shows. **Rejected on measurement:** the reference's vermilion is roughly 3.6:1 against white and fails the 4.5 text bar. A single value either fails AA or is too dark to be the approved accent — the split is what makes the direction implementable rather than aspirational.

- **Replace Inter entirely with an editorial serif.** A stronger reading of "editorial typography". **Rejected:** serif body text at 14px in dense product surfaces (tables, forms, metadata) costs real legibility, which §5.1 and §9 both make non-negotiable. The direction's editorial character is carried by display moments; making every table cell a serif is how the concept's *feel* becomes the product's *problem*.

- **Defer the whole palette to STEP-80 and ship only rules now.** **Rejected:** it reproduces exactly the state [[Design System#14]] names as unworkable — an approved direction that no component can be built against — and it would leave every screen between here and STEP-80 inheriting a palette the owner has already replaced.

## Consequences

**Easier:**

- Every screen from here inherits one visual language, and the owner's direction stops being an adjective.
- Contrast regressions become build failures rather than review findings or, worse, shipped defects.
- Navigation's dark-inside-light problem is solved once, by name, instead of per screen.
- `success` and `warning` now clear the **4.5 text bar** in light mode, where the outgoing slate/indigo values sat at 3.15 and 3.04 and were usable only for icons and fills. That is a capability the palette previously lacked.

**Harder / accepted costs:**

- **Five new semantic tokens to learn**, and a rule about when navigation tokens apply. Mitigated by naming them for their role and by the CI check catching misuse of the wrong surface family.
- **One additional font file.** Bounded to a single weight, self-hosted, and applied only at `--text-2xl` and above.
- **The `accent` / `accent-fill` split is a genuine subtlety.** A developer reaching for `bg-accent` instead of `bg-accent-fill` gets a slightly dark fill rather than a broken one — a quiet failure mode. Mitigated by the token table stating the rule and by CI checking the pairings, but it is the part of this decision most likely to be got wrong in practice, and it is recorded here as such rather than glossed.

**Follow-up this creates:**

- **No component changes in STEP-26.** The step implements the token layer and the documentation only; [[STEP-80 Product-wide UI Rebuild]] is where screens adopt it.
- **The `nav-*` family has no consumer until STEP-80.** `SidebarNav` currently paints itself with canvas tokens and will keep rendering correctly until then — the new tokens are defined and verified but unused, which is deliberate: STEP-26's scope forbids restyling any screen.
- The swap test in [[STEP-14 Design System Tokens]] remains the standing proof of §3a and is re-run against these values.

## Related

- Related notes: [[Design System]] · [[STEP-26 Product Design System Foundation]] · [[STEP-14 Design System Tokens]] · [[Design Backlog and UI Vision]] · [[STEP-80 Product-wide UI Rebuild]] · [[Frontend Architecture]]

---

## Navigation

- **Parent:** [[Development MOC]]
- **Related Notes:** [[ADR-001 Technology Stack]] · [[ADR-002 Trusted Proxy and Client Address Resolution]] · [[Design System]]
