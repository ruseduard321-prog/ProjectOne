---
title: Task Workflow
category: Claude OS
status: stable
version: "1.1"
last_updated: 2026-07-31
tags: [governance, workflow, ai]
aliases: ["Development Workflow (Claude OS)"]
---

# Task Workflow

The end-to-end process for every ProjectOne task, from receipt to completion. This is the task **lifecycle** — for which tool/MCP to use once implementation starts, see [[Workflows/Development Workflow|Development Workflow]] in `06 AI`.

> [!important] Build-plan work follows a stricter contract
> When the task is *"Implement the next step"* — executing the [[Build Plan]] — [[Execution Protocol]] governs and adds binding rules this general lifecycle does not state: verify the predecessor before starting, roll back and mark `Blocked` on validation failure, satisfy every completion condition before marking `Done`, capture the whole step in exactly one commit ([[Execution Protocol#One Step One Commit]]) — and commit nothing at all if the step ends `Blocked` ([[Execution Protocol#Blocked Steps Are Never Committed]]) — emit a completion report, and re-sync affected future steps. Follow it in full; this note remains the lifecycle it sits inside.

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
8. **Report completion.** State what changed and what's next — concise, per the Definition of Done (§22). Partial completion is not completion.

---

## Navigation

- **Previous:** [[Reading Priority]]
- **Next:** —
- **Parent:** [[Home]]
- **Related Notes:** [[Documentation Discovery]] · [[Reading Priority]] · [[Workflows/Development Workflow|Development Workflow]] · [[CLAUDE|CLAUDE.md]]
