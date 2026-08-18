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
- **A read-only command changes nothing.** `/po-review` reviews a selected change and modifies no
  file, branch, commit, Pull Request, review conversation, or Build Plan status.
- **An implementation command may perform only the mutations its declared scope explicitly
  authorizes**, and nothing beyond them. A mutation a command's scope does not name is out of
  bounds even when it would be convenient.
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
