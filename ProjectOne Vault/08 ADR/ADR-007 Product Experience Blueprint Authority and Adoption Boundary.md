---
title: "ADR-007: Product Experience Blueprint Authority and Adoption Boundary"
category: ADR
status: accepted
version: "2.0"
last_updated: 2026-08-22
tags: [adr, decision, design, frontend, accessibility, governance]
adr_number: "0007"
---

# ADR-007: Product Experience Blueprint Authority and Adoption Boundary

## Status

**Accepted** — approved by the project owner on 2026-08-22.

This decision is now binding, and later steps may build against it ([[CLAUDE|CLAUDE.md]] §7). Changing the contracts below requires a new ADR that supersedes this one — this note is not amended in place, on the same terms [[ADR-003 Product Visual Language and Token Semantics]] sets for itself.

**Binding does not mean implemented.** Nothing in this ADR has been built. Every contract it settles is delivered by [[STEP-31a Product Experience Blueprint Alignment]], which remains `Not Started`; the production stylesheet, shell and test harness are unchanged as of acceptance. What acceptance changes is that STEP-31a's gate is now open and its implementation may begin.

> [!note] Four decisions were settled ahead of acceptance, on the same day
> They were resolved individually on 2026-08-22 and are carried into this acceptance **at their settled values, unchanged**:
>
> 1. **`--text-4xl` is `3.25rem` (52px), line-height `1.05`** — Decision 11.
> 2. **Playwright is the approved shared browser-testing contract**, added inside STEP-31a — Decision 13.
> 3. **The activity/audit and workflow-run gaps do not block this ADR.** They stay recorded as open plan gaps; this ADR creates neither route and schedules neither capability — Decision 3.
> 4. **ProjectOne shows no third-party advertising and does not buy, bid or place media** — Decision 3, adopted as standing product constraints.

**Scope of supersession, stated precisely because [[ADR-003 Product Visual Language and Token Semantics]] does not permit amendment in place.** ADR-003 §Status reads: *"Changing the visual language or the token semantics below requires a new ADR that supersedes this one — this note is not amended in place."* This ADR therefore supersedes **exactly one row of exactly one decision** and nothing else:

- **ADR-003 Decision 2, the `--color-nav-surface` row, dark column only** — `ink-950` `#0F0E0D` becomes `ink-975` `#070605`. The role is unchanged; only the dark primitive moves.

**Everything else in ADR-003 remains binding and unamended**, including all six owner-approved decisions, the other four rows of Decision 2, the `accent`/`accent-fill` split, Decision 3's navigation rule, Decision 4's executable contrast check, Decision 5's display boundary and Decision 6's weight ceiling. Where this ADR adds to ADR-003 it adds in areas ADR-003 did not decide; it does not reinterpret what ADR-003 did decide.

### What the owner approved

| # | Decision | Kind | Approval |
|---|---|---|---|
| 1 | The Artifact is an approved design reference, not executable production authority | Governance | **Approved** |
| 2 | The canonical authority order for design questions | Governance | **Approved** |
| 3 | The Now / Planned / Proposed provenance boundary is preserved and binding | Governance | **Approved** |
| 4 | Bounded hybrid adoption: shared foundation now, domain screens in their owning steps | Sequencing | **Approved** |
| 5 | `--color-nav-surface` dark repoints to a new `ink-975` primitive (narrow supersession of ADR-003) | Token | **Approved** |
| 6 | Native `color-scheme` is declared on `:root` | Shared runtime contract | **Approved** |
| 7 | An explicit `[data-theme]` override joins `prefers-color-scheme` as a three-state cascade | Shared runtime contract | **Approved** |
| 8 | The three page-template contracts — Cockpit, Workbench, Focus | Shared shell contract | **Approved** |
| 9 | An inverted-surface semantic family, **in principle** — exact roles and values derived during implementation | Token semantics | **Approved** |
| 10 | Motion tokens replace the Design System's prose-only motion specification | Token | **Approved** |
| 11 | `--text-4xl` = `3.25rem` (52px), line-height `1.05` | Token | **Approved** — settled 2026-08-22 at this value |
| 12 | Speculative navigation and dead routes are prohibited | Governance | **Approved** |
| 13 | Playwright as the shared browser-testing contract, wired into required CI | Testing contract | **Approved** — settled 2026-08-22 |

Decisions 5, 6, 7, 9, 10 and 11 change shared contracts that other code will be built against. Decisions 1–4 and 12 are governance. Decision 8 is a shell contract. Decision 13 adds a testing dependency and is architectural under [[CLAUDE|CLAUDE.md]] §10 and §28, which is why it is an ADR decision rather than a step-level choice. **Under [[CLAUDE|CLAUDE.md]] §21 this is a Critical change**, and the owner's review was obtained before merge rather than only before implementation. **All 13 decisions are approved as written**, with Decisions 11 and 13 carried in at the values settled earlier the same day.

### Revision history

**v2.0 — 2026-08-22. Accepted.** Status moves `proposed` → `accepted` on the project owner's approval. **All 13 decisions approved as written; no value, boundary or contract changed at the gate.** Decisions 11 and 13, settled individually earlier the same day, are carried in unchanged — `--text-4xl` at `3.25rem` (52px) with line-height `1.05`, and Playwright as the shared browser-testing contract. The two standing advertising constraints and the non-blocking status of the activity/audit and workflow-run plan gaps are likewise carried in as decided. **Nothing is implemented by this acceptance**; delivery is [[STEP-31a Product Experience Blueprint Alignment]], which remains `Not Started`.

**v1.1 — 2026-08-22.** Pre-acceptance corrections, before the ADR went to the owner. Decision 11 settled at `3.25rem` / `1.05` with the 1.25 ratio amended to apply through `--text-3xl` and `--text-4xl` documented as a display-only exception; Decision 13 added for Playwright; Decision 8's template selection moved off `body[data-tpl]` onto a server-rendered wrapper emitting `data-template`; Decision 9 narrowed to approval in principle with membership derived from real consumers; the pre-adoption scope of the 22-role finding stated explicitly; the activity/audit and workflow-run gaps recorded as non-blocking.

**v1.0 — 2026-08-22.** Initial draft, raised by the insertion of STEP-31a after the product-experience blueprint was preserved as `5d10a81`.

## Context

On 2026-08-22, commit `5d10a81` (PR #54) preserved a complete product-experience prototype at `ProjectOne Vault/12 Assets/Prototypes/design-phase-2/` — 11 files, 16,812 lines, covering thirty route patterns across eighteen view modules. It is referred to throughout this ADR as **the Artifact**.

The Artifact arrived **earlier in the plan than the roadmap expected**. [[Build Plan]] scheduled design for domains that do not exist at [[STEP-79 Domain Screen Blueprints]] and [[STEP-80 Product-wide UI Rebuild]], deliberately: [[STEP-26 Product Design System Foundation]] excluded them on the stated grounds that *"blueprinting Video Generation, Analytics, Publishing or Billing screens today would design against a specification rather than a product."* The Artifact blueprints all of them anyway, plus several domains that appear in no Build Plan step at all.

That is not a defect in the Artifact. It is a **governance question the Artifact cannot answer about itself**: a design reference that describes a product larger than the one being built has real value as direction and real danger as authority. Nothing currently states which it is. The Artifact is preserved on `main`, linked from no vault note, and carries no recorded authority, provenance boundary or adoption rule.

### Why this needs an ADR at all

Three of the four things this decision settles are architectural under [[CLAUDE|CLAUDE.md]] §7 and §39.

**The token work by itself would not have triggered it.** ADR-003 §Context is explicit: *"A pure revalue is therefore **operational**, not architectural — exactly what §3a was built to absorb."* [[Design System#6.5 How to change a token]] authorises adding a primitive ramp and repointing semantic tokens as routine procedure. Measured against the production stylesheet, the Artifact's colour work is exactly that:

| | Count | Verdict |
|---|---|---|
| Semantic colour roles in `apps/web/src/app/globals.css` | 22 | — |
| Semantic colour roles in the Artifact | 22 | **identical set — none added, none dropped** |
| Semantic roles whose value changes | 3 | routine revalue under §6.5 |
| Primitives added | 2 (`--ivory-75`, `--ink-975`) | permitted by §6.5 step 1 |

**This measures the Artifact against production as it stands today, before any adoption.** It is the reason the Artifact's *colour* work is not architectural: ADR-003 §Context says *"What triggers the checkpoint is that the semantic layer itself gains new roles"*, and the Artifact, taken as drawn, adds none.

**It is not a claim that the production role set stays at 22.** Decision 9 proposes an inverted-surface family, and if the owner accepts it the production role set grows — by roles the Artifact needed but never named, rather than by roles it declared. The two statements are about different things and both are true: *the blueprint adds no role; this ADR may.*

What does trigger this ADR is four other things:

1. **A theme-selection mechanism that does not exist in production.** The Artifact introduces `color-scheme` and a `:root[data-theme]` override cascade. `apps/web/src/app/globals.css` has a bare `@media (prefers-color-scheme: dark)` block and nothing else; `data-theme` appears nowhere in `apps/web/src`. This is new shared runtime behaviour affecting every native control, caret, scrollbar and selection in the product.
2. **A page-template system.** ADR-003 decides tokens and says nothing about layout. STEP-26's owner clarification explicitly forbade changing "any screen layout." Three shared templates is a shell contract every future screen would build against — and the Artifact selects them by mutating an attribute on `<body>` from the client, which is a prototype technique this ADR replaces rather than adopts (Decision 8).
3. **A gap the Artifact found but did not name.** Nine canvas components paint themselves with the `nav-*` family, and the toast reaches past the semantic layer entirely for `var(--green-400)` / `var(--red-400)`. ADR-003 Decision 3 states the rule those violate: *"a component rendering inside the navigation plane references the `nav-*` family, and a component rendering on the canvas never does."* The Artifact has discovered that the product needs an **inverted surface** distinct from the navigation plane, and expressed that need by breaking the rule rather than naming the role.
4. **The authority question itself.** Whether a preserved prototype can create product commitments is not a visual decision. It is a decision about what counts as a source of truth, which is what `08 ADR/` exists to record.

Under §39's ambiguity rule — *"Ambiguous cases resolve toward the ADR"* — the remaining items resolve here too.

### The forces

- **The Artifact is genuinely good work and genuinely honest.** It marks its own speculation. Its README states plainly that *"'recipe' and 'deliverable' do not exist as product nouns anywhere in the repository today. They are introduced by this design and are proposals, not descriptions."* Discarding it would waste a complete, coherent, owner-approved direction.
- **Adopting it wholesale would ship a product that does not exist.** Of thirty prototype route patterns, twenty-one resolve to nothing in production, and eleven of those have no owning Build Plan step at any point in the plan. Five of the nine navigation-rail destinations would be hard 404s.
- **Some of it is free.** The `nav-*` token family — the matte-black rail that is the single most visually significant change — is already defined in both themes, already registered as Tailwind utilities, already contrast-verified in CI on every push, and **referenced by zero components**. Rendering it requires no new token and no new contrast work.
- **Deferring everything wastes the window.** Every frontend step between here and STEP-79 builds a surface. Each one built against today's ad-hoc shell is a surface STEP-80 must rebuild.
- **A prototype's evidence is not a product's evidence.** `QA.md` measures the generated `artifact.html` in a `data:` harness. It is real evidence about the prototype and no evidence at all about production.

## Decision

### 1. The Artifact is an approved design reference, not executable production authority

The Artifact is **approved direction**. It is not a specification, not a contract, and not a source of truth about what ProjectOne does.

Concretely, and without exception:

- **Nothing in the prototype creates backend authority.** Its payloads, mock data, fixture records and simulated worker timings describe no API, no schema, no endpoint and no field. A screen in the Artifact showing a value is not evidence that a value exists.
- **Nothing in the prototype creates product authority.** A route, a control, a noun or an interaction appearing in the Artifact does not schedule it, approve it, or make it a commitment.
- **`QA.md` is prototype evidence, not production verification.** It proves things about `artifact.html`. It does not discharge any production check. ADR-003 Decision 4's verification artefact is `scripts/check-contrast.py` in the `web` CI job, which `QA.md` never ran and — the palettes having diverged — could not have run.
- **Prototype CSS and JavaScript are never copied wholesale into production.** The Artifact is not a Tailwind build; it declares plain custom properties with no `@theme inline` registration, so **nothing in it demonstrates that its tokens generate Tailwind utilities at all**. Adoption means re-deriving a contract and implementing it in the production architecture, never lifting a file.

### 2. Canonical authority order

For any design question, the first source that answers it wins:

1. **Accepted ADRs and [[Design System]]** — binding.
2. **The approved blueprint and its handoff evidence** — the Artifact's `README.md`, `DESIGN-DECISIONS.md`, `ROUTES.md` and `QA.md`.
3. **Prototype implementation details** — `styles.css`, `prototype.js`, `screens.js`, `campaign.js`, `artifact.html`.

Where two disagree, the higher wins and the conflict is stated rather than silently resolved ([[CLAUDE|CLAUDE.md]] conflict-resolution rule). The Artifact's own stylesheet already concedes this ordering: *"If the two ever disagree, globals.css is right and this file is stale."*

Four conflicts are already known and resolve against the Artifact:

| Conflict | Resolution |
|---|---|
| `DESIGN-DECISIONS.md` DD-02a calls the `color-scheme` change *"the same three-state shape the tokens already use"* | **Factually wrong.** Production has a `prefers-color-scheme` block only. The `[data-theme]` cascade is new — see Decision 7 |
| `ROUTES.md` labels `#/settings/profile` → "appearance" as provenance **Now** | **Unsupported.** No appearance or theme control exists in production |
| The Artifact's line-height tokens use the `--text-4xl-lh` form | **Production wins.** Tailwind v4 requires `--text-4xl--line-height` inside `@theme`; the Artifact's form would register no line-height |
| `styles.css` comments state the rich tier as `>= 46rem` tall | **The Artifact's own prose wins** — DD-05 and `README.md` both say 55rem, and the implemented query is `max-height: 54.999rem`. The comment is stale |

### 3. The Now / Planned / Proposed boundary is preserved and binding

The Artifact's own provenance taxonomy (`ROUTES.md`) is adopted verbatim as a governance boundary:

- **Now** — shipped and verifiable in the repository.
- **Planned** — approved and scheduled; the owning step is named.
- **Proposed** — this design proposes it; no step owns it yet.

**A `Proposed` item is a proposal and never becomes a commitment by being drawn.** It enters the product only by the owner approving the capability and a Build Plan step owning it — in that order. This ADR schedules none of them.

**A `Planned` attribution is a claim to be verified, not accepted.** Three of the Artifact's attributions do not survive cross-referencing against the steps they name:

- `#/activity` and `#/projects/:id/activity` are attributed to STEP-34/35 and STEP-77. [[STEP-34 Notifications Domain]] declares `**Frontend:** none`; [[STEP-35 Notifications UI]] is scoped to notification components; [[STEP-77 Workspace and Collaboration Foundations]] is scoped to the workspace switcher and member management. **No step in the plan owns an activity or audit surface.**
- `#/runs` and `#/runs/:id` have no owning step. [[STEP-24 Dashboard]] explicitly declined to invent a workflow route and deferred it to "a later step" that was never created.

These are **gaps in the plan surfaced by the Artifact**, recorded rather than closed. **The owner decided on 2026-08-22 that neither gates this ADR.** They remain visible as open plan gaps in [[Build Plan#Deferred by Decision]], and:

- **This ADR creates neither route and schedules neither capability.**
- **[[STEP-31a Product Experience Blueprint Alignment]] creates neither route and schedules neither capability.**
- Closing them stays a separate owner decision, taken when it is taken.

Recording a gap is not a commitment to fill it, and an unfilled gap is not a defect in this decision.

**Two standing product constraints are adopted as settled owner decisions of 2026-08-22.** They are binding on every future step, and they are constraints rather than open questions — the only places in the Artifact that narrow the product rather than widening it:

> **ProjectOne never shows third-party advertisements to its users.** The only advertising anywhere in this product is advertising the customer owns.

> **ProjectOne does not buy media, bid, or place anything.** It makes the creative.

Any future advertising-adjacent capability inherits both, whatever step eventually owns it. The paid-media pack the Artifact draws remains `Proposed` and owned by no step.

### 4. Bounded hybrid adoption

Adoption is sequenced in four stages. This is the decision the alternatives below are weighed against.

1. **Shared foundation now** — [[STEP-31a Product Experience Blueprint Alignment]]. The token layer, the theme mechanism, the authenticated shell, and reusable layout primitives, **for routes that already exist**. The shell may change visually. No domain page is rebuilt.
2. **Real domain screens during their owning steps.** Every future step that introduces a frontend surface consumes the blueprint when it builds that surface, against the contracts this ADR establishes. The blueprint informs the screen; it does not authorise the screen.
3. **Final reconciliation at [[STEP-79 Domain Screen Blueprints]]** — enumerate the real product as it then stands, validate the preserved blueprint against real behaviour, complete what is missing, reconcile deviations deliberately, and obtain owner approval for the final set.
4. **Consolidation at [[STEP-80 Product-wide UI Rebuild]]** — the single product-wide pass over the domain pages STEP-31a deliberately did not rebuild.

**This inherits STEP-26's distinction exactly.** STEP-26's owner clarification drew the line between *the shared substrate* and *any individual surface*: *"The substrate is what every screen consumes; a surface is what one screen looks like."* STEP-31a builds the first and never the second. Stages 3 and 4 are not weakened, shortened or absorbed by stage 1.

### 5. `--color-nav-surface` dark repoints to a new `ink-975` primitive

`--ink-975: #070605` is added to Layer 1; dark `--color-nav-surface` repoints from `ink-950` to it. No role is created.

This is mechanically a §6.5 revalue and would be operational — **except that ADR-003 Decision 2 prints the superseded value, and ADR-003 cannot be amended in place.** Hence the narrow supersession recorded in §Status.

`#070605` satisfies [[Design System]] §6.1's rule that pure black is deliberately absent.

**Two further revalues are *not* part of this supersession** and are recorded here only so the set is legible. They touch [[Design System]] §6.1/§6.2 alone, appear nowhere in ADR-003's text, and are routine §6.5 procedure requiring the owner's specification sign-off but no ADR:

| Token | Theme | From | To |
|---|---|---|---|
| `--color-surface` | light | `ivory-50` `#FFFDF8` | `ivory-75` `#FDFAF3` |
| `--color-surface-raised` | light | `white` `#ffffff` | `ivory-50` `#FFFDF8` |

They close a real defect: raised surfaces currently differ from their background by two values (`#FFFDF8` on `#ffffff`), which is not a perceptible hover state.

**Every revalue runs §6.5 steps 3–5 in full** — `PRIMITIVES` and the light/dark maps updated in `scripts/check-contrast.py` *and* `globals.css`, the pairing enumeration re-run and green in CI, and [[Design System]] §6.1/§6.2 updated in the same change. ADR-003 Decision 4 is reinforced, not relaxed: the pairing count rises as the two new primitives enter the enumeration.

### 6. Native `color-scheme` is declared on `:root`

`color-scheme: light` on `:root`, `color-scheme: dark` in the dark branch.

This is not a token. It changes the caret, the selection highlight, scrollbars, and every native form control and `<dialog>` backdrop across the entire product — which today render in the user agent's light styling even under the full dark token set. That is a shared runtime behaviour, and it is currently a real defect in dark mode.

It **extends** ADR-003 Decision 1 rather than superseding it: `color-scheme` is set on `:root`, not on components, so Decision 1's prohibition on theme-aware components is untouched.

### 7. An explicit `[data-theme]` override joins `prefers-color-scheme`

The theme cascade becomes three-state: system default via `@media (prefers-color-scheme: dark)`, explicit light via `:root[data-theme="light"]`, explicit dark via `:root[data-theme="dark"]`, with the media query guarded so an explicit choice wins in both directions.

**This is a new shared runtime contract, and the larger half of what DD-02a describes.** It is the prerequisite for any user-facing appearance control, and it carries obligations the Artifact does not state because a static prototype never faces them:

- Client-side persistence and a pre-hydration script, or the user's choice flashes on every navigation.
- Persistence is **client-side only** (`localStorage` plus the attribute). Storing a theme preference on the user profile would cross into API-contract territory and is out of scope here.
- Every dark-branch token must be defined in **both** the media query and the attribute selector, or an explicit choice yields a half-themed page.

Declaring the mechanism does **not** schedule an appearance control. That surface is `Proposed` under Decision 3.

### 8. Three page-template contracts — Cockpit, Workbench, Focus

Every surface uses exactly one of three templates.

| Template | Shape |
|---|---|
| **Cockpit** | Full-bleed, height-aware, one primary action region |
| **Workbench** | The default working surface — persistent rail, wide content, list and detail |
| **Focus** | Narrow single-column, reduced chrome, one task |

**Naming is settled here because the Artifact names them twice, differently.** `ROUTES.md` and DD-03 use *Cockpit / Workbench / Focus*; `README.md` uses *Creative Cockpit / Workbench / Focused Flow*; the prototype implements `cockpit` / `workbench` / `focus`. **The short forms are canonical**, matching both the implementation and the majority of the handoff.

**The selection mechanism is not the Artifact's.** The prototype selects a template with an attribute on `<body>`, mutated by client-side JavaScript on navigation. That is a prototype technique and it is explicitly **not** adopted, for three reasons: it makes `<body>` carry per-route state, it cannot be produced by a Server Component without a hydration race, and the prototype's own template rules depend on `--protobar-height`, which is prototype chrome with no production existence.

**The adopted contract instead:**

- **`<body>` remains responsible only for global theme behaviour** — the `data-theme` attribute of Decision 7, the `color-scheme` of Decision 6, and nothing else. It never carries per-route or per-template state.
- **A template is selected by a shared, server-rendered layout primitive** that wraps the page's content and emits `data-template="cockpit" | "workbench" | "focus"` on its own wrapper element. The value is a prop, resolved on the server from the route that is already rendering.
- **No client mutation, and therefore no hydration race.** The template is present in the first byte of HTML, identical on server and client, and never reassigned after paint. Nothing reads `usePathname()` to decide it.
- **No prototype-chrome dependency.** Any offset or geometry a template needs is re-derived from production tokens; `--protobar-height` is not adopted and neither is the hardcoded `max-width: 78rem` the prototype's workbench uses while its three siblings use tokens.
- **Only existing routes are assigned a template during STEP-31a.** A template is a layout contract, not a screen, so defining three commits the product to no route; assigning them to routes that do not exist would.

DD-04's scoping discipline — that a view's full-width and height-locked rules are scoped by an attribute rather than leaking into the shared layer — **is** adopted, re-expressed against the wrapper primitive rather than against `<body>`.

**The primitive's exact API is deliberately not specified here.** It is derived from the five existing authenticated routes during implementation, per [[CLAUDE|CLAUDE.md]] §29 and §35.

### 9. An inverted-surface semantic family

This is the one place the Artifact found a real gap in ADR-003's model and did not name it.

ADR-003 Decision 3 states the rule: *"a component rendering inside the navigation plane references the `nav-*` family, and a component rendering on the canvas never does."* In the Artifact, **nine canvas components paint themselves with `nav-*`** — segmented controls, log panels, mode selectors, filters, gates, chat turns, avatars and the toast. The toast then goes further and reaches past the semantic layer entirely:

```
.toast       { background: var(--color-nav-surface); color: var(--color-text-on-nav); }
.toast--ok   { border-left-color: var(--green-400); }
.toast--bad  { border-left-color: var(--red-400); }
```

[[Design System]] §3a calls reaching for a primitive from a component *"a defect, not a style choice"* — and this one is forced, because **the `nav-*` family has no `success` / `warning` / `danger` member**. There is no correct token to reach for.

The finding is not that the Artifact is wrong; the design intent — an inverted treatment for selected controls, inverted panels and transient overlays — is coherent. The finding is that **the product needs an inverted surface that is not the navigation plane**, and that need should be named as roles rather than discovered again by every future component.

**What the owner is asked to approve is the family in principle — that an inverted surface distinct from the navigation plane is a legitimate part of the token semantics.** Nothing more.

**Its exact membership and values are technical implementation decisions, not owner decisions**, and are deliberately not fixed here:

- **Roles are derived from real consumers.** A role is added because an existing component demonstrably needs it, named for what it does and never for how it looks ([[Design System#6.5 How to change a token]]).
- **Values are set by measurement**, against every surface the role can appear on, and must clear their bars in `scripts/check-contrast.py` before anything consumes them.
- **If no current consumer justifies a role, nothing is added.** A role with no consumer is the speculative design [[CLAUDE|CLAUDE.md]] §29 and §35 forbid — and the honest outcome of Decision 9 may be an empty family. That is a success, not a failure to deliver.

Deriving the family is scoped to [[STEP-31a Product Experience Blueprint Alignment]]. Until it exists, **no production component may reach for a primitive or paint canvas UI with `nav-*`** — ADR-003 Decision 3 remains binding in the meantime.

### 10. Motion tokens replace the prose-only motion specification

`--duration-fast` `120ms`, `--duration-base` `180ms`, `--duration-slow` `240ms`, `--ease-standard` `cubic-bezier(0.2, 0, 0, 1)`.

Production has **no motion tokens of any kind** — no duration, no easing, and no `prefers-reduced-motion` handling anywhere in `globals.css`. Components use bare utilities. The Artifact is candid that this is new: *"Motion tokens — a proposal. The Design System specifies motion in prose only, with no token layer."*

The reduced-motion treatment is adopted with it, and it is stronger than the Design System's prose: a `prefers-reduced-motion` block that neutralises animations, transitions, `scroll-behavior` and `scroll-snap-type`, **and** remaps the three duration tokens to `1ms` — belt and braces, so a component that hard-codes a duration is still caught.

Restraint is a rule, not a default: motion confirms a change of state and never decorates.

### 11. `--text-4xl` is `3.25rem` (52px), line-height `1.05`

**Settled by the owner on 2026-08-22.** `--text-4xl` is added as one step above `--text-3xl`, registered as `--text-4xl: 3.25rem` **and** `--text-4xl--line-height: 1.05` in `@theme inline` — Tailwind v4's pairing syntax, not the Artifact's `-lh` form, which would register no line-height at all.

It **extends** ADR-003 Decision 5 rather than superseding it: Decision 5 bounds the display face to *"`--text-2xl` and above"*, and a step above `--text-3xl` is inside that bound by construction.

**Two things the Artifact says about this value are handled explicitly rather than inherited.**

**The Artifact's "roughly 64px" is stale prose.** `DESIGN-DECISIONS.md` DD-08 states an intent of roughly 64px while implementing `3.25rem` = 52px. The **implemented value is what the composition was measured against**, and it is what the owner selected; the sentence is a leftover from an earlier intent. **The preserved Artifact is not edited to fix it** — it is a preserved record, and correcting it in place would falsify what was actually preserved (ADR-003 sets the same precedent for its own text). The discrepancy is resolved here, where authority rank 1 governs.

**The 1.25 ratio is amended rather than broken silently.** `3.25 / 2.25 = 1.444`, so this step does not continue [[Design System]] §5.2's major third. The proposed §5.2 rule becomes: **the 1.25 scale applies through `--text-3xl`, and `--text-4xl` is a deliberate display-only exception** — one editorial size, above the display boundary, never used for body copy, labels, table cells or controls, and validated by the Artifact's measured composition rather than derived from the ratio. Stating the exception is what keeps §5.2 truthful; leaving the ratio claim standing beside a value that contradicts it is the documentation drift [[CLAUDE|CLAUDE.md]] §19 treats as a bug.

**The value is settled; this ADR is not.** Acceptance remains a decision about the whole.

### 12. Speculative navigation and dead routes are prohibited

**No navigation item may point at a route that does not exist.** No route is created to host a capability that does not exist. No control is rendered that does nothing, and no production surface displays mock data as though it were real.

This is not a new rule; it is the existing one, restated because the Artifact is the largest pressure ever put on it. `apps/web/src/lib/navigation.ts` already states it: *"a nav item pointing at a route that does not exist is a dead end rather than a roadmap."* [[STEP-24 Dashboard]] already honoured it by declining to invent a workflow route and by rendering its two unavailable sections as explicit "Not available yet" cards rather than as plausible-looking fakes.

Measured against production, adopting the Artifact's rail as drawn would violate it comprehensively: **of nine rail destinations only two resolve today.** Two more exist at different addresses, and five would be hard 404s.

**Navigation grows when routes do.** A future step that creates a surface adds its own navigation entry as part of that step.

### 13. Playwright is the shared browser-testing contract

**Settled by the owner on 2026-08-22.** ProjectOne adopts **Playwright** as its browser-testing layer. [[STEP-31a Product Experience Blueprint Alignment]] adds and configures it during implementation; nothing is added now.

**Why this is an ADR decision and not a step-level choice.** Adding a test framework is a new load-bearing dependency and a new execution substrate outside the [[CLAUDE|CLAUDE.md]] §10 stack table, which §28 and §35 place behind an ADR. It is also the first browser-based testing at any level of this repository: today `apps/web` runs Vitest with `environment: "node"` — no jsdom, no Testing Library, no axe, no end-to-end layer — so component tests render with `renderToStaticMarkup` and client behaviour is asserted by reading source text.

**Why it is needed here specifically.** A design foundation makes claims that source text cannot check. Whether focus actually moves, whether a drawer actually traps it and returns it, whether an explicit theme actually survives a reload, whether a layout actually reflows without overflow — these are properties of a running browser, and asserting them against a regex is asserting that the code *looks* correct. That is the gap [[STEP-26 Product Design System Foundation]] closed for contrast with an executable check, and the same reasoning applies: **a rule nothing runs is a rule that silently stops holding.** The shell's skip link and `aria-current` are correct today and have no test at all.

**What the browser suite must cover**, as a contract on STEP-31a rather than a list of test names:

- Real keyboard traversal and focus order across the shell and every existing route.
- The skip link: reachable first, and moving focus to the main landmark.
- Mobile navigation: focus trapped inside the drawer, `Escape` closing it, focus returned to the trigger.
- Navigation: every rendered destination resolving, and active-route semantics including `aria-current`.
- Explicit theme selection persisting across reload and navigation, in both directions, with no flash.
- Narrow-viewport reflow and overflow at the defined breakpoints.
- Reduced motion: animation and transition genuinely suppressed under `prefers-reduced-motion`.
- Every existing route still reachable and still behaving as before.

**Static and unit checks are kept, not replaced.** Token-set analysis of `globals.css`, the route-tree and navigation-destination assertions, the source-level boundary checks and `scripts/check-contrast.py` all remain — they are cheap, they run on every change, and several of them check things a browser cannot see, such as whether a token is defined only inside a media query. The two layers are complementary.

**The browser suite is wired into required CI.** A proof that runs only on demand is a proof that stops running ([[CLAUDE|CLAUDE.md]] §26).

**One manual check is retained, narrowly.** Browser automation cannot faithfully reproduce actual browser zoom, so **200% zoom stays a manual checklist item**. It is the only one. Every other proposition above is automated, and none of them is a residual gap.

## Alternatives Considered

- **Implement the entire Artifact now.** — **Rejected on measurement.** Twenty-one of thirty route patterns resolve to nothing; eleven have no owning step anywhere in the plan; five of nine rail destinations would be hard 404s. Delivering them would require inventing an activity read path, a run-detail contract, a deliverable domain, a versioning model, a workspace-level library, an invitation flow and a billing domain — every one of which is backend, schema, RLS and API work that this design cannot authorise and that §34 forbids guessing at. It would also convert the Artifact's honest `Proposed` bucket into silent product commitments, which is precisely the failure Decision 3 exists to prevent.

- **Defer everything until STEP-79/STEP-80.** — **Rejected on cost.** Twenty-two Not Started steps introduce a frontend surface before STEP-79. Each one built against today's ad-hoc shell — five pages hand-rolling the same header markup, no page-template primitive, no Button, Card or Badge — is a surface STEP-80 must then rebuild. It also leaves free value on the floor: the `nav-*` family is defined, contrast-verified in CI, and referenced by nothing, so the single most visible change in the direction is available at the cost of a class name. And it leaves two live defects standing — no `color-scheme` in dark mode, and a two-value hover delta on raised surfaces.

- **Uncontrolled page-by-page adoption.** — **Rejected on precedent.** This is the exact failure the Build Plan already diagnosed once: [[STEP-80 Product-wide UI Rebuild]] exists because rebuilding early *"would have restyled a fraction of the product and left every later domain to drift again."* Without a named shared contract, each step re-derives its own reading of the Artifact, and per-screen drift is reintroduced in the name of adopting a design system. It is also unreviewable — no single change is large enough to trigger the owner gate that the aggregate plainly deserves.

- **On testing: keep the node-only harness and prove browser behaviour by reading source text.** — **Rejected.** It is the technique the repository uses today, and it is honest about being a substitute — the boundary tests assert that a component *imports* the recovery hook rather than that recovery works. For a step whose whole subject is focus, keyboard, theme and reflow, that substitute stops being a proxy and starts being a fiction. The alternative of adding jsdom instead was also rejected: jsdom has no layout engine, so it cannot answer reflow, overflow or zoom questions at all.

- **A bounded hybrid — selected.** Shared foundation now, domain screens in their owning steps, reconciliation at STEP-79, consolidation at STEP-80. It takes the value that is genuinely free, gives the twenty-two intervening frontend steps a contract to build against, and moves neither the speculative work nor the owner gates forward. Its accepted cost is that it is more governance than a smaller decision would need — which is the trade Decision 3 is paying for deliberately.

## Consequences

**Easier:**

- Every future frontend step has a shared contract to build against instead of a 16,812-line prototype to interpret.
- The matte-black navigation plane becomes renderable with no new token and no new contrast work.
- Two live defects close: no `color-scheme` in dark mode, and an imperceptible raised-surface delta.
- The Artifact stops being an unlinked, unattributed folder on `main` and becomes a governed reference with a stated boundary.
- A gap in ADR-003's model — the inverted surface — is named rather than rediscovered by every component that needs it.

**Harder / accepted costs:**

- Two ADRs must now be read together for design questions, with a supersession that is deliberately one table row wide. Precision here is the cost of not superseding ADR-003 wholesale.
- Every token revalue re-runs the full §6.5 procedure across two files, and the contrast enumeration grows.
- The `[data-theme]` cascade requires a pre-hydration script and doubles the maintenance surface of every dark-branch token.
- Playwright adds a browser dependency, a second test runner, and browser download and execution time to required CI. Accepted deliberately: the alternative is a design foundation whose accessibility claims nothing verifies.
- Rejecting the `deliverable` noun would collapse roughly half the Artifact's surface. This ADR neither accepts nor rejects it; it keeps it `Proposed`, which means the question stays open rather than answered.

**Follow-up this creates:**

- [[STEP-31a Product Experience Blueprint Alignment]] implements exactly the contracts above, and no further, once this ADR is `Accepted`.
- [[Design System]] §5.2 gains the display-only exception for `--text-4xl` (Decision 11), and §6.1, §6.2, §7 and §8 change when this is accepted.
- The inverted-surface family's membership and values are derived and measured during STEP-31a, and may correctly turn out to be empty (Decision 9).
- The page-template wrapper primitive's API is derived from the five existing authenticated routes (Decision 8).
- Playwright is added and wired into required CI inside STEP-31a (Decision 13).
- Two plan gaps stay recorded and open — **no step owns an activity/audit surface**, and **no step owns a workflow-run route**. Neither blocks this ADR, and neither is scheduled by it.
- [[STEP-79 Domain Screen Blueprints]] narrows from origination to reconciliation.

## Related

- Related notes: [[ADR-003 Product Visual Language and Token Semantics]] · [[Design System]] · [[STEP-31a Product Experience Blueprint Alignment]] · [[STEP-26 Product Design System Foundation]] · [[STEP-79 Domain Screen Blueprints]] · [[STEP-80 Product-wide UI Rebuild]] · [[Design MOC]] · [[Frontend Architecture]]
- The Artifact: `ProjectOne Vault/12 Assets/Prototypes/design-phase-2/` — `README.md`, `DESIGN-DECISIONS.md`, `ROUTES.md`, `QA.md`, preserved by PR #54 as `5d10a81`
- Governed by: [[CLAUDE|CLAUDE.md]] §7 · §11 · §19 · §21 · §29 · §35 · §39

---

## Navigation

- **Previous:** [[ADR-006 Workflow Async Execution and Run Reconciliation]]
- **Next:** —
- **Parent:** [[Development MOC]]
- **Related Notes:** [[ADR-003 Product Visual Language and Token Semantics]] · [[Design System]] · [[STEP-31a Product Experience Blueprint Alignment]] · [[STEP-79 Domain Screen Blueprints]] · [[STEP-80 Product-wide UI Rebuild]]
