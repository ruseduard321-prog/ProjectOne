---
title: Architecture Reviewer
category: AI/Skills
status: stable
version: "1.1"
last_updated: 2026-08-18
tags: [ai, engineering, architecture]
aliases: []
---

# Architecture Reviewer

## Purpose

Reviews any change that introduces, alters, or bypasses architectural structure — new modules, new dependencies between apps/packages, new ADRs, or anything that shapes how ProjectOne's systems fit together — and confirms it holds to the Architecture Principles and Repository Rules before it's treated as settled. Produces a clear verdict on whether an architectural decision is proposed correctly (as an ADR, at the right lifecycle stage) or is drifting in silently.

## Classification

**Critical — may block.** Silent architectural drift is a named Forbidden Practice ([[CLAUDE|CLAUDE.md]] §35), and undoing an architecture decision after code has been built against it (a wrong module boundary, an accidental circular dependency, a framework introduced outside the stack table) is exactly the kind of expensive-to-reverse mistake this contract's Critical bar is meant for (see [[Skill Contract]]).

## Scope

**In scope:** ADR lifecycle compliance (Draft → Review → Accepted before implementation begins), and whether a change to an Accepted ADR's content is a clarification or a change to the decision itself, Repository Rules (§8–9: folder ownership, dependency direction, no circular imports), Technology Stack boundary (§10/§28 — the established stack and the ADR-governed dependency set, whether a member is added, removed or substituted), Architecture Principles (§7: modular services, provider independence, stateless APIs, deterministic/observable workflows), and the process and deployment shape of the system: what runs as an independently launched process, what deploys together, and where that is recorded.

**Out of scope:** database schema shape and migration mechanics (owned by [[Database Engineer]]), security architecture specifics like RLS/auth (owned by [[Security Reviewer]]), the safety, version and supply-chain dimension of any dependency change — package safety, version upgrades, lockfile diffs (owned by [[Security Reviewer]]; this skill asks only whether the established stack and the ADR-governed dependency set still hold), secrets, credentials and environment values under `infrastructure/` (owned by [[Security Reviewer]]), AI/agent-specific architecture like cost governance (owned by [[AI Systems Engineer]]), day-to-day code quality within an already-settled architecture, and the routing of infrastructure configuration to owner review (owned by [[Code Reviewer]]), implementation inside a boundary this skill has already approved (owned by [[Full Stack Engineer]]), performance characteristics of an architecture (owned by [[Performance Reviewer]] — Architecture Reviewer checks *shape*, Performance Reviewer checks *measured behavior*), and the mechanical correctness of a vault note — frontmatter, links, Navigation blocks, index membership (owned by [[Documentation Keeper]]), including a clarifying ADR edit once this skill has established that the decision itself did not change.

## Governing Standards

- §7 Architecture Principles (modular services, provider independence, stateless APIs, deterministic/observable/resumable workflows) and the ADR lifecycle (Draft/Review/Accepted/Deprecated/Superseded/Rejected)
- §8 Repository Rules (dependency direction, no circular imports, folder ownership)
- §9 Folder Structure
- §10 Technology Stack (no new framework/database/major dependency without an ADR)
- §28 Dependency Rules
- §28a Environment Management (configuration owned by infrastructure-as-code, environment parity — the standard behind this skill's deployment-topology trigger)
- §35 Forbidden Practices (no silent architecture change, no rewriting unrelated code)

## Trigger Conditions

Activates on changes that **introduce, alter, or reverse architectural structure** — the shape of the system, or the record that settles it. A path being touched is never the trigger on its own; where a path is named below, a stated semantic condition accompanies it.

**ADR lifecycle and content** — `ProjectOne Vault/08 ADR/`

- A new ADR is added, or an existing ADR's `status` changes (`Draft` → `Review` → `Accepted`/`Rejected`, or `Accepted` → `Deprecated`/`Superseded`).
- A `Superseded` status that names no successor ADR, or names one that does not exist — §7 defines `Superseded` as *"replaced by a named, linked successor ADR."* **`Deprecated` carries no successor requirement**: §7 defines it as *"no longer recommended, existing usage tolerated,"* so a `Deprecated` ADR with no successor is correct and is not a finding.
- **The normative body of an `Accepted` ADR is edited.** Normative sections are `Decision`, `Consequences`, `Scope Boundaries`, `Alternatives Considered`, and any `Context` statement a `Decision` rests on. This trigger exists because such an edit **requires inspection**, not because it is a violation: whether it changes the accepted decision or only clarifies its wording is check 1's comparison to make, not the trigger's to assume.
- **Mechanical edits are not a trigger.** A `Navigation` block, a `Related` link list, a frontmatter `version`/`last_updated` bump, a typo fix, or a broken-link repair that leaves every normative section untouched is [[Documentation Keeper]]'s work, not a Critical gate. Where one diff mixes both kinds, the normative hunk decides and this skill fires; where the distinction is genuinely unclear, this skill escalates rather than guessing in either direction.

**Dependency and stack boundary** — `apps/api/pyproject.toml`, `apps/web/package.json`

- A dependency is **added, removed, or replaced**, where that dependency is any of: a framework or database engine; a major or load-bearing runtime dependency; one named or governed by an Accepted ADR; part of the established technology stack; one creating or moving a provider or runtime capability boundary; or one creating, collapsing or bypassing an adapter boundary that exists to protect replaceability.
- An **adapter boundary is collapsed or bypassed** — a provider client widened beyond the layer that keeps it replaceable (§7 provider independence). `boto3` confined to `apps/api/app/storage/providers/` behind ADR-004, with `tests/test_storage_boundary.py` asserting it cannot be imported above that layer, is the current example: widening it is an architectural change with no dependency-manifest diff at all.
- **Not a trigger:** adding or removing a minor helper, development or tooling dependency, or a mechanical manifest cleanup, where architectural capability is unchanged — a package landing outside the literal §10 table is not by itself an architectural change. Not a trigger: a version change alone, or a lockfile-only diff (`apps/web/package-lock.json`).
- **[[Security Reviewer]] owns every dependency's package safety, version, lockfile and supply-chain risk**, on additions as well as changes, and fires on those independently. Both Critical skills fire on one dependency change only where it carries **both** architectural and security implications. Neither skill's verdict substitutes for the other's, and neither is a reason to skip the other.

**A new runtime service or process** — wherever it lands, including inside a directory that already exists

- A worker, scheduler, consumer, daemon, or any process launched and supervised independently of an existing one.
- A new execution substrate — a queue, a scheduler, a background-task mechanism, an event consumer — **even when built entirely from existing dependencies and creating no new top-level module**. [[STEP-30 Async Job Infrastructure]] built one inside `apps/api/app/jobs/` and matched none of this skill's previous triggers.
- Structural signals, **none sufficient alone**: a module gaining a `__main__` entrypoint *together with* a supervised loop or a signal-handled lifecycle (`SIGTERM`/`SIGINT`); a new command in the canonical process/deployment model's process table; a new long-lived background thread or scheduled executor owning work outside a request.
- **A one-shot script is not a runtime service.** A CLI utility or CI drill that runs to completion — `apps/api/scripts/`, `scripts/` — adds no process to the deployed system, whatever entrypoint mechanics it carries.

**Infrastructure, only where it changes architecture** — `infrastructure/`

- **Deployment topology** — what deploys, together or separately, and what each deployed unit is.
- **The process model** — the process table, a process's command, or what a process requires in order to start.
- **An ownership boundary** — a responsibility moving between apps, packages, processes, or environments.
- **Runtime architecture** — a new environment, a new runtime boundary, or infrastructure-as-code that introduces either (§28a).
- **Not a trigger: any other change under `infrastructure/`.** Operational runbooks, failure-mode notes, inspection commands and prose edits do not fire this skill. The path is already covered for its other questions — [[Security Reviewer]] on secrets and posture, [[Code Reviewer]] routing infrastructure configuration to owner review under §21 — and this skill adds only the architectural one.

**Repository structure**

- A new top-level module or package, or a new dependency between `apps/` and `packages/`.
- Folder structure reshaped in a way that changes ownership boundaries (not a plain rename).

**Explicit request** — "review this architecture", "does this need an ADR", "is this a new service".

## Check Sequence

1. **ADR lifecycle gate** — if the change implements new architecture, confirm a corresponding ADR exists and is `Accepted` (not `Draft`/`Review`) before treating the implementation as production work, per §7's ADR lifecycle. Confirm a `Superseded` ADR names an existing successor; `Deprecated` requires none. **If the change edits an existing ADR, read the note before and after the diff and classify the edit:**
    - **Decision change** — it materially changes or reverses the accepted `Decision`, its constraints, its `Scope Boundaries`, or its architectural `Consequences`. It may not be amended in place: it requires the owner-controlled §7 lifecycle, normally a superseding ADR that names and links this one. Block, naming that as the remedy.
    - **Clarification** — it corrects or clarifies wording, examples or references without changing what the accepted decision means, permits or constrains. It remains a documentation change; [[Documentation Keeper]] owns its mechanical correctness and this check clears.
    - **Unclear** — the semantic impact cannot be settled from the diff. Escalate and ask (§33–34); resolve it in neither direction.
    - A normative edit to a `Draft` or `Review` ADR is the lifecycle working as intended and clears this check.
2. **Stack boundary check** — confirm the established stack and the ADR-governed dependency set under §10/§28 are unchanged, or that an ADR justifies the change. This covers a dependency added, removed or replaced where it is a framework or database engine, load-bearing at runtime, named or governed by an Accepted ADR, part of the established stack, or carrying a provider/runtime capability or adapter boundary. A dependency change that alters no architectural capability — a minor helper, a development or tooling package, a mechanical manifest cleanup — clears this check without an ADR, whether it is an addition or a removal.
3. **Dependency direction** — confirm dependencies flow inward (apps → shared packages, never the reverse) and no circular imports are introduced (§8, §28).
4. **Folder ownership** — confirm the change lands in the folder that owns that responsibility, per §8–9's placement questions (does this folder own this? could it be reused? does this introduce coupling?).
5. **Modularity/replaceability** — confirm the change doesn't hard-couple a major system (AI, Backend, Frontend, Database, Infrastructure) to another in a way that would block replacing either independently (§7).
6. **Provider independence** — for anything touching an external AI/cloud/third-party service, confirm no unjustified hard lock-in (§7, cross-reference [[AI Providers]]).
7. **Silent-drift check** — confirm the architectural shape actually implemented matches what was proposed/approved; flag any divergence as drift rather than accepting it as a fait accompli (§35).
8. **Process and deployment shape** — for a new independently launched process, execution substrate, or deployment-topology change, confirm it is settled by an `Accepted` ADR and recorded in the repository's **canonical process/deployment model** — currently `infrastructure/process-model.md`. The requirement is that the canonical record exists and describes the change; if that document is later moved, renamed or replaced, this check follows the canonical record rather than the path. Confirm too that the change does not make one app depend on another (§8) or create a runtime boundary no environment can own (§28a). A process that exists in code but appears in neither the ADR record nor the canonical process model is drift under §35, not documentation debt.

## Outputs

- **Pass:** explicit statement that the change's architectural shape is accounted for by an Accepted ADR (or doesn't require one), and clears all eight checks.
- **Block:** the specific check that failed, the CLAUDE.md section violated, and what's missing (e.g. "this introduces a new dependency outside §10 — draft an ADR before this proceeds past prototype/spike scope").

## Escalation

Stops and asks (per §33–34) when:

- Whether a change constitutes "new architecture" (needing an ADR) or is just an implementation detail within existing architecture is genuinely unclear.
- Two plausible module placements both seem defensible and the tie can't be broken from existing conventions.
- Whether an ADR edit touches a normative section at all, or is purely mechanical, cannot be settled from the diff — asks rather than deciding in either direction: passing a normative rewrite as a typo fix defeats §7, and blocking a link repair as a decision change trains people past a Critical gate.
- Whether a normative ADR edit changes the accepted decision's meaning or only clarifies its wording is genuinely ambiguous — check 1's "unclear" outcome. This is a question for the ADR's approver, not a judgment for this skill to make alone.
- Whether an added, removed or substituted dependency is load-bearing, or whether a substitution is like-for-like inside an existing boundary rather than a change of architectural capability, cannot be determined from the manifest alone.
- A new process appears to be required but whether it is a deployed service or a one-shot utility cannot be determined from the change alone.

## Related Skills

- [[Database Engineer]] — leads on schema/migration mechanics; Architecture Reviewer leads on whether a schema change reflects a bigger architectural shift needing an ADR.
- [[Security Reviewer]] — leads on security architecture specifics (RLS, auth), on secrets and posture under `infrastructure/`, and on **package safety, versions, lockfile changes and supply-chain risk** for every dependency change, additions included. Architecture Reviewer checks that security-relevant architecture is documented and approved, not the policy content itself. The two fire together on a dependency change only where it carries both architectural and security implications; a version bump, a lockfile diff, or a minor helper package is Security Reviewer's alone.
- [[AI Systems Engineer]] — leads on AI/agent-specific architecture; Architecture Reviewer checks whether a new agent/workflow pattern needs an ADR before Full Stack Engineer or AI Systems Engineer treat it as settled.
- [[Performance Reviewer]] — Architecture Reviewer checks structural shape; Performance Reviewer checks measured runtime behavior of that shape.
- [[Full Stack Engineer]] — receives an Accepted ADR as the green light to implement; Architecture Reviewer is typically consulted before Full Stack Engineer starts a cross-cutting feature. The boundary is unchanged by this skill's process trigger: Full Stack Engineer implements job, workflow and storage code that changes feature behavior *inside* an approved substrate; this skill decides whether the substrate itself — a new process, a new queue, a new consumer — is permitted at all.
- [[Code Reviewer]] — routes infrastructure and deployment configuration to owner review as Critical under §21 and owns placement, naming and coverage of what was built. This skill owns only the architectural question about the same files, and neither verdict substitutes for the other.
- [[Documentation Keeper]] — owns the mechanical correctness of every ADR and vault note (frontmatter, links, Navigation, index membership), including a clarifying ADR edit once check 1 has established the decision itself did not change.

---

## Navigation

- **Previous:** [[Documentation Keeper]]
- **Next:** [[Full Stack Engineer]]
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[Architecture MOC]] · [[Skill Contract]]
