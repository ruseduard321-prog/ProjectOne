# ProjectOne — the product blueprint

**"The Cutting Room."** A static, dependency-free, fully clickable model of what
ProjectOne should become.

**This is not the application.** It has no build step, no framework, no network
call, no database, no authentication, no AI provider and no storage beyond a
single theme preference. Every name, number, timestamp and image in it is
invented, and every image is *drawn* rather than fetched.

Open `index.html` in any browser. Nothing to install, nothing to run.

---

## Status

| | |
|---|---|
| Phase | Final design pass — the complete product surface |
| Direction | "The Cutting Room" (owner-approved) |
| Governed by | [[ADR-003 Product Visual Language and Token Semantics]] (Accepted) |
| Branch | `design-complete-product-experience` |
| Scope | Prototype only. No production file, migration, ADR or plan status is touched. |

## Files

| File | Role |
|---|---|
| `index.html` | **Authoritative entry point.** Document shell + the 24×24 icon sprite. |
| `styles.css` | **Authoritative styling.** Tokens transcribed from `apps/web/src/app/globals.css`, then the component contracts. |
| `campaign.js` | **The campaign and the artwork.** One fictional production, and the SVG engine that draws every piece of media in the product. |
| `prototype.js` | **The core.** Utilities, the fake server payload, the router, the shell, overlays, shared components. |
| `screens.js` | **The screens.** Every product surface, registered into `PO.views`. |
| `DESIGN-DECISIONS.md` | Decisions taken here that an implementation must know about. |
| `ROUTES.md` | The route and capability inventory, with the page template each surface uses. |
| `QA.md` | The verification evidence: viewport measurements, audits, journeys. |
| `make-artifact.sh` | Regenerates `artifact.html`. Run after changing any of the five above. |
| `artifact.html` | **Generated — never edit by hand.** One self-contained file for the Artifact panel. |

### Why `artifact.html` exists, and its only two differences

The Artifact panel needs one self-contained file. It differs from the
repository copy in exactly two ways, both deliberate:

1. It omits `<!doctype>`/`<html>`/`<head>`/`<body>` — the Artifact host supplies them.
2. It loads **Inter** and **Instrument Serif** from Google Fonts, the one
   external host that panel's CSP allows, so the direction can be reviewed in
   its real faces.

**The repository copy takes no external dependency at all.** It uses the
fallback chains declared in `globals.css` (`system-ui` for body, `Georgia` for
display). The type *scale*, *weights* and the display-face *boundary* are
faithful either way; the two webfaces are the one known fidelity gap when you
open `index.html` locally.

---

## The campaign

Everything in this prototype is one piece of work, at one moment in its life.
Home, the plan, the project, the studio, a run, the library and a review all
describe the same production — because a prototype where every screen shows
different fake data reads as a folder of mockups, and one where they agree
reads as a product.

**Kitchen Confidence — Season Two.** Six techniques people are afraid of. Six
episodes. No fear. Tagline: *Cook it scared.* Launches 14 September, nine days
out.

- **Avery Kim** — creator, workspace **Owner**
- **Noor Haddad** — producer, **Admin**
- **Diego Salas** — editor, **Member**: can create, edit, start production and
  resume a stopped run; cannot approve, set budgets or manage people. He is
  who you are signed in as under the read-only scenario.
- **Priya Raman** — design, **Member**

Eighteen deliverables across the master, its derivatives, the design system,
the written work and the **paid-media pack** — with versions, open notes, an
approval trail, and one item that is blocked behind a decision rather than
behind a machine.

### The advertising

Six of those eighteen are advertisements **the creator is making**: a Meta feed
ad, a Story and Reels ad, a TikTok in-feed variation, a YouTube pre-roll, a
five-size display banner set, and the paid copy and CTA variants they all draw
from. They are campaign deliverables like any other — cut from the same master,
versioned, reviewed, approved.

Each of the six draws its own **chrome** — the furniture the placement is sold
inside — and draws it first, so the format is still identifiable at 90px when
the headline is four illegible pixels: an attribution row and a full-width
button for the feed unit, segment bars for the story, a control rail for the
in-feed variation, a skip control and an elapsed bar for the pre-roll, a keyline
unit at its real ratio for each banner size, and an A/B split for the copy test.
None of it reproduces a platform's marks — a segmented bar and a rail of circles
are layout conventions, not trademarks. See DD-17.

Two boundaries, and neither is negotiable:

- **ProjectOne never shows third-party advertisements to its users.** The only
  advertising anywhere in this product is advertising the customer owns.
- **ProjectOne does not buy media, bid, or place anything.** It makes the
  creative. The copy says so where the channels are chosen.

### The artwork

Every generated deliverable is drawn as original SVG. No raster asset, no
external request, no third-party mark.

Each scene is defined **once**, in a canonical 1600 × 900 space, inside
`<defs>`. Every derivative is the same scene under a different `viewBox` — a
real crop of the real master, exactly as a real derivative is. A 9:16 teaser is
not a different picture; it is *this* picture, cropped to the pan and
re-typeset. That is the product thesis rendered in pixels, and it costs one
`<use>` element per instance: zero duplicate ids however many frames are on
screen.

Ten set-ups make up the shoot — searing, the flip, live flame, a seasoning
macro, hands at work, the plated result, the editorial plate, plus the overhead,
the loaf and the knife. A deliverable that exists in several copies names a
**set** saying what each copy is: which set-up, which lockup, which line. Twelve
supporting posts are twelve different frames of one shoot, not one frame nudged
twelve times. See DD-16.

Three rules follow from that:

- **The campaign palette is literal, never a theme token.** A photograph does
  not change colour when the interface goes dark, and neither does this.
- **Written work is drawn on ivory; media is drawn on ink.** A script and a
  master cut must be distinguishable at 40px without reading a word.
- **Identity is the grade; variety is the subject.** One key light, one palette
  and one narrative are shared by every frame. Focal subject, composition,
  scale, typography and CTA placement are where the frames differ.

---

## Feature provenance

The customer-facing interface never says any of this. It lives here, and in the
optional annotation layer in the prototype chrome.

### Available now — shipped and verifiable in the repository

Projects and the nine-state lifecycle · project-scoped assets with upload and
signed download · the `project_planning` workflow (validate → plan → quality
check) with its approval gate, async execution and resume · AI chat · BYOK for
Anthropic and OpenAI with encrypted keys · budgets, spend records, the circuit
breaker and the retry ceiling · three roles with a fixed permission matrix ·
sign-in and sign-up · workspace rename · workspace export and erasure, and the
audit trail (both API-only today).

### On the plan — approved and scheduled, not built

| Surface in this prototype | Owned by |
|---|---|
| Notifications, and approvals actually reaching a person | STEP-34, STEP-35 |
| Thumbnails, durations and dimensions on media | STEP-32 |
| Storage usage and its ceiling | STEP-33 |
| Image generation (key art, title cards, thumbnails) | STEP-37 |
| Voice, audio and video assembly | STEP-38, STEP-58 to STEP-60 |
| Research and script agents | STEP-54, STEP-55 |
| Script review and per-segment editing | STEP-56 |
| Regeneration with cost shown first | STEP-62 |
| Subtitles and publishing metadata | STEP-63 |
| Export and delivery | STEP-64 |
| Memory, and the surface that lets you inspect and delete it | STEP-44 to STEP-47 |
| Chat tool actions, gated by approval | STEP-42 |
| Channels, connected accounts and publishing | STEP-65 to STEP-68 |
| Analytics and recommendations | STEP-69 to STEP-73 |
| Scheduling and notification preferences | STEP-74 to STEP-76 |
| People, roles, invitations and workspace switching | STEP-77 |
| Onboarding | STEP-86 |
| Plan, billing, invoices and usage limits | STEP-87 to STEP-89 |
| The screen blueprints and the product-wide UI rebuild | STEP-79, STEP-80 |

### Proposed here — no step owns it yet, and it needs owner approval

The creation cockpit and its six modes · **brief essentials** · the priced
creation plan · the workspace-level **Library** · **Recipes** · the **Studio** ·
deliverable **versions** · the **Review** surface with timecoded notes and
approval on a deliverable · the **Activity** history screen · the **run detail**
screen and a UI for starting, approving and resuming a run · the
export/erasure surface · the command palette · the **paid-media pack**.

Two of these are worth naming: **"recipe"** and **"deliverable"** do not exist
as product nouns anywhere in the repository today. They are introduced by this
design and are proposals, not descriptions.

**Brief essentials** — the four editable values inside the composer (audience,
tone, a length or scope, channels) are a product-design proposal. Nothing in
the repository extracts them from a brief today, and the interface never claims
it does: empty, the note above them reads *"Where Video starts"*; filled, it
reads *"Read from your brief"* — a statement about what a plan would be built
from, restated on the plan before anything runs, and changeable at both points.

**The paid-media pack** — every advertising format listed above is a *composed
product experience*, not a shipped capability. No step owns "advertising", and
the current backend generates **none** of these formats. The pack is assembled
from primitives that are themselves planned or proposed:

| The pack needs | Owned by |
|---|---|
| Image generation for the feed, story and banner creative | STEP-37 |
| Video assembly and cut-downs for pre-roll, Reels and TikTok | STEP-58 to STEP-60 |
| Copy generation for headline and CTA variants | STEP-54, STEP-55 |
| Per-placement crop and safe-area rules | Proposed here |
| Channel targeting | STEP-68 |

Nothing in this pack schedules, buys, bids on or delivers a placement, and the
prototype never suggests it might.

### Repurpose and Campaign

Both are presented as composed product experiences. Neither is a single
capability; each depends on primitives that are separately planned:

- **Repurpose** — transcription and highlight detection (proposed), video
  cutting (STEP-60), captions (STEP-63), image generation (STEP-37).
- **Campaign** — multi-agent orchestration (STEP-53), the research and script
  agents (STEP-54/55), media generation (STEP-57), channel targeting
  (STEP-68). The narrative, channel-plan and paid-media steps are proposed,
  and the paid pack's own dependencies are listed above.

---

## Honesty rules this prototype holds itself to

- **An approval covers exactly one step**, is spent when that step is admitted,
  and cannot be reused. The copy says so wherever an approval is offered.
- **Pre-run cost is an estimate and a range, never a quote.**
- **Resuming an interrupted step may call the provider a second time.**
  Provider work happens *at least once*, never exactly once. Nothing here
  implies otherwise, and that is exactly why resuming is a decision a person
  makes rather than something that happens on its own.
- **Starting a run hands it to production and returns.** Nothing executes
  inside the request that started it. The queue underneath is never shown: a
  job id in the interface would make the queue a public contract.
- **Failure explanations name the retry ceiling and state what was billed.**
- **Permissions and legal lifecycle transitions are read from the payload**,
  never derived in the client — the same rule the real application follows.
- **No visible control is dead.** Every button, link and control in this
  prototype does something observable. That includes the component sheet.
- **No customer-facing surface mentions a STEP number, an ADR, a build phase or
  this prototype's own mechanics.**

---

## Screens

Nine navigation destinations, thirty route patterns across eighteen view
modules, three page templates. The full inventory with its provenance is in
[ROUTES.md](ROUTES.md).

**Creative Cockpit** — full-width working surfaces: Home, Studio, Library, AI
spend.
**Workbench** — a split view with an inspector: projects, production, review,
activity, assistant.
**Focused Flow** — a centred column for consequential decisions: the creation
plan, settings, authentication, onboarding.

### Home — the Creative Cockpit

The only route that leaves the centred reading column. A workspace, not a
document.

**Top** — the thesis, then the question: *One idea. The whole production.* /
*What will we create today?*

**The primary workspace**, an asymmetric grid across the full width:

- **Left, ~62% — the composer.** Six creation modes, the writing well, the four
  **brief essentials**, a reference, a project as context, the destination, the
  ambient spend, and one primary action.

  The writing well holds the field and — while it is empty — one sentence on
  what a good brief for this mode contains, plus two that already have it.
  Keeping the guidance *inside* the well rather than under it is what stops the
  composer changing height the moment you start typing.

  Below it, **Brief essentials**: four values the mode chooses, each one press
  from being something else. Which four is mode-aware, because "length" means
  nothing to a key visual and "set size" means nothing to a trailer. Empty they
  read as where the mode starts; filled they read as what the brief was read
  as; neither is a commitment, and the plan restates all four before anything
  runs. In Campaign, **Channels** is the paid-media selector: ticking one adds
  its placements *and their cost* to the plan, and unticking it takes them off.

- **Right, ~38% — the live outcome.** *What this becomes*: the chain that leads
  to the master, the master, and a contact sheet of everything derived from it
  — one tile per piece rather than one tile per line, so twelve supporting
  posts look like twelve. Beyond ten cells the sheet says how many more rather
  than pretending the set is smaller. Selecting any of them replaces the chain
  in place with what it is, where it comes from, what stays editable, whether
  it needs approval and whether it is in the estimate. The outcome updates on
  every change of mode, essential, recipe, reference, project or destination,
  and **is shown once, never repeated further down the page.**

  The master is the panel's spring: it takes whatever height the panel has
  spare, up to a ceiling, and yields to a floor when a campaign brings
  thirty-four derivatives to the sheet below it. A fixed master would make the
  panel overflow instead — which is how a picture ends up deciding whether you
  can see the price.

**The lower row** — three zones and no operational dashboard: a recipe to start
from, the work to continue, and the single thing that most needs you.

#### Two compositions, and a floor

The height a real host gives a page is not the height of a design mock. The
published Artifact's content viewport is **1280 × 686**, so Home composes
itself two ways and knows when to stop:

- **Rich**, from 55rem of height upward: the full masthead at 52px, roomier
  rows, a taller writing well, a larger master.
- **Compact**, 40rem to 55rem: the masthead on one row, the composer's rows
  held to one line each and truncating rather than wrapping, the essentials
  tightened, the master springing between a floor and a ceiling rather than
  taking a fixed height, the zones as one-line summaries.
- **Below 40rem the lock lets go entirely** and Home becomes an ordinary
  scrolling column.

Both boundaries are measured, not chosen: the rich composition needs about
766px of content area and only clears that from roughly 880px of window height;
the compact one needs 631px at 1280 wide, and 40rem gives it 640.

The lock is measured in **every mode, empty and filled** — twelve states, not
one — because the campaign brief is a third longer than the video brief and
brings four times the deliverables.

**Nothing is hidden to reach the target.** The content area is an
`overflow: auto` region, so content that genuinely exceeds the window scrolls
rather than clipping. Exactly one label — the four-letter stage eyebrow above
each chain step — is suppressed at the compact height, and the step's name
stays. A governed notice always wins: when the budget or the breaker has
something to say, it takes the room it needs and the page scrolls.

---

## Prototype chrome

Always visible at the top of the window, deliberately styled unlike any product
surface so this can never be mistaken for the live app.

- **Scenario** — switches the *fake server payload* to reach every governed,
  empty, permission and failure state: Normal · First use · Loading · Budget
  exceeded · Breaker open · Signed in as Diego (Editor) · Rate limited ·
  Service unavailable. It changes data, never client logic.
- **Annotations** — off by default. When on, it marks each surface as
  *Available now* / *On the plan* / *Proposed* / *Simulated*, using `outline`
  and out-of-flow badges so **it moves zero pixels of layout** — verified
  across every screen.

## Keyboard

`⌘K` / `Ctrl-K` opens the command palette: every route, project, deliverable
and run, by name. `Escape` closes any overlay and returns focus to whatever
opened it. Every journey in the product is completable from the keyboard.
