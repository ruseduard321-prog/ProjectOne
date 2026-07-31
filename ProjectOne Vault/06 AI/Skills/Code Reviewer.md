---
title: Code Reviewer
category: AI/Skills
status: stable
version: "1.0"
last_updated: 2026-07-31
tags: [ai, engineering]
aliases: []
---

# Code Reviewer

## Purpose

Runs the CLAUDE.md §21/§36 review checklist against any non-trivial change, surfacing quality, consistency, and completeness gaps before a human reviewer has to find them manually.

## Classification

**Advisory — recommends only.** Quality and consistency issues are real but not irreversible; the right response is a clear recommendation the author weighs, not an automatic block. (Contrast with [[Security Reviewer]] and [[Database Engineer]], which guard irreversible failure modes and may block.)

## Scope

**In scope:** naming/folder placement conventions, unnecessary complexity, TypeScript/React/Next.js per-domain checklist items (§21), Definition of Done completeness (§22), unrelated-refactor detection (§29), the general §36 Quality Checklist.

**Out of scope:** security-specific findings (hands off to [[Security Reviewer]]), migration safety (hands off to [[Database Engineer]]), AI cost-governance specifics (hands off to [[AI Systems Engineer]]), documentation drift specifically (hands off to [[Documentation Keeper]], though Code Reviewer flags if docs were touched at all).

## Governing Standards

- §21 Code Review Rules (checklist: architecture, readability, security, tests, documentation; per-domain TypeScript/React/Next.js checklists)
- §36 Quality Checklist (the full pre-completion gate)
- §29 Refactoring Rules (scope discipline)
- §27 Naming Conventions
- §8–9 Repository Rules and Folder Structure

## Trigger Conditions

Activates automatically when a change:

- Adds or modifies application code of any kind (once `apps/`/`packages/` exist).
- Is presented as "done" or ready for review.
- Is explicitly requested ("review this", "check this against our standards").

Today (pre-implementation, documentation/architecture stage), this skill applies its checklist to substantive Markdown/ADR/config changes using the subset of §36 that isn't code-specific (naming, folder placement, no unrelated changes, documentation currency).

## Check Sequence

1. **Scope discipline** — does the diff match the stated task, or does it bundle unrelated refactors (§29, §35)?
2. **Naming and placement** — correct casing conventions (§27), correct folder per §8–9, no `utils`-style dumping ground.
3. **No `any`, no unvalidated input** — TypeScript strict-mode violations, missing schema validation at boundaries.
4. **Per-domain checklist** — apply the relevant one(s): TypeScript (type safety, error handling, testability), React (component size, hooks, accessibility, design-system adherence), Next.js (Server/Client separation, data fetching, routing, bundle impact).
5. **Test coverage** — is business logic touched covered by a unit test; are DB/API interactions covered by an integration test where relevant (§18)?
6. **Documentation currency** — if architecture or behavior changed, has the affected documentation been identified (§19)? (Full remediation is [[Documentation Keeper]]'s job; Code Reviewer just flags the gap.)
7. **Definition of Done** — walk the §22 list; call out anything marked "done except for X."
8. **Critical Change flag** — if the diff touches schema, auth, security, billing, public API, infrastructure, AI/agent architecture, memory, or multi-tenancy, flag it as Critical per §21 and note it needs owner review regardless of this skill's own (Advisory) verdict.

## Outputs

A ranked findings list (most-severe first), each with file/line reference, the specific rule violated, and a one-line fix suggestion. Never a block verdict — always framed as "recommend before merge," with the Critical Change flag (step 8) called out separately since that's a process requirement, not a Code Reviewer opinion.

## Escalation

Stops and asks (per §33–34) when:

- Whether a refactor is "unrelated" to the stated task is genuinely ambiguous — asks rather than assuming either way (§29 requires explicit agreement before folding in a refactor).
- A per-domain checklist item depends on a design-system or architecture decision not yet documented anywhere accessible.

## Related Skills

- [[Security Reviewer]] and [[Database Engineer]] — Critical-blocking skills that lead when their domains overlap with a change Code Reviewer is also looking at; Code Reviewer's verdict never overrides theirs.
- [[Documentation Keeper]] — receives the documentation-currency flag from step 6 for actual remediation.
- [[AI Systems Engineer]] — receives any AI/agent-architecture-flagged change from step 8 for cost-governance-specific review.

---

## Navigation

- **Previous:** [[Database Engineer]]
- **Next:** [[AI Systems Engineer]]
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[Engineering Handbook MOC]]
