---
title: SKILLS.md
category: AI/Skills
status: stable
version: "1.0"
last_updated: 2026-07-31
tags: [ai, documentation]
aliases: ["Skills Overview", "AI Skills Index"]
---

# SKILLS.md

Index of every specialized AI role/skill defined for ProjectOne. Each skill in [[Skills]] describes a focused persona Claude can adopt for a specific class of work — scoped responsibilities, standards it enforces, and the sections of [[CLAUDE|CLAUDE.md]] it operates under most heavily.

Every skill follows the [[Skill Contract]]: a vault specification (this section) paired with an auto-triggered runtime wrapper in `.claude/skills/`, classified as either **Critical** (may block the change) or **Advisory** (recommends only). See the contract note for the full execution model.

All ten skills are now Active — defined in full, each with a matching runtime wrapper in `.claude/skills/`. Skill Pack 1 (risk-ordered) shipped first; Skill Pack 2 completes the set.

## Active Skills

| Skill | Pack | Classification | Primary Focus | Governing CLAUDE.md Sections |
|---|---|---|---|---|
| [[Security Reviewer]] | 1 | Critical | Security, multi-tenancy, OWASP | §16, §35 |
| [[Database Engineer]] | 1 | Critical | Schema, migrations, RLS | §13, §16 |
| [[Architecture Reviewer]] | 2 | Critical | Architecture Principles, ADR lifecycle | §7, §8, §10, §28 |
| [[Code Reviewer]] | 1 | Advisory | Code review, quality gates | §21, §36 |
| [[AI Systems Engineer]] | 1 | Advisory | AI/agent cost governance, prompts | §15, §15a, §31 |
| [[Documentation Keeper]] | 1 | Advisory | Docs/vault synchronization | §19 |
| [[Full Stack Engineer]] | 2 | Advisory | End-to-end feature implementation | §11, §12, §14 |
| [[Bug Investigator]] | 2 | Advisory | Root-cause analysis, defect triage | §18, §24, §25 |
| [[Performance Reviewer]] | 2 | Advisory | Performance, scalability | §17 |
| [[Release Manager]] | 2 | Advisory | Release readiness, deployment | §37, §22, §26 |

---

## Navigation

- **Previous:** [[CLAUDE|CLAUDE.md]]
- **Next:** [[Skill Contract]]
- **Parent:** [[AI Index]]
- **Related Notes:** [[Skill Contract]] · [[Skill Template]] · [[CLAUDE|CLAUDE.md]]
