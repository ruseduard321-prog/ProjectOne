---
title: Build Plan
category: Development
status: stable
version: "4.3"
last_updated: 2026-08-16
tags: [engineering, documentation, workflow]
aliases: ["Implementation Plan", "Build Roadmap", "Step Index"]
---

# ProjectOne Build Plan

The ordered execution index taking ProjectOne from an empty repository to a verified product in the hands of real users. **94 sequential steps** — 34 delivered (29 numbered plus five inserted by owner decision: STEP-11a, STEP-16a, STEP-12a, STEP-16b, STEP-25a), and **60 future steps, STEP-30 through STEP-89**, each sized for a single Claude Code session. Three further step notes are **superseded and carry no status**, so they are deliberately not part of that 94 — they are kept as history in [[#Superseded Step Numbering]].

**The future half of this plan was rebuilt on 2026-08-15**, by owner decision, against the [[Product Coverage Audit]]. That audit measured the complete intended product against what `main` actually implements and found 24 capabilities Missing, 14 Foundation/Partial and — the finding that forced the rebuild — several P0 prerequisites with **no executable step anywhere**: file storage, async execution, the AI capability model beyond chat completion, and the Memory System. A three-step tail could not carry them.

**Dependency order outranks historical numbering.** Where the two conflicted, the dependency won and the number moved. Two previously-numbered steps were renumbered rather than cancelled, and one was split; all three are recorded in [[#Superseded Step Numbering]] rather than quietly overwritten.

**Steps execute in table order, not in numeric order.** A step numbered `Na` is placed where it belongs in the *dependency* sequence, while its number records which step's contract it amends. STEP-12a amends STEP-12's middleware contract but runs after STEP-16a, because the regression it fixes was only introduced by STEP-16.

This note is an **index, not a plan** — it holds only ID, title and status. Step detail lives in one note per step under `Steps/`, so a session reads this index plus exactly one step file, and beyond that only what [[Execution Protocol#Context Discipline]] permits.

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
| | **Foundation — delivered** | | |
| STEP-01 | [[STEP-01 Repository Bootstrap]] | Done | full |
| STEP-02 | [[STEP-02 Stack Confirmation ADR]] | Done | full |
| STEP-03 | [[STEP-03 Web App Skeleton]] | Done | full |
| STEP-04 | [[STEP-04 API App Skeleton]] | Done | full |
| STEP-05 | [[STEP-05 Environment and Secrets]] | Done | full |
| STEP-06 | [[STEP-06 Continuous Integration]] | Done | full |
| STEP-07 | [[STEP-07 Supabase Provisioning]] | Done | full |
| STEP-08 | [[STEP-08 Users and Workspaces Schema]] | Done | full |
| STEP-09 | [[STEP-09 Row Level Security Policies]] | Done | full |
| STEP-10 | [[STEP-10 Authentication Backend]] | Done | full |
| STEP-11 | [[STEP-11 Authorization and RBAC]] | Done | full |
| STEP-11a | [[STEP-11a Membership Removal Policy]] | Done | full |
| STEP-12 | [[STEP-12 API Conventions and Middleware]] | Done | full |
| STEP-13 | [[STEP-13 Auth Users Workspaces Endpoints]] | Done | full |
| STEP-14 | [[STEP-14 Design System Tokens]] | Done | full |
| STEP-15 | [[STEP-15 App Shell and Routing]] | Done | full |
| STEP-16 | [[STEP-16 Sign Up and Sign In UI]] | Done | full |
| STEP-12a | [[STEP-12a Trusted Proxy and Per-User Rate Limiting]] | Done | full |
| STEP-16a | [[STEP-16a Developer Session Inspector]] | Done | full |
| STEP-17 | [[STEP-17 AI Router and Provider Abstraction]] | Done | full |
| STEP-18 | [[STEP-18 AI Cost Governance Controls]] | Done | full |
| STEP-19 | [[STEP-19 Settings and BYOK UI]] | Done | full |
| STEP-20 | [[STEP-20 Projects Schema and Lifecycle]] | Done | full |
| STEP-21 | [[STEP-21 Projects UI]] | Done | full |
| STEP-22 | [[STEP-22 Minimum Workflow Engine]] | Done | full |
| STEP-23 | [[STEP-23 AI Chat End to End]] | Done | full |
| STEP-24 | [[STEP-24 Dashboard]] | Done | full |
| STEP-16b | [[STEP-16b Auth Refresh Outage Handling]] | Done | full |
| STEP-25 | [[STEP-25 Foundation Audit and Internal Readiness]] | Done | full |
| STEP-25a | [[STEP-25a Foundation Remediation]] | Done | full |
| | **Design Foundation** | | |
| STEP-26 | [[STEP-26 Product Design System Foundation]] | Done | full |
| | **Platform Substrate** | | |
| STEP-27 | [[STEP-27 Storage Provider Abstraction]] | Done | full |
| STEP-28 | [[STEP-28 Asset Upload and Download]] | Done | full |
| STEP-29 | [[STEP-29 Asset Management UI]] | Done | full |
| STEP-30 | [[STEP-30 Async Job Infrastructure]] | Not Started | full |
| STEP-31 | [[STEP-31 Workflow Async Execution]] | Not Started | outline |
| STEP-32 | [[STEP-32 Media Processing Pipeline]] | Not Started | outline |
| STEP-33 | [[STEP-33 Storage Quotas and Lifecycle]] | Not Started | outline |
| STEP-34 | [[STEP-34 Notifications Domain]] | Not Started | outline |
| STEP-35 | [[STEP-35 Notifications UI]] | Not Started | outline |
| | **AI Capability Expansion** | | |
| STEP-36 | [[STEP-36 AI Capability Contract Expansion]] | Not Started | outline |
| STEP-37 | [[STEP-37 Image Generation Capability]] | Not Started | outline |
| STEP-38 | [[STEP-38 Text-to-Speech Capability]] | Not Started | outline |
| STEP-39 | [[STEP-39 Embeddings Capability]] | Not Started | outline |
| STEP-40 | [[STEP-40 Tool Calling Capability]] | Not Started | outline |
| STEP-41 | [[STEP-41 Prompt Store and Versioning]] | Not Started | outline |
| STEP-42 | [[STEP-42 Chat Tool Actions]] | Not Started | outline |
| | **Context and Memory** | | |
| STEP-43 | [[STEP-43 Shared Context Manager]] | Not Started | outline |
| STEP-44 | [[STEP-44 Memory Schema and Scopes]] | Not Started | outline |
| STEP-45 | [[STEP-45 Memory Retrieval]] | Not Started | outline |
| STEP-46 | [[STEP-46 Memory Update Policies]] | Not Started | outline |
| STEP-47 | [[STEP-47 Memory Inspection and Control]] | Not Started | outline |
| STEP-48 | [[STEP-48 Richer Chat Context]] | Not Started | outline |
| | **Workflow and Agent Infrastructure** | | |
| STEP-49 | [[STEP-49 Agent Invocation Safety Ceiling]] | Not Started | outline |
| STEP-50 | [[STEP-50 Workflow Retry and Failure Recovery]] | Not Started | outline |
| STEP-51 | [[STEP-51 Workflow Branching]] | Not Started | outline |
| STEP-52 | [[STEP-52 Workflow Parallel Execution]] | Not Started | outline |
| STEP-53 | [[STEP-53 Multi-Agent Orchestration]] | Not Started | outline |
| | **Content Intelligence** | | |
| STEP-54 | [[STEP-54 Research Agent]] | Not Started | outline |
| STEP-55 | [[STEP-55 Script Agent]] | Not Started | outline |
| STEP-56 | [[STEP-56 Script Review and Editing UI]] | Not Started | outline |
| | **Media Production** | | |
| STEP-57 | [[STEP-57 Media Generation Agent]] | Not Started | outline |
| STEP-58 | [[STEP-58 Voice and Audio Generation]] | Not Started | outline |
| STEP-59 | [[STEP-59 Audio Track Assembly]] | Not Started | outline |
| | **Video Production** | | |
| STEP-60 | [[STEP-60 Video Assembly Agent]] | Not Started | outline |
| STEP-61 | [[STEP-61 Quality Assurance Agent]] | Not Started | outline |
| STEP-62 | [[STEP-62 Regeneration and Review UI]] | Not Started | outline |
| STEP-63 | [[STEP-63 Subtitles and Publishing Metadata]] | Not Started | outline |
| STEP-64 | [[STEP-64 Video Export and Delivery]] | Not Started | outline |
| | **Distribution** | | |
| STEP-65 | [[STEP-65 Channels Domain]] | Not Started | outline |
| STEP-66 | [[STEP-66 Connected Accounts and OAuth]] | Not Started | outline |
| STEP-67 | [[STEP-67 Publishing Execution]] | Not Started | outline |
| STEP-68 | [[STEP-68 Publishing Agent and Multi-Platform Targeting]] | Not Started | outline |
| | **Analytics and Optimization** | | |
| STEP-69 | [[STEP-69 Analytics Schema and Event Ingestion]] | Not Started | outline |
| STEP-70 | [[STEP-70 Platform Metrics Ingestion]] | Not Started | outline |
| STEP-71 | [[STEP-71 Analytics Metrics and Surfaces]] | Not Started | outline |
| STEP-72 | [[STEP-72 Analytics Agent]] | Not Started | outline |
| STEP-73 | [[STEP-73 Strategy Agent and Continuous Optimization]] | Not Started | outline |
| | **Automation and Collaboration** | | |
| STEP-74 | [[STEP-74 Workflow Scheduling and Triggers]] | Not Started | outline |
| STEP-75 | [[STEP-75 Notification Delivery Channels]] | Not Started | outline |
| STEP-76 | [[STEP-76 Notification Preferences]] | Not Started | outline |
| STEP-77 | [[STEP-77 Workspace and Collaboration Foundations]] | Not Started | outline |
| STEP-78 | [[STEP-78 Scheduled Publishing]] | Not Started | outline |
| | **Product UI Consolidation** | | |
| STEP-79 | [[STEP-79 Domain Screen Blueprints]] | Not Started | outline |
| STEP-80 | [[STEP-80 Product-wide UI Rebuild]] | Not Started | outline |
| | **Beta Readiness and Release** | | |
| STEP-81 | [[STEP-81 Observability and Alerting]] | Not Started | outline |
| STEP-82 | [[STEP-82 Staging Environment and Deployment Pipeline]] | Not Started | outline |
| STEP-83 | [[STEP-83 Backup, Recovery Objectives and Disaster Drill]] | Not Started | outline |
| STEP-84 | [[STEP-84 Security Review and Penetration Testing]] | Not Started | outline |
| STEP-85 | [[STEP-85 Full Product Verification and Hardening]] | Not Started | outline |
| STEP-86 | [[STEP-86 Private Beta Release]] | Not Started | outline |
| | **Commercial Readiness** | | |
| STEP-87 | [[STEP-87 Billing Schema and Subscription Management]] | Not Started | outline |
| STEP-88 | [[STEP-88 Plan Limits and Quota Enforcement]] | Not Started | outline |
| STEP-89 | [[STEP-89 Billing UI and Invoices]] | Not Started | outline |

## Phases

The future sequence is grouped into fourteen phases. Grouping is descriptive — **numbering is one continuous sequence**, and a phase boundary is not a gate.

| Phase | Steps | Count | What it establishes |
|---|---|---|---|
| **Design Foundation** | STEP-26–STEP-26 | 1 | The shared visual and interaction system, established once against the surfaces that actually exist. |
| **Platform Substrate** | STEP-27–STEP-35 | 9 | The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, and enough notification to make an asynchronous run visible. |
| **AI Capability Expansion** | STEP-36–STEP-42 | 7 | Turning a chat-only AI layer into one that can produce media and take actions, with every prompt versioned before the agents that depend on them are written. |
| **Context and Memory** | STEP-43–STEP-48 | 6 | Shared context assembly and the five-scope Memory System, with the user controls [[CLAUDE|CLAUDE.md]] §15 requires of it. |
| **Workflow and Agent Infrastructure** | STEP-49–STEP-53 | 5 | The engine extensions and the agent-safety ceiling that must exist before agents can chain. |
| **Content Intelligence** | STEP-54–STEP-56 | 3 | The first real agent chain: research and script, producing content worth generating media for. |
| **Media Production** | STEP-57–STEP-59 | 3 | Image, audio and voice generation as governed, resumable, storage-backed workflows. |
| **Video Production** | STEP-60–STEP-64 | 5 | Assembly, rendering, quality checks, regeneration and export. |
| **Distribution** | STEP-65–STEP-68 | 4 | Channels, connected accounts and the publishing path that turns finished content into published content. |
| **Analytics and Optimization** | STEP-69–STEP-73 | 5 | Event data first, then metrics, then the agents that reason over them. |
| **Automation and Collaboration** | STEP-74–STEP-78 | 5 | Scheduled and triggered execution, richer notification delivery, and the workspace collaboration foundations that depend on it. |
| **Product UI Consolidation** | STEP-79–STEP-80 | 2 | The product-wide visual rebuild, run once the real product surface exists. |
| **Beta Readiness and Release** | STEP-81–STEP-86 | 6 | Observability, staging, recovery, security review, full verification of the beta surface, and the private invite-only free beta itself. |
| **Commercial Readiness** | STEP-87–STEP-89 | 3 | Billing, plan enforcement and invoicing — after the free beta has proven the product, before any paid release. |

### Why this order

The order is derived from what genuinely blocks what, not from how important a capability is. Five chains determine most of it:

- **Storage → upload → media generation → assembly → publishing.** Nothing about media moves until files can be stored; the audit named this the single largest blocker in the product.
- **Async execution → long-running generation → rendering → scheduling.** Workflow runs currently execute inside the HTTP request, and a multi-minute render cannot.
- **Capability contract → image / TTS / embeddings / tool calling → prompt store → the agents that use them.** `Capability.CHAT_COMPLETION` is today the only member of the enum, and the prompt store lands **before** the agent chain so no agent ever ships an unversioned prompt.
- **Agent safety ceiling → chained agents → multi-agent workflows.** [[CLAUDE|CLAUDE.md]] §15a's cap on chained invocation is scheduled **before** the first agent chain, not alongside it.
- **Verification → private beta → billing.** The free beta is not gated on commercial machinery.

Three placements are owner decisions rather than dependency conclusions, and are recorded as such:

- **Design is split.** [[STEP-26 Product Design System Foundation]] establishes the shared system now, against surfaces that exist. Screens for domains that do not yet exist are blueprinted in [[STEP-79 Domain Screen Blueprints]], once their behaviour is known rather than imagined.
- **The UI rebuild runs late** ([[STEP-80 Product-wide UI Rebuild]]), so one consolidating pass covers a whole product rather than a fraction of one.
- **Billing runs after the beta**, not before it — see [[#Ordering Corrections]].

## Ordering Corrections — 2026-08-15

Three corrections were applied by owner review after the roadmap was first sequenced. Each is recorded with its reasoning, because each changed the numbering of steps that had already been written down.

### 1. The prompt store moved into the AI foundation

`Prompt Store and Versioning` sat at STEP-78, *after* seven specialized agents. Its own note admitted that by then many prompts would exist and drift would already be real.

Building Research, Script, Media, QA, Publishing, Analytics and Strategy agents against inline string constants and migrating them afterwards is deliberately creating the problem [[CLAUDE|CLAUDE.md]] §31 exists to prevent. It is now **[[STEP-41 Prompt Store and Versioning]]**, inside AI Capability Expansion and before the agent chain begins — at the point where only two prompts exist and the migration is cheapest.

### 2. Billing no longer gates the free beta

The plan said billing was not required for the private invite-only free beta, and then scheduled billing at STEP-81–83 *before* the beta at STEP-89. **Because steps execute in sequence, that made billing a beta prerequisite in practice**, whatever the note said.

Corrected: the beta is now **[[STEP-86 Private Beta Release]]**, and billing follows it as **[[STEP-87 Billing Schema and Subscription Management]]**, [[STEP-88 Plan Limits and Quota Enforcement]] and [[STEP-89 Billing UI and Invoices]].

One consequence is stated explicitly in both places rather than left to inference: **[[STEP-85 Full Product Verification and Hardening]] verifies the beta product surface**, which does not include billing. Billing carries its own required tests, and the commercial-release verification that covers it belongs to the public paid release step — which remains unscheduled by owner decision.

### 3. Notification work is no longer front-loaded

Notifications were four consecutive early substrate steps. Checked against the dependency graph, only the first two are load-bearing early: a domain and an in-app surface, so an asynchronous run that pauses for approval is visible at all.

**External delivery channels and preferences block nothing** in AI capability expansion, memory or the agent chain — the only step that genuinely needs email delivery is workspace invitations. They moved to **[[STEP-75 Notification Delivery Channels]]** and **[[STEP-76 Notification Preferences]]**, beside [[STEP-77 Workspace and Collaboration Foundations]] in Automation and Collaboration. [[STEP-34 Notifications Domain]] and [[STEP-35 Notifications UI]] stay early, which is the minimum the approval gate requires.

### Renumbering caused by these corrections

51 of the 64 future steps changed number. The range and the count are unchanged: **STEP-26 to STEP-89, 64 steps.** No step's *content* changed except where a correction required it — the prompt store, the verification scope, the beta and the three billing steps.

| Was | Now | Step |
|---|---|---|
| STEP-36 | STEP-75 | Notification Delivery Channels |
| STEP-37 | STEP-76 | Notification Preferences |
| STEP-38 | STEP-36 | AI Capability Contract Expansion |
| STEP-39 | STEP-37 | Image Generation Capability |
| STEP-40 | STEP-38 | Text-to-Speech Capability |
| STEP-41 | STEP-39 | Embeddings Capability |
| STEP-42 | STEP-40 | Tool Calling Capability |
| STEP-43 | STEP-42 | Chat Tool Actions |
| STEP-44 | STEP-43 | Shared Context Manager |
| STEP-45 | STEP-44 | Memory Schema and Scopes |
| STEP-46 | STEP-45 | Memory Retrieval |
| STEP-47 | STEP-46 | Memory Update Policies |
| STEP-48 | STEP-47 | Memory Inspection and Control |
| STEP-49 | STEP-48 | Richer Chat Context |
| STEP-50 | STEP-49 | Agent Invocation Safety Ceiling |
| STEP-51 | STEP-50 | Workflow Retry and Failure Recovery |
| STEP-52 | STEP-51 | Workflow Branching |
| STEP-53 | STEP-52 | Workflow Parallel Execution |
| STEP-54 | STEP-53 | Multi-Agent Orchestration |
| STEP-55 | STEP-54 | Research Agent |
| STEP-56 | STEP-55 | Script Agent |
| STEP-57 | STEP-56 | Script Review and Editing UI |
| STEP-58 | STEP-57 | Media Generation Agent |
| STEP-59 | STEP-58 | Voice and Audio Generation |
| STEP-60 | STEP-59 | Audio Track Assembly |
| STEP-61 | STEP-60 | Video Assembly Agent |
| STEP-62 | STEP-61 | Quality Assurance Agent |
| STEP-63 | STEP-62 | Regeneration and Review UI |
| STEP-64 | STEP-63 | Subtitles and Publishing Metadata |
| STEP-65 | STEP-64 | Video Export and Delivery |
| STEP-66 | STEP-65 | Channels Domain |
| STEP-67 | STEP-66 | Connected Accounts and OAuth |
| STEP-68 | STEP-67 | Publishing Execution |
| STEP-69 | STEP-68 | Publishing Agent and Multi-Platform Targeting |
| STEP-70 | STEP-69 | Analytics Schema and Event Ingestion |
| STEP-71 | STEP-70 | Platform Metrics Ingestion |
| STEP-72 | STEP-71 | Analytics Metrics and Surfaces |
| STEP-73 | STEP-72 | Analytics Agent |
| STEP-74 | STEP-73 | Strategy Agent and Continuous Optimization |
| STEP-75 | STEP-74 | Workflow Scheduling and Triggers |
| STEP-76 | STEP-78 | Scheduled Publishing |
| STEP-78 | STEP-41 | Prompt Store and Versioning |
| STEP-81 | STEP-87 | Billing Schema and Subscription Management |
| STEP-82 | STEP-88 | Plan Limits and Quota Enforcement |
| STEP-83 | STEP-89 | Billing UI and Invoices |
| STEP-84 | STEP-81 | Observability and Alerting |
| STEP-85 | STEP-82 | Staging Environment and Deployment Pipeline |
| STEP-86 | STEP-83 | Backup, Recovery Objectives and Disaster Drill |
| STEP-87 | STEP-84 | Security Review and Penetration Testing |
| STEP-88 | STEP-85 | Full Product Verification and Hardening |
| STEP-89 | STEP-86 | Private Beta Release |

## Scope Boundary

These steps deliver the complete target product loop — idea → planning → research → script → media → voice → assembly → quality checks → review and regeneration → export → connected-platform publishing → analytics → strategy feedback — plus the platform capabilities [[Product Bible]] names as pillars: Projects, AI Chat, Agents, Memory, Automation, Analytics, Publishing, Collaboration foundations and Continuous Optimization.

**They end at a private beta followed by billing.** [[STEP-86 Private Beta Release]] puts the product in front of invited users, free of charge; [[STEP-87 Billing Schema and Subscription Management]] through [[STEP-89 Billing UI and Invoices]] then build the commercial machinery a paid release needs. **A public, paid launch is a separate owner decision** and a later step that does not yet exist.

Deliberately **not** in this plan, and deferred with reasons stated in [[#Deferred by Decision]]: enterprise capabilities, a marketplace, real-time collaborative editing and formal compliance certification — all [[Roadmap]] Phase 3 material.

## Superseded Step Numbering

Three step notes were superseded on 2026-08-15. All three are **kept as history** with their original outlines intact, marked `Superseded`, holding no status in this plan.

| Former step | Became | Why |
|---|---|---|
| `STEP-26 Product Design System and Screen Blueprints` | **Split** — [[STEP-26 Product Design System Foundation]] keeps the number and the design-system half; [[STEP-79 Domain Screen Blueprints]] takes the blueprints | Blueprinting Video Generation, Analytics, Publishing or Billing screens today would design against a specification rather than a product |
| `STEP-27 Product-wide UI Rebuild` | **Renumbered** — [[STEP-80 Product-wide UI Rebuild]] | At STEP-27 it would have restyled the Foundation surfaces and nothing else, leaving every later domain to drift again |
| `STEP-28 Full Product Verification Polish and Hardening` | **Renumbered** — [[STEP-85 Full Product Verification and Hardening]] | Its own goal is to verify *the whole product, once*; at STEP-28 the whole product was the Foundation loop |

The approved visual direction, the reference image, the ADR checkpoint, the no-redesign-during-implementation rule and the defect policy all **carry forward** into the successor steps. Nothing was discarded in the renumbering — see each superseded note for the detail.

## Deferred by Decision

Capabilities the [[Product Coverage Audit]] recorded as specified-but-absent which are **deliberately not scheduled**, with the reason stated rather than left as silence:

| Capability | Reason |
|---|---|
| MFA, OAuth and social sign-in | Accepted in [[Foundation Audit Findings]]. Not required for an invite-only beta; revisit before public sign-up |
| Streaming AI responses | A UX quality improvement, not a capability gap. The provider contract excludes it deliberately, and adding it is one method per provider whenever it is wanted |
| Team collaboration beyond workspaces and roles | [[Roadmap]] Phase 3. [[STEP-77 Workspace and Collaboration Foundations]] delivers the foundation; presence and real-time co-editing are a separate product decision |
| Integrations and Advanced settings sections | [[Settings]] names both; neither has defined scope in any source document. Scoping them is an owner decision before they can become steps |
| Project versioning and project search | [[Projects]] names both as principles. Deferred until real usage shows what a version and a search actually need to cover |
| Marketplace, enterprise capabilities, formal certification | [[Roadmap]] Phase 3, explicitly beyond this plan |
| Idempotency keys | Recorded as an open gap since STEP-22. Folded into the API surfaces of the steps that need them rather than carried as a standalone step |
| Public paid launch | The owner's release decision makes the first release a free invite-only beta. The step that publishes publicly will be created when that decision is made |

## Source Documents

This plan is derived from, and must stay consistent with, the vault. If this plan and a source document disagree, **the source document wins** — update the plan, not the source. Individual steps name their own required reading; the full corpus is:

- [[Roadmap]] · [[Release Strategy]] · [[Deployment Strategy]] · [[Testing Strategy]] — delivery
- [[Product Bible]] and `03 Project Bible/01 Features/` — feature specifications
- [[AI Architecture]] · [[Agent Architecture]] · [[Memory System]] · [[AI Providers]] · [[Workflow Engine]] — AI systems
- [[Backend Architecture]] · [[Database Architecture]] · [[API Architecture]] · [[Frontend Architecture]] · [[Infrastructure]] — tech architecture
- [[Security Architecture]] · [[Authentication and Authorization]] · [[Privacy and Data Protection]] · [[Compliance and Governance]] — security & trust
- [[Design System]] — the UI standard every screen follows
- [[Design Backlog and UI Vision]] — the earlier long-term UI direction, now **partly superseded**. Its dark-interface visual rules and its Foundation Rule were withdrawn by owner decision on 2026-08-14; the active visual direction is recorded in [[STEP-26 Product Design System and Screen Blueprints]] and lands in [[Design System]] there. The note is retained for history and for the parts still current.
- Engineering Handbook Chapters 1–11 — binding build standards
- [[CLAUDE|CLAUDE.md]] — operating rules governing every step

## Current State

As of 2026-07-31, the project root is a git repository on branch `main` with the canonical skeleton (`apps/`, `packages/`, `infrastructure/`, `docs/`, `scripts/`, `.github/`) in place.

**Both applications now exist as skeletons.** `apps/web` is a Next.js 16.2.12 / React 19 / TypeScript-strict / Tailwind v4 skeleton with `/` and `/health` routes, building clean and serving zero client JavaScript (STEP-03). `apps/api` is a FastAPI 0.121.2 / Python 3.14.6 skeleton with the five layer directories in place and a `/health` endpoint served through a router→service path, clean under Ruff and mypy `strict` (STEP-04). Neither talks to the other yet, and neither has a database, auth or features. `packages/` and `infrastructure/` remain empty placeholders.

**Both apps now validate their configuration at startup and refuse to run without it** (STEP-05). `.env.example` templates are committed for both; real `.env` files are ignored. No secret exists in the repository yet — the first arrives with STEP-07. Conventions are documented in [[Environment and Secrets]], **approved by the project owner on 2026-07-31** as a Critical change; that owner approval gate is cleared and STEP-06 onward may proceed.

**A GitHub remote now exists** at `github.com/ruseduard321-prog/ProjectOne` (private), and all six commits are pushed. CI is committed and triggered: every push and pull request runs lint, type-check, tests and build for both apps. `apps/web` gained a Vitest runner and its first 7 tests.

**CI is live and green** — the project owner confirmed both jobs succeeded on 2026-07-31, closing STEP-06 (see [[STEP-06 Continuous Integration#Outcome]]). Note that confirming a CI run is an owner action for now: the build environment cannot observe workflow results on a private repository.

**A database exists** (STEP-07). A development Supabase project (PostgreSQL 17.6) is connected through the STEP-05 config system, Alembic applies and rolls back migrations via `scripts/migrate.{sh,ps1}`, and `/health` is now a **readiness** check reporting real database connectivity — 503 when it is unreachable. No application tables yet; the first schema is STEP-08.

**STEP-07 was approved by the project owner on 2026-08-01**, clearing its owner approval gate (Critical — database/infrastructure).

**The first application tables exist** (STEP-08): `users`, `workspaces` and `workspace_members`, created by migration `8a6f39b07c12`. They carry the standard column set every later table inherits — `id uuid`, `created_at`, `updated_at`, `deleted_at`, `version` — with `updated_at` and `version` maintained by a database trigger. Constraints enforce integrity at the database layer and were each verified by observing a rejection. Documented in [[Schema Overview]] and [[Table Conventions]].

**STEP-08 was approved by the project owner on 2026-08-01**, clearing its owner approval gate (Critical — database schema).

**Workspace isolation is now enforced at the database layer** (STEP-09). Migration `860a798d204b` enables *and forces* RLS on all three tables, adds eight per-command policies scoped `TO authenticated`, and installs `app_current_user_workspaces()` — a locked-down `SECURITY DEFINER` helper that exists because a policy on `workspace_members` cannot query `workspace_members` without recursing. Identity reaches the policies through `auth.uid()`, which returns NULL without a JWT claim, so every policy denies by default. The pattern every future tenant table copies is [[RLS Policy Pattern]].

17 isolation tests prove cross-tenant read, update and delete are all blocked, and **15 of them fail when the policies are removed** — verified, because an isolation test that passes with RLS off is testing nothing. CI gained a throwaway PostgreSQL service container to run them, plus a flag making a missing test database a hard failure rather than a silent skip.

**STEP-09 was approved by the project owner on 2026-08-01**, clearing its owner approval gate (Critical — security controls, multi-tenancy/RLS), with CI confirmed green.

**RLS now protects the application, not just the database** (STEP-10). The API authenticates requests against Supabase Auth, verifies `ES256` access tokens against the project's JWKS public key, and serves every request over a second connection as `projectone_api` — a role created by migration `d7b95c1f4e08` that does **not** carry `rolbypassrls`. Identity reaches the policies through `SET LOCAL ROLE authenticated` plus a transaction-scoped `request.jwt.claim.sub`, so `auth.uid()` resolves and the claim cannot outlive the request on a pooled connection.

Migration `c4f21a86b3de` narrowed table grants to `SELECT`/`INSERT`/`UPDATE` for `authenticated` and nothing for `anon`, and corrected the schema's default privileges so future tables inherit the same rather than Supabase's permissive `GRANT ALL`. `POST /auth/{sign-up,sign-in,sign-out,refresh}`, `GET /auth/me` and a minimal `GET /workspaces` exist; the suite grew from 25 tests to 58. Documented in [[Authentication Implementation]].

Two defects were found and fixed during validation, both reproduced against a live database before being resolved: a **pooled-connection claim leak** (a session-scoped claim survived its transaction and the next session read the previous user's workspace), and **Supabase's default privileges re-granting full DML on every future table**, which would have left the next tenant table open to `anon`. See [[STEP-10 Authentication Backend#Outcome]].

The inherited STEP-07 REST 401 turned out to be a request-shape problem, not a broken key — the `sb_secret_...` key must be sent in both the `apikey` header and `Authorization: Bearer`.

**MFA and OAuth were deliberately deferred** out of STEP-10, and remain unscheduled — see that step's Outcome for the reasoning.

**STEP-10 was approved by the project owner on 2026-08-01**, with CI confirmed green, clearing its owner approval gate (Critical — authentication, security controls, multi-tenancy).

**Roles are now enforced, in both layers** (STEP-11). Migration `9f4d2c7a1b83` makes the two UPDATE policies role-aware — a plain `member` could previously rename the workspace and rewrite anyone's role row exactly like its owner — and installs `app_current_user_workspaces_as(text[])`, the role-filtered sibling of STEP-09's helper. Above the database, `requires(<permission>)` gates a route declaratively, `AuthorizationService` makes the decision from a per-request membership lookup, and one exception handler maps refusals to **403** rather than conflating them with 401. The role model, the two-layer split and the invalidation window are [[Authorization Model]]; the structural basis for data export and erasure ships with it. The suite grew from 58 tests to 96.

Three defects were found during validation, each reproduced against a live database: **`migrations/env.py` discarded the test harness's database URL** (so a test run migrated whatever `DATABASE_URL` pointed at — invisible in CI, a live-database hazard on a developer machine), a **branched migration history**, and an **own-row `WITH CHECK` that rejected the very operation it was written for**. All three are fixed.

**STEP-11 was approved by the project owner on 2026-08-01**, with CI confirmed green, clearing its owner approval gate (Critical — authorization, security controls, multi-tenancy).

**Membership removal now works, governed by explicit rules** (STEP-11a — a step inserted by owner decision on 2026-08-01, since the fix was a Critical multi-tenancy change rather than an API convention). STEP-11 had found that soft-deleting a `workspace_members` row was impossible for *every* role including `owner`. Migration `b8e1d94c50a7` resolves it and encodes the owner's five rules: the last owner may never leave or be removed, removal is strictly ranked owner > admin > member, a member may only leave themselves, and an owner may transfer ownership before leaving.

Two mechanisms carry it. The `deleted_at` filter **moved out of the SELECT policy into the queries** — a policy answers "whose rows may this caller touch", which is a tenant question `deleted_at` has nothing to do with — and the last-owner rule became a **deferrable constraint trigger**, because it counts remaining owners and no RLS predicate can do that without recursing. Tenant isolation is provably unchanged: `app_current_user_workspaces()` still filters the caller's own membership, so a removed member still loses access immediately, and a test proves the widening stopped at the workspace boundary. The suite grew from 96 tests to 133.

**STEP-11a was approved by the project owner on 2026-08-01**, with CI confirmed green, clearing its owner approval gate (Critical — authorization, security controls, multi-tenancy/RLS).

**Every endpoint now shares one API contract** (STEP-12). Routes moved onto a `/api/v1` URL prefix — migrated, not duplicated, so the unversioned paths return 404 — with `/health` deliberately left unversioned as infrastructure. One error envelope (`{"detail", "request_id"}`) covers 401, 403, 409, 422, 404 and 500, and translation moved out of the routers entirely into a handler table in `app/core/errors.py`, finishing what STEP-11 started. Every request carries a correlation id, echoed in the `X-Request-ID` header and in every error body, and the auth endpoints are rate limited. The decisions and their reasoning are [[API Conventions]]; the suite grew from 133 tests to 160.

The rule that no credential reaches a log became **structural rather than conventional**: a redacting filter on the log handler strips bearer tokens, `Authorization` values, passwords and API keys from every record, including ones emitted by `httpx` and `uvicorn`. The reasoning is that "do not log the header" holds until someone debugging logs the headers, and that failure is silent and permanent.

Two defects were found by running the tests: **a fixture that silently disabled authentication** (overriding `get_tenant_connection` replaces `get_current_user` beneath it, so four rejection tests were passing against an app checking nothing), and **errors bypassing the envelope** when they never reached a handler — Starlette's 404 and the limiter's own 429. Both are fixed; see [[STEP-12 API Conventions and Middleware#Outcome]].

Two things [[API Architecture]] requires are explicitly **not** built yet and are recorded rather than forgotten: **audit logging** (request logging is not audit logging) and **idempotency keys** (nothing yet creates a resource from a client-supplied request). Both are named in STEP-13's inherited notes.

**STEP-12 was approved by the project owner on 2026-08-01**, with CI confirmed green, clearing its owner approval gate (Critical — public API contract, security controls). The in-process rate limiting and the deferral of audit logging to STEP-13 were approved alongside it.

**Every workspace and membership operation is now reachable over HTTP, and the consequential ones are audited** (STEP-13). Creation, member listing and addition, removal, departure, ownership transfer and the audit trail join the endpoints STEP-10 and STEP-11 built; the full contract is [[API Endpoints]]. Migration `a3c07d5e91f4` adds `audit_log` ([[Table - audit_log]]) — append-only, RLS-scoped to the workspace, with immutability resting on absent policies, absent grants (`TRUNCATE` especially, which RLS does not govern) and writes confined to the privileged path so a client cannot forge entries. It is exportable but **not** erasable, a documented [[CLAUDE|CLAUDE.md]] §16 retention exception that a workspace erasure discloses as `"audit_log": 0` rather than hiding. The suite grew from 160 tests to 191.

**The project owner made two decisions on 2026-08-01**, both asked before any code was written: members are added by existing `user_id` rather than by email (an email-keyed endpoint is an account-enumeration oracle unless every response is identical, and a full invitation flow is a larger scope), and audit logging lands in this step rather than a later one. **Inviting someone with no ProjectOne account remains unbuilt and unscheduled.**

**A defect in the plan itself was found by probing the database before designing.** The inherited notes recorded member invitation as "unsolved, needs the privileged path". That conflated two cases: the INSERT policy tests the *caller's* membership, so an existing member adding someone else is permitted over the ordinary tenant connection — verified against a live database. Only the bootstrap (a creator's own first membership row) is genuinely refused, and it is the sole operation using the privileged connection. Routing invitation through that path would have discarded RLS for an operation that never needed it. [[Authorization Model]] carried the incorrect claim and is corrected.

Three defects were found during validation: **a partial unique index does not prevent a duplicate live membership** (re-adding a removed member with a plain INSERT leaves one dead and one live row, passing the constraint while corrupting every count), **audit rows blocked test teardown** because `audit_log.workspace_id` is deliberately `RESTRICT`, and **a cluster-wide role grant left by the STEP-12 run** blocked the harness. All three are fixed; see [[STEP-13 Auth Users Workspaces Endpoints#Outcome]].

Two gaps were recorded here rather than forgotten, and **both are now closed by [[STEP-25a Foundation Remediation]]**: audit retention is bounded at a configurable 90 days (FA-07), and authentication events are recorded in [[Table - security_event_log]] (FA-06). **Idempotency keys** remain unbuilt, and `POST /workspaces` is now the first endpoint that could use them.

**STEP-13 carries an owner approval gate** (Critical — public API contract, authorization, multi-tenancy, database schema). It is `Done` and committed, but STEP-14 does not begin until the owner confirms it — including confirming the CI run, which this environment cannot observe on a private repository.

**The Design System now specifies values, not only principles** (2026-08-02). The project owner supplied v1 tokens — **explicitly initial values, not permanent branding** — with a binding architectural constraint: *all tokens are expected to change without requiring component rewrites*. [[Design System]] §3a–§6 now hold a two-layer token architecture (primitives → semantic tokens, components referencing **only** the latter), a 4px spacing scale, Inter with a 1.25 type scale, a slate/indigo palette targeting WCAG AA, and dark mode confirmed in scope for v1.

§3a is the load-bearing part: a component says `bg-accent`, never `bg-indigo-600`, so a rebrand is one edit to the semantic mapping rather than a change to every component that ever shipped. [[STEP-14 Design System Tokens]] implements that specification and does not re-decide it; its validation includes a **swap test** — reassign the accent, rebuild, confirm nothing in any component changed — so the constraint is demonstrated rather than asserted. This unblocks STEP-14, which no longer needs owner input before implementation.

**The design system exists as tokens, and the constraint behind it is proven rather than asserted** (STEP-14). `apps/web/src/app/globals.css` holds both layers: primitives sit **outside** Tailwind's `@theme` deliberately, because a primitive registered there becomes a utility class and hands components the `bg-neutral-900` escape hatch §3a forbids — verified by confirming the compiled CSS contains no primitive utility. `@theme inline` is what makes dark mode a pure remapping: utilities emit `var(--color-accent)` instead of a baked-in hex, so the theme changes at runtime with no `dark:` variant anywhere. The **swap test passed** — the accent was reassigned, rebuilt, and all five component files were byte-identical by `git hash-object` afterwards. Inter is self-hosted via `next/font`, confirmed loaded in a real browser rather than inferred from config.

**The contrast check found a defect in the specification, not the implementation.** Two dark-mode pairings failed AA — `--color-text-muted` on `--color-surface-raised` (4.04) and `--color-accent` on `--color-surface` (4.00) — because §6.3's original verification covered `--color-background` and `--color-surface` but never `--color-surface-raised`, a genuinely different surface. Extending the check to all three surfaces exposed a third failure the original set could not have caught (`--color-danger` at 3.89). The owner directed a minimal refinement: four dark-mode values moved one step within existing ramps, two primitives were added (`neutral-800`, `danger-400`), **no hue changed and no new semantic token was needed**. Verification now enumerates every foreground against every surface — 58 pairings, both themes, all passing — because a hand-picked list is what produced the gap. [[Design System]] is updated to v1.2.

The lesson worth carrying: **a pairing that is not checked is not passing, it is unknown.** The failures were latent in an approved specification and would have shipped into every dropdown and dialog had the token layer not been built before any screen consumed it — which is precisely why this step is sequenced ahead of STEP-15.

**The application shell exists and every screen now has somewhere to live** (STEP-15). `app/(app)/layout.tsx` is a route group, so it wraps every application screen without adding a segment to any URL; `/dashboard`, `/projects`, `/chat` and `/settings` are real routes with placeholder content that later steps fill rather than restructure. Nav destinations are exactly the sections with a scheduled build step — Analytics, Billing and Video Generation are specified in the Project Bible but have no step, and a nav item pointing at a route that does not exist is a dead end rather than a roadmap.

**The root `error.tsx` owed since [[STEP-03 Web App Skeleton]] is finally built**, because this is the first step where client code is legitimate — Next.js requires an error boundary to be a Client Component, which is precisely why STEP-03 could not deliver it. It renders an actionable message and never the stack trace or raw error message ([[CLAUDE|CLAUDE.md]] §24), surfacing Next.js's `digest` so a user report ties back to a server log. Client boundaries total two — the error boundary and the sidebar, which needs `usePathname` — and everything still prerenders static.

**Building the first skeleton found a missing token.** The loading state was written against `--color-surface-raised` and was invisible in light mode: that token is `#ffffff` against a `#f8fafc` canvas, **1.05**, measured in a browser rather than reasoned about. [[Design System]] §6.5 says the fix for a missing role is to name it, so `--color-skeleton` was added and recorded in §6.2 before use. That is twice in two steps that a surface token reused as a fill *on* that surface produced an invisible result — **a token naming a surface is not automatically safe as a fill on it.**

Authentication is deliberately **not** enforced by the shell. Session handling arrives with [[STEP-16 Sign Up and Sign In UI]]; gating routes before that contract exists would be a guess, and nothing inside the shell holds data yet.

**The stack is now connected end to end** (STEP-16). Sign up → sign in → shell → sign out works against a live backend, with the header identity coming from `GET /auth/me` — which is UI → API → RLS → database in one path. Tokens live in **httpOnly cookies written server-side**, never `localStorage`: a cookie script cannot read is a credential an XSS cannot walk away with, and verifying it meant checking that signed-in browser storage really was empty rather than trusting the design. Because the browser cannot read the token, every API call is server-side — which also sidesteps the API having no CORS middleware at all. The decision, the two-layer gate and the refresh behaviour are [[Web Session Handling]]. The suite grew from 7 tests to 34.

**Three defects were found by running it.** A `"use server"` file may export only async functions, so a constant in the actions module failed the build outright. A `redirect()` from the layout could not send a redirect status — it runs inside STEP-15's `loading.tsx` boundary, so Next.js had already flushed a 200 and could only finish with a meta-refresh; `src/proxy.ts` now returns a real 307 before rendering begins. And most consequentially, **clearing a dead cookie threw and stranded the user forever**: a layout that discovers a spent refresh token may not delete the cookie carrying it, and the attempt aborts the render along with the redirect that was about to fire, leaving an endless loading skeleton. A Route Handler at `/session/expired` now owns that deletion.

The lesson worth carrying: **the place that discovers a credential is dead is not always a place permitted to delete it** — and that failure mode traps the user rather than signing them out.

**Sign-out revokes the refresh token immediately, but an already-issued access token keeps working for up to an hour** — measured, not assumed, because access tokens are stateless JWTs verified locally against JWKS and revocation cannot reach them. That is inherited from STEP-10 rather than introduced here, but [[Authentication Implementation]] implied more than it delivered and now carries the measurement. Anti-enumeration proved stronger than required: registering an address that already exists is indistinguishable from registering a new one.

**One regression in an existing control is recorded rather than resolved.** With every call proxied through Next.js, the API's rate limiter keys on the web server's address, so it no longer limits per user and one user can lock out others — observed directly. It needs a trusted forwarded-client-address scheme before real traffic, and is out of STEP-16's scope.

**STEP-16 was approved by the project owner on 2026-08-03**, clearing its owner approval gate (Critical — authentication, security controls, session/token storage). The httpOnly cookie approach, server-side session handling, the Next.js proxy and the absence of `localStorage` were each confirmed.

**Two steps were inserted by owner decision on 2026-08-03**, both specified before any code was written and neither yet implemented:

- **[[STEP-16a Developer Session Inspector]]** — a development-only `/dev/session` page reporting authentication state, token expiries, proxy headers, rate limit identity and backend health. STEP-16's own security posture is what makes it necessary: cookies the browser cannot read are also cookies the developer cannot inspect. **The feature's entire risk is its exclusion**, so it requires two independent mechanisms — absence from the production build *and* a runtime 404 — each proven by observation rather than configuration review.
- **[[STEP-12a Trusted Proxy and Per-User Rate Limiting]]** — resolves the regression above. Authenticated requests key on the verified `user_id`; public requests key on a client address resolved **only** from allowlisted proxies, parsed right-to-left, failing closed. It is numbered `12a` because it amends [[STEP-12 API Conventions and Middleware]]'s contract, but it executes after STEP-16a. It carries **two gates**: an `Accepted` ADR on the trust boundary *before* implementation, and owner approval *after*.

**Both inserted steps were approved by the project owner on 2026-08-03**, who also set the execution order: **STEP-12a first, then STEP-16a, then STEP-17.** The security fix precedes the development aid because the regression is live; one consequence is that STEP-16a's rate limit identity panel will report the per-user scheme rather than documenting the broken one.

**The owner's remaining STEP-16 decision is now closed.** The one-hour post-sign-out access-token window is **accepted for Foundation** and the token lifetime is unchanged. Revisiting it would mean shortening the access-token lifetime, which trades a shorter revocation window against more refresh traffic — a decision available later, not a defect left open.

**Rate limiting now counts the right identity** (STEP-12a). [[ADR-002 Trusted Proxy and Client Address Resolution]] was `Accepted` on 2026-08-03 and implemented the same day. Authenticated requests key on `user:<user_id>` from the **validated** auth context — never a header, body field or unverified claim; public requests key on `ip:<client_address>`, resolved **only** from an allowlisted peer, walking `X-Forwarded-For` **right to left** discarding trusted hops. Never the leftmost entry: honest proxies append and a client may send the header itself, so the leftmost value is attacker-chosen, and taking it is the classic vulnerability here. Failure is **closed** — a malformed header or absent allowlist falls back to the peer address, never to no limit.

**Two mechanisms, and the reason is structural rather than stylistic.** ASGI middleware runs before FastAPI resolves dependencies, so the middleware limiter cannot know who is calling; public paths stay there, authenticated paths moved to `limit_by_user`, a route-level dependency. The two refusals are byte-identical in shape so a caller cannot tell which limiter refused them — a difference would reveal whether the endpoint considered them authenticated.

**The evidence is the negative controls, not the passing suite.** Removing the trust gate failed exactly the 4 spoofing tests; replacing the per-user key with a shared bucket failed exactly the 2 independent-bucket tests; removing a route's limit failed the wiring test. Each was restored and re-verified. `apps/api` grew from 74 tests to 113, `apps/web` from 34 to 45.

**One defect was found by writing the Outcome, not by running anything.** The first draft recorded that `limit_by_user` was applied to no production route — every test passing against a limiter that limited nothing. That does not satisfy a Definition of Done saying *"authenticated requests are limited per verified `user_id`"*. `POST /workspaces` (10/min) and `GET /{id}/export` (5/min) now carry limits on their own merits, and a test asserts the wiring through the route table.

**The limiter remains in-process and per-worker** — deliberately unchanged. This step fixed *what is counted*, not *where counts live*; a shared store is new infrastructure needing its own ADR ([[CLAUDE|CLAUDE.md]] §10, §28). Per-user keys make the approximation more visible: N workers permit N× each user's allowance. ADR-002 §Future Evolution documents the migration path and the two backend-unavailable operating modes — **Availability First** (fall back to the in-process limiter) and **Security First** (fail closed). **Foundation adopts Availability First**, on the reasoning that a cache outage taking down authentication for everyone is a larger blast radius than the risk it manages; the production decision is left open for the ADR that introduces the store, and a mixed posture is a legitimate outcome.

**A deployment obligation now binds every environment** ([[Infrastructure]]): every proxy in front of the API must be in `PROJECTONE_TRUSTED_PROXIES`, and every trusted proxy must strip or overwrite inbound `X-Forwarded-For` rather than appending. The API warns at startup when the allowlist is empty; it cannot warn when the allowlist is merely wrong.

**STEP-12a carries an owner approval gate** (Critical — security controls, public API contract, infrastructure configuration). Per the owner's instruction on 2026-08-03, intermediate approvals are deferred: one consolidated review follows STEP-17.

**The running session is inspectable in development, and unreachable in production** (STEP-16a). `/dev/session` reports authentication status, token expiries, session id, cookie presence, proxy headers, rate limit identity and API/database health — showing **no** token, cookie or key value, not even truncated, and mutating nothing. `/health` was reused rather than adding a diagnostics endpoint: new production surface for a development page is a bad trade.

**The step's central defect was found by running it, not reviewing it.** `notFound()` at the top of the page returned **`HTTP 200` with the not-found body inside it** — the root `loading.tsx` Suspense boundary has already flushed a 200 by the time a page body runs, so the page can change what renders but not the status. **This is STEP-16's `redirect()` failure one level up**, and the fix is the same: enforcement moved to `src/proxy.ts`, which runs before rendering. The lesson has now appeared twice — **anything that must control an HTTP status belongs before the render, not inside it.**

**Both exclusion mechanisms are real and independent.** An intermediate state satisfied only the runtime check, with the route still appearing as `ƒ /dev/session` in the build output; that gap was closed rather than accepted. Development-only routes are now named `page.dev.tsx`, and `next.config.ts` registers that extension **only** in a non-production build — so a production build never compiles the file at all, confirmed absent from the build output and manifests. The proxy independently 404s the whole `/dev/*` namespace (never 403, which would confirm the route exists). One depends on `NODE_ENV` at build time, the other at run time, and a test asserts the two decisions agree across every environment combination.

**The no-secrets guarantee was proven by grep, not by review.** Cookies carrying marked values were planted, the rendered HTML fetched, and every value — including each individual JWT segment, since a partial leak is still a leak — confirmed absent, while the derived facts were confirmed present so the scan was not passing against an error page. No `Set-Cookie` on any visit. `apps/web` grew from 45 tests to 74.

**The development database was three migrations behind the code, and has been reconciled** (2026-08-03, at owner instruction). It sat at `d7b95c1f4e08` while the code's head was `a3c07d5e91f4`. Four explanations were tested rather than assumed, and three ruled out: not a different database (all settings resolve to the same project), not misconfiguration, **not a reset** (it held `step16.confirmed@gmail.com` from STEP-16's validation), and **not a rollback** (zero artifacts from any unapplied migration — a rollback leaves partial ones). It was simply behind, most likely because those migrations were validated against the *test* database after STEP-11 fixed `migrations/env.py` to stop test runs touching `DATABASE_URL`.

The three migrations were applied and the result verified: revision at head, `audit_log` present with RLS **enabled and forced**, all four helper functions present, the last-owner trigger present, 9 policies across four tables, RLS forced on every tenant table, and `projectone_api` still `NOBYPASSRLS`/`NOINHERIT`. All probe rows were removed and the database confirmed back to its prior contents by query.

**The credential mismatch is fixed by automation, not by a better-documented manual step.** The role is created without a password by design (`d7b95c1f4e08`), so the pairing between it and `REQUEST_DATABASE_URL` was **two independent writes with nothing linking them** — undetectable until the first request touching a tenant table, and it cost two sessions. Proven precisely rather than guessed: the stored SCRAM-SHA-256 verifier was re-derived against every plausible variant of the `.env` value (all failed), with the derivation first validated against a control role. `scripts/sync-request-role-credential.py` now generates the password, applies it, **proves it by connecting as that role**, and only then rewrites `.env` — no human sees or types the value. `--check` verifies agreement without writing. [[DOC-02 Validate the Request-Path Credential at Startup]] proposes catching it at boot too.

**The connection architecture moved to the Supabase session pooler**, by owner decision on 2026-08-03, after the direct host proved unreachable from **both** environments. `db.<project-ref>.supabase.co` publishes an AAAA record and no A record — Supabase serves direct connections over IPv6 only, IPv4 being a paid add-on. Both URLs now use `aws-0-eu-central-1.pooler.supabase.com:5432`. Three details are mandatory and were established by testing: the username carries a `<role>.<project-ref>` suffix (bare is rejected), the port is 5432 and never 6543 (transaction mode breaks psycopg's prepared statements), and the region cannot be inferred from DNS since every region hostname resolves. **The pooler was not assumed to preserve tenant isolation** — every property was re-verified over it. The application code needed no change: `RequestSessionFactory` already used `SET LOCAL ROLE` and transaction-scoped `set_config`, chosen by STEP-10 for a different reason, which is exactly what pooling requires. See [[Environment Setup#The Connection Architecture]].

**Cross-tenant isolation is now verified behaviourally, over the request-path connection, at head.** Migration `f1a4c8d29b57` is applied. Two tenants were seeded and isolation asserted as `projectone_api` → `SET LOCAL ROLE authenticated`: the other tenant's credential is invisible, its ciphertext unreadable, an update affects **0 rows**, and `DELETE` is refused. A **negative control** disabled RLS, observed the breach directly, and restored it — so the assertions are not passing against an empty table. All probe rows removed, verified by query. The pytest suite `test_provider_credential_isolation.py` (18 tests) creates and destroys rows, so it belongs in CI against a throwaway container, never the development project. It skips on a machine with no `PROJECTONE_TEST_DATABASE_URL` and **runs in CI**, where `PROJECTONE_REQUIRE_DATABASE_TESTS` makes a missing database a hard failure rather than a silent skip — an earlier revision of this note described it as "skipped by design", which understated that and is corrected here.

**The AI Router is built, provider-agnostic, and reaches no user** (STEP-17). Two providers behind one ABC, proven by a single parametrized contract suite run against both rather than two bespoke suites. Selection follows [[AI Providers]]' documented order — preference → capability → availability → cost — and returns its reasoning as data rather than only logging it. **Two hard ceilings multiply to bound one request at six upstream calls**; both are refused below 1 at construction, and there is no "retry until success" branch to find. BYOK keys are RLS-protected tenant data, encrypted with AES-256-GCM under an environment key, with plaintext existing in exactly two places. Full detail in [[AI Router Implementation]].

**Spend is now bounded before it is incurred, and the STEP-17 gate is open** (STEP-18). Every CLAUDE.md §15a control exists and has been observed *tripping*: per-workspace and per-workflow ceilings, a spend circuit breaker distinct from the availability one, recursion and wall-clock and token caps per run, near-real-time anomaly detection with teeth, and a deploy-free emergency shutdown at three scopes. Migration `b2e6f0a71c94` adds three tables. Full reasoning in [[AI Cost Governance]].

**The central problem was that a budget must be enforced *before* a call whose cost is unknowable *until after* it.** Resolved as **reserve → call → settle**: a pessimistic worst case reserved atomically, then adjusted to the real figure. The reservation is a **compare-and-increment in one statement**, so PostgreSQL's row lock settles concurrency — the read-then-write alternative is a textbook TOCTOU race where two workers both read a total under the ceiling and both proceed. An in-process counter was refused outright: N workers each permitting the full budget is N× the ceiling, which for money is a defect rather than an approximation.

**The evidence is the negative controls and a live database, not the passing suite.** Each control's absence is reproduced and the breach observed. Against the development database, 34 checks passed including the two properties a fake structurally cannot demonstrate: **twenty concurrent threads reserving $1 against a $10 ceiling granted exactly ten**, landing on `10.000000` precisely; and cross-tenant isolation with RLS disabled mid-test to observe the breach and restored afterwards. All probe rows removed and the database confirmed back to its prior contents.

**Three defects were found by running it rather than reviewing it.** One governed call opened **six database connections** against a session pooler limited to 15 — two concurrent calls would exhaust it and the third would fail to connect, turning a cost control into an availability failure; a session collapses it to **one**, measured rather than assumed. A governance refusal had **no HTTP handler**, so a deliberate, correct control would have reached the client as a 500 — now 402 for a ceiling, 503 for a shutdown. And **`provider_credentials` was never registered for erasure** (a STEP-17 gap), so a workspace erasure silently left encrypted provider keys behind — fixed alongside registering this step's own store, since shipping one while leaving the sibling broken would knowingly ship a [[CLAUDE|CLAUDE.md]] §16 violation.

**One exposure is recorded rather than glossed:** an owner can currently zero their own `spent_usd`, because PostgreSQL policies are per-row and the UPDATE policy must exist for configuration. The immutable ledger — not that counter — is what a billing reconciliation reads, and the test documents the exposure honestly instead of asserting a protection that does not exist. Closing it is a column-level grant belonging to STEP-19.

**STEP-18 was approved by the project owner on 2026-08-03**, clearing its owner approval gate (Critical — AI architecture, database schema, security controls, multi-tenancy). STEP-19 may begin.

**A cross-tenant key leak was caught during implementation, in the router's own first draft.** `AIRouter` held the request-scoped key resolver as instance state while being constructed once and shared across requests — so two concurrent requests would race and the loser would resolve **another workspace's** credential. Same class of defect as the pooled-connection claim leak STEP-10 reproduced, and now prevented structurally: the resolver is a parameter, so there is no attribute to race on.

**CI is green again, and the test harness had three independent defects** (2026-08-04). It had been red since STEP-14's run, and none of the causes were in application behaviour that ships — but two were real bugs in code that ships, not just in tests.

- **Test teardown did not clear every workspace dependant.** Five tables reference `workspaces` with `ON DELETE RESTRICT`; teardown cleared two. STEP-17's `provider_credentials` and STEP-18's three tables were all unregistered, so `DELETE FROM workspaces` failed with `ForeignKeyViolation`. The list is now a named constant with a test asserting it against the catalog in both directions, so the next unregistered table fails by name instead of surfacing in whichever database test happened to run last. The obligation is written into [[Table Conventions]].
- **`configure_logging()` cleared every root handler**, including the one `caplog` installs, so building an app inside a test destroyed the fixture's ability to see any record. It now removes only its own named handler — still idempotent, verified across 21 calls.
- **Alembic's `fileConfig()` disabled every application logger.** `disable_existing_loggers` defaults to `True`, and because the session-scoped fixture runs migrations **in-process**, every `app.*` logger was silenced from the first database test onward. This is why two logging assertions passed locally and failed only in CI: locally the database tests skip, so it never ran.

The lesson worth carrying: **all three were invisible locally and only reachable in CI**, and the failure each produced pointed somewhere other than its cause. Diagnosing them needed the CI log, which this repository does not serve without admin rights — so pytest failures are now emitted as check-run annotations, which are readable by anyone who can see the run. That plumbing took three attempts of its own, the last because a workflow command is ignored unless it starts at the beginning of a line.

**The AI layer is reachable by a real user, and no route can return a key** (STEP-19). Nine endpoints and four settings screens — Profile, Workspace, AI Providers, AI Spend — each with a loading skeleton, an empty state and a route-scoped error boundary that keeps the shell rather than replacing the page. Members read; owners and admins write, enforced by a `requires(...)` dependency *and* an RLS policy, because the policy makes the write impossible while the dependency makes the answer honest. Full contract in [[API Endpoints#AI settings — providers, budgets and spend]].

**"Show my key" is not a feature that was declined — it is one the backend structurally cannot serve.** `key_for` is the only method producing plaintext, no route calls it, and the response type has no field capable of holding a key. Rotation is therefore *replace, never reveal*. Proven by grep against real response bodies including a 20-character prefix scan, not by reading the serializer.

**STEP-18's `spent_usd` exposure is closed by the mechanism RLS structurally cannot provide.** A PostgreSQL policy is per-row and cannot restrict columns; a **column-level grant** can, and is evaluated before any policy runs. Migration `c9d3b71e08af` revokes the table-wide `UPDATE` on `ai_budgets` in favour of `UPDATE (limit_usd, period_interval)`. Three independent gates now stand on that value — `extra="forbid"` makes sending it a 422 rather than a silent discard, the handler never passes it on, and the grant refuses it regardless of what a future route accepts. A **negative control** re-granted the column, reproduced the breach, and revoked it again.

**Two defects were found by running it, and the first is a repeat.** Revoking a provider key was **impossible for every role including `owner`**: `provider_credentials_select_same_workspace` filtered `deleted_at IS NULL`, and revocation is an `UPDATE` that *sets* it — so PostgreSQL refused the write via the policy governing *reading*, with an error naming row-level security that points at the UPDATE policy where nothing is wrong. Established by narrowing against a live database (updating `last_four` succeeded, updating `deleted_at` did not, and dropping the filter fixed it). **This is [[STEP-11a Membership Removal Policy]]'s defect exactly, on a second table**, and it recurred because [[RLS Policy Pattern]] recorded that fix as "the only exception" while still telling every new table to filter `deleted_at` in each `USING` clause. That note now states the general rule and flags the four tables still carrying the latent version (`ai_budgets`, `ai_shutdown_switches`, `users`, `workspaces`). Worse than a broken button: **`ProviderCredentialStore.erase` had been silently failing since STEP-17**, so a workspace erasure left provider keys behind — a [[CLAUDE|CLAUDE.md]] §16 obligation broken with no test covering it. The second defect: **raising a ceiling silently reset the billing period**, because `upsert_budget` collapsed an unstated interval to a 30-day default and wrote it.

**The pytest harness cannot reach the development database** — `conftest.request_database_url` rebuilds the DSN with a bare `projectone_api` username and the Supabase session pooler requires the `<role>.<project-ref>` suffix; a scratch database on the same instance hits the same wall. The 25 database-backed tests therefore first execute in CI. Rather than leave that unverified, the same assertions were driven in-process against the live database through a real `TestClient`: **37 HTTP-layer checks**, plus 11 on the grant and audit constraint and 6 on the inverted STEP-18 assertions — including a negative control that neutered the API's authorization gate and confirmed **RLS still refused the write independently**. Every probe removed its rows and confirmed the database back to its prior contents. `apps/api` grew to 325 offline tests, `apps/web` from 74 to 97.

**A STEP-18 test asserted the old exposure and would have failed in CI.** It is inverted rather than deleted, with its docstring recording what changed.

**The credential mismatch recurred and was fixed by the script built for it.** `REQUEST_DATABASE_URL` had drifted from the role's password again; `scripts/sync-request-role-credential.py` regenerated it, proved it by connecting, and confirmed `rolbypassrls = False`.

**Workspace selection is a stated limitation, not a silent one.** The web application had no workspace concept at all before this step; it now resolves the caller's *first* workspace server-side (`GET /workspaces` orders by name, so "first" is stable) and **says so on screen** when the user belongs to others. A switcher is a real feature belonging with [[STEP-20 Projects Schema and Lifecycle]] onward, not scope for a settings step.

**STEP-19 carries an owner approval gate** (Critical — public API contract, security controls, multi-tenancy, database schema, and the first user-facing AI path). It is `Done` and committed, but STEP-20 does not begin until the owner confirms it — including confirming the CI run, which this environment cannot observe on a private repository.

**The first content tables exist, and a project's lifecycle is enforced in one place** (STEP-20). Migration `e5a91c34d7f2` creates `projects` and `assets` with RLS **enabled and forced**, per-command policies routing through `app_current_user_workspaces()`, explicit grants (no `DELETE`, no `TRUNCATE`, nothing to `anon`), partial indexes and `touch_row` triggers. `ProjectRepository` reaches both over the tenant connection; `ProjectService` owns the state machine so it holds for the non-HTTP callers later phases bring. **No HTTP routes were built** — the step's Tasks named none, and [[STEP-21 Projects UI]] now owns both the endpoints and the UI, which is why it was expanded to `full` detail with that inheritance stated.

**The lifecycle gap was a decision, not an inference.** [[Projects]] gives the sequence Idea → … → Archive and never says which transitions are legal, so the question went to the project owner rather than being guessed ([[CLAUDE|CLAUDE.md]] §34). Decided on 2026-08-08: **forward one step, plus the Review → Editing loop, plus Archive from anywhere, terminal.** Recorded in [[Project Lifecycle]]. Two smaller decisions landed alongside it: `assets.project_id` is `NOT NULL`, and this step ships schema and service only.

**The transition map is derived from three rules rather than written out**, and the tests invert that — the specification is written as data and asserted against the derivation across **all 81 ordered pairs, in both directions**. Asserting the legal moves proves the map has entries; asserting every pair proves it has no *extra* ones, which is what a state machine exists for. A permissive bug passes every "the legal move works" test ever written.

**The denormalized `workspace_id` on `assets` needed a second mechanism, and this is the step's most interesting design.** Storing it buys a policy identical in shape to every other tenant table's, instead of one joining through `projects` — but it opens a hole **RLS structurally cannot see**: an INSERT naming the caller's *own* workspace satisfies the policy while pointing `project_id` at another tenant's project. A composite foreign key to `projects (id, workspace_id)` refuses it, failing with `ForeignKeyViolation` rather than an RLS error, which is exactly the point.

**The twice-paid `deleted_at` defect did not recur.** Both tables are soft-deleted and shipped **without** the filter in their SELECT policies — the first time that rule has been followed at creation rather than paid for in a later step. Both stores were registered in `REGISTERED_STORES` and both tables in `_WORKSPACE_DEPENDANTS` in the same change, rather than in the step that discovers the omission.

**No defect was found in the implementation, and the evidence is a live database plus a negative control.** The pytest harness still cannot reach the development database (STEP-19's unfixed username/pooler defect) and this machine has no local PostgreSQL or Docker, so the 21 database-backed tests **first execute in CI**. The same properties were therefore driven in-process over the real `RequestSessionFactory`: **43 checks passed**, including the soft delete succeeding through the service, cross-tenant read/update/insert/delete each refused, `WITH CHECK` blocking a workspace move, an illegal transition refused *and writing nothing*, all nine statuses accepted and a tenth refused, both stores exporting and erasing non-zero counts, and **RLS disabled mid-test to observe the breach directly** before restoring it. The migration was applied, **downgraded and re-applied** to verify the rollback path. `apps/api` grew from 325 tests to **343**; `apps/web` is untouched at 97.

**CI found the one defect the local validation structurally could not.** The first run was red on a single existing test: `test_an_owner_is_allowed_the_same_action` asserted the workspace-erasure response against a **hardcoded literal of every registered store**, and registering `ProjectStore` and `AssetStore` turned that literal stale — the behaviour was correct, the expectation was not. All 35 of the step's own tests passed. It was invisible locally because it is database-backed (so it skips here) and because the live probe exercised the stores directly rather than through `DELETE /workspaces/{id}/data`. The fix **derives** the expected key set from `REGISTERED_STORES` rather than restating it, which makes the assertion stronger: it still catches a store that stops being registered (verified by simulating each omission), now also catches an unregistered extra key, and asserts a per-store count for all six stores instead of the four the literal named. The lesson worth carrying: **an exact-match assertion over a registry is a test every future registration breaks** — derive the expectation, and the property survives while the stale-literal failure mode does not.

**One probe run crashed before its cleanup**, leaving 11 projects, 1 asset and 2 seeded tenants in the development database. Found immediately, removed by a marker-keyed cleanup script, and both tables verified empty. Recorded rather than omitted — a validation script that leaves state behind is a defect in the validation even when the code under test is correct.

**[[Schema Overview]] was two migrations out of date** (`c9d3b71e08af` and `d1f70a4c62be`, both from STEP-19, absent from a table claiming to be the full history) and is corrected. One stale line in it — *"Roles have no meaning yet"*, untrue since STEP-11 — is left as found and flagged rather than fixed silently ([[CLAUDE|CLAUDE.md]] §29).

**STEP-20 carries an owner approval gate** (Critical — database schema, multi-tenancy/RLS). It is `Done` and committed, but STEP-21 does not begin until the owner confirms it — including confirming the CI run, which this environment cannot observe on a private repository.

**[[STEP-21 Projects UI]] made projects reachable end to end** — nine routes, six Server Actions, three screens, 50 new tests. A real user creates a project, moves it through the lifecycle, attaches assets and deletes it, and no route can return another tenant's work. [[STEP-20 Projects Schema and Lifecycle]] deliberately built no HTTP layer, so `/api/v1/workspaces/{id}/projects` is this step's work rather than inherited.

**The load-bearing decision is that `legal_transitions` is a response field.** Every project response carries exactly the states that project can move to next, derived server-side from `legal_transitions_from`. **The frontend therefore holds no transition map at all** — a Vitest case scans `lib/projects.ts`'s exports and fails if any of them maps a status to a *collection* of statuses, which is the shape a second state machine would take. The consequence: a change to the lifecycle rules reaches every client with no frontend deploy, and a screen structurally cannot offer a move the server would refuse. This is the outcome the step note demanded, and it is asserted rather than intended.

**Two refusals were kept distinct, deliberately.** A status outside the nine-state vocabulary is a **422** (refused by the schema before any service code runs); a valid status the machine will not accept from here is a **409**. Collapsing them would send a client debugging a typo through a lifecycle diagram. A third asymmetry is now recorded in [[API Conventions]] as a general rule: a **workspace** id answers 403 whether the caller is a non-member or under-privileged, while a **project** id inside a workspace they do belong to answers 404 — one answer per question, regardless of cause. `test_a_project_id_is_not_an_existence_oracle` asserts a hidden project and an invented id are indistinguishable in status *and* body.

**One genuine defect was found, and only a live database could have found it.** `AssetKind` was written as bounded free text on the reasoning that asset kinds were unsettled — but `ck_assets_kind_valid` permits exactly `document`, `image`, `video`, `audio`. So the API accepted `kind: "script"`, validation passed, and PostgreSQL raised `CheckViolation`: **a client's malformed request reported as a 500**, with a constraint name in the log instead of a usable message. Fixed by typing it as a `StrEnum` mirroring the constraint, propagating a closed union to the frontend, and rendering a `<select>` rather than a text input — an interface offering a value the database refuses teaches the user to guess. Three tests now guard it, one of which reads `pg_constraint` and compares in both directions. The generalizable rule is recorded in [[Table - assets]]: **wherever the database constrains a value to a set, the outermost schema enumerates that same set** — a constraint the edge does not know about is a 500 waiting for its first user.

**Validation was 68/68 against the live development database**, driving the real routes in-process through `TestClient`, with every seeded row removed afterwards and verified to zero across all four tables. The 34 database-backed API tests still **skip locally** (STEP-19's unfixed pooler mismatch, no local PostgreSQL), which is precisely why the probe exists — CI would otherwise be the first place they ran, which is what made STEP-20 go red. `apps/api` grew from 553 collected tests to 587; `apps/web` from 97 to 113.

**Four limitations are stated rather than discovered.** No workspace switcher (inherited from STEP-19, and now more pressing because it bounds a user's actual work rather than only their settings); no asset upload (`storage_path` is null on everything these routes create — a storage backend is an ADR, and the step adding one owes it a deletion path); no idempotency keys (a retried creation makes a second project — bounded, but it should be one decision taken once across the API); and `GET /projects` is unpaginated, now named in [[API Endpoints]] as **where the pagination convention should be settled**, since [[Workflow Engine]] will let a workspace create projects programmatically.

**No project-specific permission was added**, deliberately. Every live member may create, edit, transition and delete any project in their workspace — unlike AI settings, projects are the workspace's shared work. A finer model's first question is "may I delete someone else's project?", which [[Projects]] does not answer, so it is a decision to raise rather than a detail to invent.

**STEP-21 carries an owner approval gate** (Critical — public API contract, multi-tenancy). It is `Done` and committed, but STEP-22 does not begin until the owner confirms it, including confirming the CI run.

**[[STEP-22 Minimum Workflow Engine]] gave ProjectOne its first automated execution** — two tables, six routes, an engine, one real AI agent, and 79 new tests. A workflow runs end to end through its seven phases, persists after every step, resumes correctly, refuses to execute a gated step without approval, and fails loudly on a ceiling. It is also the first step where **AI spend can occur without a human watching each call**, which is why the approval gate is the centre of it rather than a checklist at the end.

**The approval default is `True`, and that is the load-bearing decision.** `WorkflowStep.requires_approval` defaults to requiring approval, so a step author who does not consider the question gets the safe behaviour; overriding it to `False` is an assertion that the step is read-only or trivially reversible, and owes the reasoning in its docstring — the documented exemption [[CLAUDE|CLAUDE.md]] §15 requires. The planning agent *inherits* the default rather than overriding it, which is itself the decision: it spends money. Approval is gated to **owner/admin** (`UPDATE_WORKSPACE`, the project owner's decision on 2026-08-08) because a gated step is by definition one that spends money or acts externally — the same class of consequence guarding AI keys and budgets. **No new permission was added.** Two related refusals hold: **one approval covers one step**, and **resuming is not approving** (409) — otherwise anyone able to restart a run, including an automated retry, could bypass the human the gate exists for.

**Three defects were found before commit, all by the tests, and the most important one only by running the real workflow against a real database.** Step outputs were held in memory and *documented as a harmless limitation*, on the reasoning that a resumed run re-executes its earlier steps. **It does not** — a completed step is never re-run — so the planning agent resumed after approval, could not see the validation step's result, and failed the run. Every engine unit test passed, because their steps ignore their inputs. Fixed by persisting `workflow_step_runs.output` as `jsonb`; the guarding test was **verified to fail when the fix is reverted**. The other two: `resume` refused a `failed` run, which is the main thing anyone resumes; and a definition that lost steps while a run was paused reported the **truncated run as `completed`**, because `range(n, n)` is empty and execution fell through to the completion path. A fourth surfaced in the same probe — a cross-tenant `project_id` was correctly refused by the composite foreign key but reached the client as an **unhandled 500**, now translated to the same 404 any unreachable project gives.

**A failed run is a 201, not a 500**, and this is now generalized in [[API Conventions]]: an error status describes the *request*, while a resource's own state describes the outcome. The run was created, executed and recorded why it stopped — reporting that as a server error would tell the client its call did not happen when it did, and would lose the run id they need to investigate.

**An action gate is not an RLS policy**, recorded in [[RLS Policy Pattern]] as a general rule. Approval is enforced at the route rather than by a role-scoped policy, because a policy would make a member's approval match zero rows and *return success* — the silent no-op an honest 403 exists to replace.

**Validation was 60/60 against the live development database**, driving the real routes in-process, with every seeded row removed and verified to zero across six tables. The migration was applied, **downgraded and re-applied twice** (the `output` column was added after the first probe). `apps/api` grew from 587 collected tests to 666; `apps/web` is untouched at 113, since this step is backend-only by design.

**The teardown list stopped being alphabetical.** `workflow_runs` references `projects` but sorts after it, so `_WORKSPACE_DEPENDANTS` is now explicitly dependency-ordered — [[STEP-20 Projects Schema and Lifecycle]] had recorded the previous alphabetical ordering as *luck rather than design*, and this is where that luck ran out. [[Table Conventions]] now carries the dependency graph.

**Five limitations are stated rather than discovered:** execution is synchronous on the request thread (bounded by the 300s wall-clock ceiling — but the persistence model is already the one a queue would need, so moving it later changes one call site); no branching, scheduling or parallelism; no UI, so runs are reachable over HTTP only; one workflow and one agent, since the interface is the deliverable; and a resumed run re-executes an interrupted step, making step execution at-least-once — safe for every current step, but a future step with an external side effect needs its own idempotency.

**STEP-22 carried an owner approval gate** (Critical — AI/agent architecture, database schema, multi-tenancy, public API contract). The owner **approved it on 2026-08-11**, including its validated implementation and green CI, and authorized STEP-23 to proceed. The gate is closed.

**STEP-23 carried its own owner approval gate**, for the same categories plus a public API contract. The owner **approved it on 2026-08-14**, and the gate is closed. Required CI is green on `6f30b62` (all three jobs, including the database-backed suite), and the manual browser checklist is complete against the shared development database — including items 7a and 7b, re-run against a genuine forced provider outage. Test data has been removed; the AI spend audit trail was kept deliberately.

**The Pull Request remains open**: the owner merges, not Claude. `Done` records that the work is finished and approved, not that it has reached `main`.

**Five defects were found after the first green pipeline** — three by manual browser testing, two by review — and every one lived in a failure path no test was asserting against: a soft delete that could rewrite message content; a provider failure that rolled back the question with it; a failed turn that was retryable in the database and invisible on screen; a question answerable through the wrong conversation, charged and then stranded; and a release block widened so far it would have paid twice for one answer. The pattern is recorded in the step note because it outlives the step: **green CI proves the assertions that were written, and says nothing about the ones that were not.**

**A follow-up ADR is required before the next AI feature** covering provider-side idempotency, stale-claim reconciliation, lease policy and crash-window handling. STEP-23 leaves a turn stranded after a provider charge visibly stuck rather than silently retried; closing that window properly constrains every future AI call, so it is an ADR before it is a step.

**A long-term UI vision now exists, and it changes nothing in this plan** (2026-08-03). The project owner supplied [[Design Backlog and UI Vision]] — a premium-AI-OS design direction plus a Dashboard concept mockup. It is filed as **informational only** by explicit owner instruction: **not a step, not a roadmap change, not an architecture change, and overriding no engineering document.** No step was added, renumbered or rescheduled, and the [[Roadmap]] is untouched.

> [!note] Superseded on 2026-08-14
> The paragraph above records the position as it stood on 2026-08-03 and is kept as history. Design work is no longer deferred and no longer informational: the owner replaced the visual direction (warm ivory canvas, matte-black navigation, vermilion accent, editorial typography — explicitly *not* the earlier dark/blue/KPI-card direction) and scheduled it as [[STEP-26 Product Design System and Screen Blueprints]] and [[STEP-27 Product-wide UI Rebuild]], **before** any release consideration rather than after.

Its operating effect on STEP-19 through STEP-24 was deliberately narrow: **reference only, and do not redesign a shipped page because of it.** Screens were built against [[Design System]], which won wherever the two differed, and UI improvements noticed along the way were *collected* rather than acted on. The underlying reasoning still holds and is why the redesign is one pass rather than screen-by-screen: polishing screens while the surfaces beneath them are still being built means polishing twice, and consistency is only achievable across a complete set of screens.

What changed on 2026-08-14 is *when* that pass happens and *what it looks like* — before release consideration rather than after it, as [[STEP-26 Product Design System and Screen Blueprints]] and [[STEP-27 Product-wide UI Rebuild]], against a new visual direction that replaces the dark/KPI-card one.

**[[DOC-01 Align ADR Template with CLAUDE.md]] was raised** on 2026-08-03: [[ADR Template]]'s status vocabulary diverges from [[CLAUDE|CLAUDE.md]] §7, missing `Review` and — more consequentially — `Rejected`, the state that keeps a rejected decision on record. It is a documentation task rather than a Build Plan step, and lives in `09 Development/` accordingly.

**Explicitly not addressed by STEP-12a: the limiter remains in-process and per-worker.** That approximation was stated deliberately in STEP-12 and a shared store is a new infrastructure dependency requiring its own ADR ([[CLAUDE|CLAUDE.md]] §10, §28). STEP-12a fixes *what is counted*, not *where counts live* — per-user keys make the approximation more visible, since N workers permit N times the per-user allowance.

The vault, Claude OS and AI operating capabilities are built and validated ([[Environment Setup]], [[AI Index]]).

Every Project Bible note is still `status: draft` at v0.1 — the *specification* is transcribed, not accepted. Treat drafts as the best current source of truth and flag genuine ambiguity per [[CLAUDE|CLAUDE.md]] §33 rather than resolving it silently mid-step.

[[ADR-001 Technology Stack]] is the first and only ADR, written by STEP-02 and `Accepted` by the project owner on 2026-07-31. Its owner approval gate is cleared, so the stack is settled and STEP-03 onward may proceed ([[CLAUDE|CLAUDE.md]] §7).

**Foundation's build sequence is complete.** [[STEP-24 Dashboard]] was approved by the project owner on 2026-08-15, closing STEP-01 through STEP-24 plus the four inserted steps. The application has a dashboard, projects, AI chat, settings, authentication, a workflow engine and AI spend governance, all against a live API.

Two requirements were **deferred, not dropped**: the loading skeleton's reflow behaviour and [[Dashboard]]'s timed 30-second criterion. Both judge a visual design that [[STEP-27 Product-wide UI Rebuild]] replaces, so they are inherited as mandatory gates by [[STEP-26 Product Design System and Screen Blueprints]] and [[STEP-27 Product-wide UI Rebuild]] rather than answered against a layout that is about to change. Foundation shipped the functional product; the visual verdict belongs to the steps that own the design.

A second finding is carried forward: the **root error boundary's retry does not retry**. STEP-24 found the defect, fixed the four route boundaries it owns, and left `app/error.tsx` as another step's code — it is recorded as a finding for [[STEP-25 Foundation Audit and Internal Readiness]].

**The remaining plan was restructured by owner decision on 2026-08-14.** STEP-24 was in progress; everything after it changed shape. `STEP-25 Launch Readiness Criteria` was reworked into [[STEP-25 Foundation Audit and Internal Readiness]] — an audit of what Foundation actually built, rather than a definition of release criteria. Three steps follow it: [[STEP-26 Product Design System and Screen Blueprints]], [[STEP-27 Product-wide UI Rebuild]] and [[STEP-28 Full Product Verification Polish and Hardening]].

The substantive change is that **public release left the plan.** `STEP-26 First Public Release` is no longer a numbered step; its material is preserved unnumbered and non-binding as [[Public Release Draft - Unscheduled]], and a release step will be created later using the next available number, once the owner decides the product is ready. Three prior positions are superseded and recorded as such rather than deleted: that Foundation ended at STEP-26, that UI polish would follow the public release, and the dark/blue/KPI-card visual direction.

Adding and removing steps is a plan change rather than an execution detail ([[Execution Protocol#Future Step Synchronization]]), so it was made by explicit owner instruction and not by a session restructuring the plan on its own initiative.

**An outage was being reported as a signed-out session** (STEP-16b — a step inserted by owner decision on 2026-08-14, since the fix changes shared authentication behaviour rather than any dashboard surface). STEP-24's manual checklist stopped the API to exercise the dashboard's error boundary; the boundary never rendered, the browser landed on `/sign-in`, and the session cookies were gone.

The cause sat four frames above the dashboard, in `resolveAccessToken`: a bare `catch {}` cleared the session for **every** refresh failure, including one where the API was simply unreachable. `api.ts` already separates `ApiError` (a request was judged) from `ApiUnreachableError` (none completed) precisely so an outage is not mistaken for a rejection — the catch discarded that. The result destroyed a still-valid refresh credential and told the user their session had ended.

The fix re-throws `ApiUnreachableError` and leaves every other error on the existing path. The gate lives in `(app)/layout.tsx`, so all four authenticated routes were affected identically, and the **root `app/error.tsx`** is the boundary that catches it — a route-level boundary cannot, because it is nested inside the layout that failed. `auth.ts` had no test file at all, which is how this shipped; it has one now.

**Foundation has been audited, and the audit found one thing that blocks design** ([[STEP-25 Foundation Audit and Internal Readiness]], `Done` and **owner-approved on 2026-08-15**). Eleven scope areas assessed, **17 findings accepted — 1 Critical, 3 High, 9 Medium, 4 Low** — plus 16 areas recorded as verified-no-finding with the method that verified each. The record is [[Foundation Audit Findings]].

**The Critical finding is a credential reaching logs.** A PostgreSQL connection URI's password survives redaction and is written into a log through the traceback's own source line — reachable via exactly the wrong-credential case [[DOC-02 Validate the Request-Path Credential at Startup]] describes. It was found by *executing* the redaction filter rather than reading it, which is the lesson STEP-23 already recorded in a different form: green CI proves the assertions that were written.

**One severity was corrected by evidence, in the owner's review.** The audit initially rated the RLS finding High, on the grounds that isolation could not be proven — the audit machine has no PostgreSQL, so 306 of 734 API tests skip. The owner rejected the reasoning: *do not conflate "cannot run locally" with "not verified anywhere."* Re-checked, the API job runs a disposable `postgres:17` container and sets `PROJECTONE_REQUIRE_DATABASE_TESTS`, and `conftest.py` answers that flag with `pytest.fail` rather than `pytest.skip` — *refusing to skip them silently*. A green API job is therefore only reachable if the isolation tests ran. **Tenant isolation is proven**; what remains is a local false-confidence gap, now Medium.

**Two capabilities were unproven anywhere when STEP-25 recorded this, and both are now proven.** Migration downgrades (FA-02) and backup restore (FA-03) each execute on every pull request against a disposable `postgres:17` container. What remains outstanding is narrower and is stated as such: [[Backup and Disaster Recovery]] records restore capability as proven while **RPO and RTO stay unset and owner-assigned**, because a recovery objective is a business commitment rather than a drill measurement.

**The audit fixed nothing, deliberately.** An audit that remediates what it finds has changed the system it was measuring. No application code, migration, CI configuration or database was touched, no vault link was repaired and no schema note was created — and the shared Supabase database was never connected to at any point.

**Remediation is a step, not a footnote.** [[STEP-25a Foundation Remediation]] was inserted by owner decision on 2026-08-15 between STEP-25 and the design step that follows it, carrying nine findings with **FA-05 first** — an active leak outranks a missing capability, because one is happening and the other has not yet happened. Eight lower-severity findings were deferred to full-product verification (now [[STEP-85 Full Product Verification and Hardening]]) or a later remediation rather than folded in, since a remediation step that absorbs every open item stops being one.

**The gate that held design back is now open.** The design step stays `Not Started` and was deliberately **not** expanded by STEP-25a — expanding it earlier would have written a design plan against a foundation still carrying a credential leak. With FA-05 closed and merged, design became the next piece of work. What that step *is* then changed: see the post-audit paragraphs below.

**The Critical finding is closed and merged.** [[STEP-25a Foundation Remediation]] is `Done` — squash-merged to `main` as `54ad963` on 2026-08-15, closing **all nine** scheduled findings — FA-05 first, proven by reproduction and by three negative controls that turn the suite red when each redaction rule is deleted. FA-04 and FA-11 were verified by observation rather than by test alone: a click on the repaired root boundary produces a real server request where the old wiring produced none, and the rendered accessibility tree now carries the `alert` node a screen reader announces.

**FA-06 was decided by the owner and built inside the step.** Authentication-event auditing could not use `audit_log` — its `workspace_id` is `NOT NULL` by design and a failed sign-in has no tenant — so the three options were put to the owner rather than guessed at. **Option B was chosen on 2026-08-15**: a separate `security_event_log` table, which keeps `audit_log`'s tenant invariant intact. It is append-only, has **no RLS policies at all** (default-deny is the entire access model, since the events are not tenant-scoped), grants nothing to any client role, and is immutable against the privileged connection too via an UPDATE trigger. The account-existence oracle is closed four independent ways, including the one that is easy to miss: the public sign-in response is identical for an existing and an unknown account, because recording re-raises rather than translating. See [[Table - security_event_log]].

**FA-02 and FA-03 are both proven, by execution.** Both were unproven capabilities, so the drills *were* the deliverable. The migration cycle — `upgrade head` → `downgrade base` → `upgrade head`, with the resulting schema compared against the original — and the restore drill — seed two workspaces, dump, restore into a **separate empty** database, verify schema *and* per-tenant data — now run on every pull request against a disposable `postgres:17` container, and **both pass**. Neither refuses to run against anything that is not obviously disposable, so the shared Supabase database can never be a target.

**Both drills failed first on their own bugs, which is recorded rather than tidied away.** FA-02's compared PostgreSQL's system-generated `NOT NULL` constraint names, which embed the table OID and cannot survive a drop-and-recreate — so it reported a broken downgrade path that was in fact sound. FA-03's seed omitted a `NOT NULL` column, then hit a `pg_dump` version shadowing the client the workflow installed. The lesson is the step's own: **a drill that has never run is not evidence, and its first failures are as likely to be its own.** That is precisely why these findings were High.


### After the Product Coverage Audit — 2026-08-15

**The product was measured against its own specification, and the plan could not carry the gap.** [[Product Coverage Audit]] — merged to `main` as `270a0a4` — assessed **68 capabilities across 13 domains**: 21 Implemented, 14 Foundation/Partial, 24 Missing, 5 Intentionally Deferred, 4 Documentation Drift. Two of [[Product Bible]]'s eight pillars are substantially delivered. The remaining plan at that moment was three steps long.

**Three P0 prerequisites had no executable step anywhere** — not deferred with a reason, simply absent: **file storage** (`assets.storage_path` is null on every row any route can create), **async execution** (workflow runs execute inside the HTTP request, so a multi-minute render cannot), and **the AI capability model beyond chat completion** (`Capability.CHAT_COMPLETION` is the only member of the enum). The **Memory System** was a fourth, with four of its five scopes entirely absent.

**The future plan was rebuilt on 2026-08-15 by owner decision**, from STEP-26 to **STEP-89** — 64 steps in fourteen phases, ordered by dependency rather than by the previous numbering. It was then **resequenced the same day by owner review**, which moved the prompt store ahead of the agent chain, moved billing behind the private beta, and moved advanced notification work out of the early substrate; see [[#Ordering Corrections]]. Every P0 and P1 gap the audit recorded now has a step, and every capability the audit marked `no step` is either scheduled or listed in [[#Deferred by Decision]] with its reason.

**Four owner decisions shaped it.** STEP-26 is restricted to the *common* design foundation and the surfaces that exist today, with speculative domain blueprints removed. The product-wide UI rebuild moved to [[STEP-80 Product-wide UI Rebuild]] and full verification to [[STEP-85 Full Product Verification and Hardening]], so each runs against a whole product rather than a fraction of one. The first release is a **private, invite-only, free beta** ([[STEP-86 Private Beta Release]]), and billing follows it at [[STEP-87 Billing Schema and Subscription Management]] rather than preceding it.

**Two ordering corrections are worth recording.** The first draft placed media processing before the async infrastructure it depends on; the structural check that every step's dependencies carry a lower number caught it, and async execution moved earlier. Owner review then found a subtler one: the plan *said* billing was not required for the free beta while *scheduling* it first, which sequential execution turns into a prerequisite regardless of the wording. Both are the same rule — dependency and intent outrank tidy grouping — and both are recorded rather than quietly fixed.

**Nothing was implemented.** The rebuild is planning documentation: no application code, no migration, no CI change, and the shared Supabase database was never connected to.

**The product has a visual language, and the owner approved it** ([[STEP-26 Product Design System Foundation]], `Done`). The owner-approved direction — warm ivory canvas, matte-black navigation, vermilion accent, editorial typography — is now written as binding rules ([[Design System]] §0) and as token values replacing the v1 slate/indigo palette, alongside navigation conventions, shared component contracts, accessibility rules, responsive breakpoints and the four async states.

**Contrast stopped being a review step and became a build step.** `scripts/check-contrast.py` verifies **90 pairings** — every foreground against every surface it can appear on, in both themes — and runs in the `web` CI job. It found **four genuine WCAG failures** during the work that inspection had missed, each corrected before anything was committed. Two negative controls confirm it fails when it should. [[Design System#6.3]] records why this is enforced rather than requested: the same rule was twice left to memory, and twice a failure shipped.

**The ADR checkpoint triggered**, and [[ADR-003 Product Visual Language and Token Semantics]] was **`Accepted` on 2026-08-15**. Not because the values changed — §6.5 documents a revalue as routine — but because the semantic layer gained **five new roles** that the measured failures forced, and adding a role changes the contract every component is built against. Six decisions were approved: the ADR itself, the exact palette, the `accent`/`accent-fill` role split, Instrument Serif as display-only type, the `nav-*` family, and cinematic cues remaining structural.

**No screen was restyled.** `globals.css` and `layout.tsx` are the only application files touched; the `nav-*` token family is defined and verified but has no consumer until [[STEP-80 Product-wide UI Rebuild]]. The spacing, radius and elevation scales from [[STEP-14 Design System Tokens]] were deliberately left unchanged — the new direction does not contradict them, and changing them would have been change for its own sake.

**The owner clarified STEP-26's scope at the approval gate**, and it is recorded in the step rather than quietly applied. The step's original wording forbade *any* application code change, which would have prevented the token layer from existing at all — leaving an approved design language no surface could consume. The clarification permits exactly three things: the token definitions in `globals.css`, the global font wiring in `layout.tsx`, and the tooling enforcing them. Restyling a component, rebuilding a screen, changing a layout and any [[STEP-80 Product-wide UI Rebuild]] work remain out of scope. The superseded wording is preserved in the step note beside its correction.

### Platform Substrate — files now move through the product

**A user can put a file into ProjectOne and get it back out** ([[STEP-29 Asset Management UI]], `Done` — merged as `bcee2fa` via PR #23 on 2026-08-17). Upload with determinate progress, a listed and previewable asset per kind, and a confirmed delete now exist on the project screen, built entirely on the routes [[STEP-28 Asset Upload and Download]] had already proven against a real bucket. No backend file, migration or dependency was touched: the whole step is `apps/web`. The web suite went from 261 tests to 324.

**The step closes the largest remaining P0 from the [[Product Coverage Audit]] as far as the product surface goes** — `assets.storage_path` is no longer null on every row a user can create, and the storage → upload → media chain that the audit named the single biggest blocker now has its first two links working end to end.

> [!warning] STEP-29 is `Done` with one Definition of Done condition unmet
> **Its nine browser manual checks have not been performed by anyone** — confirmed with the project owner on 2026-08-17. `Done` records the owner's merge decision, not a completed checklist, and the step note carries the full list of what stays unproven ([[STEP-29 Asset Management UI#Step Completion Record]]).
>
> It is deliberately **not** reassigned to [[STEP-80 Product-wide UI Rebuild]] or [[STEP-85 Full Product Verification and Hardening]]; that was offered and declined, on the grounds that moving an open gap onto a step that has not agreed to it converts a visible debt into an invisible one.

**Two closing records were written late and one is still missing.** STEP-29's status stayed `In Progress` in both places after its merge, and was corrected by a documentation-only Pull Request on 2026-08-17 — the same lag [[STEP-28 Asset Upload and Download]] had. Neither STEP-27 nor STEP-28 has a Current State entry at all; that gap is left standing rather than back-filled here, because writing another step's completion record inside this one is the scope widening [[CLAUDE|CLAUDE.md]] §29 forbids. It is an open item for the owner, not a silent omission.

---

## Navigation

- **Previous:** —
- **Next:** [[Execution Protocol]]
- **Parent:** [[Development MOC]]
- **Related Notes:** [[Execution Protocol]] · [[Roadmap]] · [[Task Workflow]] · [[CLAUDE|CLAUDE.md]]
