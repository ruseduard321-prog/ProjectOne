---
title: STEP-25a Foundation Remediation
category: Development/Build Step
status: stable
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, security, database, quality]
step_id: STEP-25a
step_status: Done
detail_level: full
---

# STEP-25a — Foundation Remediation

**Status:** Done — squash-merged to `main` as `54ad963` on 2026-08-15
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

Record sign-up, sign-in, sign-out and token-refresh events — succeeded **and** failed — in a dedicated `security_event_log` table, per the owner's decision of 2026-08-15.

Two constraints from the audit, both binding under any option: no credential, token or cookie value may enter the record ([[CLAUDE|CLAUDE.md]] §16/§25) — task 1's redaction is a backstop, not a licence — and a failed attempt must be recorded **without** becoming an account-existence oracle, the same property `core/errors.py` already protects in its 401 responses.

See [[#FA-06 — the owner's decision, and what was built]] for the requirement-by-requirement account.

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

## FA-06 — the owner's decision, and what was built

**Option B, decided 2026-08-15: a separate `security_event_log` table, completed inside this step rather than carried forward.**

The three options were put to the owner because auditing authentication events cannot go through the existing `AuditService` without changing a documented multi-tenancy decision, and [[CLAUDE|CLAUDE.md]] §34 forbids inventing a schema:

| | Option | What it costs | What it buys |
|---|---|---|---|
| **A** | Make `workspace_id` nullable on `audit_log` | Reverses a documented decision; creates rows no RLS policy can classify | One table, one query path |
| **B** | A separate `security_event_log` table | A new table, RLS model, migration, and a second thing to retain | Keeps `audit_log`'s tenant invariant intact |
| **C** | Structured application logs only | No queryable trail; not an audit record in the §16 sense | No schema change |

**B was chosen** — the only option that records failed attempts *and* leaves `audit_log`'s tenant invariant untouched. A is a multi-tenancy regression traded for convenience; C would close the finding on paper only.

### What the owner required, and where each requirement is met

| # | Requirement | Where it is met |
|---|---|---|
| 1 | Append-only; events may precede a known user or workspace | `b2e94c17a5d3`; both columns nullable |
| 2 | `workspace_id` / `user_id` not required | Nullable, and **no** foreign key on either |
| 3 | Allowlisted event type + minimum metadata | `ck_security_event_log_type_valid`; `ALLOWED_EVENT_TYPES` |
| 4 | Never store secrets or submitted identifiers | `FORBIDDEN_METADATA_KEYS` + `_SECRET_SHAPED_VALUE`, refused at construction |
| 5 | Identical public responses for existing/nonexistent accounts | Record-then-**re-raise**; asserted end-to-end |
| 6 | RLS, default-deny, no tenant read path or endpoint | `ENABLE` + `FORCE` with **no policies at all** |
| 7 | Minimum privileges | `REVOKE ALL`; nothing granted back |
| 8 | Immutable after insert, except retention | `BEFORE UPDATE` trigger that raises |
| 9 | The approved 90-day retention | Same `audit_retention_days` setting as FA-07 |
| 10 | Disposable PostgreSQL only | CI's `postgres:17` container; shared Supabase never touched |

**The oracle is closed four independent ways** — no column can hold an identifier (not even a hash, which is an oracle to anyone who can compute it over a guess); `user_id` is null on every failure by CHECK constraint *and* by the record type; `record_failure` has no parameter that could carry an identity; and the public response is unchanged because both `sign_in` and `refresh` re-raise.

**One limit is recorded rather than papered over.** A bare password has no shape — no regex will ever catch `hunter2`. The value pattern is a backstop; the key allowlist and an API with nowhere to put a password are the actual control, and a test asserts exactly that.

## Validation

Observed, not assumed. Every check names its instrument, and every fix to a control carries a **negative control** proving the test fails without it.

| # | Check | Instrument | Outcome |
|---|---|---|---|
| 1 | A connection-URI password is **absent** from an emitted log record | Executed probe reproducing the FA-05 scenario | **PASS** — executed probe |
| 2 | Removing the new redaction pattern makes that test **fail** | Negative control | **PASS** — 10 failures without it |
| 3 | A key-shaped credential (`*_KEY`, `*_SECRET`, `*_TOKEN`, `*_PASSWORD`) is redacted | Executed probe | **PASS** — executed probe |
| 4 | Already-redacted lines are not degraded by the new patterns | Executed probe on the existing bearer-token cases | **PASS** — bearer cases unchanged |
| 5 | Restore drill completes: schema **and** per-workspace data match the source | Executed on a **disposable** database | **PASS** — executed in CI |
| 6 | The restore target was a separate empty database, and no shared Supabase data was touched | Command record | **PASS** — separate empty DB; guard refuses Supabase |
| 7 | `downgrade base` then `upgrade head` both succeed; the resulting schema matches | Executed on a **disposable** database | **PASS** — executed in CI |
| 8 | The root boundary's retry triggers a refresh, not a bare `reset()` | Unit test + observed against a real API outage | **PASS** — observed 1 → 2 server requests |
| 9 | The root boundary carries `role="alert"` and announces | Test + assistive-technology check | **PASS** — observed `alert` node |
| 10 | A locally-skipped isolation suite produces a **visible** banner naming the omitted count | Executed offline run | **PASS** — observed, names 306 |
| 11 | The offline suite still passes without PostgreSQL | Executed run with no test database | **PASS** — 479 passed offline |
| 12 | Sign-up, sign-in, sign-out and refresh — succeeded and failed — are recorded | Executed test, CI database | **PASS** — failed at import first (`ModuleNotFoundError`) |
| 13 | No credential, token, cookie or identifier reaches a stored row | Executed test | **PASS** — 7 fake sentinels absent from the serialized table |
| 14 | A failed attempt is not an account-existence oracle | Executed test | **PASS** — closed 4 ways; failure rows indistinguishable |
| 14a | Removing the key allowlist or the value pattern re-opens the leak | Negative control | **PASS** — each proven load-bearing |
| 14b | RLS default-deny: SELECT/INSERT/UPDATE/DELETE/TRUNCATE all refused | Executed test, request-path role | **PASS** — `InsufficientPrivilege` on all five |
| 14c | Rows are immutable even over the privileged connection | Executed test | **PASS** — trigger raises; row unchanged |
| 14d | Security-event retention purges at the 90-day boundary | Executed test | **PASS** — 91d deleted, 89d and 1d kept |
| 14e | Concurrent inserts remain independent | Executed test | **PASS** — two open transactions, neither blocked |
| 15 | Audit events older than 90 days are purged; newer ones are retained | Executed test | **PASS** — boundary pinned both ways |
| 16 | The retention window is configurable, not hard-coded | Executed test | **PASS** — `PROJECTONE_AUDIT_RETENTION_DAYS` |
| 17 | Full API and web suites pass, with **no new skips** | `pytest` and `vitest` | **PASS** — API 479, web 261; no new skips |
| 18 | Lint, format and type-check clean in both apps | Ruff, mypy strict, ESLint, `tsc` | **PASS** — all clean |
| 19 | Governance documents in sync | `./scripts/sync-governance-docs.sh --check` | **PASS** — in sync |
| 20 | **Required CI green, with the database-backed suite executing** | Check runs on the PR head; `PROJECTONE_REQUIRE_DATABASE_TESTS` keeps a skip red | **PASS** — all three checks green on the final head `458476c`, and again on the merge commit `54ad963` |
| 21 | `governance docs (sync check)` is **verified** as a required check | Ruleset or PR observation (task 9) | **PASS** — ruleset `20714051` read via API |

## Manual Checklist

- [x] **Done, by injected fault rather than a stopped API.** The authenticated routes need credentials this environment does not hold, so the outage was reproduced by throwing from a Server Component — the same path the root boundary catches. Observed: the boundary rendered, the retry produced a real server request (1 → 2 in the dev-server log), and with the fault cleared a single click reached the fully recovered page with no reload. The injection was reverted and the tree confirmed byte-identical.
- [x] **Done, via the rendered accessibility tree** — which is what a screen reader consumes. The tree shows `alert` wrapping the heading, message, retry control and reference. Not verified with a screen reader itself.
- [x] **Done.** `error-boundary-retry.test.ts` passes unchanged for all four; the root fix added a file rather than altering the shared `useErrorRecovery` they depend on.
- [x] **FA-06 confirmed.** Authentication events are recorded in `security_event_log`, and the public sign-in response is byte-identical for an existing and an unknown account — the property that makes recording a failure safe at all. See [[#FA-06 — the owner's decision, and what was built]].
- [x] **Done.** 479 passed, 306 skipped, banner last on screen naming the omitted count. The run still passes — the skip is deliberately not a hard local failure.
- [x] **Done.** The root boundary renders friendly copy plus an opaque digest and never `error.message` or a stack — asserted by test and observed in the rendered tree. FA-05 additionally closes the *log* path a connection string could reach.

## Definition of Done

- [x] **All nine closed** — FA-05, FA-02, FA-03, FA-04, FA-11, FA-01, FA-06, FA-07 and FA-08, each proven by execution. Nothing was closed that was not proven.
- [x] **FA-05 verified by negative control.** 16 tests failed before the fix, including the end-to-end probe showing the plaintext password in the emitted record. Each of the three rules was then deleted from `_REDACTIONS`, turning the suite red (10, 5 and 2 failures).
- [x] **FA-03 restore drill executed and PASSES** on a disposable database in CI, verifying schema *and* per-workspace data across two workspaces, restored into a separate empty database. [[Backup and Disaster Recovery]] records the proven capability and marks RPO/RTO **provisional, owner decision required** — per the instruction not to invent a production SLA.
- [x] **FA-02 cycle executed and PASSES** on a disposable database in CI, comparing the twice-migrated schema against the once-migrated one. Runs on every pull request. Its first two failures were defects in the drill — it compared system-generated `NOT NULL` constraint names that embed the table OID and so cannot survive a recreate. The downgrade path was sound; the measurement was not.
- [x] **The shared Supabase development database was never a target.** Never connected to, read from or written to. Both drills refuse `supabase.co`, RDS and Azure hosts before opening a connection — verified by running them against such URLs.
- [x] **FA-08 verified.** Ruleset `20714051` (`Protect main`, active, updated 2026-08-11) lists the check among its required status checks. The owner had already made the change, so no owner action is outstanding; the stale workflow comment is corrected and a rename guard added.
- [x] [[Foundation Audit Findings]] updated: all nine closures carry their evidence; the eight deferred findings remain `Open`.
- [x] Documentation updated: [[Backup and Disaster Recovery]], [[Table - audit_log]] and [[Build Plan]] Current State. **[[Compliance and Governance]] deliberately not edited** — its audit statement is a principle that stays true, and the concrete retention window belongs with the table that implements it rather than duplicated (§19: link, do not duplicate).
- [x] API **493 passed**, 320 skipped (the pre-existing FA-01 gap, now visible; the 14 added skips are FA-06's database-backed tests, which run in CI); web **261 passed**. Ruff, ruff format, mypy strict, ESLint zero-warning, `tsc --noEmit` and the production build all clean.
- [x] **Required CI green on the final branch head `458476c` and again on the merge commit `54ad963`**: `api`, `web` and `governance docs (sync check)` all `success`. This run is also FA-02's, FA-03's and FA-06's proof — both drills execute as steps of the `api` job and both passed, and the `Test` step runs with `PROJECTONE_REQUIRE_DATABASE_TESTS` set, which turns a skipped database test into a failure. FA-06's 14 database-backed assertions therefore genuinely executed.
- [x] **Complete.** Every manual-checklist item is confirmed.
- [x] Every review conversation resolved.
- [x] **Owner review complete.** No decisions were left outstanding: FA-06's shape was decided (option B) and built inside the step rather than carried forward.
- [x] **Squash-merged by the owner** as `54ad963`, and the branch deleted — one step, one branch, one commit on `main`.
- [x] **[[STEP-26 Product Design System and Screen Blueprints]] was not expanded by this step**, and remains `Not Started | outline`. Expanding it is the next step's work, not this one's.

### Owner approval gate

**This step is Critical** ([[CLAUDE|CLAUDE.md]] §21). It touches security controls (FA-05, FA-06), the database schema (FA-07), infrastructure and CI configuration (FA-02, FA-08), and backup/recovery (FA-03) — four categories on the Critical list, any one of which would qualify alone.

It also carries the consequence that created it: **FA-05 is Critical and blocks progression to design**, so [[STEP-26 Product Design System and Screen Blueprints]] does not begin until this step is `Done` and approved.

## Merged outcome — 2026-08-15

**Squash-merged to `main` as `54ad963`**, branch `step-25a-foundation-remediation` deleted. Seventeen branch commits became one commit on `main`, per [[Branch and Pull Request Workflow]].

| | |
|---|---|
| Pull request | [#7](https://github.com/ruseduard321-prog/ProjectOne/pull/7) |
| Final branch head | `458476c` |
| Merge commit on `main` | `54ad963` |
| Findings closed | **9 of 9** — FA-01, FA-02, FA-03, FA-04, FA-05, FA-06, FA-07, FA-08, FA-11 |
| Deferred, still `Open` | FA-09, FA-10, FA-12 – FA-17 (eight, to [[STEP-28 Full Product Verification Polish and Hardening]] or a later remediation) |

### Validation on `main` after the merge

Re-run against the merged tree rather than carried over from the branch, because the squash is a different commit and a claim about the branch is not a claim about `main`:

| Check | Result |
|---|---|
| API suite | **493 passed**, 320 skipped |
| Web suite | **261 passed** (22 files) |
| Ruff lint / format | clean |
| mypy (strict) | clean, 75 source files |
| `tsc --noEmit` | clean |
| Governance sync | **in sync** — `CLAUDE.md` and `AGENTS.md` both match their vault originals |
| Alembic | single linear head `b2e94c17a5d3`, 19 revisions |
| Required CI on `54ad963` | `api`, `web`, `governance docs (sync check)` all **success** |

### One regression was found by reviewing the step's own diff

`sign_out` had been narrowed from `AccessTokenDep` to `CurrentUserDep` while adding its FA-06 audit record. The two differ exactly where it matters: the former requires a bearer token to be *present*, the latter requires it to *verify*. Supabase's `/logout` revokes the whole session including the refresh token, so a caller with an expired access token could sign out before the change and received a 401 after it — leaving their refresh token alive until it expired on its own.

Caught in review, not by CI: **there was no sign-out test at all**, so the suite passed with the defect present. Fixed on the branch before merge (`458476c`), with the endpoint behaviour proven either side of the fix and a regression test pinning it. Recorded here because "the tests were green" was not what protected this, and the next reader should know that.

### What this step does not claim

- The database-backed proofs (FA-02, FA-03, and FA-06's schema, RLS, immutability, retention and concurrency assertions) execute **in CI only** — no local PostgreSQL was available. They run on every pull request against a disposable `postgres:17` container.
- **RPO and RTO remain unset and are the owner's to define** — see [[Backup and Disaster Recovery]]. Restore *capability* is proven; the objectives are business commitments, not drill measurements.
- The FA-06 and FA-07 retention purges are implemented and tested but **not yet scheduled**.

---

## Navigation

- **Previous:** [[STEP-25 Foundation Audit and Internal Readiness]]
- **Next:** [[STEP-26 Product Design System and Screen Blueprints]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Foundation Audit Findings]] · [[Execution Protocol]] · [[CLAUDE|CLAUDE.md]]
