---
title: Skill Contract
category: AI/Skills
status: stable
version: "1.0"
last_updated: 2026-07-31
tags: [ai, governance, engineering]
aliases: ["Skill Runtime Contract", "Shared Skill Contract"]
---

# Skill Contract

The shared execution model every ProjectOne Skill follows — both the vault specification note (`06 AI/Skills/*.md`) and its `.claude/skills/` runtime wrapper. This exists so five independently-authored skills don't drift into five different behaviors. Any new skill added after these five must conform to this contract before it is considered complete.

## Dual-Layer Architecture

Every skill has exactly two artifacts, never one alone:

1. **Vault specification** (`06 AI/Skills/<Skill Name>.md`) — the canonical, human-readable definition: purpose, scope, classification, governing CLAUDE.md sections, escalation rules. This is what gets reviewed and versioned like any other engineering standard.
2. **Runtime wrapper** (`.claude/skills/<skill-slug>/SKILL.md`) — the auto-triggered implementation Claude Code actually loads. It is deliberately thin: a pointer to the vault spec plus the concrete trigger conditions, check sequence, and output format needed to execute it. It must never restate the reasoning already in the vault spec — restating invites drift.

If the two disagree, the vault specification wins and the wrapper is out of date — this is a bug, tracked the same as any other documentation-drift bug (CLAUDE.md §19).

## Classification: Critical vs. Advisory

Every skill is classified exactly one of two ways, stated explicitly in its vault spec's frontmatter and its wrapper's trigger description:

- **Critical — may block.** Reserved for guarding mistakes that are irreversible, high blast-radius, or expensive to unwind (data exposure across tenants, an unrecoverable migration, a committed secret). A Critical skill may tell Claude to stop and require explicit resolution before the change proceeds. Blocking power is proportionate to irreversibility — it is not a way to enforce style preferences.
- **Advisory — recommends only.** Everything else. An Advisory skill surfaces findings clearly (with file/line references where applicable) but never halts the change on its own authority. The user or the calling context decides whether to act on the recommendation.

A skill's classification may only be Critical if the failure mode it guards against would otherwise violate a Forbidden Practice (CLAUDE.md §35), a mandatory Section 16 security/multi-tenancy rule, or a mandatory Section 13 migration-safety rule. When in doubt, classify Advisory — the same asymmetry CLAUDE.md §33 applies to asking questions applies here: it is cheaper to under-block and get a human's attention than to over-block and train people to bypass the skill.

## Required Sections (Vault Specification)

Every `06 AI/Skills/<Skill Name>.md` note extends the base [[Skill Template]] with these fields, in this order:

1. **Purpose** — the class of work owned, the outcome produced.
2. **Classification** — `Critical` or `Advisory`, one sentence naming which rule above justifies it.
3. **Scope** — explicitly in scope / explicitly out of scope (handed to another skill).
4. **Governing Standards** — which CLAUDE.md sections bind this skill, by number and name.
5. **Trigger Conditions** — what kind of request or file change causes this skill to activate. Concrete enough that the runtime wrapper can implement it directly.
6. **Check Sequence** — the ordered list of checks the skill performs. Deterministic and re-runnable — the same input produces the same findings.
7. **Outputs** — what the skill produces (findings list, blocking message, recommendation) and where it goes.
8. **Escalation** — when the skill stops and asks a question instead of deciding, per CLAUDE.md §33–34.
9. **Related Skills** — handoff points to/from other skills, so responsibilities don't overlap.

## Required Sections (Runtime Wrapper)

Every `.claude/skills/<skill-slug>/SKILL.md` contains:

1. **YAML frontmatter** — `name`, `description` (written so Claude Code's auto-trigger matching fires on the right tasks — specific, not generic), and a `classification: critical | advisory` field.
2. **Pointer line** — one line linking back to the vault spec as the source of truth for reasoning; the wrapper does not re-explain *why*.
3. **Trigger conditions** — restated in concrete, operational form (file globs, action types) matching the vault spec's Trigger Conditions section exactly.
4. **Check sequence** — operational steps, matching the vault spec's Check Sequence exactly, written so they can actually be executed against this repository's current state (docs/ADRs today; code once `apps/`/`packages/` exist).
5. **Output format** — for Critical skills: a clearly labeled block/pass verdict with the specific rule violated. For Advisory skills: a findings list ranked by severity, never a block verdict.
6. **Escalation** — identical trigger logic to the vault spec's Escalation section: when to stop and ask rather than proceed.

## No-Overlap Rule

Each skill owns a distinct class of decision. Where two skills could plausibly both comment on the same change (e.g. a migration that also touches AI cost logic), the vault specs' **Related Skills** sections define which one leads and which one is consulted — this is decided when each skill is authored, not improvised at runtime.

## Skills Under This Contract

All ten ProjectOne skills are Active, shipped in two packs:

| Skill | Pack | Classification | Primary Risk Guarded |
|---|---|---|---|
| [[Security Reviewer]] | 1 | Critical | Tenant data exposure, secret leakage, OWASP violations |
| [[Database Engineer]] | 1 | Critical | Irreversible/unsafe migrations, missing RLS |
| [[Architecture Reviewer]] | 2 | Critical | Silent architectural drift, unapproved framework/dependency changes |
| [[Code Reviewer]] | 1 | Advisory | Quality, consistency, review-checklist gaps |
| [[AI Systems Engineer]] | 1 | Advisory | Missing cost governance, retry/runaway limits |
| [[Documentation Keeper]] | 1 | Advisory | Vault/documentation drift |
| [[Full Stack Engineer]] | 2 | Advisory | Implementation deviating from Frontend/Backend/API standards |
| [[Bug Investigator]] | 2 | Advisory | Fixes that address symptoms instead of root cause |
| [[Performance Reviewer]] | 2 | Advisory | Unmeasured/premature optimization, foreseeable regressions |
| [[Release Manager]] | 2 | Advisory | Incomplete release verification, missing rollback capability |

---

## Navigation

- **Parent:** [[AI Index]]
- **Related Notes:** [[SKILLS]] · [[Skill Template]] · [[CLAUDE|CLAUDE.md]]
