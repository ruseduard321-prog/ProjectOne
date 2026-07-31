---
title: Build Plan
category: Development
status: stable
version: "2.0"
last_updated: 2026-07-31
tags: [engineering, documentation, workflow]
aliases: ["Implementation Plan", "Build Roadmap", "Step Index"]
---

# ProjectOne Build Plan

The ordered execution index taking ProjectOne from an empty repository to first public release. **26 sequential steps**, each sized for a single Claude Code session.

This note is an **index, not a plan** — it holds only ID, title and status. Step detail lives in one note per step under `Steps/`, so a session reads this index plus exactly one step file and nothing else.

**To execute:** say *"Implement the next step."* Claude follows [[Execution Protocol]] — no other instruction needed.

## Status Legend

| Status | Meaning |
|---|---|
| `Not Started` | Untouched. |
| `In Progress` | Claimed by the current session. Set before implementing, never left behind at session end. |
| `Done` | Every [[Execution Protocol#Step Completion]] condition met — Definition of Done satisfied, validation passed, docs updated, status synchronized, no unresolved Critical issues. |
| `Blocked` | Cannot proceed without a named unblocker, or failed validation. Rolled back where safe, reported as-is where rollback is unsafe. **Never committed** without explicit user approval ([[Execution Protocol#Blocked Steps Are Never Committed]]), so a blocked step leaves a dirty working tree by design. **Holds the queue** — the next step does not start ([[Execution Protocol#Validation Failure and Rollback]]). |

Status appears in two places — the step note and the row below — and they must always agree.

**Detail levels:** steps are written at full detail only when they become imminent. Steps still marked `outline` in the Detail column hold goal and scope only — they are expanded into full executable detail by the step immediately preceding them, per [[Execution Protocol]]. This is deliberate: detailed plans for work three months out are fiction, and [[CLAUDE|CLAUDE.md]] §29/§35 forbid speculative over-design.

## Steps

| ID | Title | Status | Detail |
|---|---|---|---|
| STEP-01 | [[STEP-01 Repository Bootstrap]] | Done | full |
| STEP-02 | [[STEP-02 Stack Confirmation ADR]] | Not Started | full |
| STEP-03 | [[STEP-03 Web App Skeleton]] | Not Started | full |
| STEP-04 | [[STEP-04 API App Skeleton]] | Not Started | full |
| STEP-05 | [[STEP-05 Environment and Secrets]] | Not Started | full |
| STEP-06 | [[STEP-06 Continuous Integration]] | Not Started | full |
| STEP-07 | [[STEP-07 Supabase Provisioning]] | Not Started | full |
| STEP-08 | [[STEP-08 Users and Workspaces Schema]] | Not Started | full |
| STEP-09 | [[STEP-09 Row Level Security Policies]] | Not Started | full |
| STEP-10 | [[STEP-10 Authentication Backend]] | Not Started | outline |
| STEP-11 | [[STEP-11 Authorization and RBAC]] | Not Started | outline |
| STEP-12 | [[STEP-12 API Conventions and Middleware]] | Not Started | outline |
| STEP-13 | [[STEP-13 Auth Users Workspaces Endpoints]] | Not Started | outline |
| STEP-14 | [[STEP-14 Design System Tokens]] | Not Started | outline |
| STEP-15 | [[STEP-15 App Shell and Routing]] | Not Started | outline |
| STEP-16 | [[STEP-16 Sign Up and Sign In UI]] | Not Started | outline |
| STEP-17 | [[STEP-17 AI Router and Provider Abstraction]] | Not Started | outline |
| STEP-18 | [[STEP-18 AI Cost Governance Controls]] | Not Started | outline |
| STEP-19 | [[STEP-19 Settings and BYOK UI]] | Not Started | outline |
| STEP-20 | [[STEP-20 Projects Schema and Lifecycle]] | Not Started | outline |
| STEP-21 | [[STEP-21 Projects UI]] | Not Started | outline |
| STEP-22 | [[STEP-22 Minimum Workflow Engine]] | Not Started | outline |
| STEP-23 | [[STEP-23 AI Chat End to End]] | Not Started | outline |
| STEP-24 | [[STEP-24 Dashboard]] | Not Started | outline |
| STEP-25 | [[STEP-25 Launch Readiness Criteria]] | Not Started | outline |
| STEP-26 | [[STEP-26 First Public Release]] | Not Started | outline |

## Scope Boundary

These 26 steps deliver the **first public release** — the Foundation loop (sign up → workspace → project → AI chat → dashboard) hardened, billed for, and shipped. Everything the [[Roadmap]] places in Phase 2 (Video Generation, Analytics, advanced agents, publishing) and Phase 3 (teams, enterprise, marketplace) is **out of scope for this plan** and gets its own step sequence once STEP-26 is Done.

One consequence is worth stating plainly rather than discovering at STEP-25: **[[Billing]] is not in these 26 steps.** A public release that charges money needs it; a free/invite-only public beta does not. STEP-25 resolves which of those this release is, and inserts billing steps if required — see that step's note.

## Source Documents

This plan is derived from, and must stay consistent with, the vault. If this plan and a source document disagree, **the source document wins** — update the plan, not the source. Individual steps name their own required reading; the full corpus is:

- [[Roadmap]] · [[Release Strategy]] · [[Deployment Strategy]] · [[Testing Strategy]] — delivery
- [[Product Bible]] and `03 Project Bible/01 Features/` — feature specifications
- [[AI Architecture]] · [[Agent Architecture]] · [[Memory System]] · [[AI Providers]] · [[Workflow Engine]] — AI systems
- [[Backend Architecture]] · [[Database Architecture]] · [[API Architecture]] · [[Frontend Architecture]] · [[Infrastructure]] — tech architecture
- [[Security Architecture]] · [[Authentication and Authorization]] · [[Privacy and Data Protection]] · [[Compliance and Governance]] — security & trust
- [[Design System]] — the UI standard every screen follows
- Engineering Handbook Chapters 1–11 — binding build standards
- [[CLAUDE|CLAUDE.md]] — operating rules governing every step

## Current State

As of 2026-07-31, **no application code exists yet**. STEP-01 is `Done`: the project root is a git repository on branch `main` with one commit, and the canonical skeleton (`apps/`, `packages/`, `infrastructure/`, `docs/`, `scripts/`, `.github/`) exists but holds no implementation — the directories are placeholders awaiting STEP-03 onward. The vault, Claude OS and AI operating capabilities are built and validated ([[Environment Setup]], [[AI Index]]).

Every Project Bible note is still `status: draft` at v0.1 — the *specification* is transcribed, not accepted. Treat drafts as the best current source of truth and flag genuine ambiguity per [[CLAUDE|CLAUDE.md]] §33 rather than resolving it silently mid-step.

No ADRs exist. STEP-02 writes the first.

---

## Navigation

- **Previous:** —
- **Next:** [[Execution Protocol]]
- **Parent:** [[Development MOC]]
- **Related Notes:** [[Execution Protocol]] · [[Roadmap]] · [[Task Workflow]] · [[CLAUDE|CLAUDE.md]]
