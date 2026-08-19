---
title: Task Workflow
category: Claude OS
status: stable
version: "1.3"
last_updated: 2026-08-18
tags: [governance, workflow, ai]
aliases: ["Development Workflow (Claude OS)"]
---

# Task Workflow

The end-to-end process for every ProjectOne task, from receipt to completion. This is the task **lifecycle** — for which tool/MCP to use once implementation starts, see [[Workflows/Development Workflow|Development Workflow]] in `06 AI`.

> [!important] Build-plan work follows a stricter contract
> When the task is *"Implement the next step"* — executing the [[Build Plan]] — [[Execution Protocol]] governs and adds binding rules this general lifecycle does not state: verify the predecessor before starting, roll back and mark `Blocked` on validation failure, satisfy every completion condition before marking `Done` — including green required CI and resolved review, so a step stays `In Progress` until the checks that could reject it have run — deliver the whole step as exactly one squashed commit on `main` ([[Execution Protocol#One Step One Commit On Main]]) while its branch may carry several, commit nothing at all if the step ends `Blocked` before anything was pushed ([[Execution Protocol#Blocked Steps Are Never Committed]]), emit a completion report, and re-sync affected future steps. Follow it in full; this note remains the lifecycle it sits inside.
>
> It also **narrows step 3 below**: build-plan reading is scoped by [[Execution Protocol#Context Discipline]], which reads a document only when it answers a question the step actually has, keeps this note and the other Claude OS routing notes out of the per-step loop, and defers output-only documentation to step 7. The discovery principles are unchanged — that section is [[Documentation Discovery]] applied strictly.

## The Workflow

```
Receive task
     ↓
Identify domain
     ↓
Read relevant documentation
     ↓
Plan
     ↓
Implement
     ↓
Test
     ↓
Update documentation
     ↓
Branch → PR → CI → review → merge
     ↓
Report completion
```

## Step by Step

1. **Receive task.** Understand what's actually being asked before doing anything else.
2. **Identify domain.** Frontend, backend, database, AI/agents, security, design, process — name it; this drives everything that follows.
3. **Read relevant documentation.** Follow [[Documentation Discovery]] and [[Reading Priority]] — never the whole vault, only what the domain requires. If something the task depends on isn't documented anywhere findable, **stop here and tell the user exactly what's missing** before planning or implementing anything (per [[CLAUDE|CLAUDE.md]] §6 step 0, §33–34).
4. **Plan.** Apply the Decision Framework ([[CLAUDE|CLAUDE.md]] §6): understand the objective, understand existing architecture, identify risks, evaluate alternatives, recommend a solution — before writing anything.
5. **Implement.** Follow the relevant layer standards ([[Engineering Handbook MOC]]) and use [[Workflows/Development Workflow|Development Workflow]] to select the right tool for each step.
6. **Test.** Per [[CLAUDE|CLAUDE.md]] §18 — business logic gets unit tests, UI changes get real browser validation, nothing is called done on the strength of a type-check alone.
7. **Update documentation.** Per §19 — update only the notes the change actually affects, in the same change, not as a follow-up. Prefer updating an existing note over creating a new one; never duplicate content — link to it instead. Keep indexes and Navigation blocks consistent. This is [[Skills/Documentation Keeper|Documentation Keeper]]'s domain.
8. **Deliver through a branch and Pull Request.** Every change reaches `main` this way — [[Branch and Pull Request Workflow]] is binding, and `main` is never modified directly. One task per branch, CI green, review conversations resolved, owner approval where the change is consequential, squash merge, branch deleted.
9. **Report completion.** State what changed and what's next — concise, per the Definition of Done (§22). Partial completion is not completion.

## Project Commands

ProjectOne defines project commands in `.claude/commands/`. A project command is an
**explicitly user-invoked orchestrator**: the owner types it, and it sequences work that this
note and the governing documents already define. Nothing invokes one automatically.

- **A command owns no governance rule and no specialist decision.** Every rule in
  [[CLAUDE|CLAUDE.md]] binds whether or not a command runs, and every specialist judgement stays
  with the skill that owns it under [[Skill Contract]]. A command routes and reports; it does not
  decide.
- **Each command declares its own mutation boundary**, in its own file, in concrete terms. That
  declaration is the command's contract and is reviewed like any other standard.
- **An inspection-only command changes no project or hosted state.** `/po-review` reviews a
  selected change and modifies no file, local branch, commit, Pull Request, review conversation,
  or Build Plan status. Its only operational side effect is refreshing and pruning local
  remote-tracking refs — repository metadata, declared in the command's own mutation boundary,
  and not a change to anything the project keeps.
- **An implementation command may perform only the mutations its declared scope explicitly
  authorizes**, and nothing beyond them. A mutation a command's scope does not name is out of
  bounds even when it would be convenient. `/po-build` executes exactly one [[Build Plan]] step
  under [[Execution Protocol]], which it sequences without altering, in three owner-invoked
  phases — `audit` (read-only), `implement`, `deliver`. It never merges, never approves, never
  resolves a review conversation, never changes the `Protect main` ruleset, and never begins the
  following step.
- **`allowed-tools` preauthorizes; `disallowed-tools` denies.** A command's tool frontmatter is
  not its boundary. Absence from `allowed-tools` removes that command's explicit preauthorization
  and nothing more; **what happens next is decided by the active Claude Code permission mode, so
  absence does not guarantee a prompt and does not guarantee the owner sees the operation at all.**
  Default mode may prompt; Auto mode runs without permission
  prompts, auto-approves local file operations, and routes other actions through its own background
  safety checks. A command therefore preauthorizes only read operations and explicitly fixed
  validation or regeneration commands, leaves generic file edits and every Git/GitHub write out of
  that list, carries explicit deny rules as defense in depth, and states its real boundary in prose
  — which governs whenever the two appear to disagree.
- **A command is permission-mode-neutral, and never relies on a control that exists in only one
  mode.** It does not detect the mode and does not stop because Auto is active. Owner authorization
  is the command's own explicit phase boundary — for `/po-build`, `audit` → `implement` →
  `deliver`, each typed by the owner — together with the approved scope, the pre-commit
  reconciliation, the deny rules, and the owner's exclusive authority over merging and every
  Critical decision. A tool prompt is never one of those controls.
- **A command re-derives repository state; approval is the exception.** Exactly two artifacts are
  conversation-derived, each required verbatim and scope-bound: `/po-build implement` requires the
  latest complete `/po-build audit` report for the same step and the same repository state, and
  `/po-build deliver` requires the latest complete `/po-review` report for the exact current head.
  A command cannot invoke another command, neither artifact is ever reconstructed from a summary,
  and an attested account is never accepted in place of a report.
- **Marking a step complete moves the head, so verification takes two passes.** `/po-build
  deliver` first verifies every gate and marks the step `Done` in a status-only commit; that push
  creates a new head, which is re-reviewed and re-tested before a second `deliver` invocation
  verifies the final head and reports `DELIVERED` — still unmerged, awaiting the owner.
- **A command states what it will not do.** `/po-build` v1 does not adopt, resume, stash or
  discard a dirty working tree, does not resume an `In Progress` step, and never repairs
  implementation code during `deliver`: review findings go to `/po-fix review`, and CI failures are
  reported rather than fixed in place.
- **No command may bypass a gate, satisfy one by assertion, or automate one away** — CI, owner
  approval, branch protection, the ADR lifecycle, and Definition of Done are untouched by the
  existence of any command. Automating *how* a check runs is operational policy; automating a
  gate *away* is forbidden (§30b, §39).

Adding or changing a project command is operational policy under §39 and needs no ADR, provided
it lowers no quality, validation, or safety bar. A command that would lower one is a change to
the standard itself and is governed accordingly.

---

## Navigation

- **Previous:** [[Reading Priority]]
- **Next:** —
- **Parent:** [[Home]]
- **Related Notes:** [[Documentation Discovery]] · [[Reading Priority]] · [[Workflows/Development Workflow|Development Workflow]] · [[CLAUDE|CLAUDE.md]] · [[Skill Contract]]
