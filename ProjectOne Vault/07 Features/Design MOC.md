---
title: Design MOC
category: MOC
status: stable
version: "1.7"
last_updated: 2026-08-22
tags: [moc, design, documentation]
aliases: ["Design Map of Content"]
---

# Design — Map of Content

## Core

- [[Design System]] — visual identity, layout, typography, color, motion, accessibility, AI design rules. **Authoritative** — the standard every screen is built against.
- [[ADR-003 Product Visual Language and Token Semantics]] — `Accepted`. The visual language and token semantics, binding.
- [[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]] — `Accepted` 2026-08-22. What the preserved product-experience blueprint *is*, what it may and may not authorise, and how it is adopted. **Binding; not yet implemented.**

## Authority Order

For any design question, the first source that answers it wins ([[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]] Decision 2):

1. **Accepted ADRs and [[Design System]]** — binding.
2. **The approved blueprint and its handoff evidence** — the Design Phase 2 Artifact's `README.md`, `DESIGN-DECISIONS.md`, `ROUTES.md`, `QA.md`.
3. **Prototype implementation details** — the Artifact's `styles.css`, `prototype.js`, `screens.js`, `campaign.js`, `artifact.html`.

Where two disagree, the higher wins and the conflict is stated rather than silently resolved.

## The Design Phase 2 Artifact

`ProjectOne Vault/12 Assets/Prototypes/design-phase-2/` — the complete product-experience blueprint preserved on 2026-08-22 as `5d10a81` (PR #54). Thirty route patterns across eighteen view modules, in the owner-approved "Cutting Room" direction.

**It is an approved design reference, not executable production authority.** Its payloads, mock data, routes and interactions create no backend and no product commitment. Its `QA.md` is **prototype evidence** — 4,978 contrast measurements and 240 route renders against the generated `artifact.html` in a `data:` harness — and discharges **no production check**; production contrast verification is `scripts/check-contrast.py` in CI, per [[ADR-003 Product Visual Language and Token Semantics]] Decision 4.

**Its provenance labels are binding**: *Now* (shipped and verifiable), *Planned* (approved, with a named owning step), *Proposed* (proposed here, owned by no step). A `Proposed` item never becomes a commitment by being drawn.

**What it proposes, in summary** — the detail lives in the Artifact's own documents and is not duplicated here:

| Kind | Items | Route |
|---|---|---|
| Routine token revalues, governed by [[Design System#6.5 How to change a token]] | `--ivory-75`; light `--color-surface` and `--color-surface-raised` | Owner sign-off on the §6.1 specification change; no ADR |
| Narrow supersession of ADR-003 | `--ink-975`, repointing dark `--color-nav-surface` | ADR-007 Decision 5 |
| New shared contracts | native `color-scheme`; the `[data-theme]` three-state cascade; the Cockpit / Workbench / Focus page templates, selected by a server-rendered layout primitive; an inverted-surface semantic family (in principle — **derived during STEP-31a and correctly empty**, see [[Design System]] §6.2); motion tokens; `--text-4xl` at `3.25rem` / `1.05` | ADR-007 Decisions 6–11 |
| New testing contract | **Playwright**, wired into required CI — owner-approved 2026-08-22 | ADR-007 Decision 13 |
| Page-specific blueprints | which template each surface uses, and every per-screen layout | [[STEP-79 Domain Screen Blueprints]], then [[STEP-80 Product-wide UI Rebuild]] |
| Proposed capabilities, **not** product scope | Studio, Library, Recipes, Review, the creation plan, deliverables and versions, the paid-media pack | Owner approval of the capability, then an owning step |

**On the role count.** Measured *before adoption*, the Artifact's role set matches production exactly — twenty-two on each side, identical names — so the trigger that produced ADR-003, the semantic layer gaining new roles, does not recur from the blueprint. The production set may still grow: the inverted-surface family would add roles the Artifact needed but never named, approved in principle with membership derived from real consumers and values from measurement. **It was derived during [[STEP-31a Product Experience Blueprint Alignment]] and is empty** — no production component renders an inverted canvas surface. One role was added by that step for a different reason: `--color-overlay`, the modal scrim, promoted during independent review when the previous mapping was found to *lighten* the page in dark mode ([[Design System]] §6.2a). It is an **overlay** role, not an inverted surface, so the family remains empty. The production role count is therefore **twenty-three**, and the contrast enumeration stays at **90 pairings** — nothing is rendered on a scrim, so it has no pairing; it is checked for polarity instead.

**Two settled owner constraints (2026-08-22), binding on every future step:** ProjectOne shows **no third-party advertising**, and **does not buy, bid or place media** — it makes the creative.

## Adoption

- [[STEP-31a Product Experience Blueprint Alignment]] — the shared foundation, for routes that already exist. Rebuilds no domain page. **`Done` (2026-08-22):** the token layer, the three-state theme cascade, `color-scheme`, the motion tokens, `--text-4xl`, the three page templates, the shared shell on the `nav-*` plane, the mobile drawer, the `--color-overlay` scrim and the Playwright suite are implemented, reviewed across three rounds and green on required CI. Ready for the owner's squash merge on [PR #56](https://github.com/ruseduard321-prog/ProjectOne/pull/56), not yet merged.
- Every future step that introduces a frontend surface consumes the blueprint when it builds that surface.
- [[STEP-79 Domain Screen Blueprints]] — final validation and reconciliation against the real product.
- [[STEP-80 Product-wide UI Rebuild]] — the product-wide implementation pass over the domain pages STEP-31a does not rebuild.

## Long-Term Direction

- [[Design Backlog and UI Vision]] — the earlier long-term UI direction, **partly superseded on 2026-08-14**. Its dark-interface visual rules and its deferral of design work until after release are no longer current; its design philosophy and its subordinate rank to [[Design System]] still are. The active visual direction and the per-page blueprints live in [[STEP-26 Product Design System Foundation]]. Where it and [[Design System]] disagree, the Design System wins.

## Applied In

- [[Dashboard]]
- [[Frontend Architecture]]
- [[Chapter 04 - React Standards]]

---

## Navigation

- **Parent:** [[Home]]
- **Related MOCs:** [[Frontend MOC]] · [[Features MOC]]
- **Related Notes:** [[ADR-003 Product Visual Language and Token Semantics]] · [[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]] · [[STEP-31a Product Experience Blueprint Alignment]]
