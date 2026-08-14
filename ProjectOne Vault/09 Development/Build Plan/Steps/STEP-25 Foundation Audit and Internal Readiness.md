---
title: STEP-25 Foundation Audit & Internal Readiness
category: Development/Build Step
status: draft
version: "3.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, process, security, quality]
step_id: STEP-25
step_status: In Progress
detail_level: full
---

# STEP-25 — Foundation Audit & Internal Readiness

**Status:** In Progress
**Detail level:** full — expanded on 2026-08-15 by owner authorization, in a documentation-only planning pass.

> [!note] Execution authorized 2026-08-15
> The plan below was written in a separate documentation-only pass while this step was still `Not Started`. The owner authorized execution on 2026-08-15, and the step moved to `In Progress` in both canonical locations at that point.
>
> Execution remains **findings-only** under D4/D7: no application code is fixed, no documentation repaired, no migration added, no remediation step created, and [[STEP-26 Product Design System and Screen Blueprints]] is not expanded. Findings are recorded in [[Foundation Audit Findings]].

## Goal

Establish what the Foundation build actually is, before anything is rebuilt on top of it. Every step from STEP-01 to STEP-24 shipped against its own Definition of Done; none of them audited the whole. This step is that audit: a single honest assessment of architecture, security, data integrity, cost controls, observability, performance and unfinished behaviour across the entire product.

## Scope

An audit produces **findings**, not fixes. Its output is a written, prioritised record of what is sound, what is weak, and what is missing — with severity assigned, so [[STEP-26 Product Design System and Screen Blueprints]] and [[STEP-27 Product-wide UI Rebuild]] are built on a known foundation rather than an assumed one.

Areas in scope, each assessed against the canonical document that governs it:

- **Architecture and technical debt** — where the shipped shape diverges from [[Backend Architecture]], [[Frontend Architecture]] and the [[Engineering Handbook MOC|Engineering Handbook]], and what that divergence costs.
- **Authentication and session handling** — token lifetime, refresh, revocation, and the session boundary as built.
- **Multi-tenancy and RLS** — every tenant-scoped table carries a policy, and no path bypasses it ([[CLAUDE|CLAUDE.md]] §16).
- **Database integrity and migrations** — constraint coverage, migration reversibility, and expand/contract compliance ([[CLAUDE|CLAUDE.md]] §13).
- **AI spend and provider failure controls** — budgets, circuit breakers, retry ceilings and fallback behaviour as actually implemented ([[CLAUDE|CLAUDE.md]] §15a, [[AI Cost Governance]]).
- **Security** — against [[Security Architecture]] and current OWASP guidance.
- **Backup and restore** — restore proven by execution, not by the existence of a backup ([[Backup and Disaster Recovery]]).
- **Observability** — whether a failure in each subsystem would actually be noticed.
- **Performance** — measured baselines for the primary journeys, not estimates.
- **Accessibility risks** — recorded as findings that feed STEP-26's accessibility rules.
- **Incomplete product behaviour** — every stub, deferred item and honest-placeholder shipped during Foundation, collected in one place.

### Findings carried in from earlier steps

Recorded where they were found, so the audit begins from what is already known rather than rediscovering it:

- **The root error boundary's retry does not retry.** `app/error.tsx` wires its button to `reset()` alone, which clears client state and re-renders the cached payload — the failure is still in it, so nothing recovers. [[STEP-24 Dashboard]] found this defect, fixed it in the four route boundaries it owns, and deliberately left the root boundary alone as another step's code ([[CLAUDE|CLAUDE.md]] §29/§35). It matters more than the others: it is the boundary [[STEP-16b Auth Refresh Outage Handling]] relies on for outage recovery, and its manual checklist recorded "a working retry control" against the same wiring now known to be inert. The fix is the existing `lib/error-recovery.ts`.

**Explicitly out of scope.** This step does **not** publish the application, does **not** deploy to production, and does **not** claim release readiness. Public release is unscheduled and is not a numbered step in this plan — see [[Public Release Draft - Unscheduled]]. Findings that require substantial remediation become their own numbered steps by owner decision; this step does not silently fix them.

## Owner Decisions Governing This Step

Recorded on 2026-08-15, when the expansion was authorized. They are binding on execution and resolve the ambiguities the outline could not.

| ID | Decision |
|---|---|
| **D1** | **Backup and restore** — plan a real restore drill against a **disposable local or CI PostgreSQL database, never the shared Supabase development database**. It must verify schema **plus representative data**. If the environment cannot do that safely, record the missing restore capability as a **High** finding and stop for an owner decision. Never claim restore was proven; never weaken isolation or modify real data. |
| **D2** | **Performance** — existing tools only. Record **indicative single-user local baselines** for the primary journeys, with **repeated measurements and the observed range**. No benchmarking dependency is added. Formal load, concurrency and release thresholds belong to [[STEP-28 Full Product Verification Polish and Hardening]]. |
| **D3** | **Findings location** — one dedicated canonical note, `ProjectOne Vault/09 Development/Foundation Audit Findings.md`, created **during execution**, with the field set defined in [[#The Findings Record]]. |
| **D4** | **Root error boundary** — STEP-25 remains an audit, not a remediation step. The inert root retry is recorded as a **High** finding and **is not fixed here**. The owner decides, after reviewing the complete record, whether it receives a separate remediation step before STEP-26. |
| **D5** | **AI follow-up ADR** — the provider-idempotency, stale-claim reconciliation, lease-policy and crash-window ADR is recorded as a **named prerequisite before the next AI feature**. It is **not drafted during STEP-25**, because STEP-26 and STEP-27 are design and UI work and do not depend on it. |
| **D6** | **Vault links** — the corrected framing is approved: **26 unresolved occurrences detected; 23 remediable across 9 targets; 3 intentional prose examples that must remain unchanged.** |
| **D7** | **Missing schema notes and broken links** — audited and recorded as findings **only**. No link is repaired and no schema note is created during the audit unless the owner later authorizes remediation. |

## Severity Model

Severity is assigned by **objective test**, not by impression. Each finding takes the **highest** severity whose test it satisfies.

| Severity | Objective definition | Consequence |
|---|---|---|
| **Critical** | Any one of: cross-tenant data access is possible; authentication or authorization can be bypassed; a secret is exposed in source control, logs, CI output or a user-facing surface; unbounded AI spend is reachable; or data loss can occur with no recovery path. | Blocks [[STEP-26 Product Design System and Screen Blueprints]] from starting. Requires an owner decision before any further step. |
| **High** | A documented guarantee is not met and a user-visible failure, security weakening or unrecoverable state can result — but no live cross-tenant, auth-bypass, secret-exposure or unbounded-spend path exists. Includes a stated recovery mechanism that does not work. | Requires an owner disposition decision before [[STEP-27 Product-wide UI Rebuild]]. May become its own numbered step. |
| **Medium** | A standard in [[CLAUDE|CLAUDE.md]] or the [[Engineering Handbook MOC|Engineering Handbook]] is violated, or documentation contradicts implementation, with no current user-visible failure and a bounded blast radius. | Scheduled into a later step by owner decision. Does not block STEP-26/27. |
| **Low** | Cosmetic, stylistic or purely informational divergence with no correctness, security or maintainability consequence beyond readability. | Recorded. May be batched or deliberately never actioned. |

Two rules keep the model honest:

- **"No finding" is a claim requiring evidence.** An area assessed clean is recorded as `no finding, verified by <named method>` — never left blank, which is indistinguishable from not having looked.
- **Severity is never lowered to make a step passable.** A Critical finding blocks STEP-26 by definition; reclassifying it to avoid that is the failure this model exists to prevent.

## The Findings Record

One canonical note, created during execution at `ProjectOne Vault/09 Development/Foundation Audit Findings.md` (D3). Every finding carries all nine fields — a finding missing any of them is incomplete, not brief:

| Field | Content |
|---|---|
| **Identifier** | `FA-NN`, stable and never reused. |
| **Area** | One of the scope areas above. |
| **Severity** | Critical / High / Medium / Low, per the objective test. |
| **Affected location** | File path and line, table name, migration id, endpoint, or vault note. |
| **Evidence** | What was observed, and by what method. Never an inference. |
| **Consequence** | What breaks, for whom, under what conditions. |
| **Recommended disposition** | Fix now / own numbered step / schedule into a named later step / accept and document. |
| **Owner decision** | Left empty by Claude. The owner fills it. |
| **Status** | Open / Accepted / Scheduled / Closed. |

## Prerequisites

- [[STEP-24 Dashboard]] — `Done`

## Required Documentation

Candidates, not a reading list ([[Execution Protocol#Context Discipline]] rule 2). Each earns a read when it answers a question the audit actually has.

- [[Security Architecture]]
- [[Database Architecture]]
- [[AI Cost Governance]]
- [[Backup and Disaster Recovery]]
- [[Compliance and Governance]]
- [[Testing Strategy]]

## Tasks

Sixteen tasks. Every one produces findings; none produces a fix (D4, D7).

### 1. Establish the findings record

Create `Foundation Audit Findings.md` (D3) with the severity model and the nine-field structure above, plus its frontmatter, Navigation block and index membership. It starts empty of findings and fills as the tasks below run.

### 2. Architecture and technical debt

Assess the shipped shape against [[Backend Architecture]], [[Frontend Architecture]] and the [[Engineering Handbook MOC|Engineering Handbook]]:

- The router → service → repository layering in `apps/api/app/` — 7 routers, 15 services, 12 repositories. Confirm routers only validate/call/return, and that no business logic sits in a router ([[CLAUDE|CLAUDE.md]] §12/§35).
- Server/Client split in `apps/web/src/` — every `"use client"` justified by a browser requirement ([[CLAUDE|CLAUDE.md]] §11).
- Dependency direction: `apps/` never depends on `apps/`; no circular imports ([[CLAUDE|CLAUDE.md]] §8/§28).
- `packages/` and `infrastructure/` are still empty placeholders — record what that means for the stated modular-services principle.

### 3. Authentication and session handling

- Token lifetime, refresh and revocation as built: `token_service.py`, `auth_service.py`, `security.py`, and the web-side `auth.ts` / `session-cookies.ts`.
- ES256 verification against the Supabase JWKS, and behaviour when the key is unavailable.
- The STEP-16b outage path: confirm `ApiUnreachableError` still re-throws rather than clearing the session, and that its only recovery surface is the root boundary named in D4.
- **Deferred and recorded, not assessed as gaps to close here:** MFA and OAuth remain deliberately deferred and unscheduled since STEP-10.

### 4. Multi-tenancy and RLS — with negative controls

Presence is not proof. For every one of the **14 tables** (`users`, `workspaces`, `workspace_members`, `projects`, `assets`, `conversations`, `messages`, `workflow_runs`, `workflow_step_runs`, `ai_budgets`, `ai_spend_records`, `ai_shutdown_switches`, `provider_credentials`, `audit_log`):

- Confirm RLS is **enabled and forced**, and that a policy exists per command.
- **Negative control, mandatory:** for each isolation guarantee, disable or bypass the control in a throwaway context and confirm the test **fails** — an isolation test that passes with RLS off is testing nothing (the standard STEP-09 set).
- Confirm `projectone_api` still lacks `rolbypassrls`, and that schema default privileges remain narrowed (`c4f21a86b3de`).
- Confirm the column-level grant `UPDATE (limit_usd, period_interval)` on `ai_budgets` (`c9d3b71e08af`) still holds, since no RLS policy can restrict a column.
- Confirm no admin or internal path bypasses RLS ([[CLAUDE|CLAUDE.md]] §16).

Negative controls run **only** against a disposable database, never the shared Supabase development project (D1's isolation rule applies here too).

### 5. Database integrity and migrations

- **18 migrations**: linear history, no branch points, each downgrade actually reverses its upgrade.
- Expand/contract compliance ([[CLAUDE|CLAUDE.md]] §13) — flag any rename-in-place, destructive change, or migration requiring a simultaneous code deploy.
- Constraint, trigger and index coverage; `deleted_at` soft-delete semantics applied consistently.
- Reconcile the schema against its documentation (feeds task 14).

### 6. API contracts and error handling

- 7 routers against [[API Conventions]] and [[API Endpoints]]: envelope shape, status-code consistency, 401-vs-403 separation, idempotency where claimed.
- `core/errors.py` mapping: every failure path returns a user-safe message with detail retained only in logs ([[CLAUDE|CLAUDE.md]] §24).
- Rate limiting: `user_rate_limit.py` and `client_address.py` — confirm right-to-left `X-Forwarded-For` parsing and fail-closed behaviour survive.
- **Record the known limitation:** the limiter is **in-process and per-worker**, so N workers permit N times the intended per-user allowance. Stated deliberately in STEP-12 and unchanged by STEP-12a, which fixed *what* is counted, not *where* counts live.

### 7. AI spend governance

Enumerate every [[CLAUDE|CLAUDE.md]] §15a control and mark each **implemented / partial / absent** with evidence:

budget ceilings · circuit breakers · retry limits · maximum execution limits (steps, wall-clock, total cost) · usage monitoring and anomaly detection · runaway/chained-agent caps · provider cost awareness · graceful degradation · emergency shutdown without a deploy.

Assessed across `ai/governance.py`, `ai/router.py`, `ai/pricing.py`, `ai/health.py`, `ai_spend_service.py`, and the three governance tables. Include the pessimistic placeholder rate in `ai/pricing.py` and what an inaccurate rate means for a ceiling expressed in dollars.

**Also recorded here (D5):** the **AI crash window** — STEP-23 leaves a turn stranded after a provider charge, visibly stuck rather than silently retried. The ADR covering provider-side idempotency, stale-claim reconciliation, lease policy and crash-window handling is a **named prerequisite before the next AI feature**, and is **not drafted in this step**.

### 8. Security, secrets and log hygiene

- OWASP pass over external-input handling; confirm every external input is schema-validated before reaching business logic.
- Credential encryption (`ai/crypto.py`) and revocation (`d1f70a4c62be`).
- **Secret scanning, explicitly:** scan the working tree **and git history** for committed secrets. Confirm only `.env.example` files are tracked and that `.env` / `.env.local` remain ignored.
- **Verify no sensitive value reaches** any of four surfaces, each checked separately: **logs**, **commits**, **CI output**, and **user-facing errors**. A key, token, cookie value or database URL appearing in any of them is Critical by the model above.
- Audit-log coverage for sensitive actions, without secrets in the log body ([[CLAUDE|CLAUDE.md]] §25).
- **Two gaps [[Build Plan]] explicitly assigned to this step:** **audit retention is unbounded** (no purge schedule, and [[CLAUDE|CLAUDE.md]] §16 requires audit logs to be retained on a *stated* schedule as a disclosed exception, not an unbounded one), and **authentication events are not audited** — sign-in, sign-out and failed attempts, arguably the most security-relevant events there are. Both are recorded as findings; the retention schedule is an owner decision, not one this step makes.
- **Idempotency keys remain unbuilt**, and `POST /workspaces` is the first endpoint that could use them — recorded alongside the AI crash window in task 7, since both are the same class of missing guarantee.
- **Data retention and deletion obligations** ([[CLAUDE|CLAUDE.md]] §16): whether a workspace deletion would actually cascade through every store that holds user data, and whether any store is unregistered with that process.

### 9. Tests and CI

- Coverage assessed **by risk, not by percentage**: which failure paths have no assertion. STEP-23's five post-green defects are the governing lens — *green CI proves the assertions that were written, and says nothing about the ones that were not.*
- **38 API test files and 21 web test files**; execute the full suite and record the real result.
- **Record the CI gating gap:** the `governance-docs` job is **not** among the `Protect main` ruleset's required checks, so it can be red while the merge button stays green. Only the project owner can add it.
- **Repository visibility:** the GitHub repository is **public**. CI results are therefore observable, and any earlier claim that CI visibility is limited by private-repository status is stale. Those stale claims live in [[Build Plan]]'s Current State and in the STEP-09 / STEP-10 step notes — recorded here as a documentation finding (task 14), not edited by this step.

### 10. Accessibility

Sweep all 5 authenticated routes and 2 auth routes for landmarks and accessible names, keyboard reachability with visible focus, skeleton `role="status"` / `aria-busy`, boundary `role="alert"`, contrast, and heading order. **Findings feed [[STEP-26 Product Design System and Screen Blueprints]]'s accessibility rules; nothing is fixed here.**

### 11. Performance baselines (D2)

Existing tools only. For each primary journey — sign-in → dashboard → projects → project detail → chat — record **indicative single-user local** timings with **repeated measurements and the observed range**, stated as indicative rather than as thresholds. **No benchmarking dependency is added.** Formal load, concurrency and release thresholds are [[STEP-28 Full Product Verification Polish and Hardening]]'s.

### 12. Backup and restore (D1)

Attempt a genuine restore drill against a **disposable local or CI PostgreSQL database**, verifying **schema plus representative data**. The shared Supabase development database is never a target, and no real data is modified.

**If the environment cannot perform the drill safely, do not simulate it:** record the missing restore capability as a **High** finding and **stop for an owner decision**. Also record whether [[Backup and Disaster Recovery]]'s RPO/RTO targets have actual values — the note currently states they should be defined rather than defining them.

### 13. Observability

For each subsystem — auth, database, AI provider calls, workflow runs, rate limiting — determine whether a failure would actually be noticed, and by what signal. A subsystem that can fail silently is a finding ([[CLAUDE|CLAUDE.md]] §26).

### 14. Documentation, vault and roadmap consistency

- [[Build Plan]] Current State against what the code actually does, including the stale private-repository claims from task 9.
- Every Project Bible note is still `status: draft` at v0.1 — record the standing implication.
- **Missing schema notes:** 11 `Table - *` notes document **14** tables. `conversations`, `messages` and `workflow_step_runs` have none. **Recorded as findings; not created** (D7).
- **Vault links (D6):** re-run the resolution measurement and confirm **26 unresolved occurrences / 23 remediable across 9 targets / 3 intentional prose examples** in [[Skills/Documentation Keeper|Documentation Keeper]] that **must remain unchanged**. **Recorded; not repaired** (D7).
- [[DOC-01 Align ADR Template with CLAUDE.md]] — [[ADR Template]] lacks `Review` and `Rejected`. Recorded as an open documentation task.
- [[DOC-02 Validate the Request-Path Credential at Startup]] — `REQUEST_DATABASE_URL` is validated for presence and never for correctness. Recorded as an open backlog item.

### 15. Incomplete product behaviour — one catalogue

Every stub, deferral, placeholder and known limitation shipped during Foundation, in one place:

the dashboard's `StubSections()` honest stubs · the root retry defect (D4) · the per-worker rate limiter · the AI crash window (D5) · deferred MFA and OAuth · the single-workspace limitation · the pessimistic AI pricing placeholder · DOC-01 · DOC-02 · missing schema notes · unresolved vault links · and the **two owner-deferred visual gates** (loading-skeleton reflow, the timed 30-second [[Dashboard]] criterion) — which are **not STEP-25's to answer**; the audit only confirms they remain live gates on STEP-26/27.

### 16. Consolidate and prioritise

Produce the final prioritised record; propose for each High or Critical finding whether it warrants its own numbered step. **Proposing is not creating** — adding a step is a plan change and the owner's decision ([[Execution Protocol#Future Step Synchronization]]).

> [!warning] STEP-26 is expanded only at the end of STEP-25
> [[STEP-26 Product Design System and Screen Blueprints]] is expanded to full detail as the **final act of STEP-25 execution**, using the **final approved audit findings** — never during planning, and never before the findings are settled. Its accessibility rules depend on task 10's output.

## Validation

Observed, not assumed. Every check names its instrument, and a check that cannot be run is recorded as such rather than skipped silently.

| # | Check | Instrument |
|---|---|---|
| 1 | Every scope area yields at least one finding **or** an explicit `no finding, verified by <method>` | The findings record, read end to end |
| 2 | Every finding carries all nine fields | Structural pass over the record |
| 3 | Every severity assignment satisfies its objective test | Re-read each against [[#Severity Model]] |
| 4 | RLS and tenant isolation claims are backed by an **executed negative control** that failed with the control removed | Test run against a **disposable** database |
| 5 | Full test suite executed; real pass/fail counts recorded | `pytest` (API) and `vitest` (web) |
| 6 | Lint and type-check clean in both apps | Ruff + mypy strict; ESLint + `tsc` |
| 7 | Secret scan over working tree **and git history** returns no exposure | Scan run and its output recorded |
| 8 | No sensitive value in logs, commits, CI output or user-facing errors | Four surfaces checked separately |
| 9 | Vault link inventory reproduced — 26 / 23 / 3 (D6) | Re-run of the resolution measurement, not memory |
| 10 | Restore drill executed against a disposable database, **or** the gap recorded as High and stopped for owner decision (D1) | Drill output, or the finding |
| 11 | Performance baselines are repeated measurements with a stated range, marked indicative (D2) | Recorded timings |
| 12 | **No application code, migration, CI config or database was modified** | `git status` and the diff |
| 13 | Governance documents still in sync | `./scripts/sync-governance-docs.sh --check` |

Check 12 is the one that defines this step: an audit that changed the system it audited has invalidated its own findings.

## Manual Checklist

Read-only walkthrough. Nothing is fixed, and no data is written beyond what a normal session creates.

- [ ] Sign-in and sign-up render; validation errors are user-safe and expose no internal detail.
- [ ] All 5 authenticated routes render: dashboard, projects, project detail, settings, chat.
- [ ] Each route's loading, empty and error state is present and honest.
- [ ] **Each error boundary's retry genuinely recovers** — the four route boundaries recover; the **root boundary is re-confirmed inert by observation** (D4) and recorded, not fixed.
- [ ] The dashboard's stub sections still read as honest stubs, implying no information the product lacks.
- [ ] Keyboard traversal reaches every interactive control with a visible focus state.
- [ ] The single-workspace limitation is still disclosed in the interface.
- [ ] `/dev/session` returns 404 in a production build, by both mechanisms STEP-16a required.
- [ ] Sign-out clears the session, and an unauthenticated visit to an app route redirects.

## Definition of Done

- [ ] Every scope area assessed and recorded with severity, per the objective model.
- [ ] All findings in `Foundation Audit Findings.md`, each with all nine fields (D3).
- [ ] The carried-forward STEP-24 findings are resolved into the record: the root retry defect recorded as **High** (D4), and the two owner-deferred visual gates confirmed as still-live gates on STEP-26/27.
- [ ] The AI idempotency/reconciliation/lease/crash-window ADR is recorded as a **named prerequisite before the next AI feature**, and **was not drafted** (D5).
- [ ] Negative-control evidence exists for every RLS and tenant-isolation claim.
- [ ] Secret scanning completed across working tree and history, and all four leak surfaces verified.
- [ ] Restore drill executed against a disposable database, **or** the gap recorded as High with an owner decision requested (D1).
- [ ] Performance baselines recorded as indicative, repeated, with ranges (D2).
- [ ] The full known-debt catalogue is complete: per-worker limiter, DOC-01, DOC-02, missing schema notes, root retry, AI crash window, deferred MFA/OAuth, single-workspace limitation, every shipped stub.
- [ ] **No remediation was performed** — no link repaired, no schema note created, no code changed (D4, D7).
- [ ] Documentation updated: this note, the findings record, [[Build Plan]] Current State.
- [ ] [[STEP-26 Product Design System and Screen Blueprints]] expanded to full detail **at the end of the step**, from the final approved findings.
- [ ] Full validation executed and results recorded honestly, including anything that could not be run.
- [ ] Required CI green on the Pull Request; manual checklist complete.
- [ ] Every review conversation resolved.
- [ ] **Owner approval gate satisfied** — see below.
- [ ] Pull Request open and **NOT merged**; the owner squash-merges.

### Owner approval gate

**This step is Critical** ([[CLAUDE|CLAUDE.md]] §21) and carries an owner approval gate.

Its own changes are documentation-only, which argues the other way. But §21's test is what a change *touches*, and this audit's findings are assessments of authentication, authorization, multi-tenancy/RLS, database schema, AI/agent architecture, security controls and public API contracts — the entire Critical list. More decisively, its **output governs STEP-26, STEP-27 and STEP-28**: a wrong or incomplete severity assignment here silently authorizes building on a foundation nobody actually verified. §21's own instruction settles the remaining doubt — when uncertain, default to Critical.

The gate is substantive rather than ceremonial: **every Critical finding blocks STEP-26 by definition**, and every High finding requires an owner disposition before STEP-27.

---

## Outcome

**Audit executed 2026-08-15.** Findings live in [[Foundation Audit Findings]]: **17 findings — 0 Critical, 5 High, 8 Medium, 4 Low** — plus 16 areas recorded as verified-no-finding with the method that verified each.

**No Critical finding was identified**, so nothing structurally blocks [[STEP-26 Product Design System and Screen Blueprints]]. That statement is bounded: the RLS **negative controls** that would make the isolation claim conclusive could not be executed here.

**Three verifications are unproven, not passed.** The audit machine has no local PostgreSQL, no Docker and no `psql`/`pg_dump`, so under D1 and execution rules 6–7 they are recorded as unproven rather than approximated:

- **RLS negative controls** — 306 of 734 API tests skipped locally for a missing test database; the isolation proof exists only in CI.
- **Migration downgrades** — all 18 have downgrade bodies and the history is linear, but no downgrade was executed.
- **Backup and restore** — the drill could not run and was **not simulated**. D1 mandates an owner decision here.

**Two defects were found that were not previously recorded**: a database-URL password reaching logs un-redacted (FA-05), and the root error boundary missing its alert role (FA-11) alongside the already-known inert retry (FA-04).

**Nothing was remediated.** No application code, migration, CI configuration or database was touched; no link was repaired; no schema note was created; no remediation step was created; and [[STEP-26 Product Design System and Screen Blueprints]] was **not** expanded — it is expanded only after the owner settles the findings.

**Severities are proposed, not settled**, and every disposition awaits the owner (execution rule 11).

---

## Navigation

- **Previous:** [[STEP-24 Dashboard]]
- **Next:** [[STEP-26 Product Design System and Screen Blueprints]]
- **Parent:** [[Build Plan]]
