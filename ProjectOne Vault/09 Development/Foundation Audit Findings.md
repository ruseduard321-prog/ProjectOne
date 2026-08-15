---
title: Foundation Audit Findings
category: Development
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, audit, security, quality, governance]
aliases: ["Audit Findings", "STEP-25 Findings"]
---

# Foundation Audit Findings

The findings record produced by [[STEP-25 Foundation Audit and Internal Readiness]], covering STEP-01 through STEP-24 plus the four inserted steps.

**This is an audit record, not a remediation plan.** Nothing here was fixed by [[STEP-25 Foundation Audit and Internal Readiness]].

**Severities were reviewed and settled by the project owner on 2026-08-15** ([[STEP-25 Foundation Audit and Internal Readiness#Severity Model]]). Remediation is scheduled as [[STEP-25a Foundation Remediation]], which runs between STEP-25 and [[STEP-26 Product Design System and Screen Blueprints]] — no fix in this record has been implemented yet.

> [!warning] Audit environment limitation
> The audit machine has **no local PostgreSQL, no Docker and no `psql`/`pg_dump`**. Under D1 and execution rules 6-7, every verification requiring a disposable database is recorded as **unproven** rather than approximated.
>
> **This is not the same as unverified.** CI runs a disposable PostgreSQL 17 service container, and the isolation suite is proven to execute there ([[#FA-01]]). Migration downgrades ([[#FA-02]]) and the restore drill ([[#FA-03]]) have no such proof anywhere and remain genuinely unproven.
>
> The shared Supabase development database was **never** connected to, read from, or written to during this audit.

## Summary

| Severity | Count | Identifiers |
|---|---|---|
| **Critical** | 1 | FA-05 |
| **High** | 3 | FA-02, FA-03, FA-04 |
| **Medium** | 9 | FA-01, FA-06 to FA-13 |
| **Low** | 4 | FA-14 to FA-17 |

**One Critical finding.** FA-05 — a reachable path writes a plaintext database password into logs. Raised to Critical by the owner on 2026-08-15 under the model's secret-exposure test, and it **blocks progression to design** until remediated.

**Tenant isolation is proven, in CI.** Verified rather than inferred on 2026-08-15 — see FA-01 below. No reachable cross-tenant path or authentication bypass was found, and no unbounded-spend path exists.

> [!note] Owner review applied 2026-08-15
> Severities below reflect the owner's review decisions. FA-05 was raised to Critical; FA-01 was reduced to Medium and reframed after CI evidence proved the isolation tests execute. FA-07 and FA-08 carry owner decisions. Remediation is scheduled as [[STEP-25a Foundation Remediation]], which runs **before** [[STEP-26 Product Design System and Screen Blueprints]].

### Classification of controls

| Class | Areas |
|---|---|
| **Verified sound** | **Tenant isolation, proven in CI** (FA-01 evidence), static RLS coverage (14/14 tables enabled and forced), migration linearity, secret hygiene in source and history, error-envelope and 401/403 separation, AI execution ceilings, credential redaction for bearer tokens and API keys, production exclusion of the dev session page, full lint/type/test suites green |
| **Confirmed defects** | **Database-URL password reaching logs (FA-05 — Critical)**, root error boundary retry (FA-04), root boundary missing alert role (FA-11), audit retention unbounded (FA-07), authentication events unaudited (FA-06) |
| **Unproven** | Migration downgrades (FA-02), backup/restore (FA-03). **FA-01 is no longer in this class** — isolation is proven in CI; only local reproduction is missing. |
| **Accepted / deferred** | Per-worker rate limiter, MFA/OAuth, single-workspace limitation, AI crash window, dashboard stubs, idempotency keys, Project Bible draft status |

---

## Findings

### FA-01
- **Area:** Multi-tenancy and RLS — local developer-environment verification gap
- **Severity:** Medium *(owner-assigned 2026-08-15, reduced from the proposed High)*
- **Affected location:** `apps/api/tests/conftest.py`; developer environments without PostgreSQL
- **Evidence — tenant isolation IS proven, in CI.** Verified on 2026-08-15 rather than inferred:
  - Check runs on PR head `37b4d27`: **`api (lint, format, typecheck, test)` — `completed` / `success`** (run id `94922696090`). All three jobs green; `web` and `governance docs (sync check)` also `success`.
  - The API job runs a **disposable `postgres:17` service container** (`.github/workflows/ci.yml`), pinned to the same major version as the development project, and sets `PROJECTONE_TEST_DATABASE_URL` against it.
  - The job also sets **`PROJECTONE_REQUIRE_DATABASE_TESTS: '1'`**. In `tests/conftest.py`, the `migrated_database` fixture reads that flag and, when the database URL is absent, calls **`pytest.fail(...)`** — *"The RLS isolation tests must run here — refusing to skip them silently"* — instead of `pytest.skip`.
  - Therefore **a green API job is only reachable if the database-backed tests actually executed**. A skipped isolation suite would have turned the job red. The job is green, so the RLS and tenant-isolation tests ran against real PostgreSQL, with **zero database skips**.
  - A separate pre-flight step asserts the container is reachable and exits non-zero otherwise, so a broken container cannot masquerade as a healthy one.
  - Job logs could not be downloaded (`403: Must have admin rights to Repository`), so the pass is established from the fail-closed mechanism plus the green conclusion rather than from a pytest summary line. That chain is deterministic, not probabilistic.
- **Consequence:** Isolation is **verified**. What remains is narrower: **a developer machine without PostgreSQL runs a suite that silently omits 306 of 734 tests and still reports green.** Locally the flag is unset, so the same fixture takes the `pytest.skip` branch. The risk is a contributor believing a local green run covers isolation when it does not — a false-confidence gap, not an unproven control.
- **Recommended disposition:** Close the local gap so the omission is visible: print a prominent summary banner when the isolation suite is skipped, and document the one-line invocation for running it against a disposable container. Scheduled in [[STEP-25a Foundation Remediation]].
- **Owner decision:** **Reclassified Medium on 2026-08-15.** *"Do not conflate 'cannot run locally' with 'not verified anywhere.'"* Isolation is proven in CI; this is a developer-environment verification gap.
- **Status:** **Closed 2026-08-15** — **Closed** by [[STEP-25a Foundation Remediation]] (commit `8d49fe1`). An end-of-run banner in `tests/conftest.py` names the omitted count, states that isolation *is* proven in CI so the wording does not overstate the gap, and gives the one-line invocation for a disposable container. Observed: a full offline run reports **306 database-backed tests were NOT run** as the last thing on screen, and still passes — the skip is deliberately not a hard local failure.


### FA-02
- **Area:** Database integrity and migrations
- **Severity:** High *(owner-approved 2026-08-15)*
- **Affected location:** `apps/api/migrations/versions/` (18 files)
- **Evidence:** Static analysis confirms a **strictly linear** history (no branch points) and a non-empty `downgrade()` body in **all 18** migrations. No downgrade was *executed*, because doing so requires a database and none is safely available.
- **Consequence:** Reversibility is asserted by inspection, not demonstrated. A downgrade that fails only at runtime — a dropped object another migration depends on, an ordering error — would be invisible to this audit. **No complete downgrade verification exists anywhere**, including CI: the API job applies migrations forward to set the schema up and never exercises the reverse direction. Unlike FA-01, there is no other environment in which this is already proven, which is why it stays High.
- **Recommended disposition:** Execute a full downgrade-to-base then upgrade-to-head cycle against the CI service container, and consider adding it as a CI step.
- **Owner decision:** **Accepted 2026-08-15 — High retained.** No complete downgrade verification exists anywhere, including CI. Scheduled in [[STEP-25a Foundation Remediation]] (task 5).
- **Status:** **Closed 2026-08-15 — proven by execution in CI.** `scripts/migration_cycle_drill.py` executes `upgrade head` → `downgrade base` → `upgrade head` against a disposable `postgres:17` container and compares the twice-migrated schema against the once-migrated one across tables, columns, constraints, indexes, RLS flags, policies and functions. **It passes.** Wired into the `api` job, so reversibility is re-proven on every pull request rather than asserted once.
  - *Worth recording:* the drill's first two runs failed on a defect in **the drill**, not in the migrations. It compared PostgreSQL's system-generated `NOT NULL` constraint names (`2200_<oid>_<attnum>_not_null`), which embed the table OID and therefore cannot survive a drop-and-recreate by construction. Nullability is still verified through `columns.is_nullable`, which is the property that actually matters. **The downgrade path was sound all along** — the measurement was wrong, which is its own lesson about drills that have never run.

### FA-03
- **Area:** Backup and restore
- **Severity:** High *(owner-approved 2026-08-15)*
- **Affected location:** [[Backup and Disaster Recovery]]; audit environment
- **Evidence:** No `pg_dump`, no `psql`, no Docker, no local PostgreSQL (ports 5432 and 5433 both closed). The restore drill D1 requires **could not be performed**, and per D1's own instruction it was **not simulated**. Separately, [[Backup and Disaster Recovery]] states RPO and RTO *should be defined* and **defines no actual values**.
- **Consequence:** ProjectOne has **no demonstrated ability to restore from backup**, and no numeric recovery objective to restore against. This is the single largest unproven guarantee in the Foundation.
- **Recommended disposition:** Owner decision required — D1 mandates a stop here. Likely its own numbered step: provision a disposable PostgreSQL, execute a schema-plus-data restore drill, and give [[Backup and Disaster Recovery]] real RPO/RTO numbers.
- **Owner decision:** **Accepted 2026-08-15 — High retained.** Remediation must establish an **executed** backup/restore drill on a disposable PostgreSQL environment, never shared Supabase data. Scheduled in [[STEP-25a Foundation Remediation]] (task 2).
- **Status:** **Closed 2026-08-15 — restore proven by execution.** `scripts/backup_restore_drill.py` runs in the `api` job on every pull request against a disposable `postgres:17` container: it applies migrations to head, seeds **two workspaces**, takes a `pg_dump` backup, restores into a **separate empty database**, and verifies schema *and* data — tables, columns, constraints, RLS enabled *and* forced, policy count, the Alembic revision pointer, and row content per tenant. **It passes.** Two workspaces deliberately: one proves the rows returned, two prove they returned attached to the right tenant. A separate target equally so — restoring over the source would pass on an empty dump.
  - *Getting here took three corrections, all to the drill rather than to ProjectOne:* a seed omitting `projects.created_by` (`NOT NULL`, no default); a constraint comparison including OID-derived system names; and `pg_dump` 16 shadowing the version-17 client the workflow installs, which needed the versioned directory prepended to `PATH`.
  - **The drill refuses `supabase.co`, RDS and Azure hosts before connecting.** The shared Supabase development database was never a target.

### FA-04
- **Area:** Incomplete product behaviour / reliability
- **Severity:** High *(owner-approved 2026-08-15)*
- **Affected location:** `apps/web/src/app/error.tsx`
- **Evidence:** Carried forward from [[STEP-24 Dashboard]] and re-confirmed by reading the file. The root boundary wires its button to `reset` directly. All four route boundaries instead call `useErrorRecovery(reset)` from `lib/error-recovery.ts`. Calling `reset()` alone clears client state and re-renders the **cached** payload, which still contains the failure.
- **Consequence:** The root boundary's "Try again" control does not recover. It is the boundary [[STEP-16b Auth Refresh Outage Handling]] depends on for outage recovery — a route-level boundary cannot catch a failure in the layout that wraps it — so the product's stated recovery path for an API outage is inert. STEP-16b's manual checklist recorded "a working retry control" against this wiring.
- **Recommended disposition:** One-line fix using the existing `useErrorRecovery`. **Not performed here** (D4). Owner decides whether it becomes a remediation step before [[STEP-26 Product Design System and Screen Blueprints]].
- **Owner decision:** **Accepted 2026-08-15 — High retained.** Kept separate from FA-11: same file, but a functional defect rather than an accessibility one. Scheduled in [[STEP-25a Foundation Remediation]] (task 3).
- **Status:** **Closed 2026-08-15** — **Closed** by [[STEP-25a Foundation Remediation]] (commit `049456c`). `apps/web/src/app/error.tsx` now recovers through `useErrorRecovery(reset)`. **Verified by observation, not only by test**: with a fault injected into a Server Component, clicking *Try again* produced a real server request (1 → 2 in the dev-server log, where the old wiring produced zero across three clicks), and with the fault cleared a single click took the boundary to the fully recovered page without a reload.

### FA-05
- **Area:** Security — log redaction / secret exposure
- **Severity:** **Critical** *(owner-assigned 2026-08-15, raised from the proposed High)*
- **Affected location:** `apps/api/app/core/logging.py`
- **Evidence:** Executed probe against the real `redact()` and `RedactingFilter`. Bearer tokens, authorization headers, and password/api-key/secret/token key-value shapes all redact correctly. But a **PostgreSQL connection URI carrying an inline password does not** — the string returns unchanged. An end-to-end probe attaching the filter to a handler and calling `logger.exception()` on a failed `psycopg.connect(...)` produced a log record **containing the plaintext password**, because the traceback renders the source line holding the URI. The BYOK encryption key in KEY=value form is likewise unmatched.
- **Consequence:** A database connection failure — precisely the scenario [[DOC-02 Validate the Request-Path Credential at Startup]] describes as reachable via a rotated or wrong credential — can write a live database password into application logs. **The owner raised this to Critical on 2026-08-15**: the severity model's Critical test is *a secret is exposed in ... logs*, and the path is reachable, which settles it regardless of whether it has yet occurred. A logged database password is a credential an operator, a log aggregator, or anyone with log access can read. **This finding blocks progression to design** and is remediated first in [[STEP-25a Foundation Remediation]].
- **Recommended disposition:** Add a URI-password pattern and a key-shaped pattern to the redaction set, with a negative-control test proving the un-redacted form fails. **First item in [[STEP-25a Foundation Remediation]].**
- **Owner decision:** **Critical, 2026-08-15.** *"A reachable path that writes a plaintext database password into logs is a secret-exposure defect and must block progression to design."*
- **Status:** **Closed 2026-08-15** — **Closed** by [[STEP-25a Foundation Remediation]] (commit `8e20702`) — the Critical finding, remediated first. Three named patterns added to `_REDACTIONS`: `_URI_PASSWORD`, `_KEY_SHAPED_ENV` and `_KEY_SHAPED_URL`. The URI rule replaces only the password, keeping scheme, user, host and database so a connection failure stays diagnosable. **Proven by reproduction and negative control**: 16 tests failed first, including the end-to-end probe showing the plaintext password in the emitted record; each rule was then physically deleted from the tuple, turning the suite red (10, 5 and 2 failures respectively).

### FA-06
- **Area:** Security / observability
- **Severity:** Medium *(owner-approved 2026-08-15)*
- **Affected location:** `apps/api/app/services/audit_service.py`
- **Evidence:** No sign-in, sign-out or failed-authentication event appears in the audit service. Confirmed by search; the gap is also acknowledged in [[Build Plan]]'s Current State, which assigns it to this step.
- **Consequence:** The most security-relevant events in the product leave no audit trail. A credential-stuffing attempt or a suspicious session would be unreconstructable after the fact.
- **Recommended disposition:** Own numbered step, or fold into whichever step next touches authentication.
- **Owner decision:** **Accepted 2026-08-15 — Medium.** Scheduled in [[STEP-25a Foundation Remediation]] (task 7), with the constraint that a failed attempt must not become an account-existence oracle.
- **Status:** **Open — BLOCKED on an owner decision.** [[STEP-25a Foundation Remediation]] could not close this without inventing a schema, which [[CLAUDE|CLAUDE.md]] §34 forbids. `audit_log` is deliberately tenant-scoped: `workspace_id` is `NOT NULL` with a `RESTRICT` foreign key, `actor_id` is `NOT NULL`, and the RLS policy filters on `workspace_id IN app_current_user_workspaces()`. Migration `a3c07d5e91f4` states the reasoning outright — *a nullable tenant column on a tenant-scoped table is a row that no policy can classify*. **Authentication events have neither column.** `sign_in` receives only an email and a password; there is no workspace until one is selected, and a *failed* attempt has no authenticated actor and may name no existing account at all. Storing them therefore requires one of: **(a)** making `workspace_id` nullable, reversing a documented multi-tenancy decision; **(b)** a separate `security_event_log` table with its own RLS model; or **(c)** structured application logs only, with no new table. Each is a schema or multi-tenancy change and therefore **Critical** under §21, requiring the owner's decision before implementation. See [[STEP-25a Foundation Remediation#FA-06 owner decision required]].

### FA-07
- **Area:** Security / data retention
- **Severity:** Medium *(owner-approved 2026-08-15)*
- **Affected location:** `audit_log` table; `apps/api/app/services/audit_service.py`
- **Evidence:** No retention, purge, prune or expiry mechanism exists for `audit_log`. [[CLAUDE|CLAUDE.md]] §16 requires audit logs to be retained on a **stated** schedule, disclosed as a bounded legal exception to deletion — not retained indefinitely by default.
- **Consequence:** Audit retention is unbounded, so the documented exception to user erasure is unbounded too. A compliance gap against §16's own wording, and it grows without limit.
- **Recommended disposition:** Implement a **90-day** retention policy with a scheduled purge, made configurable before public release, and test the deletion/retention behaviour rather than only implementing it. Scheduled in [[STEP-25a Foundation Remediation]].
- **Owner decision:** **Set on 2026-08-15 — initial audit-event retention is 90 days, configurable before public release.** The remediation must define deletion/retention behaviour *and* test it.
- **Status:** **Closed 2026-08-15** — **Closed** by [[STEP-25a Foundation Remediation]] (commit `c196438`). 90 days via `PROJECTONE_AUDIT_RETENTION_DAYS`, configurable rather than hard-coded. Zero means *retain indefinitely* and never reaches a `DELETE`; a negative window is rejected at startup, since it would place the cutoff in the future and expire every row. The purge is a filtered `DELETE` over the privileged connection, never `TRUNCATE`. 15 tests pin the boundary in both directions; removing the `WHERE` clause turns the guard red. [[Table - audit_log]] updated.

### FA-08
- **Area:** Tests and CI
- **Severity:** Medium *(owner-approved 2026-08-15)*
- **Affected location:** `.github/workflows/ci.yml`; the `Protect main` ruleset
- **Evidence:** The workflow's own comment states the governance-docs job is **not** among the ruleset's required checks, so it can be red while the merge button stays green. Three jobs exist: governance docs (sync check), web (lint, typecheck, test, build), and api (lint, format, typecheck, test).
- **Consequence:** Drift between the canonical vault governance documents and the repository-root `CLAUDE.md` / `AGENTS.md` — the files the agent harnesses actually read — can reach `main` unblocked.
- **Recommended disposition:** Add `governance docs (sync check)` to the `Protect main` ruleset's required checks. This is an **owner-operated repository-setting action** that Claude cannot perform, and it must be **verified before [[STEP-25a Foundation Remediation]] can complete**.
- **Owner decision:** **Approved on 2026-08-15 — the governance-docs job must become a required main-branch check.** Recorded as an owner-operated setting change, verified as part of STEP-25a's Definition of Done.
- **Status:** **Closed 2026-08-15** — **Closed** by [[STEP-25a Foundation Remediation]] (commit `284f29a`) — **verified, and no owner action is outstanding**. The `Protect main` ruleset (id `20714051`, `active`, updated 2026-08-11) lists `governance docs (sync check)` among its required status checks alongside `web` and `api`. The owner had already made the change; the workflow comment claiming otherwise was stale and is corrected. A new test guards the rename hazard the verification exposed: the ruleset matches on the literal check name, so renaming the job would silently remove the gate.

### FA-09
- **Area:** Documentation
- **Severity:** Medium *(owner-approved 2026-08-15)*
- **Affected location:** [[Build Plan]] Current State; [[STEP-09 Row Level Security Policies]]; [[STEP-10 Authentication Backend]]
- **Evidence:** All three state or rely on the repository being **private**, and use that to explain why CI results cannot be observed from the build environment. The owner confirmed on 2026-08-15 that the repository is **public**.
- **Consequence:** A stale premise that has repeatedly justified deferring CI confirmation to the owner. A future session reading it would reach the same wrong conclusion.
- **Recommended disposition:** Correct the three notes. **Not repaired here** (D7 — recorded only).
- **Owner decision:** **Accepted 2026-08-15 — Medium.** Deferred out of STEP-25a to [[STEP-28 Full Product Verification Polish and Hardening]] or a later owner-approved remediation.
- **Status:** Open

### FA-10
- **Area:** Documentation
- **Severity:** Medium *(owner-approved 2026-08-15)*
- **Affected location:** `ProjectOne Vault/05 Architecture/Schema/`
- **Evidence:** 11 `Table - *` notes document **14** existing tables. Missing: **conversations**, **messages**, **workflow_step_runs**.
- **Consequence:** Three tables — two of them holding user message content — have no canonical schema documentation, so [[Schema Overview]] understates the data model a future engineer must reason about.
- **Recommended disposition:** Create the three notes. **Not created here** (D7).
- **Owner decision:** **Accepted 2026-08-15 — Medium.** Deferred out of STEP-25a to [[STEP-28 Full Product Verification Polish and Hardening]] or a later owner-approved remediation.
- **Status:** Open

### FA-11
- **Area:** Accessibility
- **Severity:** Medium *(owner-approved 2026-08-15)*
- **Affected location:** `apps/web/src/app/error.tsx`
- **Evidence:** All four route error boundaries carry an alert role. The root boundary carries **no role attribute** at all. All five loading skeletons correctly carry a status role.
- **Consequence:** When the root boundary renders — the outage path from [[STEP-16b Auth Refresh Outage Handling]] — a screen-reader user receives no announcement that an error occurred. Compounds FA-04 on the same file.
- **Recommended disposition:** Add the alert role alongside the FA-04 fix. Feeds [[STEP-26 Product Design System and Screen Blueprints]]'s accessibility rules.
- **Owner decision:** **Accepted 2026-08-15 — Medium retained.** Kept separate from FA-04: same file, but an accessibility finding with its own proof. Scheduled in [[STEP-25a Foundation Remediation]] (task 4).
- **Status:** **Closed 2026-08-15** — **Closed** by [[STEP-25a Foundation Remediation]] (commit `049456c`). The root boundary's message container now carries `role="alert"`, matching the arrangement all four route boundaries already use. **Verified by observation**: the rendered accessibility tree shows an `alert` node wrapping the heading, message, retry control and reference — the node a screen reader announces, where previously there was no role at all.

### FA-12
- **Area:** AI spend / observability
- **Severity:** Medium *(owner-approved 2026-08-15)*
- **Affected location:** `apps/api/app/services/ai_spend_service.py`
- **Evidence:** Anomaly detection is genuinely implemented — a 7-day baseline, a 10x multiplier and a noise floor below which it does not fire. On trip it emits a **log line only**. No alerting channel, notification or dashboard consumes it.
- **Consequence:** [[CLAUDE|CLAUDE.md]] §15a requires *automatic alerting* on sharp deviation. A log line nobody watches satisfies the detection half and not the alerting half — a runaway spend would be recorded and unnoticed.
- **Recommended disposition:** Route to a real alerting channel when observability infrastructure lands.
- **Owner decision:** **Accepted 2026-08-15 — Medium.** Deferred out of STEP-25a; routed to observability work when an alerting channel exists.
- **Status:** Open

### FA-13
- **Area:** API contracts / reliability
- **Severity:** Medium *(owner-approved 2026-08-15)*
- **Affected location:** `apps/api/app/routers/`; the AI turn path
- **Evidence:** Two related gaps, both previously recorded and re-confirmed. **Idempotency keys are unbuilt** — `POST /workspaces` is the first endpoint that could use them. **The AI crash window** from [[STEP-23 AI Chat End to End]] leaves a turn stranded after a provider charge, visibly stuck rather than silently retried.
- **Consequence:** A retried request can double-charge or double-create. [[Build Plan]] already records that closing the crash window properly constrains every future AI call.
- **Recommended disposition:** The ADR covering provider-side idempotency, stale-claim reconciliation, lease policy and crash-window handling is a **named prerequisite before the next AI feature**. **Not drafted here** (D5). Not blocking STEP-26/27, which are design and UI work.
- **Owner decision:** **Accepted 2026-08-15 — Medium.** Deferred out of STEP-25a. The ADR remains a **named prerequisite before the next AI feature**, which STEP-26 and STEP-27 are not, so it gates neither.
- **Status:** Open

### FA-14
- **Area:** Architecture / technical debt
- **Severity:** Low *(owner-approved 2026-08-15)*
- **Affected location:** `packages/`, `infrastructure/`
- **Evidence:** Both remain empty placeholders after 28 steps.
- **Consequence:** The modular-services principle ([[CLAUDE|CLAUDE.md]] §7) is currently carried entirely by discipline inside two applications. No code is shared, so no coupling has formed — but nothing structurally enforces the boundary either.
- **Recommended disposition:** Accept for now. Revisit when a second consumer of shared logic appears.
- **Owner decision:** **Accepted 2026-08-15 — Low.** Accepted as a documented trade-off; revisit when a second consumer of shared logic appears.
- **Status:** Open

### FA-15
- **Area:** Documentation / vault integrity
- **Severity:** Low *(owner-approved 2026-08-15)*
- **Affected location:** Vault-wide
- **Evidence:** Measurement reproduced with Obsidian path-resolution semantics: **26 unresolved occurrences across 11 targets**. Of these, **23 across 9 targets are remediable** — 21 are Engineering Handbook chapter shorthand (a link to `Security Standards` where the note is `Chapter 09 - Security Standards`), one is a stale step title (`STEP-11a Membership Lifecycle Repair`, now `STEP-11a Membership Removal Policy`), and one is a bare `Skills` folder reference. The remaining **3 are intentional prose examples** inside [[Skills/Documentation Keeper|Documentation Keeper]] which **must remain unchanged**.
- **Consequence:** Navigation friction only. Confirms the D6 framing exactly.
- **Recommended disposition:** Batch-fix the 23; never touch the 3. **Not repaired here** (D7). Carried to [[STEP-28 Full Product Verification Polish and Hardening]] or a later owner-approved remediation — deliberately not folded into STEP-25a.
- **Owner decision:** **Framing approved on 2026-08-15** — 26 detected / 23 remediable across 9 targets / 3 intentional prose examples that remain unchanged.
- **Status:** Open

### FA-16
- **Area:** Documentation
- **Severity:** Low *(owner-approved 2026-08-15)*
- **Affected location:** [[ADR Template]]; `apps/api/app/core/config.py`
- **Evidence:** Two standing tasks re-confirmed open. [[DOC-01 Align ADR Template with CLAUDE.md]] — the template's status vocabulary lacks `Review` and `Rejected`. [[DOC-02 Validate the Request-Path Credential at Startup]] — `REQUEST_DATABASE_URL` is validated for presence and never for correctness.
- **Consequence:** DOC-01 risks a rejected decision leaving no record. DOC-02 turns a bad credential into a first-request 500 rather than a startup failure — and, per FA-05, one that can log the password.
- **Recommended disposition:** DOC-02 gains urgency from FA-05; consider handling them together.
- **Owner decision:** **Accepted 2026-08-15 — Low.** Deferred out of STEP-25a. DOC-02 is explicitly excluded from STEP-25a's scope despite sharing a cause with FA-05, on scope-discipline grounds.
- **Status:** Open

### FA-17
- **Area:** Incomplete product behaviour
- **Severity:** Low *(owner-approved 2026-08-15)*
- **Affected location:** Product-wide
- **Evidence:** Catalogue of every deliberately-shipped limitation, all disclosed rather than hidden: the dashboard's stub sections; the **in-process, per-worker rate limiter** (N workers permit N times the per-user allowance); **MFA and OAuth deferred** since STEP-10 and still unscheduled; the **single-workspace limitation**, disclosed in the interface on three screens; the **pessimistic AI pricing placeholder**; every Project Bible note still `status: draft` at v0.1; and **[[Billing]] absent** from the 28 steps.
- **Consequence:** None individually. Recorded so the set is visible in one place rather than distributed across 28 step notes.
- **Recommended disposition:** Accept. Each is a known, documented trade-off.
- **Owner decision:** **Accepted 2026-08-15 — Low.** Every item accepted as a known, documented trade-off.
- **Status:** Open

---

## Verified — no finding

Recorded with the method that verified them, because an area assessed clean and left blank is indistinguishable from one never examined.

| Area | Result | Method |
|---|---|---|
| RLS static coverage | **14/14 tables** enabled **and** forced, 39 policies | Parsed all 18 migrations; STEP-09's loop form confirmed by reading `860a798d204b` |
| Migration history | **Linear**, no branch points; 18/18 have downgrade bodies | Revision-graph reconstruction |
| Secrets in source | **None.** Only `.env.example` tracked; real env files ignored | `git ls-files` plus `git check-ignore` |
| Secrets in history | **None.** Every match is a fixture, CI throwaway or placeholder | Pattern scan across full history; the committed CI BYOK value decodes to the ASCII string `test-byok-key-32-bytes-long-xxxx` |
| Bearer / API-key redaction | **Works** | Executed probe on `redact()` (contrast FA-05) |
| Error envelope | Uniform detail plus request id; 401/403 deliberately unmergeable; identical messages prevent an existence oracle | Read `core/errors.py`; no raw exception string in any router |
| AI execution ceilings | **All present**: chained-invocation cap (5), wall-clock (300s), token ceiling (500k), retry and fallback ceilings, availability breaker, database-backed spend ceiling and emergency shutdown | Read `ai/governance.py` control table and constants |
| API lint / types | Ruff **clean**; mypy strict **clean, 73 files** | Executed |
| Web lint / types | ESLint **clean** with zero warnings allowed; `tsc --noEmit` **clean** | Executed |
| Web tests | **253/253 passed**, 21 files | Executed |
| Web build | **3/3 succeeded** | Executed |
| Dev session page exclusion | **Absent from the production route manifest** | Inspected the build output |
| Loading skeletons | Status role on **all 5** | Grep across all loading files |
| Route error boundaries | Alert role on **all 4** (root excluded — FA-11) | Grep |
| Duplicate H1 | **No defect** — the two headings per page are mutually exclusive branches | Read `dashboard/page.tsx` at both sites |
| Deletion cascade | Export/erase pair implemented per store; `audit_log` deliberately does not erase and **says so** as a documented legal exception | Read `data_ownership_service.py` |

## Indicative performance baselines

Per **D2**: existing tools only, single-user, local, repeated. **These are indicative, not thresholds.** Formal load, concurrency and release thresholds belong to [[STEP-28 Full Product Verification Polish and Hardening]].

| Measurement | Runs | Observed range |
|---|---|---|
| Web production build | 3 | **11.5 s – 21.2 s** (first run cold) |
| API test suite (428 tests) | 3 | **9.28 s – 9.43 s** |
| Web test suite (253 tests) | 1 | **3.70 s** |
| Client JS shipped | — | **663 KB** across 19 chunks |

No HTTP journey timings were taken: that would require running the application against the shared database, which execution rule 5 makes read-only and rule 12 requires asking about first.

## Remediation outcome — STEP-25a, 2026-08-15

**Eight of the nine scheduled findings are closed and proven by execution. One (FA-06) is blocked on an owner decision.**

| ID | Severity | Outcome | Proof |
|---|---|---|---|
| **FA-05** | **Critical** | **Closed** | Reproduction + three negative controls |
| FA-03 | High | **Closed** | Restore executes and verifies in CI |
| FA-04 | High | **Closed** | Observed recovery, 1 → 2 server requests |
| FA-11 | Medium | **Closed** | Observed `alert` node in the accessibility tree |
| FA-02 | High | **Closed** | Cycle executes and passes in CI |
| FA-01 | Medium | **Closed** | Observed banner, 306 named |
| **FA-06** | Medium | **BLOCKED** | Owner decision required — see the finding |
| FA-07 | Medium | **Closed** | 15 tests, boundary pinned both directions |
| FA-08 | Medium | **Closed** | Ruleset verified via API |

**The Critical finding is closed**, so the consequence that created this step — *FA-05 blocks progression to design* — no longer holds.

> [!important] The drills found their own bugs before they found any of ProjectOne's
> Both drills failed on first execution, and **both failures were defects in the drills themselves**:
>
> - **FA-02** compared PostgreSQL's system-generated `NOT NULL` constraint names, which embed the table OID and cannot survive a drop-and-recreate. Once excluded, the cycle **passes** — the downgrade path was sound all along, and the earlier report that it was "genuinely broken" was wrong.
> - **FA-03** seeded `projects` without `created_by`, a `NOT NULL` column with no default — then hit `pg_dump` 16 shadowing the version-17 client the workflow installs. Both fixed; the drill now **passes**.
>
> Recorded rather than tidied away, because it is the honest lesson of the step: **a drill that has never run is not evidence, and its first failures are as likely to be its own.** That is exactly why FA-02 and FA-03 were High — an untested capability tells you nothing either way.

### Limitations, stated rather than implied

- **FA-02 and FA-03 execute in CI only.** The remediation environment has no Docker, no WSL distribution, no PostgreSQL server and no `pg_dump`, so neither drill could run locally; provisioning one would have meant installing software, which the execution rules make a stop-and-ask. Both run in the `api` job against the disposable `postgres:17` container and **both pass there**, on every pull request. That is a real and repeating proof — but it is CI's, not a local reproduction, and is recorded as such rather than rounded up.
- **FA-04's observation used an injected fault**, not a genuine API outage: reaching the authenticated routes needs credentials this environment does not hold. The injected fault exercises the same code path — a Server Component throwing, caught by the root boundary — and the fault injection was fully reverted, with the working tree confirmed byte-identical to the commit.
- **FA-11 was verified through the rendered accessibility tree**, which is what a screen reader consumes, rather than with a screen reader itself.
- **FA-07's purge is implemented and tested, but nothing schedules it yet.** The mechanism, its configuration and its boundary behaviour are proven; wiring it to a scheduler is deployment work that belongs with the infrastructure it runs on.

## Approved remediation order

**Settled by the owner on 2026-08-15: FA-05 is first.** An active secret-exposure defect outranks a missing capability — a password reaching logs is happening now, whereas absent restore proof is a risk that has not yet materialised.

The binding sequence is [[STEP-25a Foundation Remediation]]'s scope table; this is its summary.

**Scheduled in [[STEP-25a Foundation Remediation]], before design begins:**

1. **FA-05** *(Critical)* — stop the credential reaching logs. First, and blocking.
2. **FA-03** *(High)* — executed restore drill on a disposable PostgreSQL, never shared Supabase data.
3. **FA-04** *(High)* — the inert root retry, the recovery path STEP-16b depends on.
4. **FA-11** *(Medium)* — the root boundary's alert semantics; same file as FA-04, separate finding.
5. **FA-02** *(High)* — a complete downgrade/upgrade cycle against the disposable container.
6. **FA-01** *(Medium)* — make the local skip visible; isolation itself is already proven in CI.
7. **FA-06** *(Medium)* — authentication-event audit coverage.
8. **FA-07** *(Medium)* — 90-day retention with tested deletion behaviour.
9. **FA-08** *(Medium)* — the required-check ruleset change, owner-operated and verified.

**Deferred to [[STEP-28 Full Product Verification Polish and Hardening]] or a later owner-approved remediation** — neither blocking nor small enough to be clearly bounded: FA-09, FA-10, FA-12, FA-13, FA-14, FA-15, FA-16, FA-17.

FA-13's ADR remains a **named prerequisite before the next AI feature**, which STEP-26 and STEP-27 are not.

---

## Navigation

- **Previous:** [[STEP-25 Foundation Audit and Internal Readiness]]
- **Next:** —
- **Parent:** [[Development MOC]]
- **Related Notes:** [[STEP-25 Foundation Audit and Internal Readiness]] · [[Build Plan]] · [[CLAUDE|CLAUDE.md]]
