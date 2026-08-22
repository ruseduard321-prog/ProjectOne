---
title: Design System
category: Design
status: stable
version: "2.4"
last_updated: 2026-08-22
tags: [design, documentation, feature]
aliases: ["Design System & Visual Language", "Visual Language"]
source_pdf: "[[12 Assets/PDF/ProjectOne_Design_System_Visual_Language_v1.0.pdf|ProjectOne_Design_System_Visual_Language_v1.0.pdf]]"
---

# ProjectOne Design System & Visual Language v1.0

## Purpose

This document defines the visual identity and user experience principles of ProjectOne. Its objective is to ensure that every screen feels intentionally designed, premium, consistent and timeless regardless of whether it is created by a human designer or an AI assistant.

## 0. Visual Language

> [!important] Owner-approved direction and owner-approved values
> The direction below was approved on 2026-08-14; the token values expressing it (§4–6) were approved on **2026-08-15** through [[ADR-003 Product Visual Language and Token Semantics]] (`Accepted`), written by [[STEP-26 Product Design System Foundation]]. **Both are binding.**
>
> Concept reference: `ProjectOne_Product_Design_Direction_v1.0.png` in `12 Assets/Images`. **It is direction, not a screen specification.** It illustrates surfaces that do not exist today; the rules below are what is binding, not the pixels in that image.

> [!important] A set of changes to this document is **accepted and not yet applied** — 2026-08-22
> The **Design Phase 2 Artifact** (`ProjectOne Vault/12 Assets/Prototypes/design-phase-2/`, preserved as `5d10a81`) is the complete product-experience blueprint in this direction. It is an approved design **reference**, not executable production authority, and it does not change anything in this document by existing.
>
> [[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]] settles a bounded set of changes arising from it, and was **approved by the project owner on 2026-08-22**. All 13 of its decisions are binding.
>
> **Binding, but not yet applied here.** [[STEP-31a Product Experience Blueprint Alignment]] delivers them and is `Not Started`, so **every value, rule and contract in this document below still stands exactly as written**, and `apps/web/src/app/globals.css` is unchanged. A reader implementing today follows this document; a reader planning follows ADR-007. The two converge when STEP-31a lands, which is the change that will edit the sections named below.
>
> What will change, and where — recorded so a reader knows what is settled and pending application, not duplicated from the Artifact's own documents:
>
> | Section | Proposed change | Kind |
> |---|---|---|
> | §6.1, §6.2 | `--ivory-75` added; light `--color-surface` → `ivory-75`, light `--color-surface-raised` → `ivory-50` | Routine revalue under §6.5 — owner sign-off on the §6.1 specification change, no ADR |
> | §6.1, §6.2 | `--ink-975` added; dark `--color-nav-surface` → `ink-975` | Same mechanism, but it narrowly supersedes a value printed in [[ADR-003 Product Visual Language and Token Semantics]] Decision 2, so it needs ADR-007 |
> | §6.2, §6.4 | Native `color-scheme` on `:root`, and a three-state `[data-theme]` cascade beside `prefers-color-scheme` | New shared runtime contract |
> | §5.2 | `--text-4xl: 3.25rem` (52px), line-height `1.05` — **owner-selected 2026-08-22.** The **1.25 scale applies through `--text-3xl`**, and `--text-4xl` is documented as a deliberate **display-only exception**, validated by the Artifact's measured composition rather than derived from the ratio | New token + a stated exception to §5.2 |
> | §6.2 | An **inverted-surface** semantic family, so canvas components stop reaching for `nav-*` and for raw primitives. Approved **in principle**; membership derived from real consumers and values from contrast measurement — and **if no current consumer justifies a role, nothing is added** | New token semantics |
> | §7 | Three page-template contracts — **Cockpit, Workbench, Focus** — selected by a **server-rendered shared layout primitive** emitting `data-template`. `<body>` keeps global theme behaviour only; no client mutation, no hydration race, no prototype-chrome dependency | New shared contract |
> | §8 | Motion tokens replacing §8's prose-only specification | New tokens |
> | §9.2 | **Playwright** as the shared browser-testing contract, wired into required CI — owner-approved 2026-08-22 | New testing contract |
>
> **On the role count.** Measured *before adoption*, the Artifact's semantic role set matches production exactly — twenty-two on each side, none added, none dropped — which is why its colour work is §6.5 procedure rather than architecture. That is **not** a claim that the production role set stays at 22: the inverted-surface family above would grow it, by roles the Artifact needed but never named.
>
> **The Artifact's "roughly 64px" sentence is stale prose.** It implements `3.25rem` = 52px, which is the value the composition was measured against and the value the owner selected. **The preserved Artifact is not edited to correct it** — it is a preserved record, and this document is authority rank 1.
>
> **The Artifact's `QA.md` discharges no check in this document.** It measures the prototype against itself in a `data:` harness. Production contrast verification is `scripts/check-contrast.py` in CI (§6.3), which `QA.md` never ran and — the palettes having diverged — could not have run.
>
> **Four owner decisions of 2026-08-22 are settled inputs, not open questions:** the `--text-4xl` value above; Playwright as the browser-testing contract; that the unowned activity/audit and workflow-run surfaces do **not** gate the ADR and are created by neither it nor STEP-31a; and two standing product constraints — **ProjectOne shows no third-party advertising, and does not buy, bid or place media.**
>
> Adoption is bounded and sequenced: [[STEP-31a Product Experience Blueprint Alignment]] takes the shared foundation for routes that already exist and rebuilds no domain page; each later frontend step consumes the blueprint when it builds its own surface; [[STEP-79 Domain Screen Blueprints]] reconciles the blueprint against the real product; [[STEP-80 Product-wide UI Rebuild]] implements it product-wide. See [[Design MOC#Authority Order]].

ProjectOne looks like a **production studio's workspace**, not a SaaS dashboard. The identity in one line:

> **An ivory canvas the interface sits on, a matte-black rail it hangs from, and a single vermilion accent used sparingly enough to still mean something.**

Stated as rules, so they can be checked rather than admired:

1. **The canvas is warm ivory, never white and never grey.** Grey is the default every framework ships; the cream cast is the identity. No neutral-grey value exists in the palette (§6.1).
2. **Navigation is matte black in both themes.** It is a fixed dark plane the product hangs from — the one element that does not change with the theme, and the reason `nav-*` is its own token family (§6.2).
3. **One accent, used sparingly.** Vermilion marks the primary action, the active location, and state that needs attention. **A screen with vermilion in five places has none** — if everything is accented, nothing is.
4. **Typography carries the personality; decoration does not.** The editorial serif at display sizes is where the character lives (§5.1a). Everything else is Inter, quiet and legible.
5. **Depth comes from surface and spacing, not shadow.** Three restrained elevation levels exist and signal what floats above what (§4.3). Ivory surfaces separate by tone, not by drop shadow.
6. **Cinematic cues are structural, never skeuomorphic.** Duration badges on media, filmstrip rhythm in galleries, generous margins around content. **No paper textures, no tape, no torn edges, no film-grain overlays** — the concept reference uses them as illustration; the product does not.
7. **Nothing that reads as generic AI.** No blue/purple gradients, no glassmorphism, no glow, no KPI-card grid as a default layout (§13).

**What this is not:** a dark interface, a Linear/Vercel clone, or a template aesthetic. §13's anti-patterns apply with full force, and "it looked good in the reference" is not an argument against them.

## 1. Design Philosophy

ProjectOne should feel calm, professional, premium and trustworthy. The interface must help users think clearly rather than impress them with visual effects.

## 2. Emotional Goals

Users should feel in control, productive and confident. Avoid visual noise, unnecessary decoration and playful elements that reduce perceived quality.

## 3. Core Principles

- Simplicity over decoration.
- Consistency over creativity.
- Readability over density.
- Function before aesthetics.
- Every pixel must have a purpose.

## 3a. Token Architecture

> [!important] These values are **v1 initial values, not permanent branding**
> Every number and hex code in §4–6 is expected to change. The architecture below exists so that changing them is a **one-line edit to a mapping**, never a change to a component. A design system whose values cannot be replaced without touching components is a design system that will be abandoned the first time branding changes.

**Two layers, and components may only reference the second.**

| Layer | Example | Who may reference it |
|---|---|---|
| **Primitive** — a raw value with no meaning | `--color-neutral-900`, `--color-accent-600` | The semantic layer only. **Never a component.** |
| **Semantic** — a role, with no intrinsic value | `--color-surface`, `--color-accent`, `--color-danger` | Components, exclusively. |

The indirection is the whole point. A button that says `bg-blue-600` hardcodes a brand decision into a component, and rebranding then means editing every button that ever shipped. A button that says `bg-accent` states its *intent*, and rebranding is one line in the mapping.

**The binding rule:**

> A component references a **semantic** token or it references nothing. Any component naming a primitive, a hex code, a pixel value or a Tailwind default palette class (`bg-blue-600`, `p-[13px]`, `#3b82f6`) is a defect, not a style choice.

**Why this survives a rebrand.** Replacing the palette means reassigning `--color-accent` from one primitive to another. Every component that says `bg-accent` follows automatically, because none of them ever knew what the accent *was*. The same holds for the spacing scale, the type scale and the radius scale.

**Three consequences worth stating, because they are what people get wrong:**

- **Semantic names describe role, never appearance.** `--color-danger`, not `--color-red`. The day errors stop being red, a token called `red` is either wrong or a lie, and both are worse than a rename.
- **A missing semantic token is a design decision, not a licence to use a primitive.** If a component needs a color with no semantic name, the correct move is to add the token — which forces the question "what role is this?" — not to reach past the layer.
- **Dark mode is a remapping, not a second set of components.** The semantic layer points at different primitives; components are untouched and do not know a theme exists.

## 4. Layout

Use a consistent grid, generous whitespace, predictable spacing and clear visual hierarchy. Never overcrowd interfaces.

### 4.1 Spacing scale (v1)

**A 4px base unit**, because it divides cleanly into the 8px rhythm most layout work wants while still allowing tight adjustments — an 8px base forces awkward half-steps, and a 2px base is too fine to enforce any consistency at all.

| Token | Value | Typical use |
|---|---|---|
| `--space-0` | `0` | Reset |
| `--space-1` | `0.25rem` (4px) | Icon-to-label gaps |
| `--space-2` | `0.5rem` (8px) | Tight internal padding |
| `--space-3` | `0.75rem` (12px) | Control padding |
| `--space-4` | `1rem` (16px) | Default element gap |
| `--space-6` | `1.5rem` (24px) | Card padding, group separation |
| `--space-8` | `2rem` (32px) | Section separation |
| `--space-12` | `3rem` (48px) | Major layout blocks |
| `--space-16` | `4rem` (64px) | Page-level rhythm |

Deliberately **non-continuous** — there is no `--space-5`, `--space-7`, `--space-9`. A gapped scale is a constraint: it makes "which spacing?" a choice between a few defensible options instead of an arbitrary number, which is how spacing stays consistent without anyone policing it.

`rem` rather than `px` so spacing respects a user's browser font size — a hard accessibility requirement, not a preference (§9).

### 4.2 Radius scale (v1)

| Token | Value | Use |
|---|---|---|
| `--radius-sm` | `0.25rem` (4px) | Inputs, small controls |
| `--radius-md` | `0.5rem` (8px) | Buttons, cards |
| `--radius-lg` | `0.75rem` (12px) | Dialogs, panels |
| `--radius-full` | `9999px` | Avatars, pills |

Four values, deliberately. §13 names "random border radii" as an anti-pattern, and the only reliable defence is having too few options to improvise with.

### 4.3 Elevation (v1)

| Token | Value | Use |
|---|---|---|
| `--shadow-sm` | `0 1px 2px rgb(0 0 0 / 0.05)` | Resting cards |
| `--shadow-md` | `0 4px 6px -1px rgb(0 0 0 / 0.08)` | Dropdowns, popovers |
| `--shadow-lg` | `0 10px 20px -5px rgb(0 0 0 / 0.12)` | Dialogs |

Three levels, all restrained — §13 forbids excessive shadows, and depth in a calm interface comes from spacing and surface color far more than from shadow. **Elevation is not a decoration; it signals what floats above what.** If two things are on the same plane, they get the same shadow.

## 5. Typography

Use a modern sans-serif typeface with a defined type scale. Limit font weights and establish consistent heading, body and caption styles.

### 5.1 Typeface (v1)

**Inter**, with a system-font fallback stack:

```
--font-sans: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
--font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
```

Chosen for legibility at small sizes and a neutral, professional tone that carries the "calm, premium, trustworthy" goal in §1 without personality that dates. **Self-hosted via `next/font`, never a CDN link** — a third-party font request is a render-blocking dependency on someone else's uptime and a privacy leak of every visitor's IP to that host.

The fallback stack is not decoration: it is what renders during load and on failure, and a stack ending in bare `sans-serif` produces a visibly different page. `--font-mono` exists for one reason — ids, tokens and code fragments, where proportional digits actively mislead.

### 5.1a Display face (v2)

**Instrument Serif**, one weight (400), self-hosted via `next/font` on the same terms as Inter.

```
--font-display: var(--font-instrument-serif), Georgia, "Times New Roman", serif;
```

**Bounded deliberately: `--text-2xl` and above, and nothing else.** Page titles and the few large headings where the direction's editorial quality actually lives. **Never** body copy, labels, table cells, controls, captions or metadata.

The boundary is the whole decision. A serif at 14px in a dense table costs real legibility, which §9 makes non-negotiable — the editorial character belongs in display moments, and making every cell a serif is how the concept's *feel* becomes the product's *problem*. Inter remains the body and UI face, unchanged: it was chosen for legibility at small sizes and a tone that does not date, and nothing in the new direction argues against it.

One weight, because only display sizes use it and additional weights would be payload nothing renders.

**This is the choice most open to owner substitution**, and the cheapest to change — one primitive and one `next/font` import ([[ADR-003 Product Visual Language and Token Semantics]] §5).

### 5.2 Type scale (v1)

A **1.25 (major third)** ratio, rounded to sensible pixel values:

| Token | Size | Line height | Use |
|---|---|---|---|
| `--text-xs` | `0.75rem` (12px) | 1.5 | Captions, metadata, timestamps |
| `--text-sm` | `0.875rem` (14px) | 1.5 | Secondary text, table cells, labels |
| `--text-base` | `1rem` (16px) | 1.6 | Body — the default |
| `--text-lg` | `1.125rem` (18px) | 1.5 | Lead paragraphs, card titles |
| `--text-xl` | `1.5rem` (24px) | 1.4 | Section headings |
| `--text-2xl` | `1.875rem` (30px) | 1.3 | Page titles |
| `--text-3xl` | `2.25rem` (36px) | 1.2 | Display, used sparingly |

**Line height tightens as size grows**, which is not arbitrary: long body lines need vertical breathing room to track from line to line, while a large heading with generous leading reads as disconnected words rather than one phrase.

`1rem` body minimum. Anything below 12px is not used for content — §9 and §3 both make readability non-negotiable, and "it's just metadata" is how interfaces become unusable for anyone over forty.

### 5.3 Weights (v1)

**Three only:** `400` regular, `500` medium, `600` semibold.

§5 says limit font weights, and three is the smallest set that expresses body / emphasis / heading. **No `700`+**: bold headings in a calm interface read as shouting, and hierarchy here comes from size and color, not weight. Every additional weight is also another font file to load.

## 6. Color System

Maintain a restrained palette with one primary accent color and limited semantic colors for success, warning and error states. Avoid excessive gradients and saturated colors.

### 6.1 Primitives (v2)

Raw values. **No component may reference these.**

> [!important] These values were **approved by the owner on 2026-08-15**
> They express the owner-approved visual direction — warm ivory canvas, matte-black navigation, vermilion accent — as concrete numbers, and were accepted through [[ADR-003 Product Visual Language and Token Semantics]]. Changing them is a specification change governed by §6.5, and changing the *semantics* around them requires a superseding ADR.
>
> The v1 slate/indigo values this replaces are recorded in [[STEP-14 Design System Tokens]] and in git history.

The palette is warm throughout. **No value in it is neutral grey**, and that is the single decision the identity rests on: a cream canvas and warm near-blacks are what separate this product from the default admin panel that every framework ships with (§13, §14).

| Ramp | 50 | 100 | 200 | 300 | 400 | 450 | 500 | 600 | 700 | 800 | 900 | 950 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Ivory** — the canvas | `#FFFDF8` | `#FAF6EE` | `#F2ECE1` | `#E4DBCB` | `#CFC4B0` | — | — | — | — | — | — | — |
| **Ink** — warm near-blacks | — | — | — | — | `#9A9189` | `#8F867E` | `#6E665F` | `#57504A` | `#3A3531` | `#232120` | `#121110` | `#0F0E0D` |
| **Charcoal** — dark surfaces | — | — | — | — | — | — | — | `#332F2C` | `#242120` | `#1A1816` | — | — |
| **Vermilion** — the accent | — | — | — | `#F58555` | `#F0663A` | — | `#E2511F` | `#C84016` | `#A83512` | — | — | — |
| **Green** — success | — | — | — | — | `#5FA971` | — | — | `#2F6B3D` | — | — | — | — |
| **Amber** — warning | — | — | — | — | `#D9A339` | — | — | — | `#7A5A0C` | — | — | — |
| **Red** — danger | — | — | — | — | `#EF7A68` | — | — | `#C0341F` | — | — | — | — |

**Pure black is deliberately absent**, as it was in v1 and for the same reason: `#000` is harsher on screen than a warm near-black and is the fastest way to make an interface feel cheap. The matte-black navigation is `ink-900` `#121110` — black enough to read as matte, warm enough to belong to the ivory beside it.

**`ink-450` exists because one value could not serve two bars.** Navigation's muted text needs 4.5:1 on a dark plane; an input's edge needs 3:1 on ivory. `ink-400` satisfies the first and fails the second at **2.87**. Splitting them is the same move that produced `--color-border-strong` in v1 — see §6.3.

**Two vermilion steps carry the accent, not one.** `verm-500` `#E2511F` is the fill hue from the approved direction. Measured as *text* on ivory it is **3.82**, below the 4.5 bar. `verm-600` `#C84016` is the step that survives as text. This is not a compromise on the direction; it is what the direction costs to implement accessibly, and §6.2 names both roles.

**The semantic hues are muted toward the warm palette** rather than taken from the pure spectrum, and all three now clear the **4.5 text bar** in light mode. The v1 values cleared only 3:1 (success `3.15`, warning `3.04`) and were therefore usable for icons and fills but **never for running text** — a limitation §6.3 recorded and this palette removes.

### 6.2 Semantic tokens (v2)

**This is the only layer components may reference.**

#### Canvas tokens

The interface that sits *on* the ivory.

| Token | Light | Dark | Role |
|---|---|---|---|
| `--color-background` | `ivory-100` | `ink-950` | Page canvas |
| `--color-surface` | `ivory-50` | `char-800` | Cards, panels — sits *above* the canvas |
| `--color-surface-raised` | `#ffffff` | `char-700` | Dropdowns, dialogs |
| `--color-border` | `ivory-300` | `char-600` | **Decorative** dividers and separators |
| `--color-border-strong` | `ink-450` | `ink-400` | **Interactive** boundaries — input outlines, control edges |
| `--color-text` | `ink-900` | `ivory-200` | Primary content |
| `--color-text-muted` | `ink-500` | `ink-400` | Secondary, captions, placeholders |
| `--color-accent` | `verm-600` | `verm-400` | The accent **as text or as a border** |
| `--color-accent-hover` | `verm-700` | `verm-300` | Accent hover/press |
| `--color-accent-fill` | `verm-600` | `verm-500` | The accent **as a background** carrying text on top |
| `--color-accent-contrast` | `#ffffff` | `ink-950` | Text **on** `--color-accent-fill` |
| `--color-success` | `green-600` | `green-400` | Confirmation |
| `--color-warning` | `amber-700` | `amber-400` | Caution |
| `--color-danger` | `red-600` | `red-400` | Errors, destructive actions |
| `--color-danger-contrast` | `#ffffff` | `ink-950` | Text **on** a danger surface |
| `--color-skeleton` | `ivory-300` | `char-600` | Loading placeholder fill (§10) |
| `--color-focus-ring` | `verm-600` | `verm-400` | Focus indicator (§9) |

#### Navigation tokens

**Navigation is its own surface family, not a styled sidebar.** The rail is dark in the *light* theme, which no canvas token can describe: every pairing above assumes foreground and background move together with the theme, and navigation breaks that assumption.

| Token | Light | Dark | Role |
|---|---|---|---|
| `--color-nav-surface` | `ink-900` | `ink-950` | The navigation plane |
| `--color-nav-surface-raised` | `ink-800` | `char-800` | Active / hovered navigation item |
| `--color-text-on-nav` | `ivory-100` | `ivory-200` | Navigation labels |
| `--color-text-on-nav-muted` | `ink-400` | `ink-400` | Secondary navigation text, section labels |
| `--color-accent-on-nav` | `verm-400` | `verm-400` | The accent **on** the navigation plane |

**The binding rule:** *a component rendering inside the navigation plane references the `nav-*` family; a component rendering on the canvas never does.* Painting navigation with canvas tokens plus overrides is how components become theme-aware, which §6.4 forbids.

`--color-accent-on-nav` is **identical in both themes**, because the plane it sits on is dark in both. The light-mode `--color-accent` measures **3.99** on `nav-surface` and fails AA outright — this is the same one-step-lighter rule §6.2 has always stated for dark mode, applied to a dark region that happens to live inside the light theme.

#### Two accent roles, and this is the one most likely to be got wrong

`--color-accent` and `--color-accent-fill` are **two separate semantic roles**, which **currently resolve to the same value in light mode (`#C84016`) and diverge in dark mode** (`#F0663A` as a foreground, `#E2511F` as a fill).

**Separate because the roles are genuinely different, not because the values must always be.** They answer different questions and carry different accessibility bars:

- **`--color-accent`** is the accent *as a foreground* — link text, an active label, an icon, a border. Bar: **4.5:1** against every surface it appears on.
- **`--color-accent-fill`** is the accent *as a background* — a primary button, a filled badge, a progress bar. Bar: **3:1** against the surface behind it, and 4.5:1 for `--color-accent-contrast` on top of it.

The approved vermilion is a fill colour: as text it is 3.82 on ivory. Collapsing the two would mean either failing AA or darkening the brand until it is no longer the approved accent.

**The matching light-mode value is a fact about today's palette, not a property of the design.** Naming both roles is what lets either be retuned — for a theme, for a contrast correction, for a rebrand — without dragging the other with it. Dark mode already exercises that independence. A token that exists only while two numbers differ would have to be reintroduced the moment they do, which is why `--color-border` / `--color-border-strong` and `--color-skeleton` are separate roles on the same reasoning.

> [!warning] The quiet failure mode
> Reaching for `bg-accent` where `bg-accent-fill` belongs produces a *slightly dark fill* — it looks fine, so nothing catches it in review. It is recorded here, and in [[ADR-003 Product Visual Language and Token Semantics]], as the known sharp edge of this system rather than glossed over.

**`*-contrast` tokens exist so no component ever guesses what text colour survives on a coloured background.** That guess is where contrast failures come from, and it is a solved problem once the pairing is named. Note `--color-danger-contrast` is **not** white in both themes: white on the lighter dark-mode red fails outright.

**Two border tokens, deliberately.** They have genuinely different requirements and collapsing them fails one of the two: `--color-border` is decorative and tuned to be quiet, while `--color-border-strong` marks an **interactive** boundary and must clear WCAG's 3:1 non-text bar. Using the decorative token on an input is the most likely way to break accessibility while the interface still looks fine to whoever built it.

**`--color-skeleton` is not `--color-surface-raised`.** In light mode that token is `#ffffff` against a near-white canvas — a ratio of **1.05**, invisible. A skeleton is informational, so it must be *distinguishable* even though it is not operable (§6.3).

### 6.3 Contrast is a constraint on the palette, not a review step

Every pairing above targets **WCAG 2.1 AA** — 4.5:1 for text, 3:1 for non-text and interactive boundaries (§9). A palette that fails contrast is not a style disagreement; it is a broken interface for a substantial number of users.

> [!important] This is now an executable check, not an instruction someone must remember
> `scripts/check-contrast.py` enumerates **every** foreground against **every** surface it can appear on, in both themes — **90 pairings** — and runs in the `web` CI job. A token change that breaks a pairing now **fails the build** instead of reaching review.
>
> This exists because the rule below previously depended on someone remembering it, and twice it was not remembered: the first check omitted `--color-surface-raised` entirely and shipped two live dark-mode failures, and a loading skeleton was built against a token that rendered it at 1.05:1. Both are recorded below. **A pairing that is not checked is not passing; it is unknown** — so the script checks all of them rather than a hand-picked list.
>
> Run it locally with `python scripts/check-contrast.py --table` to see every pairing and its margin.

**All 90 pairings pass** as of 2026-08-15 (STEP-26). The script also guards against drift between itself and `globals.css`: it parses the stylesheet's primitives and fails if the two disagree, so the check cannot silently verify a palette the product no longer uses.

**Four failures were found by measurement during STEP-26 and corrected before anything was committed.** Each one is a case where no existing token could be repointed to fix it, which is why [[ADR-003 Product Visual Language and Token Semantics]] was required:

| Pairing | Measured | Bar | Correction |
|---|---|---|---|
| `accent` as text on the ivory canvas | 4.39 | 4.5 | Accent darkened to `verm-600` `#C84016`; the fill hue kept as its own role |
| `accent` as text on matte-black navigation | 3.99 | 4.5 | New `--color-accent-on-nav`, the lighter `verm-400` step |
| Navigation muted text on raised navigation | 4.49 | 4.5 | `ink-400` lightened to `#9A9189` |
| `border-strong` on the ivory canvas | 2.87 | 3.0 | New `ink-450` primitive, distinct from navigation's `ink-400` |

Every one of these looked correct until it was measured. That is the entire argument for the check.

**Skeletons are checked at a 1.2:1 visibility floor, not 3:1.** A skeleton is informational — it says "content is coming" — so WCAG's non-text bar does not apply to it. But it must be *seen*, which is the defect that created `--color-skeleton` in the first place, and an unchecked skeleton is how that defect returns. The floor is a ProjectOne rule, labelled as such in the script's output rather than presented as a WCAG requirement.

The margins worth knowing, because they are where a change will break first:

| Pairing | Ratio | Bar |
|---|---|---|
| `skeleton` on `surface-raised` (dark) | 1.21 | 1.2 (visibility) |
| `skeleton` on `background` (light) | 1.27 | 1.2 (visibility) |
| `border-strong` on `background` (light) | 3.31 | 3.0 |
| `border-strong` on `surface` (light) | 3.51 | 3.0 |
| `accent-fill` on `surface-raised` (dark) | 4.13 | 3.0 |
| `text-on-nav-muted` on `nav-surface-raised` (light) | 4.63 | 4.5 |
| `accent` on `background` (light) | 4.64 | 4.5 |
| `text-muted` on `background` (light) | 5.22 | 4.5 |

**Skeleton fills carry the tightest margins in the system**, by construction: a placeholder that stands out strongly is a placeholder that looks like content. They are the first thing to re-check on any surface change.

`--color-text-muted` now sits at **5.22** on the light canvas, against **4.55** in v1 — the token most likely to fail on a future palette has meaningfully more room than it used to.

**Any future token change must be re-checked the same way.** Contrast is a property of a *pair*, so changing one token silently changes the compliance of every pairing it appears in. This cannot be eyeballed, and "it looks fine" is how it gets missed — which is now enforced rather than requested.

<details>
<summary>Historical: the v1 slate/indigo corrections (2026-08-02, STEP-14)</summary>

The first pass verified against `--color-background` and `--color-surface` only, omitting `--color-surface-raised`. That produced two live dark-mode failures — `--color-text-muted` at 4.04 and `--color-accent` at 4.00 — corrected by moving `--color-surface-raised` to `neutral-800`, `--color-accent` to `accent-400`, `--color-accent-hover` to `accent-200` and `--color-danger` to `danger-400`.

Under v1, light-mode `warning` (3.04) and `success` (3.15) cleared the non-text bar but **not** the 4.5 text bar, so they could not carry running text. The v2 palette removes that limitation.

</details>

### 6.4 Dark mode is in scope

Answered deliberately rather than inherited from the template. The skeleton carries a `prefers-color-scheme` block from `create-next-app`, and the choice is to **implement it properly** — the semantic layer makes it a remapping rather than a second design, so the marginal cost is small and it is far cheaper now than retrofitting once screens exist.

**No component is theme-aware.** A component containing `dark:` variants has leaked a theme decision out of the token layer, which is the same defect as hardcoding a hex.

### 6.5 How to change a token

Written down because "the architecture supports it" is worth nothing if the procedure is folklore.

**To rebrand** — change the accent, or the whole palette:

1. Edit the primitives in §6.1, or add a new ramp.
2. Repoint the affected semantic tokens in §6.2. **This is the only edit that touches behaviour.**
3. Re-run `python scripts/check-contrast.py`, updating the palette **in both** the script and `globals.css` — the script fails if they disagree. Not optional, and now enforced in CI (§6.3).
4. Update this document in the same change, so the vault and the stylesheet cannot disagree ([[CLAUDE|CLAUDE.md]] §19).
5. Rebuild. **No component file is touched at any point.** If one needs to be, the layering has been broken and that is the bug to fix — not the component.

**To add a semantic token** — when a component needs a color, spacing or size with no existing role:

1. Name the **role**, never the appearance (`--color-info`, not `--color-blue`).
2. Map it onto an existing primitive; add a primitive only if genuinely none fits.
3. Check its contrast against every surface it can appear on.
4. Record it in §6.2 before using it.

**What is *not* a valid response to a missing token:** reaching for a primitive, a Tailwind default class, or an inline value "just this once". That is how the layer erodes — never in one decisive moment, always in a series of individually reasonable exceptions.

**Versioning.** These are v1 values and are expected to change. A change to §4–6 is a **specification change**, not a code change: it is recorded here first, and the implementation follows. That ordering is what keeps the document authoritative rather than descriptive.

## 7. Components

Buttons, cards, tables, forms, dialogs and navigation elements must share identical spacing, radius, elevation and interaction behavior across the application.

> [!info] How a step that builds a screen consumes the blueprint
> Any Build Plan step introducing a frontend surface reads the **Design Phase 2 Artifact** as reference for that surface, at authority rank 2 ([[Design MOC#Authority Order]]) — this document and the accepted ADRs outrank it, and the prototype's own CSS and JavaScript rank below both.
>
> Three rules bound that use, and none of them is discretionary:
>
> 1. **The blueprint informs the screen; it does not authorise it.** A route, control or product noun appearing in the Artifact is not scheduled by appearing there. Anything the Artifact labels `Proposed` needs the owner's approval of the capability and an owning step, in that order.
> 2. **No prototype file is copied.** Contracts are re-derived and implemented in the production architecture. The Artifact is not a Tailwind build and proves nothing about how its tokens compile.
> 3. **Where the blueprint and this document disagree, this document wins**, and the step says so rather than resolving it quietly.
>
> A surface built this way is still reconciled at [[STEP-79 Domain Screen Blueprints]] and implemented product-wide at [[STEP-80 Product-wide UI Rebuild]].

### 7.1 Shared component contracts

**A contract is the component's public interface plus the states it is required to define.** Recorded here so a screen consumes a component rather than reinventing one, and so a component's async behaviour is decided once instead of per screen (§10).

These are **the components that exist today**, against surfaces that exist today. No contract is written for a domain that has not been built — a contract for an unbuilt screen is a guess, and guesses in a specification read as decisions.

| Component | Public interface | Required states |
|---|---|---|
| **`EmptyState`** | `title` (noun phrase), `description` (one sentence), `action?` | Terminal — it *is* the empty state |
| **`FormField`** | `id`, `name`, `label`, `type`, `autoComplete`, `error?`, `hint?`, `defaultValue?`, `disabled?`, `placeholder?`, `required?`, `inputMode?` | Default · disabled · **error** (`aria-invalid` + `aria-describedby`) · hint |
| **`SettingsSection`** | `title`, `description`, `aside?`, `children` | Structural — states belong to its children |
| **`StatusBadge`** | `status` | Resting · archived |
| **`SidebarNav`** | none — reads the current route | Resting · hover · **active** (`aria-current="page"`) · focus |
| **`UserMenu`** | `email` | Resting · hover · focus · submitting |
| **`Transcript`** | message list | Loading · empty · error · populated · streaming |
| **`SpendSummary`** | spend figures | Loading · empty · error · populated |
| **`ConfirmDialog`** | `triggerLabel`, `title`, `description`, `cancelLabel?`, `children` | Closed (trigger: resting · hover · focus) · **open** (focus trapped, `Escape` closes, focus returns to the trigger) |

> [!note] `ConfirmDialog` was added by [[STEP-29 Asset Management UI]], and why it was missing is worth recording
> The token layer already named a dialog in three places — `--radius-lg` as "Dialogs, panels" (§4.2), `--shadow-lg` as "Dialogs" (§4.3), `--color-surface-raised` as "Dropdowns, dialogs" (§6.2) — while this table defined none. Not an oversight in either direction: [[STEP-26 Product Design System Foundation]] shipped the tokens and **no components at all**, so the first screen to need a dialog was always going to be the one that wrote its contract.
>
> **It is built on a native `<dialog>`.** `showModal()` supplies the focus trap, the `Escape` handler, the inert background and the top-layer stacking that a hand-built modal must otherwise reimplement correctly — and a modal whose focus escapes is one a keyboard user can lose. The behaviour required of it is §9a rule 2's, generalised from the navigation drawer: trap focus, close on `Escape`, return focus to the control that opened it.
>
> **Cancel is focused first and confirm is never the default.** A destructive action reached by pressing Enter on a dialog the user has not read is the failure the component exists to prevent. There is deliberately no backdrop-click dismissal — a stray click that dismisses is harmless, and the same gesture landing on a confirm button is not.
>
> Verified through the rendered accessibility tree rather than automatically, which §9.2 already names as the standard for dialog work.

**Rules binding on every shared component, current and future:**

1. **Props are explicit, `readonly`, and minimal.** No unrelated data, no prop drilling where composition solves it ([[CLAUDE|CLAUDE.md]] §11).
2. **Presentation only.** No data fetching and no business logic inside a shared component.
3. **Server Component by default.** `"use client"` requires a stated reason in the component's own docstring — `SidebarNav` needs the pathname, `FormField` needs form context. Both say so where they are defined.
4. **Semantic tokens only.** No hex, no primitive, no Tailwind default palette class, no `dark:` variant (§3a, §11).
5. **Every state in the table above is implemented, not assumed.** A component whose error state was never built has an undefined error state, not an absent one.
6. **Accessibility is part of the contract, not a review finding** (§9).

### 7.2 Navigation conventions

**Structure.** A persistent left rail on the matte-black plane, holding top-level product sections. Workspace identity sits at the top, the signed-in user at the bottom. Section order is stable and does not reorder by recency — a navigation that moves is a navigation users must re-read.

**States.** Every navigation item defines four, and all four are required:

| State | Treatment |
|---|---|
| Resting | `--color-text-on-nav-muted` |
| Hover | `--color-text-on-nav` on `--color-nav-surface-raised` |
| **Active** | `--color-accent-on-nav`, on `--color-nav-surface-raised`, **plus `aria-current="page"`** |
| Focus | The standard focus ring (§9), never suppressed |

**`aria-current` is mandatory on the active item, and colour alone never conveys "you are here."** Colour is invisible to assistive technology and to anyone who cannot distinguish the two states — this is WCAG 1.4.1 (use of colour) and it is the single most common navigation accessibility defect.

**Depth is capped at two levels.** A third level is a signal the information architecture is wrong, not a licence to nest further.

## 8. Motion

Animations exist only to improve comprehension. Keep transitions subtle, short and purposeful. Avoid decorative animations.

## 9. Accessibility

Support keyboard navigation, screen readers, sufficient color contrast and visible focus states by default.

**These are system-level rules, not per-screen review findings.** Two of them exist because [[Foundation Audit Findings]] recorded live defects — FA-11 (a root error boundary that announced nothing to assistive technology) and FA-04 (a retry control that did not recover). Both were closed in [[STEP-25a Foundation Remediation]]; the rules below are what stops them recurring per screen.

### 9.1 Binding rules

1. **Contrast is enforced, not reviewed.** WCAG 2.1 AA — 4.5:1 text, 3:1 non-text and interactive boundaries — verified across all 90 pairings by `scripts/check-contrast.py` in CI (§6.3).
2. **Focus is always visible.** A 2px `--color-focus-ring` outline at 2px offset, defined once globally. **`outline: none` without a replacement of equal or better visibility is a defect**, never a style choice.
3. **Colour never carries meaning alone** (WCAG 1.4.1). Every state distinguished by colour also carries text, an icon, or an ARIA attribute. Active navigation carries `aria-current`; an invalid field carries `aria-invalid` and a message, not just a red border.
4. **Every interactive element is keyboard reachable and operable**, in a tab order that follows visual order. No positive `tabIndex`.
5. **Every input has a programmatically associated label** — `htmlFor`/`id`, not placeholder text. A placeholder is not a label: it disappears on focus, exactly when it is needed.
6. **Errors are announced, not only shown.** `aria-invalid` on the field, `aria-describedby` pointing at the message, and `role="alert"` on any error surface that appears after load — the FA-11 rule, generalised.
7. **Heading levels never skip.** The page owns its `h1`; sections use `h2`. Screen readers navigate by heading, so a skipped level makes a screen harder to traverse than an unstyled one.
8. **Regions are labelled.** `aria-label` on `<nav>`, `aria-labelledby` on sections, so assistive technology announces a region by name rather than as anonymous.
9. **Touch targets are at least 44×44px** on coarse pointers.
10. **Motion respects `prefers-reduced-motion`** (§8).
11. **`rem`, never `px`, for spacing and type**, so the interface respects the user's browser font size.

### 9.2 What is checked automatically, and what is not

**Automated:** contrast (CI, all 90 pairings), lint rules for accessibility attributes, `tsc` for required props.

**Not automated, and therefore stated as rules someone must apply:** tab order correctness, whether a label describes its field usefully, whether an error message is actionable, and screen-reader announcement quality. FA-11 was verified through the rendered accessibility tree rather than an automated rule, and that remains the standard for boundary and dialog work.

## 9a. Responsive Behaviour

**Breakpoints, stated once rather than improvised per screen.** Tailwind's defaults, adopted deliberately rather than by inertia — inventing a bespoke set would mean every utility class needs a mental translation:

| Name | Min width | Layout intent |
|---|---|---|
| *(base)* | 0 | Single column. Navigation collapses to a drawer. |
| `sm` | 640px | Single column, wider gutters. |
| `md` | 768px | **The rail appears.** Two-column content becomes viable. |
| `lg` | 1024px | Full shell: persistent rail plus multi-column content. |
| `xl` | 1280px | Content max-width engages; the canvas grows, the content does not. |

**Rules:**

1. **Mobile-first.** Base styles are the narrow case; breakpoints add, never subtract.
2. **The navigation rail is persistent from `md` and a drawer below it.** The drawer traps focus while open, closes on `Escape`, and returns focus to the control that opened it.
3. **Content has a maximum width.** Beyond `xl` the canvas widens and the content does not — measure matters more than filling the viewport, and full-width body text at 2560px is unreadable.
4. **Tables reflow or scroll within their own container; the page never scrolls horizontally.**
5. **No layout is described as "desktop-only."** Every surface is usable at 375px, whatever its primary context.
6. **Breakpoints are for layout, not for hiding content.** Content hidden on small screens must be reachable another way.

## 10. Empty, Loading & Error States

Every feature must define polished loading skeletons, informative empty states and actionable error messages. These states are part of the product experience.

**Four states, defined as a system.** [[CLAUDE|CLAUDE.md]] §11 requires them of every async surface, and a per-screen answer produces per-screen drift — four different versions of "nothing here yet" is how a product stops looking like one product.

| State | When | Treatment | Required |
|---|---|---|---|
| **Loading** | Data in flight | `--color-skeleton` fills matching the **shape** of the content they replace | Never a bare spinner where a skeleton fits; never a layout shift on arrival |
| **Empty** | Request succeeded, nothing to show | `EmptyState` — what is empty, why, and the action that changes it | Distinguished from error; **never** a blank region |
| **Error** | Request failed | Actionable message, a working retry, `role="alert"` | Never a raw exception, a status code, or a stack trace |
| **Success** | A state-changing action completed | Confirmation of **what** changed, announced to assistive technology | Never silence after a destructive or irreversible action |

**Binding rules:**

1. **All four are implemented, or the surface is incomplete.** A surface with no error state has an undefined error state, not an absent one — this is a Definition of Done item ([[CLAUDE|CLAUDE.md]] §22), not polish.
2. **Empty and error are never conflated.** "No projects yet" and "we could not load your projects" require different words and different actions; showing the first when the second is true is a lie about the system.
3. **Skeletons mirror content shape**, so arrival does not reflow the page. A skeleton that does not match its content is a layout shift with extra steps.
4. **Errors are recoverable.** A retry that does not actually re-run the failed operation is worse than no retry — it manufactures confidence in a failure. That was FA-04, a live defect, and it is the reason this is a rule.
5. **Success is stated for anything consequential**, and silence is reserved for the trivially reversible.
6. **These are designed together with the happy path, never added afterwards.** A feature "done except for its error state" is not done.

## 11. AI Design Rules

When AI generates UI it must:

- Follow the design system without exception.
- Reuse existing components.
- Never invent new styles.
- Respect spacing, typography and color tokens.
- Keep interfaces visually minimal.
- **Reference semantic tokens only** (§3a). A generated component containing a hex code, a raw pixel value, a Tailwind default palette class (`bg-blue-600`, `text-gray-500`) or a `dark:` variant is rejected, not adjusted — it has reached past the layer that makes rebranding possible.
- **Add a semantic token rather than reaching for a primitive** when no existing token fits. That forces the question "what role does this color play?", which is the question the semantic layer exists to make someone answer.

## 12. Premium Quality Checklist

Before approving any screen verify:

- Visual hierarchy is obvious.
- Alignment is pixel-perfect.
- Spacing is consistent.
- No unnecessary UI elements exist.
- Components match the design system.
- Accessibility is preserved.
- Performance is not sacrificed for appearance.
- **No component references a primitive, a hex code, a raw pixel value or a `dark:` variant** (§3a). The practical test: *could the entire brand be replaced by editing §6.2 alone?* If any component would need touching, the layering has been broken.
- **Every color pairing meets WCAG AA** (§6.3) — checked against the values, not assumed from the palette.

## 13. Anti-Patterns

Avoid:

- Generic AI-looking dashboards.
- Random border radii.
- Excessive shadows.
- Too many accent colors.
- Inconsistent spacing.
- Decorative icons without purpose.
- Copying template aesthetics.

## 14. Long-Term Vision

ProjectOne should develop a recognizable visual identity. A screenshot should be identifiable as ProjectOne even without the logo because of its consistency and design language.

[[Design Backlog and UI Vision]] elaborated what that identity should eventually look like. It remains **subordinate to this document** — where the two disagree, this one wins — and its dark-interface visual rules were **superseded on 2026-08-14**.

The active visual direction (warm ivory canvas, matte-black navigation, vermilion accent, editorial typography, cinematic production cues) is stated as binding rules in **§0** and expressed as token values in §4–6, written by [[STEP-26 Product Design System Foundation]] from the owner-approved concept reference `ProjectOne_Product_Design_Direction_v1.0.png`.

**The direction is no longer an adjective, and the values are settled.** [[ADR-003 Product Visual Language and Token Semantics]] was `Accepted` on 2026-08-15, so these tokens are what every later surface is built against ([[CLAUDE|CLAUDE.md]] §7). **No screen has adopted them yet** — [[STEP-80 Product-wide UI Rebuild]] is where that happens, and until then the runtime token layer exists while the screens still render against the roles they already used.

## Conclusion

The Design System is the single source of truth for every interface decision. New components and screens must extend the existing language rather than reinvent it.

---

## Navigation

- **Previous:** —
- **Next:** —
- **Parent:** [[Design MOC]]
- **Related Notes:** [[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]] · [[Frontend Architecture]] · [[React Standards]] · [[Dashboard]] · [[Design Backlog and UI Vision]] · [[STEP-14 Design System Tokens]] · [[STEP-26 Product Design System Foundation]] · [[ADR-003 Product Visual Language and Token Semantics]] · [[Chapter 04 - React Standards]] · [[Chapter 05 - NextJS Architecture]]
