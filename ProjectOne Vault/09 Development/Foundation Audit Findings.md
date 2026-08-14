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

**This is an audit record, not a remediation plan.** Nothing here was fixed. Every disposition is a *recommendation* awaiting the project owner's decision, and every severity is *proposed* rather than settled ([[STEP-25 Foundation Audit and Internal Readiness#Severity Model]]).

> [!warning] Audit environment limitation
> The audit machine has **no local PostgreSQL, no Docker and no `psql`/`pg_dump`**. Under D1 and execution rules 6-7, every verification requiring a disposable database is recorded as **unproven** rather than approximated. This affects RLS negative controls, migration downgrade execution, and the restore drill.
>
> The shared Supabase development database was **never** connected to, read from, or written to during this audit.

## Summary

| Severity | Count | Identifiers |
|---|---|---|
| **Critical** | 0 | none |
| **High** | 5 | FA-01, FA-02, FA-03, FA-04, FA-05 |
| **Medium** | 8 | FA-06 to FA-13 |
| **Low** | 4 | FA-14 to FA-17 |

**No Critical finding was identified.** No reachable cross-tenant path, authentication bypass, secret exposure or unbounded-spend path was found. That statement is bounded by the environment limitation above: the RLS *negative controls* that would make the isolation claim conclusive could not be executed here.

### Classification of controls

| Class | Areas |
|---|---|
| **Verified sound** | Static RLS coverage (14/14 tables enabled and forced), migration linearity, secret hygiene in source and history, error-envelope and 401/403 separation, AI execution ceilings, credential redaction for bearer tokens and API keys, production exclusion of the dev session page, full lint/type/test suites green |
| **Confirmed defects** | Root error boundary retry (FA-04), database-URL password reaching logs (FA-05), root boundary missing alert role (FA-11), audit retention unbounded (FA-07), authentication events unaudited (FA-06) |
| **Unproven** | RLS negative controls (FA-01), migration downgrades (FA-02), backup/restore (FA-03) |
| **Accepted / deferred** | Per-worker rate limiter, MFA/OAuth, single-workspace limitation, AI crash window, dashboard stubs, idempotency keys, Project Bible draft status |

---

## Findings

### FA-01

- **Area:** Multi-tenancy and RLS
- **Severity:** High *(proposed)*
- **Affected location:** `apps/api/tests/` — 306 skipped tests, including `test_rls_isolation.py`, `test_chat_isolation.py`, `test_ai_spend_isolation.py`, `test_project_isolation.py`, `test_provider_credential_isolation.py`
- **Evidence:** Full suite run on the audit machine: **428 passed, 306 skipped, 0 failed** (`pytest -q`). Every skip reports the identical cause — `PROJECTONE_TEST_DATABASE_URL is not set`. **41.7% of the API suite did not execute here.** Static analysis of all 18 migrations confirms RLS is enabled *and* forced on all 14 tables with 39 policies total, but presence is not denial: the negative controls that prove a policy actually refuses could not run.
- **Consequence:** Tenant isolation is *evidenced* but not *proven* on this machine. The proof exists only in CI, whose PostgreSQL 17 service container sets the variable. A developer running the suite locally receives a green result that silently omits every isolation test — the exact false-pass shape [[STEP-09 Row Level Security Policies]] warned about.
- **Recommended disposition:** Accept the CI run as the authoritative isolation proof, and treat a local green result as incomplete. Consider making a missing test database a hard failure locally, as it already is in CI.
- **Owner decision:** _pending_
- **Status:** Open

### FA-02

- **Area:** Database integrity and migrations
- **Severity:** High *(proposed)*
- **Affected location:** `apps/api/migrations/versions/` (18 files)
- **Evidence:** Static analysis confirms a **strictly linear** history (no branch points) and a non-empty `downgrade()` body in **all 18** migrations. No downgrade was *executed*, because doing so requires a database and none is safely available.
- **Consequence:** Reversibility is asserted by inspection, not demonstrated. A downgrade that fails only at runtime — a dropped object another migration depends on, an ordering error — would be invisible to this audit.
- **Recommended disposition:** Execute a full downgrade-to-base then upgrade-to-head cycle against the CI service container, and consider adding it as a CI step.
- **Owner decision:** _pending_
- **Status:** Open

### FA-03

- **Area:** Backup and restore
- **Severity:** High *(proposed)*
- **Affected location:** [[Backup and Disaster Recovery]]; audit environment
- **Evidence:** No `pg_dump`, no `psql`, no Docker, no local PostgreSQL (ports 5432 and 5433 both closed). The restore drill D1 requires **could not be performed**, and per D1's own instruction it was **not simulated**. Separately, [[Backup and Disaster Recovery]] states RPO and RTO *should be defined* and **defines no actual values**.
- **Consequence:** ProjectOne has **no demonstrated ability to restore from backup**, and no numeric recovery objective to restore against. This is the single largest unproven guarantee in the Foundation.
- **Recommended disposition:** Owner decision required — D1 mandates a stop here. Likely its own numbered step: provision a disposable PostgreSQL, execute a schema-plus-data restore drill, and give [[Backup and Disaster Recovery]] real RPO/RTO numbers.
- **Owner decision:** _pending_
- **Status:** Open

### FA-04

- **Area:** Incomplete product behaviour / reliability
- **Severity:** High *(proposed)*
- **Affected location:** `apps/web/src/app/error.tsx`
- **Evidence:** Carried forward from [[STEP-24 Dashboard]] and re-confirmed by reading the file. The root boundary wires its button to `reset` directly. All four route boundaries instead call `useErrorRecovery(reset)` from `lib/error-recovery.ts`. Calling `reset()` alone clears client state and re-renders the **cached** payload, which still contains the failure.
- **Consequence:** The root boundary's "Try again" control does not recover. It is the boundary [[STEP-16b Auth Refresh Outage Handling]] depends on for outage recovery — a route-level boundary cannot catch a failure in the layout that wraps it — so the product's stated recovery path for an API outage is inert. STEP-16b's manual checklist recorded "a working retry control" against this wiring.
- **Recommended disposition:** One-line fix using the existing `useErrorRecovery`. **Not performed here** (D4). Owner decides whether it becomes a remediation step before [[STEP-26 Product Design System and Screen Blueprints]].
- **Owner decision:** _pending_
- **Status:** Open

### FA-05

- **Area:** Security — log redaction
- **Severity:** High *(proposed)*
- **Affected location:** `apps/api/app/core/logging.py`
- **Evidence:** Executed probe against the real `redact()` and `RedactingFilter`. Bearer tokens, authorization headers, and password/api-key/secret/token key-value shapes all redact correctly. But a **PostgreSQL connection URI carrying an inline password does not** — the string returns unchanged. An end-to-end probe attaching the filter to a handler and calling `logger.exception()` on a failed `psycopg.connect(...)` produced a log record **containing the plaintext password**, because the traceback renders the source line holding the URI. The BYOK encryption key in KEY=value form is likewise unmatched.
- **Consequence:** A database connection failure — precisely the scenario [[DOC-02 Validate the Request-Path Credential at Startup]] describes as reachable via a rotated or wrong credential — can write a live database password into application logs. Rated High rather than Critical because no evidence was found that this has occurred, the value is a database credential rather than a tenant secret, and reaching it requires a connection-time exception.
- **Recommended disposition:** Add a URI-password pattern and a key-shaped pattern to the redaction set. Not performed here.
- **Owner decision:** _pending_
- **Status:** Open

### FA-06

- **Area:** Security / observability
- **Severity:** Medium *(proposed)*
- **Affected location:** `apps/api/app/services/audit_service.py`
- **Evidence:** No sign-in, sign-out or failed-authentication event appears in the audit service. Confirmed by search; the gap is also acknowledged in [[Build Plan]]'s Current State, which assigns it to this step.
- **Consequence:** The most security-relevant events in the product leave no audit trail. A credential-stuffing attempt or a suspicious session would be unreconstructable after the fact.
- **Recommended disposition:** Own numbered step, or fold into whichever step next touches authentication.
- **Owner decision:** _pending_
- **Status:** Open

### FA-07

- **Area:** Security / data retention
- **Severity:** Medium *(proposed)*
- **Affected location:** `audit_log` table; `apps/api/app/services/audit_service.py`
- **Evidence:** No retention, purge, prune or expiry mechanism exists for `audit_log`. [[CLAUDE|CLAUDE.md]] §16 requires audit logs to be retained on a **stated** schedule, disclosed as a bounded legal exception to deletion — not retained indefinitely by default.
- **Consequence:** Audit retention is unbounded, so the documented exception to user erasure is unbounded too. A compliance gap against §16's own wording, and it grows without limit.
- **Recommended disposition:** Owner sets a retention period; implement a scheduled purge. The period is a business and legal decision, not an engineering one.
- **Owner decision:** _pending_
- **Status:** Open

### FA-08

- **Area:** Tests and CI
- **Severity:** Medium *(proposed)*
- **Affected location:** `.github/workflows/ci.yml`; the `Protect main` ruleset
- **Evidence:** The workflow's own comment states the governance-docs job is **not** among the ruleset's required checks, so it can be red while the merge button stays green. Three jobs exist: governance docs (sync check), web (lint, typecheck, test, build), and api (lint, format, typecheck, test).
- **Consequence:** Drift between the canonical vault governance documents and the repository-root `CLAUDE.md` / `AGENTS.md` — the files the agent harnesses actually read — can reach `main` unblocked.
- **Recommended disposition:** Owner adds the governance-docs check to the required checks. Only the owner can change the ruleset.
- **Owner decision:** _pending_
- **Status:** Open

### FA-09

- **Area:** Documentation
- **Severity:** Medium *(proposed)*
- **Affected location:** [[Build Plan]] Current State; [[STEP-09 Row Level Security Policies]]; [[STEP-10 Authentication Backend]]
- **Evidence:** All three state or rely on the repository being **private**, and use that to explain why CI results cannot be observed from the build environment. The owner confirmed on 2026-08-15 that the repository is **public**.
- **Consequence:** A stale premise that has repeatedly justified deferring CI confirmation to the owner. A future session reading it would reach the same wrong conclusion.
- **Recommended disposition:** Correct the three notes. **Not repaired here** (D7 — recorded only).
- **Owner decision:** _pending_
- **Status:** Open

### FA-10

- **Area:** Documentation
- **Severity:** Medium *(proposed)*
- **Affected location:** `ProjectOne Vault/05 Architecture/Schema/`
- **Evidence:** 11 `Table - *` notes document **14** existing tables. Missing: **conversations**, **messages**, **workflow_step_runs**.
- **Consequence:** Three tables — two of them holding user message content — have no canonical schema documentation, so [[Schema Overview]] understates the data model a future engineer must reason about.
- **Recommended disposition:** Create the three notes. **Not created here** (D7).
- **Owner decision:** _pending_
- **Status:** Open

### FA-11

- **Area:** Accessibility
- **Severity:** Medium *(proposed)*
- **Affected location:** `apps/web/src/app/error.tsx`
- **Evidence:** All four route error boundaries carry an alert role. The root boundary carries **no role attribute** at all. All five loading skeletons correctly carry a status role.
- **Consequence:** When the root boundary renders — the outage path from [[STEP-16b Auth Refresh Outage Handling]] — a screen-reader user receives no announcement that an error occurred. Compounds FA-04 on the same file.
- **Recommended disposition:** Add the alert role alongside the FA-04 fix. Feeds [[STEP-26 Product Design System and Screen Blueprints]]'s accessibility rules.
- **Owner decision:** _pending_
- **Status:** Open

### FA-12

- **Area:** AI spend / observability
- **Severity:** Medium *(proposed)*
- **Affected location:** `apps/api/app/services/ai_spend_service.py`
- **Evidence:** Anomaly detection is genuinely implemented — a 7-day baseline, a 10x multiplier and a noise floor below which it does not fire. On trip it emits a **log line only**. No alerting channel, notification or dashboard consumes it.
- **Consequence:** [[CLAUDE|CLAUDE.md]] §15a requires *automatic alerting* on sharp deviation. A log line nobody watches satisfies the detection half and not the alerting half — a runaway spend would be recorded and unnoticed.
- **Recommended disposition:** Route to a real alerting channel when observability infrastructure lands.
- **Owner decision:** _pending_
- **Status:** Open

### FA-13

- **Area:** API contracts / reliability
- **Severity:** Medium *(proposed)*
- **Affected location:** `apps/api/app/routers/`; the AI turn path
- **Evidence:** Two related gaps, both previously recorded and re-confirmed. **Idempotency keys are unbuilt** — `POST /workspaces` is the first endpoint that could use them. **The AI crash window** from [[STEP-23 AI Chat End to End]] leaves a turn stranded after a provider charge, visibly stuck rather than silently retried.
- **Consequence:** A retried request can double-charge or double-create. [[Build Plan]] already records that closing the crash window properly constrains every future AI call.
- **Recommended disposition:** The ADR covering provider-side idempotency, stale-claim reconciliation, lease policy and crash-window handling is a **named prerequisite before the next AI feature**. **Not drafted here** (D5). Not blocking STEP-26/27, which are design and UI work.
- **Owner decision:** _pending_
- **Status:** Open

### FA-14

- **Area:** Architecture / technical debt
- **Severity:** Low *(proposed)*
- **Affected location:** `packages/`, `infrastructure/`
- **Evidence:** Both remain empty placeholders after 28 steps.
- **Consequence:** The modular-services principle ([[CLAUDE|CLAUDE.md]] §7) is currently carried entirely by discipline inside two applications. No code is shared, so no coupling has formed — but nothing structurally enforces the boundary either.
- **Recommended disposition:** Accept for now. Revisit when a second consumer of shared logic appears.
- **Owner decision:** _pending_
- **Status:** Open

### FA-15

- **Area:** Documentation / vault integrity
- **Severity:** Low *(proposed)*
- **Affected location:** Vault-wide
- **Evidence:** Measurement reproduced with Obsidian path-resolution semantics: **26 unresolved occurrences across 11 targets**. Of these, **23 across 9 targets are remediable** — 21 are Engineering Handbook chapter shorthand (a link to `Security Standards` where the note is `Chapter 09 - Security Standards`), one is a stale step title (`STEP-11a Membership Lifecycle Repair`, now `STEP-11a Membership Removal Policy`), and one is a bare `Skills` folder reference. The remaining **3 are intentional prose examples** inside [[Skills/Documentation Keeper|Documentation Keeper]] which **must remain unchanged**.
- **Consequence:** Navigation friction only. Confirms the D6 framing exactly.
- **Recommended disposition:** Batch-fix the 23; never touch the 3. **Not repaired here** (D7).
- **Owner decision:** _pending_
- **Status:** Open

### FA-16

- **Area:** Documentation
- **Severity:** Low *(proposed)*
- **Affected location:** [[ADR Template]]; `apps/api/app/core/config.py`
- **Evidence:** Two standing tasks re-confirmed open. [[DOC-01 Align ADR Template with CLAUDE.md]] — the template's status vocabulary lacks `Review` and `Rejected`. [[DOC-02 Validate the Request-Path Credential at Startup]] — `REQUEST_DATABASE_URL` is validated for presence and never for correctness.
- **Consequence:** DOC-01 risks a rejected decision leaving no record. DOC-02 turns a bad credential into a first-request 500 rather than a startup failure — and, per FA-05, one that can log the password.
- **Recommended disposition:** DOC-02 gains urgency from FA-05; consider handling them together.
- **Owner decision:** _pending_
- **Status:** Open

### FA-17

- **Area:** Incomplete product behaviour
- **Severity:** Low *(proposed)*
- **Affected location:** Product-wide
- **Evidence:** Catalogue of every deliberately-shipped limitation, all disclosed rather than hidden: the dashboard's stub sections; the **in-process, per-worker rate limiter** (N workers permit N times the per-user allowance); **MFA and OAuth deferred** since STEP-10 and still unscheduled; the **single-workspace limitation**, disclosed in the interface on three screens; the **pessimistic AI pricing placeholder**; every Project Bible note still `status: draft` at v0.1; and **[[Billing]] absent** from the 28 steps.
- **Consequence:** None individually. Recorded so the set is visible in one place rather than distributed across 28 step notes.
- **Recommended disposition:** Accept. Each is a known, documented trade-off.
- **Owner decision:** _pending_
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

## Proposed remediation order

Ordering only — **nothing here is scheduled, and no step was created** (execution rule 4).

1. **FA-03** — backup/restore is the largest unproven guarantee, and D1 already mandates an owner stop.
2. **FA-05** — a credential can reach logs; cheap to fix and pairs naturally with DOC-02 (FA-16).
3. **FA-04 + FA-11** — one file, two defects, one small change; the inert retry is the recovery path STEP-16b depends on.
4. **FA-01 + FA-02** — prove isolation and reversibility against the CI container.
5. **FA-06 + FA-07** — authentication auditing and a retention period; both need an owner policy decision.
6. **FA-08** — one ruleset change, owner-only.
7. **FA-09 + FA-10 + FA-15** — documentation batch.
8. **FA-13** — the AI ADR, before the next AI feature rather than before STEP-26.
9. **FA-12, FA-14, FA-16, FA-17** — as infrastructure and priorities allow.

---

## Navigation

- **Previous:** [[STEP-25 Foundation Audit and Internal Readiness]]
- **Next:** —
- **Parent:** [[Development MOC]]
- **Related Notes:** [[STEP-25 Foundation Audit and Internal Readiness]] · [[Build Plan]] · [[CLAUDE|CLAUDE.md]]
