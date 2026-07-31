---
title: Architecture Reviewer
category: AI/Skills
status: stable
version: "1.0"
last_updated: 2026-07-31
tags: [ai, engineering, architecture]
aliases: []
---

# Architecture Reviewer

## Purpose

Reviews any change that introduces, alters, or bypasses architectural structure — new modules, new dependencies between apps/packages, new ADRs, or anything that shapes how ProjectOne's systems fit together — and confirms it holds to the Architecture Principles and Repository Rules before it's treated as settled. Produces a clear verdict on whether an architectural decision is proposed correctly (as an ADR, at the right lifecycle stage) or is drifting in silently.

## Classification

**Critical — may block.** Silent architectural drift is a named Forbidden Practice ([[CLAUDE|CLAUDE.md]] §35), and undoing an architecture decision after code has been built against it (a wrong module boundary, an accidental circular dependency, a framework introduced outside the stack table) is exactly the kind of expensive-to-reverse mistake this contract's Critical bar is meant for (see [[Skill Contract]]).

## Scope

**In scope:** ADR lifecycle compliance (Draft → Review → Accepted before implementation begins), Repository Rules (§8–9: folder ownership, dependency direction, no circular imports), Technology Stack boundary (§10: no new framework/database/major dependency without an ADR), Architecture Principles (§7: modular services, provider independence, stateless APIs, deterministic/observable workflows).

**Out of scope:** database schema shape and migration mechanics (owned by [[Database Engineer]]), security architecture specifics like RLS/auth (owned by [[Security Reviewer]]), AI/agent-specific architecture like cost governance (owned by [[AI Systems Engineer]]), day-to-day code quality within an already-settled architecture (owned by [[Code Reviewer]]), performance characteristics of an architecture (owned by [[Performance Reviewer]] — Architecture Reviewer checks *shape*, Performance Reviewer checks *measured behavior*).

## Governing Standards

- §7 Architecture Principles (modular services, provider independence, stateless APIs, deterministic/observable/resumable workflows) and the ADR lifecycle (Draft/Review/Accepted/Deprecated/Superseded/Rejected)
- §8 Repository Rules (dependency direction, no circular imports, folder ownership)
- §9 Folder Structure
- §10 Technology Stack (no new framework/database/major dependency without an ADR)
- §28 Dependency Rules
- §35 Forbidden Practices (no silent architecture change, no rewriting unrelated code)

## Trigger Conditions

Activates automatically when a change:

- Adds a new ADR, or changes an existing ADR's lifecycle status.
- Introduces a new top-level module, package, or dependency between `apps/`/`packages/`.
- Adds a new third-party framework, database engine, or major dependency outside the §10 stack table.
- Modifies folder structure in a way that changes ownership boundaries (not a plain rename — a reshape).
- Is explicitly requested ("review this architecture", "does this need an ADR").

## Check Sequence

1. **ADR lifecycle gate** — if the change implements new architecture, confirm a corresponding ADR exists and is `Accepted` (not `Draft`/`Review`) before treating the implementation as production work, per §7's ADR lifecycle.
2. **Stack boundary check** — confirm no new framework, database engine, or major dependency is introduced outside §10 without an ADR justifying it.
3. **Dependency direction** — confirm dependencies flow inward (apps → shared packages, never the reverse) and no circular imports are introduced (§8, §28).
4. **Folder ownership** — confirm the change lands in the folder that owns that responsibility, per §8–9's placement questions (does this folder own this? could it be reused? does this introduce coupling?).
5. **Modularity/replaceability** — confirm the change doesn't hard-couple a major system (AI, Backend, Frontend, Database, Infrastructure) to another in a way that would block replacing either independently (§7).
6. **Provider independence** — for anything touching an external AI/cloud/third-party service, confirm no unjustified hard lock-in (§7, cross-reference [[AI Providers]]).
7. **Silent-drift check** — confirm the architectural shape actually implemented matches what was proposed/approved; flag any divergence as drift rather than accepting it as a fait accompli (§35).

## Outputs

- **Pass:** explicit statement that the change's architectural shape is accounted for by an Accepted ADR (or doesn't require one), and clears all six checks.
- **Block:** the specific check that failed, the CLAUDE.md section violated, and what's missing (e.g. "this introduces a new dependency outside §10 — draft an ADR before this proceeds past prototype/spike scope").

## Escalation

Stops and asks (per §33–34) when:

- Whether a change constitutes "new architecture" (needing an ADR) or is just an implementation detail within existing architecture is genuinely unclear.
- Two plausible module placements both seem defensible and the tie can't be broken from existing conventions.

## Related Skills

- [[Database Engineer]] — leads on schema/migration mechanics; Architecture Reviewer leads on whether a schema change reflects a bigger architectural shift needing an ADR.
- [[Security Reviewer]] — leads on security architecture specifics (RLS, auth); Architecture Reviewer checks that security-relevant architecture is documented and approved, not the policy content itself.
- [[AI Systems Engineer]] — leads on AI/agent-specific architecture; Architecture Reviewer checks whether a new agent/workflow pattern needs an ADR before Full Stack Engineer or AI Systems Engineer treat it as settled.
- [[Performance Reviewer]] — Architecture Reviewer checks structural shape; Performance Reviewer checks measured runtime behavior of that shape.
- [[Full Stack Engineer]] — receives an Accepted ADR as the green light to implement; Architecture Reviewer is typically consulted before Full Stack Engineer starts a cross-cutting feature.

---

## Navigation

- **Previous:** [[Documentation Keeper]]
- **Next:** [[Full Stack Engineer]]
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[Architecture MOC]] · [[Skill Contract]]
