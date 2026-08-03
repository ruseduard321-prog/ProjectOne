---
title: Design System
category: Design
status: stable
version: "1.4"
last_updated: 2026-08-03
tags: [design, documentation, feature]
aliases: ["Design System & Visual Language", "Visual Language"]
source_pdf: "[[12 Assets/PDF/ProjectOne_Design_System_Visual_Language_v1.0.pdf|ProjectOne_Design_System_Visual_Language_v1.0.pdf]]"
---

# ProjectOne Design System & Visual Language v1.0

## Purpose

This document defines the visual identity and user experience principles of ProjectOne. Its objective is to ensure that every screen feels intentionally designed, premium, consistent and timeless regardless of whether it is created by a human designer or an AI assistant.

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

### 6.1 Primitives (v1)

Raw values. **No component may reference these.**

A neutral ramp does most of the work in a calm interface, plus one accent and three semantic hues:

| Ramp | 50 | 100 | 200 | 400 | 500 | 600 | 700 | 800 | 900 | 950 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Neutral** | `#f8fafc` | `#f1f5f9` | `#e2e8f0` | `#94a3b8` | `#64748b` | `#475569` | `#334155` | `#1e293b` | `#0f172a` | `#020617` |
| **Accent** (indigo) | `#eef2ff` | — | `#c7d2fe` | `#818cf8` | `#6366f1` | `#4f46e5` | `#4338ca` | — | — | — |
| **Success** (green) | `#f0fdf4` | — | — | — | `#22c55e` | `#16a34a` | `#15803d` | — | — | — |
| **Warning** (amber) | `#fffbeb` | — | — | — | `#f59e0b` | `#d97706` | `#b45309` | — | — | — |
| **Danger** (red) | `#fef2f2` | — | — | `#f87171` | `#ef4444` | `#dc2626` | `#b91c1c` | — | — | — |

`neutral-800` and `danger-400` were added on 2026-08-02 during STEP-14, when the
contrast check was extended to cover `--color-surface-raised` — a surface the
original verification omitted. Neither is a new hue; both are one step within an
existing ramp. See §6.3.

A slate-based neutral rather than pure grey: a slight blue cast reads as more considered than `#808080`, and pure black (`#000`) is deliberately absent — it is harsher on screen than a very dark slate and is the fastest way to make an interface feel cheap.

Indigo as the v1 accent: distinctive enough to be recognisable (§14), restrained enough not to fight the content (§1). **This is the value most expected to change**, and thanks to §3a it is also among the cheapest.

### 6.2 Semantic tokens (v1)

**This is the only layer components may reference.**

| Token | Light | Dark | Role |
|---|---|---|---|
| `--color-background` | `neutral-50` | `neutral-950` | Page canvas |
| `--color-surface` | `#ffffff` | `neutral-900` | Cards, panels — sits *above* the canvas |
| `--color-surface-raised` | `#ffffff` | `neutral-800` | Dropdowns, dialogs |
| `--color-border` | `neutral-200` | `neutral-700` | **Decorative** dividers and separators |
| `--color-border-strong` | `neutral-500` | `neutral-400` | **Interactive** boundaries — input outlines, control edges |
| `--color-text` | `neutral-900` | `neutral-100` | Primary content |
| `--color-text-muted` | `neutral-500` | `neutral-400` | Secondary, captions, placeholders |
| `--color-accent` | `accent-600` | `accent-400` | Primary actions, active state, focus |
| `--color-accent-hover` | `accent-700` | `accent-200` | Accent hover/press |
| `--color-accent-contrast` | `#ffffff` | `neutral-950` | Text **on** an accent surface |
| `--color-success` | `success-600` | `success-500` | Confirmation |
| `--color-warning` | `warning-600` | `warning-500` | Caution |
| `--color-danger` | `danger-600` | `danger-400` | Errors, destructive actions |
| `--color-danger-contrast` | `#ffffff` | `neutral-950` | Text **on** a danger surface |
| `--color-skeleton` | `neutral-200` | `neutral-700` | Loading placeholder fill (§10) |
| `--color-focus-ring` | `accent-500` | `accent-400` | Focus indicator (§9) |

**Accent and semantic colors shift one step lighter in dark mode.** A hue tuned for contrast against white is too dark against near-black; reusing it produces the muddy, low-contrast dark mode that looks like an afterthought because it is one.

**`*-contrast` tokens exist so no component ever guesses what text color survives on a colored background.** That guess is where contrast failures come from, and it is a solved problem if the pairing is named once.

Note that `--color-danger-contrast` is **not** white in both themes. White on the lighter dark-mode red fails the 4.5 bar outright; near-black reaches 7.29:1. A `*-contrast` token that is "always white" is an assumption, not a pairing — which is precisely why it is a token rather than a convention.

**`--color-skeleton` is not `--color-surface-raised`, and the difference is why it exists.** Added during STEP-15, when the first loading skeleton was built against `surface-raised` and turned out to be invisible: in light mode that token is `#ffffff` against a `#f8fafc` canvas, a ratio of **1.05**. A skeleton is informational — it says "content is coming" — so it must be *distinguishable*, even though it is not operable and so not subject to the 3:1 non-text bar (§6.3). Reusing a surface token for a fill that needs to be seen against that same surface is the mistake this token prevents.

**Two border tokens, deliberately.** They have genuinely different requirements and collapsing them fails one of the two:

- `--color-border` is decorative — dividers, table rules, card edges. It carries no information a user must perceive, so it is tuned to be quiet.
- `--color-border-strong` marks an **interactive** boundary: where an input begins and ends. WCAG's 3:1 non-text contrast requirement applies here, because a control whose edge is invisible is a control some users cannot find. `neutral-200` on a light background is 1.18:1 and fails outright.

Using the decorative token on an input is the most likely way to break accessibility while the interface still looks fine to whoever built it.

### 6.3 Contrast is a constraint on the palette, not a review step

Every pairing above targets **WCAG 2.1 AA** — 4.5:1 for body text, 3:1 for non-text and interactive boundaries (§9). A palette that fails contrast is not a style disagreement; it is a broken interface for a substantial number of users.

**All 58 pairings are computed and verified across both themes**, against **all three** surfaces — `--color-background`, `--color-surface` and `--color-surface-raised` — plus the two text-on-fill pairings (`*-contrast` on their fill).

> [!warning] The original check omitted `--color-surface-raised`, and that omission produced two live failures
> The first pass (2026-08-02, 28 pairings) verified against `--color-background` and `--color-surface` only. `--color-surface-raised` is a genuinely different surface — in dark mode it is several ramp steps lighter than either — so every foreground appearing on a dropdown or dialog was unverified.
>
> Implementing the tokens in STEP-14 surfaced two dark-mode failures as a result: `--color-text-muted` on `--color-surface-raised` at **4.04**, and `--color-accent` on `--color-surface` at **4.00**, both against a 4.5 bar. The second was not a coverage gap but a missed combination — accent *as text* on a dark card, which is the most common way an accent is used.
>
> The corrections are recorded in §6.1–6.2 above. **A pairing that is not checked is not passing; it is unknown** — which is why the check now enumerates every foreground against every surface rather than a hand-picked list.

Three corrections came out of checking rather than out of review — `--color-danger-contrast` in dark mode and the split of `--color-border` in the first pass, and the dark-mode surface/accent corrections below in the second.

**The dark-mode corrections (2026-08-02, STEP-14).** All three follow the rule §6.2 already states — semantic colors shift one step lighter in dark mode — applied to the surface that was missed:

| Token | Was | Now | Why |
|---|---|---|---|
| `--color-surface-raised` | `neutral-700` | `neutral-800` | At `700` this surface is light enough that muted text (4.04) and the accent both fall below AA on it. `800` clears every foreground while staying visibly raised above `--color-surface`. |
| `--color-accent` | `accent-500` | `accent-400` | `accent-500` as text is 4.00 on a dark card — below AA on **every** dark surface, not just the raised one. |
| `--color-accent-hover` | `accent-400` | `accent-200` | Forced by the row above: hover must stay distinguishable from the resting accent. |
| `--color-danger` | `danger-500` | `danger-400` | 3.89 as text on `surface-raised`. Passed on the two surfaces originally checked, which is precisely how it was missed. |

Nothing here changes a hue — every value is one step within a ramp that already existed, so the slate/indigo identity is unchanged.

**Any future token change must be re-checked the same way.** Contrast is a property of a *pair*, so changing one token silently changes the compliance of every pairing it appears in — this is not something that can be eyeballed, and "it looks fine" is how it gets missed.

The margins worth knowing, because they are where a change will break first:

| Pairing | Ratio | Bar |
|---|---|---|
| `warning` on `background` (light) | 3.04 | 3.0 |
| `success` on `background` (light) | 3.15 | 3.0 |
| `warning` on `surface` (light) | 3.19 | 3.0 |
| `success` on `surface` (light) | 3.30 | 3.0 |
| `text-muted` on `background` (light) | 4.55 | 4.5 |
| `danger` on `background` (light) | 4.62 | 4.5 |
| `text-muted` on `surface` (light) | 4.76 | 4.5 |
| `accent` on `surface-raised` (dark) | 4.90 | 4.5 |

Light mode now carries the tightest margins, and `--color-surface-raised` is the surface to check first on any change — it is the lightest dark surface and the darkest light one, so it is where both themes run out of room.

`--color-text-muted` is the token most likely to fail on a future palette, because "muted" pulls toward the background by definition. It is deliberately `neutral-500` rather than anything lighter for exactly that reason — and at 4.55 it has almost no room left.

The light-mode `warning` and `success` values clear the 3:1 non-text bar but **not** the 4.5:1 text bar. They are for icons, borders and fills; body text stays `--color-text`. A future change putting `success-600` on a light surface as running text would be non-compliant, which is the kind of thing that looks harmless in a mockup.

### 6.4 Dark mode is in scope for v1

Answered deliberately rather than inherited from the template. The skeleton carries a `prefers-color-scheme` block from `create-next-app`, and the choice is to **implement it properly** — the semantic layer makes it a remapping rather than a second design, so the marginal cost is small and it is far cheaper now than retrofitting once screens exist.

**No component is theme-aware.** A component containing `dark:` variants has leaked a theme decision out of the token layer, which is the same defect as hardcoding a hex.

### 6.5 How to change a token

Written down because "the architecture supports it" is worth nothing if the procedure is folklore.

**To rebrand** — change the accent, or the whole palette:

1. Edit the primitives in §6.1, or add a new ramp.
2. Repoint the affected semantic tokens in §6.2. **This is the only edit that touches behaviour.**
3. Re-run the contrast check across all pairings, both themes (§6.3). Not optional — see above.
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

See also: [[Frontend Architecture]] · [[React Standards]]

## 8. Motion

Animations exist only to improve comprehension. Keep transitions subtle, short and purposeful. Avoid decorative animations.

## 9. Accessibility

Support keyboard navigation, screen readers, sufficient color contrast and visible focus states by default.

## 10. Empty, Loading & Error States

Every feature must define polished loading skeletons, informative empty states and actionable error messages. These states are part of the product experience.

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

[[Design Backlog and UI Vision]] elaborates what that identity should eventually look like — screen composition, the premium-OS feel, the Dashboard concept. It is **informational only and subordinate to this document**: where the two disagree, this one wins, and the difference is a UI Polish candidate rather than a defect. It is deliberately deferred until after [[STEP-26 First Public Release]] and must not trigger redesign of a shipped screen during Foundation.

## Conclusion

The Design System is the single source of truth for every interface decision. New components and screens must extend the existing language rather than reinvent it.

---

## Navigation

- **Previous:** —
- **Next:** —
- **Parent:** [[Design MOC]]
- **Related Notes:** [[Frontend Architecture]] · [[React Standards]] · [[Dashboard]] · [[Design Backlog and UI Vision]] · [[STEP-14 Design System Tokens]] · [[Chapter 04 - React Standards]] · [[Chapter 05 - NextJS Architecture]]
