# Route and capability inventory

Every addressable surface in the prototype, the page template it uses, and
whether the capability behind it exists today, is on the plan, or is proposed
by this design.

**Provenance** is one of:

- **Now** — shipped and verifiable in the repository.
- **Planned** — approved and scheduled; the owning step is named.
- **Proposed** — this design proposes it; no step owns it yet.

---

## Navigation

Nine destinations in the rail, in two groups.

| Group | Item | Route |
|---|---|---|
| Make | Home | `#/dashboard` |
| Make | Projects | `#/projects` |
| Make | Studio | `#/studio` |
| Make | Library | `#/library` |
| Make | Production | `#/runs` |
| Workspace | Assistant | `#/assistant` |
| Workspace | Activity | `#/activity` |
| Workspace | AI spend | `#/spend` |
| Workspace | Settings | `#/settings/profile` |

Everything else is reached from a surface that owns it, or from the command
palette (`⌘K`), which indexes every route, project, deliverable and run by
name.

---

## Routes

| Route | Template | Surface | Provenance |
|---|---|---|---|
| `#/dashboard` | Cockpit | Home — the creation cockpit | Proposed |
| `#/plan` | Focus | Creation plan: every deliverable, its cost, its gates | Proposed |
| `#/projects` | Workbench | Projects | **Now** |
| `#/projects/:id` | Workbench | Project overview, the master, the brief, the lifecycle | **Now** |
| `#/projects/:id/work` | Workbench | Deliverables by stage | Proposed |
| `#/projects/:id/runs` | Workbench | Production for this project | **Now** (API) |
| `#/projects/:id/activity` | Workbench | Project activity | Planned · STEP-77 audit surfacing |
| `#/studio` · `#/studio/:id` | Cockpit | The editor: rail, canvas, timeline, inspector | Proposed |
| `#/library` | Cockpit | Everything the workspace has made | Proposed |
| `#/library/assets` | Cockpit | The work, filtered by medium, purpose or what needs you | Proposed |
| `#/library/recipes` | Cockpit | Recipes | Proposed |
| `#/runs` | Workbench | Production, grouped by what needs you | **Now** (API) |
| `#/runs/:id` | Workbench | One run: banner, output, every step | Proposed screen over **Now** data |
| `#/review/:id` | Workbench | Review: the work, its versions, its notes, one decision | Proposed |
| `#/activity` | Workbench | Workspace activity | Planned · STEP-34/35, STEP-77 |
| `#/assistant` | Workbench | AI chat | **Now** |
| `#/spend` | Cockpit | AI spend, its ceilings, and the stop control | **Now** |
| `#/settings/profile` | Focus | Name, email, appearance | **Now** |
| `#/settings/workspace` | Focus | Workspace name and what isolation guarantees | **Now** |
| `#/settings/members` | Focus | People and roles | Planned · STEP-77 |
| `#/settings/providers` | Focus | BYOK keys and fallback order | **Now** |
| `#/settings/notifications` | Focus | Per-event delivery | Planned · STEP-76 |
| `#/settings/billing` | Focus | Plan, AI ceiling, invoices | Planned · STEP-87 to STEP-89 |
| `#/settings/security` | Focus | Sign-in, export, erasure, deletion | **Now** (API) / Proposed (surface) |
| `#/signin` | Focus, chromeless | Sign in | **Now** |
| `#/join` | Focus, chromeless | Accept an invitation | Planned · STEP-77 |
| `#/welcome` | Focus, chromeless | First use: workspace, provider, ceiling | Planned · STEP-86 |
| `#/spec` | Cockpit | Component specimens — prototype only | n/a |
| not found | Focus | Anything else | **Now** |

**Thirty route patterns**, rendered by **eighteen view modules**, resolving to
fifty-eight distinct addresses that the interface itself links to — every
project, every run, every deliverable, by name.

**No route was added for advertising.** The paid-media pack is a set of
campaign deliverables, so it appears on Home's preview, on the creation plan,
in the project's deliverables, under the library's *Paid media* filter and in
review — and nowhere as a destination of its own. See DD-15.

---

## Overlays

Not routes, because a drawer, a modal or an inspector is the better product
pattern for each of them.

| Overlay | Opened from | Kind |
|---|---|---|
| Command palette | `⌘K`, the rail, the topbar | Modal |
| Reference picker | Composer | Modal |
| Project context picker | Composer | Modal |
| Destination | Composer | Popover |
| Brief essential — audience, tone, length or scope | Composer | Popover, single choice |
| Brief essential — channels | Composer | Popover, multi-select; stays open while ticking |
| Add a deliverable back | Creation plan | Modal |
| Start production | Creation plan | Spending confirmation |
| Approve one step | Run detail, notifications | Drawer |
| What happened | Run detail | Drawer |
| Resume production | Failure drawer, run detail | Spending confirmation |
| Regenerate | Studio, review | Spending confirmation |
| Asset inspector | Library | Drawer |
| Archive project | Project | Destructive confirmation |
| Invite someone | Settings → People | Modal |
| Provider key | Settings → AI providers, onboarding | Modal |
| AI ceiling | Settings → Billing | Modal |
| Export everything | Settings → Security | Modal |
| Delete workspace | Settings → Security | Destructive, type-to-confirm |
| Pause all AI spend | AI spend | Destructive confirmation |
| Workspace / account / appearance / notifications | Rail, topbar | Popovers |
| Navigation | Topbar, below 48rem | Drawer |

**Spending and destructive confirmations focus the safe choice first**, and the
two that delete or pause ignore a backdrop click, because a mis-click should
never spend money or stop production.

---

## States

Reached through the Scenario control in the prototype chrome, which changes the
fake server payload and never the client logic.

| Scenario | What it demonstrates |
|---|---|
| Normal | The workspace mid-production |
| First use | Every empty state, on every screen |
| Loading | Skeletons that match the shape of what is coming |
| Budget exceeded | The ceiling reached; a run in flight allowed to finish |
| Breaker open | AI paused; nothing new starts; saved work untouched |
| Signed in as Diego (Editor) | The permission boundary, as a person rather than a toggle |
| Rate limited | A transient limit that clears on its own |
| Service unavailable | The connection gone, and what is still usable |
