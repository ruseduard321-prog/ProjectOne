---
title: Execution Protocol
category: Development
status: stable
version: "1.5"
last_updated: 2026-08-01
tags: [engineering, workflow, governance, ai]
aliases: ["Build Plan Protocol", "Step Execution Rules"]
---

# Execution Protocol

The rules Claude follows when the user says **"Implement the next step."** This note is binding: it governs how the [[Build Plan]] is executed, and no step may be run in a way that contradicts it.

## The Loop

1. **Locate** — open [[Build Plan]] (the index only).
2. **Select** — scan the step table top to bottom; take the **first step whose Status is not `Done`**. That is the step. There is no judgment call here.
3. **Verify the predecessor** — before any new work, confirm the previous step actually completed: its Status is `Done` in both places, and its Definition of Done genuinely holds against the current state of the project. A `Done` marking that no longer matches reality is a defect to surface, not a green light — stop and report it rather than building on top of it.
4. **Check the working tree** — run `git status`. It should be clean. Uncommitted changes mean a previous session ended `Blocked` and left its work in place ([[#Blocked Steps Are Never Committed]]) — **do not discard them and do not commit them**. Identify the blocked step, confirm with the user whether to resume it, discard it, or commit it, and act on that answer before starting anything new.
5. **Read** — open that one step note, then read only what [[#Context Discipline]] permits. The step's *Required Documentation* is a candidate list, not a reading list.
6. **Mark In Progress** — set the step's Status to `In Progress` in both the step note and the [[Build Plan]] index, before implementing.
7. **Implement** — perform the step's Tasks, and only those tasks.
8. **Validate** — run the step's Validation section. Every check must actually pass, observed, not assumed. On any failure, go to [[#Validation Failure and Rollback]] — do not continue down this list.
9. **Update documentation** — update the notes this step's work affected, per [[CLAUDE|CLAUDE.md]] §19. Keep indexes and Navigation blocks consistent.
10. **Synchronize future steps** — reconcile the remaining outline steps against what was actually built; see [[#Future Step Synchronization]].
11. **Expand the next step** — if the following step is marked `outline`, expand it to full detail now, while its context is loaded. Update its Detail column to `full`.
12. **Mark Done** — only if every condition in [[#Step Completion]] is met. Set Status to `Done` in both the step note and the index.
13. **Commit once** — stage everything the step produced and create **exactly one commit** containing implementation, documentation and [[Build Plan]] status updates together. See [[#One Step One Commit]]. Only a step that reached `Done` is committed: a `Blocked` step is left uncommitted ([[#Blocked Steps Are Never Committed]]).
14. **Verify the tree is clean** — run `git status` and confirm there is nothing uncommitted. A dirty tree at this point means the step is not finished.
15. **Report and stop** — emit the [[#Step Completion Report]] and stop. Do not begin the next step.

## Hard Rules

- **Never skip a step.** If STEP-07 is `Not Started` and STEP-08 looks more urgent, STEP-07 is still the step.
- **Never run two steps in one session.** Finishing early is not permission to continue.
- **Never mark `Done` on unvalidated work.** A step whose Validation did not pass is `In Progress` or `Blocked`, never `Done`. Partial completion is not completion ([[CLAUDE|CLAUDE.md]] §22).
- **Never widen scope.** Work not in the step's Tasks belongs to a later step or to no step. No opportunistic refactors ([[CLAUDE|CLAUDE.md]] §29/§35).
- **Never invent missing information.** If a step depends on a schema, contract or decision that is not documented, stop and say exactly what is missing ([[CLAUDE|CLAUDE.md]] §33–34). That is a `Blocked` step, not a guess.
- **Never read a document without a question it answers.** Reading is scoped by [[#Context Discipline]], not by a checklist. This never overrides the rule above it — when a fact is genuinely needed and only a document holds it, read the document.
- **Status lives in two places and must agree.** The step note and the index. Updating one without the other is a defect.
- **One step, one commit.** A completed step produces exactly one commit — never several, and never a commit that spans two steps. Splitting a step across commits is only permitted when the user explicitly asks for it ([[#One Step One Commit]]).
- **Never commit a partially implemented step.** A `Blocked` step produces **no commit** — not the partial work, not the `Blocked` status marking. Committing any of it requires explicit user approval, asked for and received ([[#Blocked Steps Are Never Committed]]).
- **Never leave the project in a partially completed or inconsistent state.** Every session ends at a coherent boundary: the step is finished and committed, or it is `Blocked` — rolled back where safe, reported where not — and left uncommitted for the user to decide on. Half-applied work with no marker is the one outcome this protocol exists to prevent.

## Context Discipline

Context is a finite budget spent against one step. Every token spent on a document that changes nothing is a token unavailable to the implementation, the validation, and the debugging that follows — and long steps end with debugging, which is where context runs short. These rules govern loop item 5 and every read after it.

**They reduce reading, never rigour.** Implementation quality, validation quality and safety are unchanged. A step still stops rather than guessing when something genuinely is not documented ([[CLAUDE|CLAUDE.md]] §33–34) — reading less is not the same as knowing less, and the moment those two conflict, read.

### The Rules

1. **Read only what the current step needs.** Necessity is judged against this step's Tasks and Validation, not against the subject area in general.
2. **A checklist is not a reason to read.** A document named in *Required Documentation* is a candidate. It earns a read when it answers a question this implementation actually has — otherwise it is skipped, and the step note's summary of it stands.
3. **Never reread [[CLAUDE|CLAUDE.md]] during implementation.** It is in context on every turn. Opening it duplicates what is already loaded.
4. **The Claude OS routing notes are read once per project, or when they change.** [[Start Here]], [[Documentation Discovery]], [[Reading Priority]] and [[Task Workflow]] describe how to find documentation. Their routing is known; re-deriving it each session buys nothing. They are **not part of this loop** — see [[#Relationship to CLAUDE.md §6 Step 0]].
5. **Never reread a file created or modified earlier in the same session** unless debugging requires that specific file. The edit tools fail loudly; a verification read confirms nothing that silence did not already confirm.
6. **Read before implementing only what influences implementation.** Documents that are *outputs* of the step — indexes, MOCs, [[Environment Setup]], [[Schema Overview]], Navigation blocks — are opened during loop item 9, not item 5. Reading them up front means reading them twice.
7. **One architecture document at a time.** When a step names several, read the single one that answers the current question. Read a second only when the first proves insufficient — which is a fact discovered, not assumed in advance.
8. **Name the unknown before opening a High-cost document.** State the specific question it resolves. If no concrete unknown exists, do not open it. This rule catches the most expensive habit: reading a large document to feel prepared rather than to learn something.
9. **Prefer established code over documentation.** Once the repository demonstrably implements a pattern — the router→service→repository layering, the migration shape, the test fixtures — the code is the more accurate and far cheaper specification. Read the handbook chapter when introducing a pattern, not when following one.
10. **Quality is held constant.** These rules exist to cut unnecessary loading only. Nothing here licenses skipping validation, skipping documentation updates, or implementing against an assumption instead of a source.

### Relationship to CLAUDE.md §6 Step 0

[[CLAUDE|CLAUDE.md]] §6 step 0 requires every ProjectOne task to begin at [[Start Here]]. **For build-plan execution, this protocol satisfies that requirement and replaces the reading.**

The intent of step 0 is that no task begins without the vault's operating procedure governing it — not that four routing notes are re-read to reach a conclusion already known. This protocol *is* that procedure in its stricter build-plan form, it is read every step (rule 4 does not apply to this note), and it is more specific than what the routing notes would have pointed to. Following it is compliance with step 0, not an exception to it.

This narrowing is scoped to build-plan steps. Any other ProjectOne task still enters through [[Start Here]] as §6 requires.

### What This Does Not Change

- **The step note is always read in full**, every step, without exception.
- **[[Build Plan]] is always read** — the index to select the step, plus the recent Current State entries.
- **Every code file being modified is read before editing it.**
- **Genuine unknowns are always resolved from a source.** Rule 2 permits skipping a document that answers nothing; it never permits guessing at what the document would have said. A step that needs an undocumented fact is `Blocked` ([[#Blocking]]), exactly as before.
- **Validation is untouched.** Observed, not assumed, every check, every step.

### Why

Audited after STEP-10: of roughly eighteen vault documents read, about six changed nothing about the outcome — two large security documents restating [[CLAUDE|CLAUDE.md]] §16, the four routing notes, and several read because a checklist named them. Both defects that step found — a pooled-connection claim leak and Supabase's default privileges re-granting DML on every future table — were found by testing against a live database, not by reading. The context those six documents consumed was most needed later, during exactly that debugging.

The governing habit is the one rule 8 encodes: **open a document to answer a question, not to satisfy a list.**

## One Step One Commit

Every Build Plan step produces **exactly one commit**. Not one for the code and another for the docs, not a cleanup commit afterwards — one.

The commit is created last, after the work is actually finished, in this order:

1. Implement the step's Tasks.
2. Run every check in the step's Validation section.
3. Update all affected documentation ([[CLAUDE|CLAUDE.md]] §19).
4. Update the [[Build Plan]] index row.
5. Mark the step `Done` in both places ([[#Step Completion]]).
6. Create one commit containing implementation, documentation and Build Plan updates together.
7. Verify `git status` reports a clean tree.
8. Report and stop.

Steps 1–5 come before the commit deliberately: committing first and updating documentation afterwards is what produces the second commit this rule exists to prevent.

### Why

A step is the unit of work in this plan, so it should be the unit of history. One commit per step means `git log` reads as the Build Plan itself, each step is revertable in one operation, and there is no window in which the code says one thing and the Build Plan says another. Multiple commits per step turn a clean sequence into an archaeology problem for whoever reads it later — and this repository will be read far more often than it is written ([[CLAUDE|CLAUDE.md]] §38).

### The Exception

The user may explicitly ask for a step to be split across several commits. That is the only exception, it is never assumed, and a step's size is not a reason to invoke it — a large step is still one commit.

### Commit Message

The message follows [[CLAUDE|CLAUDE.md]] §20: atomic, and explaining *why* rather than restating the diff. Name the step (`STEP-NN`) so history and plan stay traceable to each other.

### On Failure

**One commit per step means one commit per *completed* step. A step that fails produces no commit at all.**

A `Blocked` step is never committed without explicit user approval — not the partial implementation, and not the `Blocked` status update on its own. Follow [[#Validation Failure and Rollback]]: roll back if it is safe, mark the step `Blocked` in the working tree, report, and stop, leaving the changes uncommitted for the user to inspect.

This is the one case where the session deliberately ends on a **dirty tree**. The clean-tree check in [[#The Loop]] item 14 is a completion condition, not a failure condition — a blocked step has nothing to be clean about yet.

## Validation Failure and Rollback

When implementation or validation fails:

1. **Do not mark the step `Done`.** Not "done with a caveat," not "done pending a fix."
2. **Do not commit.** A failed step creates no commit — see [[#Blocked Steps Are Never Committed]] below. This governs everything that follows.
3. **Assess whether rollback is safe**, then take exactly one of these two paths:
   - **Rollback is safe** — restore the project to the last known good state (the previous step's verified state): revert the partial implementation, discard half-written config, undo the broken build. Then stop, **without committing**.
   - **Rollback is unsafe or impossible** — data loss, an already-applied destructive migration, an external side effect that cannot be undone. **Stop immediately without rolling back and without committing**, and report the situation. An unrecoverable rollback is worse than the failure it was meant to fix. If preserving the current state genuinely requires a commit, **ask for user approval first and wait** — never commit a partially implemented step on your own judgment.
4. **Mark the step `Blocked`** in both the step note and the index. These edits stay **uncommitted** along with everything else.
5. **Explain, in the step note and the report:** what failed, why it failed, and what is required to continue. Name the specific unblocker — a missing credential, an unaccepted ADR, a contradicting document, an owner decision. "Validation failed" is not an explanation. When rollback was unsafe, say exactly what was left in place and why it could not be undone.
6. **Stop immediately.** Do not attempt the next step, and do not attempt speculative fixes outside the step's scope.

A failed step holds the queue exactly like any other `Blocked` step. Progress resumes when the named unblocker is resolved, not by working around it.

### Blocked Steps Are Never Committed

**A `Blocked` step must not produce a commit.** This holds whether the step was rolled back or left in place, and it covers the partial implementation, the documentation updates, and the `Blocked` status marking alike — all of it stays in the working tree.

The only way a blocked step's work reaches a commit is **explicit user approval, asked for and received**. Silence is not approval, and neither is a rollback being unsafe — that is a reason to ask, not a reason to proceed.

**Why.** A commit is a claim that a coherent unit of work is finished. A partial step is not that, and recording one as history makes `git log` stop matching the Build Plan — the exact drift [[#One Step One Commit]] exists to prevent. Leaving the failure uncommitted in the working tree also keeps it visible and trivially discardable: the next session sees a dirty tree and a `Blocked` step and knows immediately that something needs a decision, rather than finding a tidy history that hides a half-built step.

**The tree stays dirty, and that is correct.** A blocked step is the one session outcome that does not end clean. It still ends *coherently* — rolled back or explicitly reported, with the step marked `Blocked` and the reason written down — which is what the Hard Rule against inconsistent state actually requires.

## Blocking

A step is `Blocked` when it cannot proceed without something Claude may not decide alone — an unaccepted ADR, a missing credential, an owner decision, an undocumented contract — or when it failed under [[#Validation Failure and Rollback]].

When blocking: set Status to `Blocked` in both places, add a **Blocked because:** line to the step note naming the specific unblocker, report it, and stop — leaving all of it **uncommitted** ([[#Blocked Steps Are Never Committed]]). **Do not skip ahead to the next step** — a blocked step still holds the queue. The user decides whether to unblock it or explicitly authorize a reorder.

This applies to every block, not only failures. A step blocked before any code was written (an unaccepted ADR, a missing credential) has nothing to commit anyway; a step blocked partway through has work that must stay in the working tree until the user says otherwise.

## Step Completion

A step may be marked `Done` only when **all** of the following hold:

- [ ] Every Definition of Done item is satisfied.
- [ ] All required validation has passed — observed, not assumed.
- [ ] All affected documentation has been updated ([[CLAUDE|CLAUDE.md]] §19).
- [ ] The step note status and the [[Build Plan]] index row are synchronized.
- [ ] No Critical issues remain unresolved ([[CLAUDE|CLAUDE.md]] §21).
- [ ] The step's work is captured in exactly one commit and `git status` reports a clean tree ([[#One Step One Commit]]).

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
Commit:        <short SHA and subject — exactly one>
Known issues:  <only if any exist; omit the line otherwise>
Next step:     STEP-NN <title>
```

A `Blocked` step reports under [[#Validation Failure and Rollback]] instead — what failed, why, and what unblocks it. Because a blocked step is never committed, its report must also state what is left in the working tree, so the user can act on it:

```
Step:          STEP-NN
Status:        Blocked
Failed at:     <which task or validation check>
Why:           <the actual cause, not "validation failed">
Rollback:      <rolled back to last known good state / NOT rolled back — why it was unsafe>
Uncommitted:   <what is sitting in the working tree right now>
Commit:        none — blocked steps are not committed
Unblocked by:  <the specific thing needed: a credential, an ADR acceptance, an owner decision>
Approval needed: <only if a commit is being requested; state exactly what would be committed>
```

## Future Step Synchronization

After completing a step, check the remaining outline steps against what was actually built.

If the implementation changed any assumption, dependency, architectural choice, or execution detail that a later outline step relies on, **update those outline steps now** — while the context is loaded and the divergence is obvious. A plan that describes a system that no longer exists misleads the next session more effectively than a gap would ([[CLAUDE|CLAUDE.md]] §19: documentation drift is a bug).

Bounded deliberately:

- **Update only the outline steps the change actually affects.** Not a sweep of all remaining steps.
- **Do not expand an outline step into full detail** unless it is the immediate next step (loop item 11). Correcting an outline's stated assumption is synchronization; writing its task list early is the speculative over-design [[CLAUDE|CLAUDE.md]] §29/§35 forbids.
- **If the change invalidates a step entirely** — the step is now unnecessary, or a new step is needed between two existing ones — surface that to the user rather than silently restructuring the plan. Adding or removing steps is a plan change, not an execution detail.

## Owner Approval Gates

Some steps require the project owner's decision before the *next* step may start — architecture decisions ([[CLAUDE|CLAUDE.md]] §7: implementation waits for an `Accepted` ADR) and Critical changes ([[CLAUDE|CLAUDE.md]] §21: schema, auth, security, billing, public API, infrastructure, AI/agent architecture, memory, multi-tenancy).

A step carrying a gate says so in its Definition of Done. Claude completes the step, marks it `Done`, and stops — the following step does not begin until the owner confirms. Silence is never approval.

## Progressive Detail

Steps far from execution stay at outline level: goal and scope, no task breakdown. They are expanded by the step before them (loop item 11), when the surrounding code actually exists and the detail can be accurate rather than imagined.

This is not laziness — a task list written against a codebase that does not exist yet is a guess, and guesses in a plan are worse than gaps because they read as decisions.

## Amending This Protocol

This note is **operational policy, not architecture** — it governs how Claude executes work, not how the system is built. Under [[CLAUDE|CLAUDE.md]] §39, changing it does **not** require an ADR. That includes the loop, reading scope ([[#Context Discipline]]), commit mechanics, reporting format, synchronization rules, and the ordering of validation and documentation work.

What an amendment does require: the project owner's approval, the change written into this note rather than carried as a session habit, every document it contradicts updated in the same change ([[CLAUDE|CLAUDE.md]] §19), and the reasoning recorded so a later session sees why the rule exists rather than only that it does.

Two changes fall outside that latitude and need the fuller scrutiny:

- **Lowering a quality, validation or safety bar.** Reordering when checks run is operational. Removing a check, weakening [[#Step Completion]], or relaxing [[#Owner Approval Gates]] changes the standard itself.
- **An execution rule that encodes an architectural constraint.** Where a rule is genuinely both, the architectural half governs and an ADR is required.

## Why This Exists

[[Task Workflow]] describes the lifecycle of *any* ProjectOne task. This protocol is the narrower contract for *build-plan execution specifically*, closing the failure modes that break long multi-session builds:

- **Ambiguity about what to do next** — answered by one deterministic question: what is the first step that is not `Done`?
- **Silent scope creep across sessions** — bounded by the step's Tasks and nothing else.
- **Inconsistent state left behind on failure** — closed by [[#Validation Failure and Rollback]]: every session ends finished and committed, or `Blocked` and uncommitted, never half-applied and never committed halfway.
- **A plan drifting from the code it describes** — closed by [[#Future Step Synchronization]], which reconciles the remaining outline against what was actually built.
- **History that no longer matches the plan** — closed by [[#One Step One Commit]]: one step is one commit, so the log and the Build Plan stay readable as the same sequence.
- **Context exhausted before the work is finished** — closed by [[#Context Discipline]]: reading is scoped to questions the step actually has, so the budget survives to the debugging that ends most steps.

Every session starts from the same question and ends at a verifiable boundary with a report of what changed.

---

## Navigation

- **Previous:** [[Build Plan]]
- **Next:** [[STEP-01 Repository Bootstrap]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Build Plan]] · [[Task Workflow]] · [[Documentation Discovery]] · [[CLAUDE|CLAUDE.md]]
