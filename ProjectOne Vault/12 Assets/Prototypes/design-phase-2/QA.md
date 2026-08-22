# Verification evidence

Every figure below was measured in a browser against the generated
`artifact.html`, not asserted from the source.

**A note on how this was measured.** The verification harness renders local
files from a `data:` document, where `location.hash` is not writable. Routing
was therefore exercised through the router's own navigation API and its
documented fallback (DD-10), not by typing URLs. Hash addressing, browser
back/forward and deep links are the mechanism everywhere the host permits a
fragment write; that path could not be exercised in this harness and is
reported as verified by construction rather than by observation.

---

## 1 · Route and control sweep

Every route rendered under every scenario, checking for thrown errors,
duplicate element ids, dead controls, dead links, heading structure, unlabelled
form controls, unnamed controls, and horizontal overflow.

Thirty route addresses — every pattern, plus a concrete instance of each
parameterised one and a deliberate miss — were swept under each of the eight
scenarios.

**240 route renders. 7,342 controls. 0 thrown errors. 0 duplicate ids. 0 dead
controls. 0 dead links. Exactly one `h1` per screen, with no skipped heading
levels. 0 unlabelled inputs. 0 controls without an accessible name. 0
horizontal overflow at 1280 × 686.**

Every form control resolves a label: checked by `label[for]`, `aria-label`,
`aria-labelledby` and enclosing `<label>` in turn, across all thirty routes.

Content check across all 240 renders: no occurrence of `STEP-nn`, `Build Plan`,
`ADR-nn`, a build phase, `Supabase` or `globals.css` in any customer-facing
surface. Those words appear only in the annotation layer, the prototype chrome
and the component sheet, which declares itself prototype-only.

**Console: 0 application errors.** The only two entries in the log are the
preview harness refusing to navigate a top frame to a `data:` URL — the host
limitation described above, not the application.

---

## 2 · Viewport measurements

Home, light theme, fresh load. `contentOver` is the content area's overflow;
`outside` lists essential controls whose bounding rectangle is not fully inside
the viewport; `scrollers` lists every element that scrolls.

**Every viewport was measured in all twelve Home states** — six creation modes
× empty and filled — not in one. The campaign brief is a third longer than the
video brief and brings four times the deliverables, so a single-state
measurement proves nothing about the other eleven.

| Viewport | doc height | Page scroll | H-overflow | Content over | Panel scroll | Outside | Clipped | States |
|---|---|---|---|---|---|---|---|---|
| **1280 × 686** ⭐ | 686/686 | none | none | **0** | none | none | 0 | 12/12 |
| 1440 × 900 | 900/900 | none | none | **0** | none | none | 0 | 12/12 |
| 1280 × 800 | 800/800 | none | none | **0** | none | none | 0 | 12/12 |
| 1100 × 760 | 760/760 | none | none | **0** | none | none | 0 | 12/12 |
| 1024 × 686 | 686/686 | none | none | **0** | none | none | 0 | 12/12 |
| 768 × 1024 (tablet) | 1024/1876–2569 | natural | none | 0 | none | below the fold, by design | 0 | 12/12 |
| 390 × 844 (mobile) | 844/2224–2833 | natural | none | 0 | none | below the fold, by design | 0 | 12/12 |
| 720 × 450 (200% zoom) | 450/2360–3360 | natural | none | 0 | none | below the fold, by design | 0 | 12/12 |
| 1280 × 630 (below the floor) | 630/1096–1581 | natural | none | 0 | none | below the fold, by design | 0 | 12/12 |

The doc-height ranges on the scrolling tiers span the twelve states: the
shortest is Plan mode filled, the tallest Repurpose empty.

⭐ is the published Artifact's content viewport and the primary acceptance
target. At 1280 × 686 it satisfies both halves of the criterion in DD-09:
`scrollHeight (686) <= clientHeight (686)`, **and** every essential control —
the prompt, the primary action, the reference, project and destination
controls, the master, the totals row, all three zones and the urgent item — has
a visible bounding rectangle inside the viewport.

**Horizontal overflow: none at any size**, verified by comparing
`documentElement.scrollWidth` against `clientWidth` and by sweeping every
element in the document for a rectangle outside the viewport.

**Clipped controls: none at any size**, verified by walking each control's
ancestors for a clipping container it falls outside of. A *scrollable*
ancestor is not a clipping one: wide tables and the tablet-width studio rail
scroll inside their own `overflow-x: auto` container, which is the documented
pattern, and the walk stops there rather than reporting reachable content as
lost.

Below 40rem of height the lock releases and the page scrolls normally; the
rail's own navigation scrolls internally when the window is shorter than the
rail, which is the correct behaviour for a fixed rail.

---

### 2a · The prototype chrome bar below 48rem

A `select` sizes to its widest option and will not shrink below that while its
`min-width` resolves to `auto`. The scenario control's longest option —
`Scenario: Signed in as Diego (Editor)` — held it at 246px, which on the
two-row bar pushed the annotations switch 7px past the viewport at 375px.

The select now shrinks and truncates; the switch keeps its full width, because
it is the smaller and harder-to-hit of the two targets. Nothing else moved: the
rule lives inside the existing `max-width: 47.999rem` block, so every width from
48rem up is untouched by construction and was re-measured to confirm it.

| Width | Document | Overflow | Select | Toggle | Bar height |
|---|---|---|---|---|---|
| 360 | 360 | **0** | 16 → 228 | 236 → 344 | 72px |
| 375 | 375 | **0** | 16 → 243 | 251 → 359 | 72px |
| 390 | 390 | **0** | 16 → 258 | 266 → 374 | 72px |
| 768 | 768 | **0** | natural | natural | 40px |
| 1280 | 1280 | **0** | 898 → 1144 | 1156 → 1264 | 40px |

All thirty routes were swept at 360, 375 and 390: **0 with horizontal
overflow.** Both controls were exercised at 360px — switching the scenario to
Member applied it, and the annotations toggle flipped its `aria-pressed` state.
The bar stays two rows at every width, so `--protobar-height` is unchanged and
the sticky offsets built on it are unaffected.

---

## 3 · Contrast

Every rendered element carrying text, measured against its resolved background
and its own font size and weight, at the WCAG 2.1 AA bars (4.5:1, or 3:1 for
large text).

| Theme | Surfaces | Elements checked | Failures |
|---|---|---|---|
| Light | 30 routes + 6 filled Home modes | 2,489 | **0** |
| Dark | 30 routes + 6 filled Home modes | 2,489 | **0** |

**4,978 measurements, 0 failures.** Re-run in full after the token remap in
DD-01 and DD-02 and again after the art-direction pass in DD-16 to DD-18:
neither the warmer light palette nor the five new set-ups cost anything, because
no interface colour changed in either.

A separate run at 1280 × 686 across the six Home modes in both themes and both
composer states measured a further **2,164 elements, 0 failures.**

Three exclusions, all principled rather than convenient:

- Type set *inside* the campaign artwork is not interface text. It is burned
  into a picture, on a scrim drawn beneath it, and it does not change between
  themes. **56,296 such nodes** were excluded on that basis.
- Type painted *on* the artwork — the numbered review pins — sits on an ember
  disc drawn by a pseudo-element, which a resolver walking `background-color`
  up the ancestor chain cannot see; measured naively it compares the numeral
  against the page ground and reports a failure that is not there. **24 nodes.**
- Screen-reader-only text is clipped out of the visual layer, so its contrast
  is not a property anyone experiences. **344 nodes.**

Both of the last two were confirmed by hand rather than assumed: the pin's
plate and the `.zcount` status dot were read off `getComputedStyle` directly to
establish that the real painted background passes.

---

## 4 · Annotations

Turning the provenance layer on must move nothing, or it changes the design it
is annotating.

Measured across all thirty routes with transitions and animations disabled so
nothing in flight is mistaken for a shift, comparing element *references* rather
than list positions — turning the layer on inserts nodes, so a positional
comparison silently compares different elements: **29,112 elements compared
before and after, 0 moved, 0 height changes.** Document height identical
everywhere. The annotation chrome itself — the legend, the toggle and the badges
— is excluded, since appearing is what it is for. The layer is out of flow by construction — an `outline` plus an
absolutely-positioned badge.

---

## 5 · Journeys

Assertions driven by real clicks on real controls, in order. Nothing below was
asserted from the source.

### 5a · The composer, the brief essentials and the paid pack

| | Step | Result |
|---|---|---|
| A1 | Four mode-aware essentials render — Audience / Tone / Run time / Channels | PASS |
| A2 | Empty, the composer shows one guidance sentence and two example briefs | PASS |
| A3 | The audience popover opens with five options and the current one pressed | PASS |
| A4 | Choosing one updates the value and closes the popover | PASS |
| A5 | Filled, the examples give way and the note becomes *"Read from your brief"* | PASS |
| A6 | The Channels popover lists all five paid placements | PASS |
| A7 | Unticking Display: `40 deliverables · $4.77–$11.51` → `35 · $4.52–$10.91` | PASS |
| A8 | The popover stays open while ticking, and focus returns to the row pressed | PASS |
| A9 | Ticking it back restores both the deliverables and the cost | PASS |
| A10 | The contact sheet reports the true count — *34 pieces*, 9 tiles, `+25` | PASS |
| A11 | The full pack on Home: **40 deliverables · $4.77–$11.51 · ~3h 34m · 2 approvals** | PASS |
| A12 | Home still fits 1280 × 686 with the full pack — `doc 686/686`, content over 0 | PASS |
| A13 | The plan carries a **Paid media** stage | PASS |
| A14 | All six paid formats appear on the plan by name | PASS |
| A15 | The plan restates all four essentials before anything runs | PASS |
| A16 | Removing the banner set re-derives: `$4.77–$11.51` → `$4.52–$10.91` | PASS |
| A17 | The project's deliverables hold the paid work | PASS |
| A18 | The library's **Paid media** filter returns exactly the six paid items | PASS |
| A19 | The placement is named on the card — *"Meta feed · 1080 × 1350 · 2 variants"* | PASS |
| A20 | An ad opens in review with its versions, its open note and *Approve version 2* | PASS |
| A21 | A member is told the role boundary, and is offered no approve control | PASS |
| A21b | …and is never told it is *"your"* approval, which they cannot give | PASS |
| A22 | The budget ceiling disables starting and says why | PASS |

A placement whose channel is unticked is **not** offered by the plan's
*"Add something back"* picker — it was never on the plan, and its channel is
where it comes back. Verified.

### 5c · Art direction — one campaign, not one photograph

Fifteen assertions, run against the built artifact.

| # | Assertion | Result |
|---|---|---|
| 1 | Ten set-ups defined and injected | **PASS** — 10 groups |
| 2 | No duplicate ids in the scene library | **PASS** — 0 |
| 3 | No paid headline is truncated by its wrap | **PASS** — 0 dropped words |
| 4 | Six placements produce six thumbnail silhouettes | **PASS** — 6 distinct |
| 5 | Five banner sizes produce five ratios | **PASS** — 5 |
| 6 | Twelve supporting posts span many set-ups | **PASS** — 10 over 12 |
| 7 | Six title cards carry six episode titles | **PASS** — 6 |
| 8 | Six vertical teasers carry six captions | **PASS** — 6 |
| 9 | The copy test shows two buttons in two positions | **PASS** — 2 |
| 10 | `One idea. The whole production.` unchanged | **PASS** |
| 11 | Home's campaign sheet shows all six paid placements | **PASS** |
| 12 | Every tile on that sheet is a different picture | **PASS** — 9 of 9 |
| 13 | The Creation Plan draws the same mappings | **PASS** — 7 over 12 rows |
| 14 | Library's paid filter: six cards, six set-ups | **PASS** |
| 15 | Review keeps the placement chrome | **PASS** — skip control present |

Assertion 11 is the one that changed the code rather than confirming it. The
contact sheet filled its cells run-length — every copy of the first deliverable
before moving on — so a campaign with twelve supporting posts showed twelve
supporting posts and none of the six paid formats. It now fills round-robin,
which is what a sheet of selects is for.

---

### 5b · The full product journey

Twenty-two assertions driven by real clicks on real controls, in order.

| | Step | Result |
|---|---|---|
| 1 | An idea is typed; the primary action enables | PASS |
| 2 | Switching mode changes the outputs, and switching back restores them | PASS |
| 3 | A reference is attached; the picker closes; the chain's source updates | PASS |
| 4 | A destination is chosen from its popover | PASS |
| 5 | The plan is prepared | PASS |
| 6 | Removing a deliverable marks 3 dependents unbuildable, naming what they lost | PASS |
| 6b | The estimate re-derives: `$1.34 – $3.27` → `$0.09 – $0.27` | PASS |
| 6c | Adding it back restores the plan and clears the blocks | PASS |
| 7 | Production starts, behind a cost confirmation | PASS |
| 8 | The run is queued, and says nothing executed inside the request | PASS |
| 9 | The worker advances it to an approval gate | PASS |
| 9b | The change is announced in a live region | PASS |
| 10 | The approval drawer states the one-step scope — *"Approve one step · Step 2 of 3"* | PASS |
| 10b | The safe choice is focused first | PASS |
| 11 | Approving releases exactly that step | PASS |
| 12 | The run completes and **shows what it produced** | PASS |
| 13 | A stopped run explains the retry ceiling and what was billed | PASS |
| 13b | The failure drawer carries the attempt log | PASS |
| 14 | Resuming warns that the provider may be called a second time | PASS |
| 14b | The safe choice is focused first | PASS |
| 14c | The run resumes from the last completed step | PASS |
| 15 | The library lists the whole campaign | PASS |
| 16 | Review shows the work, its versions and one decision | PASS |
| 17 | A note is added and appears pinned to the frame | PASS |
| 18 | Approving stamps the version | PASS |
| 19 | An open note can be resolved | PASS |
| 20 | The project reflects the new state | PASS |
| 21 | Regenerating shows the cost first and adds a version beside the old one | PASS |
| 22 | The command palette searches and navigates | PASS |

---

## 6 · Keyboard and focus

- **33 focus stops** on Home; tab order follows the visual order with one
  inversion (the ambient spend link, which sits to the right of the heading it
  follows in the document).
- **No positive `tabindex`** anywhere.
- **Overlays trap focus** and **return it to the control that opened them** —
  verified for both drawers and popovers, including the two brief-essential
  popovers. `aria-expanded` tracks the trigger, `aria-pressed` tracks the
  current value on every option, Escape closes, and focus returns to the
  essential that was pressed.
- **Overlays are emptied when they close.** A closed `<dialog>` is inert, so
  stale markup does no visible harm — but it leaves stale ids and stale
  `data-act` attributes in the document for the next thing that searches it.
- **Escape** closes any overlay; the `cancel` handler is intercepted so the
  dialog stack stays authoritative.
- **Spending and destructive confirmations focus the safe choice first**
  ("Not now", "Cancel", "Keep my workspace") and the destructive ones ignore a
  backdrop click.
- **Focus rings**: every list row, card, chip and control was checked against
  its clipping ancestors. One control — the segmented mode bar, which clips its
  own rounded corners — takes an inset ring so it cannot be cut off. Everything
  else has clear room for the 2px offset ring.
- **Reduced motion**: nine keyframe animations exist (`enter`, `pulse`, `pop`,
  `modalin`, `drawerin`, `navin`, `toastin`, `spin`, `sheetin`) and all are
  neutralised by the `prefers-reduced-motion` block, which sets every duration
  to 1ms with `!important` on the universal selector, along with every
  transition, `scroll-behavior` and `scroll-snap-type`.
- **`color-scheme`** is declared for all three theme states, so the caret, the
  selection, the scrollbars and every native control resolve in the same world
  as the page (DD-02a).

---

## 7 · Build

- `node --check` passes on all three scripts.
- `make-artifact.sh` is **deterministic**: two consecutive runs produce
  byte-identical output — `724a715294e0a06e282a3909269ebdda`, 490,604 bytes.
- The generated artifact is self-contained and takes exactly one external
  dependency: the two typefaces from Google Fonts, the one host the Artifact
  CSP allows.
- No secret, key, token or fencing sequence appears in any source file. The two
  key-shaped strings (`4d1c`, `9f27`) are invented last-four fragments, and the
  copy around them states that a key never reaches the browser.

---

## 8 · Known limitations that a static prototype cannot honestly solve

- **The simulated worker is timing only.** The step sequence, the approval gate
  and the step record mirror what the backend does; how fast it happens does
  not, and it is annotated as simulated wherever it appears.
- **The assistant's conversation is fixed.** Making it respond freely would
  mean inventing answers, and the point of that screen is that its answers are
  true.
- **Nothing is uploaded.** The reference picker attaches from an invented
  library; no file is read from disk and nothing leaves the page.
- **Hash addressing could not be exercised in this harness** — see the note at
  the top.
- **A governed notice makes Home scroll.** When the budget ceiling or the
  breaker has something to say, the notice takes the room it needs and the
  content area scrolls by roughly 120px at 686px of height. The message
  outranks the layout target; nothing is hidden to preserve it.
- **The set rotations are authored, not inferred.** Which set-up, lockup and
  line each copy of a multi-copy deliverable gets is a fixed list written by
  hand. Nothing here is a model choosing a composition, and the prototype does
  not imply that it is.
- **The paid-media pack is drawn, not generated.** Every advertising format in
  this prototype is original SVG produced by the artwork engine. The current
  backend generates none of them, the README's provenance ledger names each
  primitive the pack would need, and the interface never implies otherwise.
- **The brief essentials are not extracted from anything.** They are the mode's
  own values, editable. Nothing reads a brief and infers an audience today, and
  the note above them is a statement about what the plan would be built from —
  restated on the plan, changeable at both points — not a claim that inference
  happened.
- **Screenshots from the verification harness are unreliable in light mode.**
  The preview pane's screenshot compositor renders some composited layers with
  the wrong theme's values while the DOM and CSSOM are correct — confirmed by
  reading computed styles on the same elements in the same frame. Every visual
  claim in this document is therefore backed by measurement rather than by an
  image.
