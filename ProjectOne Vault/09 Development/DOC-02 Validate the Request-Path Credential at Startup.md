---
title: DOC-02 Validate the Request-Path Credential at Startup
category: Development
status: draft
version: "1.0"
last_updated: 2026-08-03
tags: [engineering, backlog, observability, security]
aliases: ["DOC-02", "Startup Credential Validation"]
---

# DOC-02 — Validate the Request-Path Credential at Startup

**A backlog item, not a [[Build Plan]] step.** It is small, it is not a
prerequisite for anything scheduled, and inserting it into the plan would push
every later step's number for a change that takes one function. The owner
decides whether it becomes a step or is folded into whichever step next touches
`app/core/config.py`.

**Raised by the project owner on 2026-08-03**, after the incident described
below cost most of a session.

## The problem

`REQUEST_DATABASE_URL` is validated for **presence** at startup and for
**correctness** never. A wrong password, a wrong host, a dropped role or a
rotated credential all produce the identical symptom: the API starts cleanly,
reports itself healthy, and then fails on the **first request that touches a
tenant table** — with a `psycopg.OperationalError` that surfaces as a 500.

This is exactly the failure mode [[Environment and Secrets]] and
[[CLAUDE|CLAUDE.md]] §28a say configuration validation exists to prevent:

> A missing or malformed required variable stops the process with a message
> naming the variable — it never surfaces as a confusing failure at first use,
> hours later, in a request handler.

The variable is checked against that standard. The **credential it contains** is
not.

## What made it expensive

Observed during the STEP-17 environment reconciliation:

- `FATAL: password authentication failed for user "projectone_api"` appeared on
  a request, not at boot, so the process that started successfully was not the
  process that revealed the fault.
- The privileged connection (`DATABASE_URL`) worked normally throughout, so
  migrations, health checks and every non-tenant route behaved perfectly. Only
  the multi-tenancy path was broken, and that is the path with the fewest
  smoke-test-shaped signals.
- Root-cause analysis had to rule out a project reset, a wrong database, rolled
  back migrations and the test harness before reaching the actual cause. A
  startup check would have named it in one line.

The role is created without a password by design (`d7b95c1f4e08` — a credential
in a migration is a credential in source control), so the pairing between the
role's password and `.env` has **no committed source of truth and no automated
consistency check**. That is correct on the security merits and is precisely why
it needs a runtime check.

## What to build

A startup probe in `get_settings()` or the application factory, alongside the
existing `PROJECTONE_TRUSTED_PROXIES` and `PROJECTONE_BYOK_ENCRYPTION_KEY`
validations:

1. Open a connection using `REQUEST_DATABASE_URL`.
2. Assert it authenticates.
3. Assert `current_user` is the expected role.
4. **Assert `rolbypassrls` is false.** This is the higher-value half. A
   request-path connection that authenticates *and* bypasses RLS is worse than
   one that cannot connect at all — it serves every tenant's rows while
   everything looks healthy ([[RLS Policy Pattern]]).
5. Exit with a message naming the variable, in the established format.

## The decisions the owner has to make

Neither is Claude's to settle, which is part of why this is a note rather than a
commit:

- **Does the API refuse to start, or warn loudly?** Refusing is consistent with
  every other check in `get_settings()` and catches the fault at the earliest
  possible moment. It also makes the database a hard startup dependency: a brief
  database outage during a deploy would turn a rolling restart into an outage of
  its own. A warning inverts both trade-offs.
- **Does it run in every environment?** A startup probe adds a connection to
  every process start, including tests and CI.

A reasonable default, offered as a recommendation rather than a decision:
**fail closed in development and staging, warn in production** — inverted from
the usual instinct, because production is where a hard startup dependency on the
database is most dangerous and where monitoring already exists to surface a
warning.

## Related

The same reasoning extends to `SUPABASE_SECRET_KEY`, which has the identical
shape: validated for presence, proven only when a user first tries to sign in.
Worth considering in the same change rather than as a third round.

---

## Navigation

- **Parent:** [[Development MOC]]
- **Related Notes:** [[Environment Setup]] · [[Environment and Secrets]] · [[RLS Policy Pattern]] · [[STEP-17 AI Router and Provider Abstraction]] · [[DOC-01 Align ADR Template with CLAUDE.md]]
