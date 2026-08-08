---
title: Project Lifecycle
category: Architecture
status: stable
version: "1.0"
last_updated: 2026-08-08
tags: [architecture, projects, backend, standards]
aliases: ["Project State Machine", "Lifecycle Transitions"]
---

# Project Lifecycle

**Which lifecycle transitions a project may make, and why.** Implemented by `ProjectService` in `apps/api/app/services/project_service.py` ([[STEP-20 Projects Schema and Lifecycle]]).

[[Projects]] gives the sequence and stops there. Which transitions are *legal* was a genuine gap in the specification rather than something to infer, so it was decided by the project owner on 2026-08-08 and recorded here.

## The States

```
Idea → Planning → Generation → Review → Editing → Approval → Publishing → Analytics
                                  ↑         ↓
                                  └─────────┘

                        Archive  ← reachable from every state above
```

Nine states, stored in `projects.status` as `text` with a CHECK constraint ([[Table - projects]]).

## The Rules

Three, and each is a decision rather than a default.

### 1. Forward, one step at a time

A project moves to the next state in the sequence and never skips.

Skipping is what makes a state meaningless. If a project can jump from Idea to Publishing, *"in Approval"* stops guaranteeing that anything was approved, and every consumer of `status` has to re-derive what actually happened rather than trusting the column.

### 2. Review and Editing form a loop

`review → editing` is the one backward edge, and it is the edge content work actually needs: a reviewer sends a draft back for changes, and the revised draft continues forward.

Without it, a rejected review would have to be archived and the project recreated — losing its assets and its history over an ordinary editorial event.

> [!note] The loop is not symmetric
> `editing → approval` is rule 1's ordinary forward step, not a second backward edge. `editing → review` is **refused**: revised work is re-approved, not re-reviewed. "Review ↔ Editing loop" reads as if the edge went both ways, and it does not.

### 3. Archive is reachable from everywhere, and is terminal

A project can be abandoned at any point — an idea that goes nowhere is the common case, not an error — so archiving is always available.

**Un-archiving is refused.** A state machine that can leave its terminal state has no terminal state, and *"restore this project"* would have to answer *to which state* — which makes it a distinct feature rather than a transition.

### Everything else is refused

That refusal is the whole value of the machine. A status column accepting any assignment is a `text` field with extra steps.

**No state transitions to itself.** Not a special case — it falls out of the rules — but worth stating, because a self-transition is the shape a double-clicked button produces, and permitting it would inflate `version` and falsify `updated_at` on a no-op.

## Archive Is Not Deletion

The two are distinct, and the distinction matters:

| | Meaning |
|---|---|
| **Archive** | A lifecycle state. The work is finished or abandoned, and the project remains part of the workspace. |
| **Delete** | Soft deletion (`deleted_at`). The project is removed from the workspace. |

A user archives a campaign they want a record of, and deletes one created by mistake. Deletion is permitted from any state, archived included — requiring a project to be archived first would be ceremony rather than a safeguard, since the deletion is soft either way.

## Where the Rules Live

**In the service, not the database, and not a router.**

- **Not a router** — business logic in a router is logic a non-HTTP caller silently bypasses ([[CLAUDE|CLAUDE.md]] §12). Every caller of `projects` in later phases will be a non-HTTP one: [[Workflow Engine]] advances a project through Generation and Review without a request in sight.
- **Not the database** — a CHECK constraint sees one row at a time and cannot compare a new status against the old one. Expressing this in SQL would mean a trigger comparing `OLD` to `NEW`: a second copy of the rule, in a language where it is far harder to read and test.

The database still carries the **vocabulary** (`ck_projects_status_valid`), which is what guarantees the service can never be handed a value outside the nine states it reasons about. The split is the same one `workspace_members.role` uses with `apps/api/app/core/permissions.py`.

`ProjectRepository.update_status` writes whatever it is given, so `ProjectService.transition` is the only thing standing between a caller and an illegal state. Every path that changes a status goes through it.

## The Map Is Derived, Not Written Out

`_build_transitions()` derives the full nine-state map from the three rules above rather than listing it as a literal. A literal would be a fourth place the rules live, and the one most likely to drift from the prose — reordering the sequence would change the derivation correctly and silently disagree with a hand-written table.

The test suite inverts that: `test_project_lifecycle.py` writes the specification out **as data** and asserts it against the derivation across **all 81 ordered pairs**, in both directions. Asserting a handful of legal moves proves the map has entries; asserting every pair proves it has no *extra* ones, which is the property a state machine exists for. A bug making the machine permissive passes every "the legal move works" test ever written.

## For the UI

`legal_transitions_from(status)` returns exactly the states reachable in one step. [[STEP-21 Projects UI]] consumes it rather than reimplementing the rules in TypeScript — a screen offering a transition that will be refused wastes the user's time, and two copies of a state machine diverge.

An illegal transition raises `IllegalTransitionError`, whose message **names both states**. That is safe and useful: the caller already knows the current status, since they read the project to attempt the move, so telling them why is actionable rather than a disclosure ([[CLAUDE|CLAUDE.md]] §24). Contrast `ProjectNotFoundError`, which deliberately conflates "does not exist" with "RLS hid it".

---

## Navigation

- **Previous:** —
- **Next:** [[Table - projects]]
- **Parent:** [[Architecture MOC]]
- **Related Notes:** [[Projects]] · [[Table - projects]] · [[Table - assets]] · [[Backend Architecture]] · [[Workflow Engine]]
