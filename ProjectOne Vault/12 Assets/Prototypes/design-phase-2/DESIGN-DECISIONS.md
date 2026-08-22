# Design decisions

Decisions taken in this prototype that an implementation must know about,
including the ones that need the owner's approval before they become real.

---

## DD-01 · The rail is the deepest plane, in both themes

**Status: RESOLVED. Option 1 taken — one new primitive, one remapped token.**

The dark theme used to map `--color-nav-surface` and `--color-background` to
the *same* primitive (`#0F0E0D`), so the matte-black rail — the direction's
load-bearing identity element — dissolved into the page it hangs beside. A
component-level border was holding the edge together, which encoded a
workaround as a rule.

**The decision.** The rail is the deepest plane in the room, in both themes:
matte black against ivory in light, and below the canvas in dark. One primitive
is added and one semantic token is remapped.

| | Was | Now |
|---|---|---|
| `--ink-975` (new primitive) | — | `#070605` |
| `--color-nav-surface`, dark | `var(--ink-950)` `#0F0E0D` | `var(--ink-975)` `#070605` |

Nothing else moves. The dark surface ladder is now monotone through four
planes — rail `#070605`, canvas `#0F0E0D`, panel `#1A1816`, sheet `#242120` —
and the rail's hover state (`--color-nav-surface-raised`, `#1A1816`) gained
contrast against it rather than losing any.

**The border stays**, and its job changes. At the bottom of the luminance range
a seven-step tonal difference is real but quiet, and a long vertical boundary
reads better with a hairline on it. It is now the detail that makes the step
read as an edge, not the thing standing in for a missing step. Restrained, and
supported — which is what was asked for.

**What this asks of `globals.css`:** add `--ink-975: #070605` to the primitive
layer and repoint dark `--color-nav-surface` at it, in both the
`prefers-color-scheme` block and the `[data-theme="dark"]` block.

## DD-02 · Nothing in the light theme is pure white

**Status: RESOLVED. The candidate fix recorded here was taken.**

The approved direction contains no pure white: its lightest large plane
measures about `#FAF4EB`. The token layer used to map `--color-surface-raised`
to `#ffffff` — the background of the composer, the outcome panel, every modal,
drawer and popover, and every input. On an ivory canvas a pure-white panel
reads as a hole rather than as a raised surface.

**The decision.** Three warm planes, monotone in both luminance *and* warmth:
the canvas you work on, the panel that sits on it, the sheet you write on.

| | Was | Now | R−B |
|---|---|---|---|
| `--ivory-75` (new primitive) | — | `#FDFAF3` | 10 |
| `--color-background` | `--ivory-100` `#FAF6EE` | unchanged | 12 |
| `--color-surface` | `--ivory-50` `#FFFDF8` | `--ivory-75` `#FDFAF3` | 10 |
| `--color-surface-raised` | `--white` `#ffffff` | `--ivory-50` `#FFFDF8` | 7 |

The old ladder *lost* warmth as it rose (12 → 7 → 0) and ended on a colour the
direction does not contain. The new one stays warm all the way up, and the
raised plane keeps exactly the separation from the canvas that the old
mid-plane had.

Two things improved that were not the point. Hover states are now visible:
`--color-surface` on `--color-surface-raised` used to be a two-value
difference (`#FFFDF8` on `#ffffff`) and is now a real step. And every measured
contrast result survived — **3,680 rendered text elements per theme, 0
failures**, unchanged from before the remap.

`--white` is kept as a primitive and still used for `--color-accent-contrast`
and `--color-danger-contrast`, which are type *on* vermilion and red, not
surfaces.

**What this asks of `globals.css`:** add `--ivory-75: #FDFAF3` to the primitive
layer, and repoint light `--color-surface` and `--color-surface-raised` one
rung down.

## DD-02a · The page declares its `color-scheme`

Neither theme block declared `color-scheme`, so the caret, the text selection,
the scrollbars and every native control kept the operating system's scheme
while the page kept ours — the two disagreeing in exactly the places CSS does
not control.

`color-scheme: light` is now set on bare `:root`, and `dark` in both the
`prefers-color-scheme` block and the `[data-theme="dark"]` block, with an
explicit `:root[data-theme="light"]` so the toggle wins in both directions —
the same three-state shape the tokens already use.

## DD-03 · Three page templates, and no fourth

Every surface uses one of **Cockpit**, **Workbench** or **Focus**, selected by
`body[data-tpl]` and nothing else.

The alternative — letting each screen choose its own width and rhythm — is what
produces a product where nine screens look like nine products. The alternative
in the other direction — one template for everything — is what produced the
previous version's complaint that every screen opened with the same masthead
and was distinguishable only by the word in its heading.

Three is the number of genuinely different jobs: operate a workspace, inspect
one thing beside its context, decide one thing carefully.

## DD-04 · Full width is scoped to one route

`body[data-view="dashboard"]` scopes every full-width and height-locked rule.
No other screen can inherit a layout it was not designed for, and removing Home
would remove the entire lock with it. Other screens keep their readable centred
widths.

## DD-05 · Two compositions on Home, and a measured floor

The published Artifact's content viewport is **1280 × 686** — not 800, and not
900. Home therefore has a rich composition, a compact one, and a height below
which it stops trying.

Both boundaries are measured rather than chosen:

- The **rich** composition needs about 766px of content area and only clears
  that from roughly **55rem** (880px) of window height. Above the boundary the
  masthead is 52px and the rows are roomier.
- The **compact** composition needs 631px at 1280 wide, so the lock's floor is
  **40rem** (640px). Below it the lock releases entirely and Home scrolls like
  any other document.

Setting the boundary by taste rather than measurement is what produced the
previous version's 150px overflow at 1280 × 800, where the three lower zones
simply fell off the bottom of the window and were quietly called optional.

**Nothing is hidden to reach the target.** Exactly one label is suppressed at
the compact height — the four-letter stage eyebrow above each chain step — and
the step's own name stays. Where a row would otherwise wrap and cost the page
twenty pixels it does not have, it is held to one line and truncates; the full
text of an example is still what lands in the field when you press it.

## DD-06 · Media is drawn once and cropped, never redrawn

Each scene is defined once in a canonical 1600 × 900 space inside `<defs>`, and
every derivative is the same scene under a different `viewBox`.

This is not a rendering optimisation, though it is one: zero duplicate ids
however many frames are on screen, and one `<use>` element per instance. It is
the product thesis made visible. A 9:16 teaser that is demonstrably a crop of
the 16:9 master teaches "one idea, the whole production" in a way no caption
can.

Two consequences, both deliberate:

- **The campaign palette is literal, never a semantic token.** A photograph
  does not change colour when the interface goes dark.
- **Written work is drawn on ivory, media on ink.** A script and a master cut
  have to be distinguishable at 40px without reading a word.

## DD-07 · Listings letterbox; presentations do not

A library holds 16:9 masters, 9:16 teasers, 1:1 cards and portrait pages.
Laying each one out at its own aspect turns a grid into a staircase, and a
vertical clip four times the height of the card beside it stops being
comparable at all.

Every **listing** therefore shows its media letterboxed on a 16:9 ink plate:
uniform rhythm, with the true shape still visible inside it. Every
**presentation** — the review stage, the plan hero, the studio canvas — keeps
the real aspect, because there the shape of the thing is the information.

## DD-08 · One type step added: `--text-4xl`

**Status: a proposal, not a transcription.**

The approved direction sets the Home question at roughly 64px. The scale in
`globals.css` stops at `--text-3xl` (36px), and reinterpreting an existing step
would change what it means everywhere it is already used.

So one step is **added** above the display boundary: `--text-4xl: 3.25rem`,
line-height `1.05`. Additive, so nothing existing changes meaning, and bounded
by ADR-003's rule that the display face is used at the largest sizes and never
for body copy, labels or controls.

It is used in exactly one place: the Home question, at 64rem of width and 55rem
of height and above. Below that the question steps down through
`clamp(2.25rem, 5vh, 2.75rem)` rather than to a fixed smaller size, so a 686px
host and an 850px one are both composed rather than one being a squeezed
version of the other.

## DD-09 · Verify against the host viewport, not the design mock

A design that is only measured at the size it was drawn at is measured at the
one size nobody will use. For this prototype the host viewport is
**1280 × 686**, and it is the primary acceptance target.

Every claim of "no scroll" in [QA.md](QA.md) means both of:

- `document.documentElement.scrollHeight <= clientHeight`, **and**
- every essential control has a visible bounding rectangle inside the viewport.

Either one alone can be satisfied by a page that has quietly clipped something.

## DD-10 · The router survives a host that will not let it write its own URL

Hash routing is the addressing scheme: every screen has a stable address,
browser back and forward work, and refreshing keeps you where you were.

Some hosts will not let a document change its own fragment — a `data:` document
is the common one. The router detects that its write did not take and falls
back to an in-memory route, so the prototype still navigates. Where the
fallback engages, the address bar stops tracking the route and back/forward
stop applying to it. That is the honest cost, and it is why it is a fallback
rather than the mechanism.

## DD-11 · The specimen sheet has no dead controls either

A page full of buttons that do nothing is the dark pattern the rest of this
prototype refuses, and documentation does not get an exemption. Every specimen
on `#/spec` is live: it toggles, opens something, or reports what it is.

## DD-12 · Roles are a person, not a toggle

The read-only scenario signs you in as **Diego Salas, Editor** rather than
flipping an abstract permission flag. The rail, the account menu and every
refusal message change with him.

A permission boundary demonstrated as a switch is a feature; demonstrated as a
colleague, it is a product. It also caught a real defect: the rail's identity
was static markup, so the previous version said "Owner" on the very screen
whose purpose was to show what a Member cannot do.

## DD-13 · The composer's height is spent on the brief, not on the field

A textarea given `flex: 1 1 auto` absorbs every spare pixel in the row. It
looks generous in a mock and reads as a void in use: a three-line placeholder
floating in a hundred and twenty-eight pixels of ivory, with the eye going
straight to the empty part.

The field is now bounded and the space goes to things that carry information:

- **The writing well** holds the field *and*, while it is empty, the guidance —
  one sentence on what a good brief for this mode contains, and two that
  already have it. Guidance inside the well rather than under it is what keeps
  the composer from changing height the moment you start typing.
- **Brief essentials** — four values, label and value on one line, two by two.
  Which four is mode-aware. They are one press from being something else, and
  the note above them never claims more than it should: *"Where Video starts"*
  when empty, *"Read from your brief"* when filled.

One implementation note worth keeping, because it cost an hour: a textarea's
automatic height is `rows` × line-height, and `height: 100%` against a parent
of *indefinite* height resolves to `auto`. The field therefore never shrank
below three lines however small the window got, and no `min-height` could
persuade it to. Giving the field `flex-basis: 0` makes its height definite,
which is what lets both rules finally apply.

## DD-14 · The master is the preview panel's spring

The outcome panel carries a chain, a master and a contact sheet, and the sheet
is the part whose size the *content* decides — six deliverables in Plan mode,
thirty-four in a campaign with its paid pack.

Give the master a fixed height and the panel overflows whenever the sheet grows,
which is how a picture ends up deciding whether you can see the price. Give it
a share of the viewport and it is right at one window size.

So the master takes whatever height the panel has spare, up to a ceiling, and
yields to a floor when the sheet needs the room. Everything else in the panel
is `flex: none`. For that to work the flex chain above it — `.wrap`,
`.cockpit`, `.cockpit__work` — has to be allowed to compress (`min-height: 0`,
and an explicit `minmax(0, 1fr)` row), and the composer is pinned at
`min-height: min-content` so it is never the thing that yields. Writing is what
you came to do; it does not get squeezed to make room for a preview of it.

## DD-15 · Advertising is a campaign output, not a subsystem

The paid-media pack — feed ad, story and Reels ad, in-feed TikTok variation,
pre-roll, five display sizes, and the copy variants they share — is six more
deliverables on the Campaign mode's plan. It has **no route, no navigation
destination and no separate section**, because it is not a different kind of
work: it is the same master, cropped and re-typeset for a placement that
happens to be bought.

Three consequences:

- **Channels drive it.** The `Channels` essential is the paid selector in
  Campaign mode; each placement is tied to a channel, and unticking one takes
  its deliverables *and their cost* off the plan. They are not "removed" — they
  were never asked for, so the plan's add-back picker does not offer them.
- **The library groups by purpose, not by medium.** A pre-roll is video, a
  banner is a still, the copy is written — so the paid filter keys on what the
  work is *for*. The medium filters stay true.
- **The artwork knows what an ad is.** `lockup: 'ad'` measures its own crop and
  arranges a headline, a brand and one call to action either horizontally or
  stacked, so the same lockup holds at 728 × 90 and at 160 × 600. At
  contact-sheet size the type is dropped and the CTA pill is kept: four
  illegible pixels of headline say nothing, and the pill says "paid".

**Two boundaries the prototype states in the interface, not just here.**
ProjectOne shows no third-party advertising to its users — the only advertising
in the product is advertising the customer owns. And ProjectOne makes the
creative; it does not buy media, bid, or place anything.

---

## DD-16 · A campaign is a shoot, not a photograph

**Decision.** A deliverable that exists in several copies names a **set** — an
ordered list saying what each copy is: which set-up, which lockup, which line.
The seat picks the entry. Ten set-ups replace the original five.

**The problem it fixes.** The first build leaned entirely on the seat offset to
tell copies apart: twelve supporting posts were twelve shifted crops of one pan.
That is technically a set and emotionally a repeat, and it was the single thing
holding the campaign back from reading as premium. A shifted crop of one picture
is still one picture.

**The ten set-ups**, chosen so the six things a food campaign actually shoots
are all present: `sear` (searing, wide) · `flip` (motion, food in the air) ·
`flame` (live fire, rebuilt with a subject under it) · `spice` (seasoning macro)
· `hands` (hands at work) · `plate` (the plated result) · `quote` (the editorial
plate) · plus `over`, `loaf` and `knife` from the original set.

**What holds identity, and what carries variety.** Identity is the grade, the
literal ember-and-ivory palette, the one warm key, and the master narrative —
all unchanged, all shared by every frame. Variety is spent on focal subject,
composition, scale, typography and CTA placement. That split is the whole
decision: one campaign, not one image and not forty unrelated stock photographs.

**Two consequences worth stating.** `plate` is the only set-up built on ivory
rather than ink, which is what lets it read as an ending rather than as another
step. `quote` is deliberately near-empty, because a campaign that never stops
showing food never lets a sentence land — and the `social` rotation includes
frames with **no type at all**, since a feed that captions every post reads as a
content farm.

**Every word in every set already exists in this campaign** — episode titles,
techniques, the tagline, the idea. A set recombines the campaign; it does not
write a new one.

---

## DD-17 · A paid placement is furniture, not a crop

**Decision.** Each of the six paid formats draws its own **chrome** — the
furniture the placement is sold inside — and the chrome is drawn **first**, so
it survives the thumbnail when the headline cannot.

| Placement | What identifies it at 90px |
|---|---|
| Meta feed | attribution row on top, one full-width button welded to the base |
| Story / Reels | five segment bars across the head, centred pill at the foot |
| TikTok | a rail of controls hard right, copy hard left — the only asymmetric one |
| YouTube pre-roll | a skip control and an elapsed bar along the very bottom edge |
| Display | a keyline unit at its real ratio, floated on a mat that dims the rest |
| Copy / CTA test | both halves at once, split by a hairline, marked A and B |

**Why chrome and not a crop.** Six placements that share a picture *and* a
layout are one advertisement with six file names. At contact-sheet scale the
headline is four illegible pixels, so the only thing that can distinguish them
is silhouette — and silhouette is exactly what platform furniture is.

**The display set draws sizes, not stills.** A banner is sold as a size, so the
unit is drawn at its real ratio on a mat rather than full-bleed. Five sizes are
then five visibly different shapes at any tile size.

**Nothing here reproduces a platform's marks.** A segmented progress bar and a
rail of circles are layout conventions, not trademarks. No logo, brand name or
third-party asset appears in any placement, and the boundary in DD-15 is
unchanged: this is advertising the customer owns, never advertising shown to
them.

---

## DD-18 · Type in a picture is measured, never estimated

**Decision.** Every headline, caption and pull-quote set into artwork is wrapped
and sized against its **measured** width, using `getComputedTextLength` against
the fonts that actually loaded, cached once the font set is ready.

**Why a constant could not work.** The two builds of this prototype are not set
in the same faces. The artifact loads Instrument Serif and Inter; the repository
copy takes no external dependency and falls back to Georgia and the system sans.
Their advances differ by about a quarter — measured at 0.317–0.357 per character
for Instrument Serif against 0.425–0.475 for Georgia. A character count safe for
one wastes a quarter of the frame on the other.

**And why the first attempt was worse than the bug.** A fixed count with a line
cap does not overflow — it silently drops the last words. "Six techniques. No
fear." became "Six techniques. No". Losing a word out of a campaign is a worse
failure than a headline touching the frame edge, because nobody notices it.

**The rule.** Blocks shrink to fit; they never truncate. Where a measurement is
unavailable the fallback is the *wider* face, which is the safe direction to be
wrong in.
