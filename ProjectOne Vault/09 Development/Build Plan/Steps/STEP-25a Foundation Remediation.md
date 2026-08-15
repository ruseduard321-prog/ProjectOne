---
title: STEP-25a Foundation Remediation
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, security, database, quality]
step_id: STEP-25a
step_status: In Progress
detail_level: full
---

# STEP-25a — Foundation Remediation

**Status:** In Progress
**Detail level:** full — inserted between [[STEP-25 Foundation Audit and Internal Readiness]] and [[STEP-26 Product Design System and Screen Blueprints]] by owner decision on 2026-08-15, closing the findings STEP-25 recorded.

## Why This Step Exists

[[STEP-25 Foundation Audit and Internal Readiness]] is an audit: it produces findings, never fixes. It found **17**, and the owner settled their severities on 2026-08-15. One is **Critical** and, by the severity model's own consequence column, **blocks progression to design**.

This step is where that backlog is discharged. It is numbered `25a` rather than `29` because it amends what STEP-25 assessed rather than adding new product surface — the same convention [[STEP-11a Membership Removal Policy]], [[STEP-12a Trusted Proxy and Per-User Rate Limiting]], [[STEP-16a Developer Session Inspector]] and [[STEP-16b Auth Refresh Outage Handling]] follow.

**Design does not begin until this step is `Done`.** [[STEP-26 Product Design System and Screen Blueprints]] and [[STEP-27 Product-wide UI Rebuild]] rebuild the product's surface; rebuilding on a foundation with a known credential leak and an unproven restore path is exactly what the audit existed to prevent.

## Goal

Close the nine findings the owner scheduled for remediation before design, and **prove each closure by execution** rather than by inspection. Two of them (FA-02, FA-03) are unproven capabilities, so the proof *is* the deliverable.

## Scope

### In scope — the nine scheduled findings

Ordered as the owner directed on 2026-08-15: **FA-05 first.** An active secret-exposure defect outranks a missing capability, because a password reaching logs is happening now while absent restore proof is a risk that has not yet materialised.

| # | ID | Severity | What must change |
|---|---|---|---|
| 1 | **FA-05** | **Critical** | A PostgreSQL URI password must never reach a log. Redaction extended, proven by negative control. |
| 2 | **FA-03** | High | An **executed** backup/restore drill on a disposable PostgreSQL — schema **and** representative data. Never shared Supabase data. |
| 3 | **FA-04** | High | The root error boundary's retry must actually recover, via the existing `lib/error-recovery.ts`. |
| 4 | **FA-11** | Medium | The root boundary must announce itself to assistive technology. |
| 5 | **FA-02** | High | A complete `downgrade` → `upgrade` cycle, executed against a disposable container. |
| 6 | **FA-01** | Medium | Make a locally-skipped isolation suite **visible**. Isolation itself is already proven in CI. |
| 7 | **FA-06** | Medium | Authentication events — sign-in, sign-out, failed attempts — must be audited. |
| 8 | **FA-07** | Medium | **90-day** audit retention, configurable before public release, with tested deletion behaviour. |
| 9 | **FA-08** | Medium | `governance docs (sync check)` becomes a **required** `main` check — owner-operated, and verified here. |

### Explicitly out of scope

**Eight findings are deliberately not in this step** — neither blocking nor small enough to be clearly bounded. They go to [[STEP-28 Full Product Verification Polish and Hardening]] or a later owner-approved remediation: **FA-09** (stale private-repository claims), **FA-10** (three missing schema notes), **FA-12** (spend-anomaly alerting channel), **FA-13** (idempotency keys and the AI crash window), **FA-14** (empty `packages/`/`infrastructure/`), **FA-15** (23 remediable vault links), **FA-16** (DOC-01/DOC-02), **FA-17** (the accepted-limitation catalogue).

**FA-13's ADR remains a named prerequisite before the next AI feature** — which STEP-26 and STEP-27 are not, so it does not gate them.

This step also does **not** redesign any screen, does **not** publish or deploy, and does **not** claim release readiness.

> [!warning] FA-16/DOC-02 is related to FA-05 but stays out
> DOC-02 (validating `REQUEST_DATABASE_URL` at startup) shares a cause with FA-05 and would pair naturally. It is **out of scope** regardless: FA-05 is fixed by making the leak impossible, and adding startup validation is a separate behavioural change to configuration loading. Scope discipline ([[CLAUDE|CLAUDE.md]] §29/§35) outranks convenience.

## Prerequisites

- [[STEP-25 Foundation Audit and Internal Readiness]] — `Done`, with its findings owner-approved
- A **disposable PostgreSQL environment** (local container or the CI service container). Tasks 2 and 5 cannot be completed without one, and **must never** target the shared Supabase development database.

## Required Documentation

Candidates, not a reading list ([[Execution Protocol#Context Discipline]] rule 2).

- [[Foundation Audit Findings]] — the authoritative record of what must change
- [[Backup and Disaster Recovery]] — for the RPO/RTO values task 2 must supply
- [[Security Architecture]] · [[Compliance and Governance]] — for tasks 1, 7 and 8

## Tasks

Nine tasks, in the owner's order. Each closes one finding and **proves** the closure.

### 1. FA-05 — stop a database password reaching logs *(Critical, first)*

Extend `apps/api/app/core/logging.py`'s `_REDACTIONS` so a credential cannot survive rendering:

- A **connection-URI password** pattern: `scheme://user:<secret>@host` redacts the password while keeping scheme, user and host, so the log line still identifies *which* connection failed.
- A **key-shaped environment pattern** for `KEY=value` forms, covering `PROJECTONE_BYOK_ENCRYPTION_KEY` and any `*_KEY` / `*_SECRET` / `*_TOKEN` / `*_PASSWORD` / `*_URL` carrying credentials.
- Preserve the existing negative-lookahead discipline: an already-redacted line must not be re-redacted into a less informative one, which is the defect the current bearer-token rule was written to avoid.

**Proof required — the audit's own reproduction, inverted.** Attach `RedactingFilter` to a handler, call `logger.exception()` on a failed `psycopg.connect(...)` carrying a password, and assert the password is **absent** from the emitted record. Then a **negative control**: remove the new pattern and confirm the test **fails**. A redaction test that passes without the rule is testing nothing — the standard [[STEP-09 Row Level Security Policies]] set.

### 2. FA-03 — prove restore by executing it *(High)*

Against a **disposable local or CI PostgreSQL container**, never the shared Supabase development database:

- Apply migrations to head; seed **representative data** across tenant-scoped tables (at least two workspaces, so the restore is verifiable as tenant-correct rather than merely non-empty).
- Take a backup with standard tooling.
- **Restore into a separate, empty database** — restoring over the source proves far less.
- Verify **schema** (tables, constraints, triggers, RLS enabled *and* forced, policy count) **and data** (row counts and content per workspace) match the source.
- Record the drill so it is repeatable, and give [[Backup and Disaster Recovery]] **actual RPO and RTO values** rather than the current statement that they should be defined.

Provisioning a disposable environment is a prerequisite, not a task deliverable. If none can be provisioned, this step is `Blocked` — it is never marked complete on an unexecuted drill.

### 3. FA-04 — make the root retry actually retry *(High)*

Change `apps/web/src/app/error.tsx` to recover through the existing `useErrorRecovery(reset)` from `lib/error-recovery.ts`, as all four route boundaries already do. No new abstraction: the mechanism exists and is tested.

**Proof required:** a test asserting the root boundary's retry triggers a refresh rather than a bare `reset()`, mirroring the existing `error-boundary-retry.test.ts` coverage. Then verify by observation against a genuine API outage — the exact scenario [[STEP-16b Auth Refresh Outage Handling]] depends on this boundary for, and the one whose checklist recorded "a working retry control" against wiring now known to be inert.

### 4. FA-11 — give the root boundary alert semantics *(Medium)*

Add `role="alert"` to the root boundary's error container, matching all four route boundaries. Same file as task 3 and naturally done alongside it, but **a separate finding with separate proof**: a screen reader must announce the failure.

### 5. FA-02 — prove migrations reverse *(High)*

Against the same disposable container:

- Execute a full **`downgrade base`** from head, then **`upgrade head`** again, and confirm both directions complete without error.
- Confirm the twice-migrated schema matches the once-migrated schema, so a downgrade/upgrade round trip is genuinely idempotent.
- Consider adding this cycle as a **CI step**, so reversibility stops being a claim nobody re-checks. If added, it is a new job and must be considered for the required-checks list alongside task 9.

### 6. FA-01 — make a skipped isolation suite visible *(Medium)*

Isolation is **already proven in CI** and this task does not re-prove it. It closes the local false-confidence gap:

- Emit a **prominent end-of-run banner** when the database-backed tests are skipped, so a local green run cannot be mistaken for full coverage. `-ra` already reports skip reasons; a summary line stating *how many* tests were omitted and *why* is what a reader actually notices.
- Document the one-line invocation for running the isolation suite against a disposable container.

**Do not** make the skip a hard local failure: a contributor without PostgreSQL must still be able to run the offline suite, which is the deliberate design `conftest.py` records.

### 7. FA-06 — audit authentication events *(Medium)*

Record sign-in, sign-out and **failed** authentication attempts through the existing `AuditService`, following the established action vocabulary.

Two constraints from the audit: no credential, token or cookie value may enter the audit body ([[CLAUDE|CLAUDE.md]] §16/§25) — task 1's redaction is a backstop, not a licence — and a failed attempt must be recorded **without** becoming an account-existence oracle, the same property `core/errors.py` already protects in its 401 responses.

### 8. FA-07 — 90-day audit retention, tested *(Medium)*

Per the owner's decision of 2026-08-15:

- Implement a **90-day** retention policy for audit events, **configurable** before public release rather than hard-coded.
- Implement the deletion/purge behaviour that enforces it.
- **Test it** — the owner's instruction is explicit that remediation defines retention behaviour *and* tests it. A policy no test exercises is a comment.
- Update [[Compliance and Governance]] and the `audit_log` documentation so the retention window is disclosed as the bounded legal exception [[CLAUDE|CLAUDE.md]] §16 requires, rather than the unbounded one it is today.

Any schema change here is **expand/contract** and ships with its RLS unchanged ([[CLAUDE|CLAUDE.md]] §13/§16).

### 9. FA-08 — make the governance check required *(Medium, owner-operated)*

`governance docs (sync check)` must become a **required check** on the `Protect main` ruleset.

**Claude cannot perform this** — it is a repository-settings change only the owner can make. This task is therefore: request it explicitly, then **verify it took effect** by observing the ruleset's required-check list or a PR that reports the check as required. Verification is part of this step's Definition of Done; the change itself is the owner's action.

## FA-06 owner decision required

**Task 7 is blocked, and deliberately not guessed at.** Auditing authentication events cannot be done through the existing `AuditService` without changing a documented multi-tenancy decision, and [[CLAUDE|CLAUDE.md]] §34 forbids inventing a schema.

**The constraint.** `audit_log` is tenant-scoped by design (migration `a3c07d5e91f4`): `workspace_id` is `NOT NULL` with a `RESTRICT` foreign key, `actor_id` is `NOT NULL`, and the RLS policy filters on `workspace_id IN app_current_user_workspaces()`. The migration states the reasoning outright — *a nullable tenant column on a tenant-scoped table is a row that no policy can classify.*

**Why authentication events do not fit.** `POST /auth/sign-in` receives an email and a password and nothing else. There is no workspace until one is selected, and no authenticated actor until the attempt succeeds. A **failed** attempt — the most security-relevant case, and the one FA-06 names explicitly — has neither, and may name no existing account at all.

### The three options

| | Option | What it costs | What it buys |
|---|---|---|---|
| **A** | Make `workspace_id` nullable on `audit_log` | Reverses a documented decision; creates rows no RLS policy can classify; every existing policy and query needs re-examination | One table, one query path |
| **B** | A separate `security_event_log` table | A new table, a new RLS model, a new migration, a second thing to retain and purge | Keeps `audit_log`'s tenant invariant intact; the natural home for events that are genuinely not tenant-scoped |
| **C** | Structured application logs only | No queryable trail; no retention policy; not an audit record in the §16 sense | No schema change at all |

**Recommendation: B.** It is the only option that records failed attempts *and* leaves `audit_log`'s tenant invariant untouched. A is a multi-tenancy regression traded for convenience, and C does not satisfy §16's requirement for an audit trail of security-relevant actions — it would close the finding on paper only.

**This is Critical either way** ([[CLAUDE|CLAUDE.md]] §21: schema, security controls, multi-tenancy), so it needs the owner's decision before implementation, not after. The two constraints the audit attached hold under any option: no credential, token or cookie value may enter the record, and a failed attempt must not become an account-existence oracle — the property `core/errors.py` already protects in its 401 responses.

## Validation

Observed, not assumed. Every check names its instrument, and every fix to a control carries a **negative control** proving the test fails without it.

| # | Check | Instrument |
|---|---|---|
| 1 | A connection-URI password is **absent** from an emitted log record | Executed probe reproducing the FA-05 scenario |
| 2 | Removing the new redaction pattern makes that test **fail** | Negative control |
| 3 | A key-shaped credential (`*_KEY`, `*_SECRET`, `*_TOKEN`, `*_PASSWORD`) is redacted | Executed probe |
| 4 | Already-redacted lines are not degraded by the new patterns | Executed probe on the existing bearer-token cases |
| 5 | Restore drill completes: schema **and** per-workspace data match the source | Executed on a **disposable** database |
| 6 | The restore target was a separate empty database, and no shared Supabase data was touched | Command record |
| 7 | `downgrade base` then `upgrade head` both succeed; the resulting schema matches | Executed on a **disposable** database |
| 8 | The root boundary's retry triggers a refresh, not a bare `reset()` | Unit test + observed against a real API outage |
| 9 | The root boundary carries `role="alert"` and announces | Test + assistive-technology check |
| 10 | A locally-skipped isolation suite produces a **visible** banner naming the omitted count | Executed offline run |
| 11 | The offline suite still passes without PostgreSQL | Executed run with no test database |
| 12 | Sign-in, sign-out and failed attempts appear in the audit log | Executed test |
| 13 | No credential, token or cookie value appears in any audit body | Executed test |
| 14 | A failed attempt is not an account-existence oracle | Executed test |
| 15 | Audit events older than 90 days are purged; newer ones are retained | Executed test |
| 16 | The retention window is configurable, not hard-coded | Executed test |
| 17 | Full API and web suites pass, with **no new skips** | `pytest` and `vitest` |
| 18 | Lint, format and type-check clean in both apps | Ruff, mypy strict, ESLint, `tsc` |
| 19 | Governance documents in sync | `./scripts/sync-governance-docs.sh --check` |
| 20 | **Required CI green, with the database-backed suite executing** | Check runs on the PR head; `PROJECTONE_REQUIRE_DATABASE_TESTS` keeps a skip red |
| 21 | `governance docs (sync check)` is **verified** as a required check | Ruleset or PR observation (task 9) |

## Manual Checklist

- [ ] Stop the API; confirm the **root** boundary renders and its "Try again" **genuinely recovers** once the API returns — the FA-04 scenario end to end.
- [ ] Confirm the root boundary is announced by a screen reader (FA-11).
- [ ] Confirm the four route boundaries still recover — task 3 must not regress them.
- [ ] Sign in, sign out, and fail a sign-in; confirm all three appear in the audit log with no credential material.
- [ ] Run the API suite locally **without** a test database; confirm the skip banner is unmissable and the run still passes.
- [ ] Confirm no user-facing error surfaces a connection string, stack trace or internal detail.

## Definition of Done

- [ ] All nine scheduled findings closed, each **proven by execution**.
- [ ] **FA-05 verified by negative control** — the test fails without the new redaction.
- [ ] **FA-03 restore drill executed** on a disposable database, verifying schema *and* representative data, with real RPO/RTO values written into [[Backup and Disaster Recovery]].
- [ ] **FA-02 downgrade/upgrade cycle executed** on a disposable database.
- [ ] **The shared Supabase development database was never a target** of any drill, migration test or destructive operation.
- [ ] **FA-08 verified**: `governance docs (sync check)` is a required `main` check — the owner's action, confirmed by observation.
- [ ] [[Foundation Audit Findings]] updated: each closed finding's **Status** set to `Closed` with the evidence that closed it. Findings deferred out of scope stay `Open` and are not silently closed.
- [ ] Documentation updated ([[CLAUDE|CLAUDE.md]] §19): [[Backup and Disaster Recovery]], [[Compliance and Governance]], the `audit_log` schema note, and [[Build Plan]] Current State.
- [ ] Full API and web suites pass with **no new skips**; lint, format and type-check clean.
- [ ] Required CI green on the Pull Request, **with the database-backed suite executing**.
- [ ] Manual checklist complete.
- [ ] Every review conversation resolved.
- [ ] **Owner approval gate satisfied** — see below.
- [ ] Pull Request open and **NOT merged**; the owner squash-merges.
- [ ] **[[STEP-26 Product Design System and Screen Blueprints]] is not expanded by this step.** It is expanded by whichever step immediately precedes it once this one is `Done`.

### Owner approval gate

**This step is Critical** ([[CLAUDE|CLAUDE.md]] §21). It touches security controls (FA-05, FA-06), the database schema (FA-07), infrastructure and CI configuration (FA-02, FA-08), and backup/recovery (FA-03) — four categories on the Critical list, any one of which would qualify alone.

It also carries the consequence that created it: **FA-05 is Critical and blocks progression to design**, so [[STEP-26 Product Design System and Screen Blueprints]] does not begin until this step is `Done` and approved.

---

## Navigation

- **Previous:** [[STEP-25 Foundation Audit and Internal Readiness]]
- **Next:** [[STEP-26 Product Design System and Screen Blueprints]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Foundation Audit Findings]] · [[Execution Protocol]] · [[CLAUDE|CLAUDE.md]]
