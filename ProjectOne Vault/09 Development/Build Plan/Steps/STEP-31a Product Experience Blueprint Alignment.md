---
title: STEP-31a Product Experience Blueprint Alignment
category: Development/Build Step
status: draft
version: "1.7"
last_updated: 2026-08-22
tags: [engineering, workflow, build-step, design, frontend]
step_id: STEP-31a
step_status: In Progress
detail_level: full
phase: "Design Foundation"
---

# STEP-31a — Product Experience Blueprint Alignment

**Status:** In Progress
**Phase:** Design Foundation — The shared visual and interaction system, established once against the surfaces that actually exist.
**Phase note:** this step belongs to Design Foundation, which [[STEP-26 Product Design System Foundation]] opened, but it **executes** between [[STEP-31 Workflow Async Execution]] and [[STEP-32 Media Processing Pipeline]], where the owner's design milestone placed it. Platform Substrate pauses at STEP-31 and resumes at STEP-32; the [[Build Plan]] table marks both transitions. Steps execute in table order, and a phase boundary is not a gate.
**Detail level:** full — inserted by owner decision on 2026-08-22 and written at full detail on insertion. It was not expanded by a predecessor: [[STEP-31 Workflow Async Execution]]'s expansion task was withdrawn by the project owner on 2026-08-20 when the plan paused for this design milestone.

**Its number records what it amends.** STEP-31a does not amend STEP-31's contract. It amends the plan's *design sequencing* — the assumption, written into [[STEP-26 Product Design System Foundation]] and [[STEP-79 Domain Screen Blueprints]], that no product-wide design direction would exist until STEP-79. One arrived at STEP-31. The `a` records where that happened.

## Objective

Reconcile the approved product-experience blueprint with the binding [[Design System]], and establish the shared foundation every later frontend step builds on — without rebuilding a single domain page.

## Why This Step Exists Now

On 2026-08-22, commit `5d10a81` (PR #54) preserved a complete product-experience prototype at `ProjectOne Vault/12 Assets/Prototypes/design-phase-2/` — the **Artifact**. It arrived earlier in the plan than the roadmap expected, and it describes a larger product than the one being built.

Doing nothing is not neutral. Twenty-two Not Started steps introduce a frontend surface before [[STEP-79 Domain Screen Blueprints]]. Each one built against today's shell — five pages hand-rolling identical header markup, no page-template primitive, no shared Button, Card or Badge — is a surface [[STEP-80 Product-wide UI Rebuild]] must rebuild. Meanwhile the `nav-*` token family is defined in both themes, contrast-verified in CI on every push, and **referenced by no component at all**: the most visible change in the approved direction is currently free and unclaimed.

Adopting the Artifact wholesale is equally unavailable. Of thirty prototype route patterns, twenty-one resolve to nothing in production and eleven have no owning step anywhere in the plan.

This step takes the value that is genuinely free, gives the intervening steps a contract, and moves neither the speculative work nor the owner gates forward.

## Dependencies

- **[[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]] — `Accepted` 2026-08-22, and binding on every task below.** It is the contract this step implements; see [[#The ADR-007 gate]].
- [[ADR-003 Product Visual Language and Token Semantics]] — `Accepted` and unchanged except for the single row ADR-007 narrowly supersedes.
- [[STEP-26 Product Design System Foundation]] — the token layer, the contrast check and the substrate/surface distinction this step inherits.
- The Artifact — approved design reference, not executable authority (ADR-007 Decision 1).

## The ADR-007 gate

**The gate is open.** [[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]] was **approved by the project owner on 2026-08-22**, with **all 13 decisions approved as written** and no value changed at the gate. Under [[CLAUDE|CLAUDE.md]] §7 implementation may now begin.

ADR-007 carries 13 decisions. Six of them — Decisions 5, 6, 7, 9, 10 and 11 — change shared design contracts that other code will be built against, and **Decision 13 adds the browser-testing architecture the owner approved on the same day**.

**Accepted is not implemented.** This step is `Not Started` and nothing in ADR-007 has been built: the production stylesheet, the shell and the test harness are unchanged. What acceptance settles is *what* to build, not that it is built.

**Four decisions were settled ahead of acceptance on 2026-08-22** and carried into it unchanged. They are inputs to this step, not open items:

| Settled | Value |
|---|---|
| `--text-4xl` | `3.25rem` (52px), line-height `1.05` — ADR-007 Decision 11 |
| Browser testing | **Playwright**, added and wired into required CI inside this step — ADR-007 Decision 13 |
| The activity/audit and workflow-run gaps | Recorded and open, **non-blocking**. This step creates neither route |
| Advertising | ProjectOne shows no third-party advertising and does not buy, bid or place media |

**One thing remains a judgement made during implementation, not a decision owed by the owner:** the inverted-surface family's exact roles and values (ADR-007 Decision 9). The owner approves the family *in principle*; membership is derived from real consumers and values from contrast measurement. **If no current consumer justifies a role, nothing is added** — an empty family is a valid outcome.

**It was accepted without modification**, so this note needs no correction before Task 1. Should the ADR later be amended or superseded, the note is corrected first rather than reinterpreted during implementation.

## What the audit found that the plan did not anticipate

Recorded here because each one changes what this step can honestly promise.

- **Before adoption, the role sets match exactly** — twenty-two colour roles in `globals.css`, twenty-two in the Artifact, identical names. Three values move and two primitives are added. **The Artifact itself declares no new role**, so the trigger that forced ADR-003 into existence — *"the semantic layer itself gains new roles"* — does not recur from the blueprint, and its colour work is routine §6.5 procedure rather than architecture. **The production role set may still grow**: ADR-007 Decision 9 adds an inverted-surface family **if real consumers justify one**, by roles the Artifact needed but never named. The two statements are about different things and both hold.
- **The `nav-*` family has no consumer.** `--color-nav-surface`, `--color-nav-surface-raised`, `--color-text-on-nav`, `--color-text-on-nav-muted` and `--color-accent-on-nav` are defined, registered as Tailwind utilities and CI-verified — and referenced by zero components. So are `--color-accent-fill`, `--font-display` (loaded on every page, applied to nothing), `--shadow-sm` and `--shadow-md`.
- **The shell's best accessibility features are its least tested.** The skip link and `aria-current="page"` both exist and are correct. **Neither has a single test.** Any change to `SidebarNav` can silently drop `aria-current` and CI stays green.
- **There is no browser in the test harness today.** Vitest with `environment: "node"` — no jsdom, no Testing Library, no axe, no end-to-end layer at any level of the repository. Component tests use `renderToStaticMarkup`; client behaviour is asserted by reading source text. **This step closes that gap**: the owner approved Playwright on 2026-08-22 (ADR-007 Decision 13), and adding it is Task 7 here — see [[#Required Tests and Proofs]].
- **The Artifact contains four factual errors about production**, all resolved against it by ADR-007 Decision 2: DD-02a's claim that a three-state theme shape already exists; `ROUTES.md` labelling an appearance control as `Now`; the `-lh` line-height form that Tailwind v4 would not register; and a stale `>= 46rem` comment contradicting its own 55rem prose.
- **Three of the Artifact's `Planned` attributions do not survive cross-referencing.** No step owns an activity/audit surface; no step owns a workflow-run route. Recorded as plan gaps, closed by nobody here.
- **Nine canvas components in the Artifact paint themselves with `nav-*`, and the toast reaches past the semantic layer for raw primitives** — because the `nav-*` family has no status members. This is the one real gap the Artifact found in ADR-003's model.

## Scope

- **Reconcile the approved blueprint with the binding [[Design System]]**, recording every accepted decision, every deviation and every deferral in the Design System itself rather than leaving the Artifact as a parallel authority.
- **Apply the accepted global token, theme and type changes** — the ADR-007 Decision 5 revalues, `color-scheme` (Decision 6), the `[data-theme]` cascade (Decision 7), motion tokens (Decision 10), and `--text-4xl` at `3.25rem` (52px) with line-height `1.05`, owner-selected on 2026-08-22 (Decision 11) — through the full [[Design System#6.5 How to change a token]] procedure, in both `globals.css` and `scripts/check-contrast.py`.
- **Add only the shared runtime contracts ADR-007 justifies**, and no others: the three page templates (Decision 8) and the inverted-surface family (Decision 9).
- **Establish the authenticated shell and reusable layout/template primitives for routes that actually exist** — `/dashboard`, `/projects`, `/projects/[projectId]`, `/chat`, `/settings`, and the public `(auth)` surfaces. This includes rendering the navigation plane with the `nav-*` family that already exists for it.
- **Keep navigation limited to real reachable routes** (ADR-007 Decision 12). The four existing `NAV_ITEMS` destinations stay four.
- **Preserve all current authentication, authorization and behaviour exactly.** This is a presentation change.
- **Add and configure Playwright**, and create executable accessibility, responsive, theme and regression proofs in it — including for the shell contracts that are currently correct and untested — wired into required CI.
- **Document how future frontend steps consume the blueprint** — one durable statement in [[Design System]], not a link sprayed across twenty-two step notes.

**The shared shell may change visually.** That is the point of the step. What it may not do is rebuild any individual domain page.

## Out of Scope

- **No page-by-page product rebuild.** Domain pages keep their current structure and content; that pass is [[STEP-80 Product-wide UI Rebuild]].
- **No Studio, Library, Recipes, Review, Plan or any other speculative production route.** These are `Proposed` under ADR-007 Decision 3 and enter the product only via owner approval and an owning step, in that order.
- **No fake controls and no mocked production data.** A control that does nothing and data that is not real are forbidden ([[CLAUDE|CLAUDE.md]] §35). Where a surface has nothing to show, it says so, as [[STEP-24 Dashboard]] already does.
- **No advertising subsystem.** No paid-media pack, no ad formats, no placement. ADR-007 Decision 3's two standing constraints are binding.
- **No API, database, migration, auth, RLS, worker or Supabase change of any kind.** If a visual change appears to require one, that is the signal to stop, not to widen.
- **No new runtime dependency.** Playwright is a *development and CI* dependency, approved by name in ADR-007 Decision 13; it ships in no bundle. Nothing else is added.
- **No [[STEP-32 Media Processing Pipeline]] implementation**, and no expansion of it. STEP-32 stays `outline` and `Not Started`.
- **No deletion or weakening of [[STEP-79 Domain Screen Blueprints]] or [[STEP-80 Product-wide UI Rebuild]].** Both remain, with STEP-79 narrowed from origination to reconciliation.
- **No import of the prototype as production code.** No file is copied. Prototype CSS and JavaScript are re-derived, never lifted (ADR-007 Decision 1).
- **No new product noun.** `deliverable`, `recipe`, `master`, `version` and `set` do not enter the codebase.

## Surfaces Affected

**Frontend:** `apps/web/src/app/globals.css` (tokens, theme cascade, motion); `apps/web/src/app/layout.tsx` and `(app)/layout.tsx` (shell, theme attribute); `apps/web/src/components/shell/` (navigation, the page-template wrapper primitive, new layout primitives); `apps/web/src/lib/navigation.ts` (unchanged destinations). **Testing:** Playwright added as a development dependency with its configuration and specs, plus the existing Vitest suite. **Tooling and CI:** `scripts/check-contrast.py`, and the `web` CI job gains the browser suite as a required check. **Documentation:** [[Design System]], [[Design MOC]], [[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]], [[STEP-79 Domain Screen Blueprints]]. **Backend, database, infrastructure:** none.

## Required Documentation

A candidate list, not a reading list ([[Execution Protocol#Context Discipline]] rule 2).

| Document | The question it answers | Likely needed |
|---|---|---|
| [[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]] | What was approved, at what value, and which Artifact capabilities stayed `Proposed` | **Yes** — `Accepted` 2026-08-22, and the contract this step implements |
| [[Design System]] §3a, §5.2, §6.1–6.5, §7, §8, §9–9a, §10 | The binding token architecture, scale, procedure and rules being changed | **Yes** |
| [[ADR-003 Product Visual Language and Token Semantics]] | Which decisions survive unchanged, and the one row that does not | **Yes** |
| The Artifact's `README.md`, `DESIGN-DECISIONS.md`, `ROUTES.md` | The approved direction and its provenance labels | **Yes** — as reference, at authority rank 2 |
| [[STEP-26 Product Design System Foundation]] | The substrate/surface precedent and the §6.5 procedure as actually run | Probably |
| The Artifact's `QA.md` | What the prototype proved about itself | Only if a specific prototype behaviour is in question — it discharges no production check |
| The Artifact's `styles.css` / `prototype.js` | A specific implementation detail whose intent the handoff leaves ambiguous | Only when rank 1 and 2 do not answer it |
| [[Frontend Architecture]] · [[Chapter 04 - React Standards]] | Server/Client boundaries for new shared primitives | Only if a primitive's boundary is genuinely unclear |

## Tasks

### 1. Confirm the gate before touching anything

Re-verify at `origin/main` that [[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]] reads `Accepted` and that its 13 decisions are unchanged from the values this note was written against — in particular `--text-4xl` at `3.25rem` / `1.05` (Decision 11) and Playwright (Decision 13).

It was accepted on 2026-08-22 with no modification at the gate, so this is a confirmation rather than an open question. **If the ADR has since been amended, superseded or reverted, this step is `Blocked` and nothing below runs** — the note is corrected first, per [[#The ADR-007 gate]].

### 2. Apply the token and theme changes through the §6.5 procedure

Add `--ivory-75` and `--ink-975` as primitives. Repoint light `--color-surface`, light `--color-surface-raised` and dark `--color-nav-surface`. Add `--text-4xl` with its `--text-4xl--line-height` pairing at the selected value. Add the four motion tokens. Declare `color-scheme` and add the `[data-theme]` cascade with every dark-branch token defined in both selectors.

Update `scripts/check-contrast.py`'s `PRIMITIVES` and its light/dark maps **in the same change** — the script fails if the two disagree, and that is the intended behaviour. Re-run the full pairing enumeration and record the new count.

### 3. Derive and measure the inverted-surface family

Enumerate the canvas components that need an inverted treatment. Name the roles by what they do, never by appearance. Map each onto an existing primitive; add one only if none fits. Measure every new role against every surface it can appear on and add those pairings to the contrast enumeration. Record the family in [[Design System]] §6.2 before anything consumes it.

**If measurement shows the family is not yet needed by any existing component, say so and add nothing.** A role with no consumer is the speculative design §29/§35 forbid.

### 4. Establish the page-template contracts

Build the shared, **server-rendered** layout/wrapper primitive that selects Cockpit, Workbench or Focus, emitting `data-template` on its own wrapper element from a prop resolved on the server (ADR-007 Decision 8).

- **`<body>` keeps only global theme behaviour** — `data-theme` and `color-scheme`. It never carries per-route or per-template state.
- **No client mutation and no hydration race.** The template is in the first byte of HTML, identical on server and client, never reassigned after paint, and never derived from `usePathname()`.
- **No prototype-chrome dependency.** `--protobar-height` is not adopted; any offset is re-derived from production tokens, and the prototype's hardcoded workbench `max-width` is replaced by a token.
- **Assign templates to the five existing authenticated routes and the public `(auth)` surfaces only.** No template is assigned to a route that does not exist.

Derive the primitive's public API from those routes. Do not design it in advance.

### 5. Build the shared shell and layout primitives

Render the navigation plane with the `nav-*` family. Extract the page-header and section primitives the five existing authenticated pages currently duplicate by hand, consumed inside the Task 4 wrapper. Add the mobile navigation the shell does not have today, with focus trapping and focus return. Apply `--font-display` at `--text-2xl` and above per ADR-003 Decision 5. Correct `bg-accent` to `bg-accent-fill` where a fill is what is meant.

**Navigation destinations do not change.** `NAV_ITEMS` has four entries before this task and four after.

### 6. Preserve behaviour, and prove it

No route's auth gate, redirect, server action, data fetch or error handling changes. Every existing behavioural test stays green **and unmodified** — see [[#Required Tests and Proofs]].

### 7. Add Playwright and write the proofs

Add and configure Playwright (ADR-007 Decision 13), and wire the browser suite into the `web` CI job as a **required** check — a proof that runs only on demand is a proof that stops running.

Implement every proposition in [[#Required Tests and Proofs]], including the shell contracts that are correct and untested today. Keep the existing static and unit checks: they are complementary, not superseded, and several of them check things a browser cannot see.

**Do not delete or weaken an existing test to make a visual change pass** — see proposition 12.

### 8. Documentation

Update [[Design System]] with the accepted tokens, the theme cascade, the template contracts, the inverted-surface family and the motion tokens — and with the one durable statement of how a future frontend step consumes the blueprint. Update [[Design MOC]] and the ADR indexes. Narrow [[STEP-79 Domain Screen Blueprints]] only if the audit shows its wording has drifted further than this insertion already corrected.

Update this note's status and the [[Build Plan]] index row together. **Do not expand [[STEP-32 Media Processing Pipeline]]** — expansion is the succeeding step's own concern and STEP-32 stays `outline`.

## Required Tests and Proofs

**Stated as propositions to prove, not as test names.** Two layers, deliberately complementary:

- **Browser (Playwright)** — approved by the owner on 2026-08-22 (ADR-007 Decision 13), added by Task 7, and wired into required CI. It proves behaviour that only exists in a running browser: focus, keyboard, persistence, reflow, motion.
- **Static and unit (Vitest, `scripts/check-contrast.py`)** — kept in full. They run on every change, and several of them check things a browser cannot see, such as whether a token is defined *only* inside a media query.

| # | Proposition | Proven by |
|---|---|---|
| 1 | **No dead navigation.** Every rendered navigation destination resolves to a route that exists. | Static — `NAV_ITEMS` against the App Router tree and `proxy.ts`'s matcher. **Browser** — each destination navigated and asserted not to 404 |
| 2 | **All existing routes remain reachable and behave as before.** No route removed, renamed or re-gated; each still renders its own content. | Static route-tree diff. **Browser** — every existing route visited signed-in and asserted to render its landmark heading |
| 3 | **Active-route semantics and `aria-current`.** Exactly one item active per shell route; the active item carries `aria-current="page"`; a lookalike prefix does not match. | Static — extends `navigation.test.ts`. **Browser** — asserted in the live DOM on each route. *Closes a real gap: `aria-current` has no test today* |
| 4 | **Real keyboard traversal and focus order.** Tabbing through the shell and each route reaches every interactive element in an order matching visual order, with a visible focus indicator and no trap outside a modal. | **Browser** — actual `Tab` presses, reading `document.activeElement` at each stop |
| 5 | **Skip-link behaviour.** The skip link is the first focusable element and **moves focus** to the main landmark when activated. | **Browser** — focus asserted after activation, not merely the `href`. *Closes a real gap: the skip link has no test today* |
| 6 | **Mobile drawer focus contract.** Focus is trapped inside the open drawer, `Escape` closes it, and focus returns to the trigger. | **Browser** — at a mobile viewport, driving real keys and asserting `document.activeElement` at each stage |
| 7 | **Explicit theme persistence.** An explicit choice survives reload and navigation in both directions, wins over the system preference, and produces no flash of the wrong theme. | **Browser** — set, reload, navigate, assert the resolved attribute and computed background. **Static** — every dark-branch token defined in *both* the media query and `[data-theme="dark"]`, and none defined only inside a media query |
| 8 | **Contrast checker synchronization.** `scripts/check-contrast.py` and `globals.css` declare identical primitives, and every pairing clears its bar in both themes. | The existing CI check, extended with the new primitives and any inverted-surface roles |
| 9 | **Negative control.** Changing a primitive in only one file fails the check; changing it in both produces a genuine contrast failure. Both reverted. | Manual, observed and recorded — the precedent STEP-26 set for proving the check is not vacuously passing |
| 10 | **Narrow-viewport reflow and overflow.** No horizontal overflow and no content loss at each defined breakpoint and at 320px. Content hidden at a breakpoint is reachable another way. | **Browser** — measured `scrollWidth` against `clientWidth` at each viewport, and the hidden-content route exercised |
| 11 | **Reduced motion is genuinely suppressed.** Under `prefers-reduced-motion`, animation and transition do not run. | **Browser** — emulated media feature, computed durations asserted |
| 12 | **Loading, empty, error and success contracts.** Every existing async surface keeps its four states; every `loading.tsx` keeps `role="status"`; every `error.tsx` keeps `role="alert"` and never renders `error.message`. | Rendered markup + source assertion, extending the existing boundary tests |
| 13 | **No behavioural-test deletion.** Every pre-existing behavioural test passes **unmodified**. | Diff proof — no assertion weakened, skipped or removed. A visual change requiring a deleted assertion changed behaviour |
| 14 | **No prototype route or proposed capability entered production.** No new route, no new nav destination, no `deliverable`/`recipe`/`studio`/`library` identifier, no mock data rendered as real. | Static — route-tree diff plus a repository grep for the proposed nouns |
| 15 | **The template is server-rendered and stable.** `data-template` is present in the initial HTML, identical after hydration, and never reassigned on navigation; `<body>` carries only theme state. | Static — server-rendered markup inspected before hydration. **Browser** — attribute asserted across client-side navigations |

**One manual check, and only one.** Browser automation cannot faithfully reproduce **actual browser zoom**, so **200% zoom stays a manual checklist item** with a recorded result. Every other proposition above is automated. Nothing in this table is a residual gap.

## Definition of Done

The shared foundation the approved blueprint requires exists and is consumed by the shell, every existing route behaves exactly as before, and no speculative route, control or product noun entered the codebase.

Additionally, per [[Execution Protocol#Step Completion]]:

- [ ] [[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]] re-confirmed `Accepted` and unamended at `origin/main` before implementation began.
- [ ] `--text-4xl` is `3.25rem` with line-height `1.05`, registered in Tailwind's `--text-4xl` / `--text-4xl--line-height` pairing form.
- [ ] Every token change ran the full [[Design System#6.5 How to change a token]] procedure, with `globals.css` and `scripts/check-contrast.py` in agreement.
- [ ] The contrast enumeration is green in CI, with its new pairing count recorded, and the negative control observed.
- [ ] Playwright is configured and its suite is a **required** check on the `web` CI job.
- [ ] Every browser proposition in [[#Required Tests and Proofs]] passes, observed.
- [ ] Every pre-existing behavioural test passes unmodified.
- [ ] `aria-current`, the skip link and the mobile drawer's focus contract have tests, which they did not before.
- [ ] The 200% zoom manual check is performed and its result recorded — the only manual item.
- [ ] `<body>` carries theme state only; `data-template` is server-rendered and stable across navigation.
- [ ] Required CI green, and the manual checklist complete.
- [ ] Documentation updated: [[Design System]], [[Design MOC]], ADR indexes, and the statement of how future frontend steps consume the blueprint.
- [ ] Owner approval obtained — this step is Critical.
- [ ] Status synchronized between this note and the [[Build Plan]] index.
- [ ] [[STEP-32 Media Processing Pipeline]] left `outline` and `Not Started`, deliberately unexpanded.

## Implementation Record (In Progress)

Written during implementation on 2026-08-22. **The step remains `In Progress`**: it becomes `Done` only after independent review, green required CI and the owner gate ([[Execution Protocol#Step Completion]]).

### What was built

| Task | Outcome |
|---|---|
| 1. Confirm the gate | [[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]] re-read at `origin/main` (`b24bc95`): `accepted`, v2.0, 13 decisions unchanged, `--text-4xl` at `3.25rem`/`1.05`, Playwright named. Not blocked |
| 2. Tokens and theme | `--ivory-75` and `--ink-975` added; light `--color-surface`/`--color-surface-raised` and dark `--color-nav-surface` repointed; `color-scheme` declared; three-state `[data-theme]` cascade with a guarded media query and a duplicated dark branch; four motion tokens with the two-part reduced-motion block; `--text-4xl` in Tailwind's pairing form. `scripts/check-contrast.py` updated in the same change |
| 3. Inverted surface | **Derived and empty.** No production component renders an inverted canvas surface. Recorded in [[Design System]] §6.2 with the one candidate that was deliberately not promoted |
| 4. Page templates | `PageTemplate` emits `data-template` from a server-resolved prop, assigned in segment layouts so `page`/`loading`/`error` agree. `<body>` carries no per-route state |
| 5. Shell and primitives | The rail is a full-height three-region plane on the `nav-*` family — its first consumer since STEP-26 — with `ShellIdentity`, `SidebarNav` and `UserMenu` from top to bottom, mirrored by `MobileNav`'s drawer below `md`. `PageHeader` replaces 13 hand-written headers and is the display face's first consumer. `bg-accent` corrected to `bg-accent-fill` in 11 places. `NAV_ITEMS` unchanged at four |
| 6. Behaviour preserved | All 324 pre-existing tests pass **unmodified**. No auth, redirect, server action, data fetch or error handling changed |
| 7. Playwright | Added as a dev dependency, configured with `retries: 0`, and run inside the **already-required** `web` CI job. 79 browser tests after the review round, including a derived keyboard-order proof and a shell-structure proof |
| 8. Documentation | [[Design System]] §4.2a, §5.2, §6.1–6.4, §7.1, §7.2, §8, §9.2, §9a; [[Design MOC]]; the governed `AGENTS.md` command table. §7.2's claim that **workspace** identity sits at the top of the rail was corrected: the shell has no workspace data, and the document now describes what is built |

### Three findings that changed the work

- **ADR-007 Decision 5 predicts the contrast pairing count will rise. It does not, and the enumeration is right.** The check enumerates *semantic roles*, so primitives enter it only through the roles pointing at them. Two primitives were added and three roles repointed: three pairings changed value, none changed existence. The count is still **90**. Recorded in [[Design System]] §6.3 rather than quietly reconciled.
- **The contrast script's drift guard was one-directional**, and its semantic maps were not guarded at all — so a role added to `globals.css` would have been silently never contrast-checked, which is the exact failure the script exists to prevent. Widened to catch three drifts, with four negative controls observed.
- **Two real overflow defects were found by the browser suite**, both pre-existing and both in the shell: the header's user menu could not shrink, and `<main>` could not shrink beside the rail. Both violated §9a rule 4 at 320px, 375px and (for `/settings`) 768px, and neither was visible to any existing check.

### Independent review round 1 — findings applied 2026-08-22

Four findings were raised against the first implementation and all four are corrected. None required discarding the work.

| # | Finding | Correction |
|---|---|---|
| **R1** | The shell was incomplete: a full-width canvas header sat **above** a rail holding only four links, so the plane began halfway down the screen and read as an empty black block | The rail is now **one full-height column from the top of the viewport**, in three regions — product identity, the four existing destinations, the signed-in user with sign-out. The detached desktop header is gone; a compact header remains **below `md` only**, carrying the drawer trigger and the wordmark. The drawer carries the same three regions. Identity and sign-out moved onto the plane and onto `nav-*` tokens |
| **R2** | `keyboard.spec.ts` walked a fixed 25 stops and asserted only "more than three were reached" — it proved tabbing does *something*, not that it does the right thing, and a new unreachable control would not have failed it | The expected sequence is now **derived from the page**: every rendered, enabled, tabbable element in DOM order, marked with an identity index. The walk must reach all of them in that order, show a visible focus ring at every stop, visit no interactive element the derivation missed, and leave the document at the end. A negative `tabindex` no longer excuses a button or a link |
| **R3** | The template test called `page.content()`, which serializes the **hydrated DOM**, while its comment claimed it read the raw response — so it could not distinguish a server-rendered attribute from one a client effect added after paint | It now reads `response.text()` — the document body the server actually sent — asserts the template there **first**, and only then asserts the hydrated DOM matches. The client-navigation proof and the `<body>` assertions are retained; the misleading comment is replaced with why the two differ |
| **R4** | The 200% zoom check was reported as passed on the strength of CSS `zoom: 2` and an equivalent narrow viewport, which are approximations rather than the accepted manual test | **Corrected below. It is not passed.** |

**Negative controls for R2, observed.** A reachable `<button>` added to `/dashboard`: the expectation grew on its own and the proof still passed. The same button with `tabIndex={-1}`: the proof **failed** with *"tab order does not match DOM order"*. Both reverted, and the file is byte-identical to before the probe.

**No pre-existing behavioural test was changed by this round.** The specs edited (`keyboard`, `routes`, `mobile-nav`) were all written by this step.

### Independent review round 2 — finding R5 applied 2026-08-22

| # | Finding | Correction |
|---|---|---|
| **R5** | The modal scrim was `backdrop:bg-text/40`. `--color-text` is ivory in dark mode, so the scrim **lightened** the page it existed to subdue — a pale grey veil that inverted the drawer's hierarchy rather than reinforcing it. Round 1 recorded it as a future candidate; visual inspection proved it a live defect with two consumers | A named semantic role, **`--color-overlay`** ([[Design System]] §6.2a): `ink-950` at 45% in light, `ink-975` at 65% in dark, mixed in the token so no consumer chooses its own opacity. `ConfirmDialog` and `MobileNav` both write `backdrop:bg-overlay` and style nothing themselves |

**It is an overlay role, not an inverted surface, and the inverted-surface family stays empty.** A surface is opaque and carries foregrounds, so it has contrast bars and appears in the §6.3 enumeration. The scrim is translucent and carries nothing — both consumers paint their own panel above it — so no pairing exists to check and the count stayed at **90**. That distinction is documented in §6.2a rather than assumed, and the stale "first candidate for a future step" paragraph is gone.

**The property that was wrong is polarity, so polarity is what is now measured — twice.**

- `scripts/check-contrast.py` composites the **declared** scrim over all five surfaces it can cover, in both themes, and fails if the result is lighter than what it covers, or unchanged on the canvas. Measured: light `background` 0.9241 → 0.2708, dark `background` 0.0044 → 0.0028. Dark `nav-surface` is the one permitted equality — the rail is already `ink-975`, the palette's deepest value and the scrim's own colour, so nothing is lightened and the rail's content still dims.
- `e2e/scrim.spec.ts` opens the drawer in each theme with the *system* preference set to the opposite, reads the computed `::backdrop` colour, and asserts it is translucent, darker than the page, and darker still once composited.
- `shell-contracts.test.ts` proves both dialogs use the shared role and that **no** file styles a backdrop any other way; `theme-tokens.test.ts` proves the role exists in all three theme blocks, is registered as a utility, and mixes from an `ink-*` primitive in every one.

**Negative controls, observed.** Reverting the dark token to `ivory-200 40%`: the contrast script failed with *"dark scrim LIGHTENS background … a veil that lightens is not a veil"* on all five surfaces, plus the mirror-drift line. Reverting both consumers to `backdrop:bg-text/40`: both static proofs failed, and the browser proof failed in **dark only** — *"the scrim (oklab(0.944756 …)) is lighter than the page it covers"* — while light still passed, which is the defect's actual shape. All reverted.

**Visual inspection, 375×812, drawer open, both themes.** Light: the ivory page dims to a deep warm grey and the drawer reads as raised above it. Dark: the page recedes — cards, headings and the accent all subdued — with no grey wash. Drawer contrast and readability unchanged in both; identity, four destinations, address and sign-out all legible and unclipped.

**No pre-existing behavioural test was changed by this round**, and no shell layout, route, server action or data fetch was touched: the change is one token, two class strings, one checker, one new spec and two additions to tests this step already owns.

### CI round 1 — one real defect, found by the suite it added 2026-08-22

The first pipeline run on [PR #56](https://github.com/ruseduard321-prog/ProjectOne/pull/56) was green for API and governance and red for one browser case: **`/settings` scrolled horizontally at exactly 768px** — `scrollWidth` 825 against a 768 viewport, first offender `div.flex-1`.

**Cause, measured rather than guessed.** The AI Spend budget row places two `flex-1` wrappers side by side from `sm`. A flex item defaults to `min-width: auto`, so it cannot shrink below its content's min-content width — and an `<input>` with no width is sized by the user agent from `size=20` **in the resolved font**. Each wrapper's min-content was therefore the input's intrinsic width, and the row's floor was two of them plus the gap. Beside the 240px rail at `md`, the available width is 430px; the row needed 442px locally and ~537px on the runner.

**It was font-dependent, which is why it passed here and failed there.** Measured at 768px: the overflow begins once an input exceeds ~228px. macOS renders it at **213px** — 15px of margin, not a passing structure. A sweep of input font sizes reproduced the failure locally with the identical offender: 18px → `scrollWidth` 771, 20px → 813, 24px → 901, bracketing CI's 825.

**Fix:** `min-w-0` on the two wrappers — nothing hidden, no breakpoint moved, no tolerance loosened, no design change. After it, the input measures **207px at every font size tested (16 → 64px)** and the row fills its container exactly, so the layout no longer depends on font metrics at all.

**Regression proof:** the existing `responsive.spec.ts` case, unchanged in what it asserts. Its failure *message* was strengthened to name the cause rather than the symptom — overflow in px, `scrollWidth`/`clientWidth`, and the offender's width, min-content and parent row. Verified by negative control: with the fix reverted and inputs widened, it reports *"content overflows by 271px … div.flex-1 (width 367, min-content 367) inside div.flex flex-col gap-4 sm:flex-row sm:gap-4"*.

**The two latent instances are closed in the same change.** `/projects/[projectId]` carried the same pattern twice — the add-asset form in `page.tsx` and `AssetUpload.tsx` — each pairing an intrinsic `<input>` with a shrinkable `<select>`. Both passed at the time they were found, but reached within **2px** of the viewport edge once inputs were widened to 24px: the same defect, one font change from the same failure. Both wrappers in both rows now carry `min-w-0`, so the invariant holds wherever the pattern appears rather than only where CI happened to catch it.

**The invariant, stated once:** *a form control carries an intrinsic width, so the flex item holding it must be allowed to shrink below it.* That sentence is the comment at all three sites; the measurement and the reasoning live here rather than being repeated in the markup.

### The 200% browser-zoom check — `Pending owner manual verification`

**Not performed, and not claimed.** [[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]] Decision 13 keeps this manual precisely because browser automation cannot reproduce the browser's own zoom control, and driving CSS `zoom` or a proportionally narrower viewport is **not** that test — it approximates the layout consequence and reproduces neither the device-pixel rendering nor the browser's rounding.

What was run, recorded as **supporting evidence only**:

- CSS `zoom: 2` at 1280×800, and a 640×400 viewport (the CSS viewport a 1280×800 window has at 200%): no horizontal overflow, no overflowing element, the rail correctly collapsed to the drawer with every destination still reachable, headings and controls legible.

That evidence is consistent with the check passing. **It does not discharge it.** The check is completed by the project owner during review, and [[#Definition of Done]]'s zoom item stays open until then.

### Deliberately not done

- **No appearance control.** The cascade is the contract a control would be built on; the surface itself is `Proposed` under ADR-007 Decision 3.
- **`--text-4xl` has no consumer.** Where a screen's editorial display moment falls belongs to the step that owns the screen. Verified to compile correctly by probe: `.text-4xl{font-size:3.25rem;line-height:var(--tw-leading,1.05)}`.
- **No domain page rebuilt**, no route created, no product noun introduced, and [[STEP-32 Media Processing Pipeline]] left `outline` / `Not Started`.

## Risks and Governance Gates

**Critical** — this step changes shared design contracts that every later frontend surface is built against, and it carries an ADR that must reach `Accepted` first ([[CLAUDE|CLAUDE.md]] §7, §21). It touches no schema, auth, API or AI surface.

The risks worth naming are the mistakes actually available here:

- **Scope creep into STEP-80.** The single most likely failure. "While the shell is open" is how a foundation step becomes a product rebuild. The substrate/surface line from STEP-26 is the test: is this what every screen consumes, or what one screen looks like?
- **A `Proposed` capability entering production by looking obvious.** The Artifact is coherent and persuasive, which is exactly what makes Studio, Library, Recipes and the deliverable noun dangerous. Proposition 13 exists because judgment alone is not a control.
- **Drifting from the settled `--text-4xl` contract.** The value is decided — `3.25rem` / 52px, line-height `1.05`. The live risk is implementation or documentation departing from it: registering it in the Artifact's `-lh` form rather than Tailwind's `--text-4xl--line-height` pairing, letting [[Design System]] §5.2 keep a ratio claim the value contradicts instead of stating the display-only exception, or reviving the Artifact's stale "roughly 64px" prose as though it were the target.
- **Weakening a test to make a visual change pass.** Proposition 12 is the guard. A rebuild requiring deleted assertions changed behaviour.
- **Treating Playwright's arrival as licence to widen.** It is added to prove this step's contracts, not to backfill end-to-end coverage of the product. Tests for behaviour this step does not touch belong to the steps that own it.
- **A flaky browser suite becoming a suite nobody trusts.** A test that is retried until it passes is not a proof ([[CLAUDE|CLAUDE.md]] §20a). Instability is fixed or the test is removed and reported, never silenced.
- **Reporting an unobserved result.** Every proposition is observed or reported as not observed, per [[CLAUDE|CLAUDE.md]] §30b's observed-versus-attested rule.
- **Inventing component APIs the audit cannot yet justify.** This note records contracts and acceptance criteria deliberately, not signatures. A primitive's public interface is derived from the components that need it, during implementation.

## Audit Gaps Closed

**Design system application** — partial. The token layer STEP-26 built acquires its first consumer; the product-wide rollout remains [[STEP-80 Product-wide UI Rebuild]]. Closes two untested shell accessibility contracts that have been correct and unproven since [[STEP-15 App Shell and Routing]], and closes the repository's **complete absence of browser-based testing** — a gap every prior frontend step worked around rather than closed.

---

## Navigation

- **Previous:** [[STEP-31 Workflow Async Execution]]
- **Next:** [[STEP-32 Media Processing Pipeline]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]] · [[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]] · [[ADR-003 Product Visual Language and Token Semantics]] · [[Design System]] · [[STEP-26 Product Design System Foundation]] · [[STEP-79 Domain Screen Blueprints]] · [[STEP-80 Product-wide UI Rebuild]]
