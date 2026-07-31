---
title: Execution Protocol
category: Development
status: stable
version: "1.1"
last_updated: 2026-07-31
tags: [engineering, workflow, governance, ai]
aliases: ["Build Plan Protocol", "Step Execution Rules"]
---

# Execution Protocol

The rules Claude follows when the user says **"Implement the next step."** This note is binding: it governs how the [[Build Plan]] is executed, and no step may be run in a way that contradicts it.

## The Loop

1. **Locate** — open [[Build Plan]] (the index only).
2. **Select** — scan the step table top to bottom; take the **first step whose Status is not `Done`**. That is the step. There is no judgment call here.
3. **Verify the predecessor** — before any new work, confirm the previous step actually completed: its Status is `Done` in both places, and its Definition of Done genuinely holds against the current state of the project. A `Done` marking that no longer matches reality is a defect to surface, not a green light — stop and report it rather than building on top of it.
4. **Read** — open that one step note. Read only the documents its *Required Documentation* section names, plus [[Start Here]] per [[CLAUDE|CLAUDE.md]] §6 step 0. Nothing else.
5. **Mark In Progress** — set the step's Status to `In Progress` in both the step note and the [[Build Plan]] index, before implementing.
6. **Implement** — perform the step's Tasks, and only those tasks.
7. **Validate** — run the step's Validation section. Every check must actually pass, observed, not assumed. On any failure, go to [[#Validation Failure and Rollback]] — do not continue down this list.
8. **Update documentation** — update the notes this step's work affected, per [[CLAUDE|CLAUDE.md]] §19. Keep indexes and Navigation blocks consistent.
9. **Synchronize future steps** — reconcile the remaining outline steps against what was actually built; see [[#Future Step Synchronization]].
10. **Expand the next step** — if the following step is marked `outline`, expand it to full detail now, while its context is loaded. Update its Detail column to `full`.
11. **Mark Done** — only if every condition in [[#Step Completion]] is met. Set Status to `Done` in both the step note and the index.
12. **Report and stop** — emit the [[#Step Completion Report]] and stop. Do not begin the next step.

## Hard Rules

- **Never skip a step.** If STEP-07 is `Not Started` and STEP-08 looks more urgent, STEP-07 is still the step.
- **Never run two steps in one session.** Finishing early is not permission to continue.
- **Never mark `Done` on unvalidated work.** A step whose Validation did not pass is `In Progress` or `Blocked`, never `Done`. Partial completion is not completion ([[CLAUDE|CLAUDE.md]] §22).
- **Never widen scope.** Work not in the step's Tasks belongs to a later step or to no step. No opportunistic refactors ([[CLAUDE|CLAUDE.md]] §29/§35).
- **Never invent missing information.** If a step depends on a schema, contract or decision that is not documented, stop and say exactly what is missing ([[CLAUDE|CLAUDE.md]] §33–34). That is a `Blocked` step, not a guess.
- **Status lives in two places and must agree.** The step note and the index. Updating one without the other is a defect.
- **Never leave the project in a partially completed or inconsistent state.** Every session ends at a coherent boundary: the step is finished, or it is rolled back and `Blocked`. Half-applied work with no marker is the one outcome this protocol exists to prevent.

## Validation Failure and Rollback

When implementation or validation fails:

1. **Do not mark the step `Done`.** Not "done with a caveat," not "done pending a fix."
2. **Restore the last known good state** if the project was left inconsistent — partially applied migrations, half-written config, a broken build. A clean revert to the previous step's verified state beats a broken forward state. If a rollback is itself risky (data loss, an already-applied destructive migration), stop before rolling back and report the situation instead — an unrecoverable rollback is worse than the failure it was meant to fix.
3. **Mark the step `Blocked`** in both the step note and the index.
4. **Explain, in the step note and the report:** what failed, why it failed, and what is required to continue. Name the specific unblocker — a missing credential, an unaccepted ADR, a contradicting document, an owner decision. "Validation failed" is not an explanation.
5. **Stop immediately.** Do not attempt the next step, and do not attempt speculative fixes outside the step's scope.

A failed step holds the queue exactly like any other `Blocked` step. Progress resumes when the named unblocker is resolved, not by working around it.

## Blocking

A step is `Blocked` when it cannot proceed without something Claude may not decide alone — an unaccepted ADR, a missing credential, an owner decision, an undocumented contract — or when it failed under [[#Validation Failure and Rollback]].

When blocking: set Status to `Blocked` in both places, add a **Blocked because:** line to the step note naming the specific unblocker, report it, and stop. **Do not skip ahead to the next step** — a blocked step still holds the queue. The user decides whether to unblock it or explicitly authorize a reorder.

## Step Completion

A step may be marked `Done` only when **all** of the following hold:

- [ ] Every Definition of Done item is satisfied.
- [ ] All required validation has passed — observed, not assumed.
- [ ] All affected documentation has been updated ([[CLAUDE|CLAUDE.md]] §19).
- [ ] The step note status and the [[Build Plan]] index row are synchronized.
- [ ] No Critical issues remain unresolved ([[CLAUDE|CLAUDE.md]] §21).

If any condition fails, the step is **not** `Done`. Mark it `Blocked` when user intervention is required, `In Progress` when the remaining work is Claude's to finish in this session. There is no third option and no partial credit — partial completion is not completion ([[CLAUDE|CLAUDE.md]] §22).

## Step Completion Report

Every successfully completed step ends with this report. **10–15 lines, no preamble, no narration of the work** — the transcript already shows what happened.

```
Step:          STEP-NN
Goal:          <what was completed, one line>
Created:       <files created, or "none">
Modified:      <files modified, or "none">
Docs updated:  <vault notes updated, or "none">
Tests run:     <what was executed>
Validation:    <passed / failed — with the specific result>
Known issues:  <only if any exist; omit the line otherwise>
Next step:     STEP-NN <title>
```

A `Blocked` step reports under [[#Validation Failure and Rollback]] instead — what failed, why, and what unblocks it.

## Future Step Synchronization

After completing a step, check the remaining outline steps against what was actually built.

If the implementation changed any assumption, dependency, architectural choice, or execution detail that a later outline step relies on, **update those outline steps now** — while the context is loaded and the divergence is obvious. A plan that describes a system that no longer exists misleads the next session more effectively than a gap would ([[CLAUDE|CLAUDE.md]] §19: documentation drift is a bug).

Bounded deliberately:

- **Update only the outline steps the change actually affects.** Not a sweep of all remaining steps.
- **Do not expand an outline step into full detail** unless it is the immediate next step (loop item 10). Correcting an outline's stated assumption is synchronization; writing its task list early is the speculative over-design [[CLAUDE|CLAUDE.md]] §29/§35 forbids.
- **If the change invalidates a step entirely** — the step is now unnecessary, or a new step is needed between two existing ones — surface that to the user rather than silently restructuring the plan. Adding or removing steps is a plan change, not an execution detail.

## Owner Approval Gates

Some steps require the project owner's decision before the *next* step may start — architecture decisions ([[CLAUDE|CLAUDE.md]] §7: implementation waits for an `Accepted` ADR) and Critical changes ([[CLAUDE|CLAUDE.md]] §21: schema, auth, security, billing, public API, infrastructure, AI/agent architecture, memory, multi-tenancy).

A step carrying a gate says so in its Definition of Done. Claude completes the step, marks it `Done`, and stops — the following step does not begin until the owner confirms. Silence is never approval.

## Progressive Detail

Steps far from execution stay at outline level: goal and scope, no task breakdown. They are expanded by the step before them (loop item 8), when the surrounding code actually exists and the detail can be accurate rather than imagined.

This is not laziness — a task list written against a codebase that does not exist yet is a guess, and guesses in a plan are worse than gaps because they read as decisions.

## Why This Exists

[[Task Workflow]] describes the lifecycle of *any* ProjectOne task. This protocol is the narrower contract for *build-plan execution specifically*, closing the four failure modes that break long multi-session builds:

- **Ambiguity about what to do next** — answered by one deterministic question: what is the first step that is not `Done`?
- **Silent scope creep across sessions** — bounded by the step's Tasks and nothing else.
- **Inconsistent state left behind on failure** — closed by [[#Validation Failure and Rollback]]: every session ends finished or rolled back and `Blocked`, never half-applied.
- **A plan drifting from the code it describes** — closed by [[#Future Step Synchronization]], which reconciles the remaining outline against what was actually built.

Every session starts from the same question and ends at a verifiable boundary with a report of what changed.

---

## Navigation

- **Previous:** [[Build Plan]]
- **Next:** [[STEP-01 Repository Bootstrap]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Build Plan]] · [[Task Workflow]] · [[Documentation Discovery]] · [[CLAUDE|CLAUDE.md]]
