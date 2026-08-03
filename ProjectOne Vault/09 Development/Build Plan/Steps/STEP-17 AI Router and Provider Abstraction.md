---
title: STEP-17 AI Router and Provider Abstraction
category: Development/Build Step
status: draft
version: "1.2"
last_updated: 2026-08-02
tags: [engineering, workflow, build-step, ai,backend]
step_id: STEP-17
step_status: Done
detail_level: full
---

# STEP-17 — AI Router and Provider Abstraction

**Status:** Done

**Every blocker is resolved and the step is fully verified against a live database.** The schema gap was migrated ([[#Environment reconciliation, 2026-08-03]]); the credential mismatch was root-caused and **automated away** ([[#Credential root cause, 2026-08-03]]); and the connection architecture moved to the Supabase session pooler by owner decision ([[#Connection architecture migration, 2026-08-03]]).

## Environment reconciliation, 2026-08-03

Performed before starting this step, at the owner's instruction, and recorded here because it changed the state of the running system.

### Diagnosis: simply behind

Four readings were tested rather than assumed:

| Reading | Verdict | Evidence |
|---|---|---|
| A different database | **Ruled out** | `DATABASE_URL`, `REQUEST_DATABASE_URL` and `SUPABASE_URL` all resolve to project `pquegalrmmjzhajulhoc` |
| Incorrect configuration | **Ruled out** | Config internally consistent; the privileged connection resolves and the expected roles exist |
| A project reset | **Ruled out** | The database held `step16.confirmed@gmail.com`, created **2026-08-02 21:16** — the [[STEP-16 Sign Up and Sign In UI]] validation user. A reset database could not contain it |
| Rolled-back migrations | **Ruled out** | **Zero** artifacts from any of the three unapplied migrations: no `audit_log` table or index, none of `app_current_user_workspaces_as` / `app_workspace_role` / `app_protect_last_owner`, no last-owner trigger, no privileged-update policy. A rollback leaves partial artifacts; there were none |
| **Simply behind** | **Confirmed** | State was exactly and coherently `d7b95c1f4e08`: STEP-09's 8 policies and helper present, everything after it absent |

**Most likely cause**, offered as explanation rather than established fact: these three migrations were authored and validated against the *test* database (`PROJECTONE_TEST_DATABASE_URL`). [[STEP-11 Authorization and RBAC]]'s Outcome records fixing `migrations/env.py` precisely so a test run could no longer migrate whatever `DATABASE_URL` pointed at — correct, and it also means the development database was never separately advanced.

### Migration

`alembic upgrade head` applied `9f4d2c7a1b83` → `b8e1d94c50a7` → `a3c07d5e91f4`. No errors.

### Structural verification — all passed

| Check | Result |
|---|---|
| `alembic_version` == head | `a3c07d5e91f4` |
| `audit_log` table exists | Yes, RLS **enabled and forced** |
| `app_current_user_workspaces()` | Present |
| `app_current_user_workspaces_as(text[])` | Present |
| `app_workspace_role(uuid)` | Present |
| `app_protect_last_owner()` | Present |
| `trg_workspace_members_protect_last_owner` | Present |
| RLS policies | **9** across four tables |
| RLS enabled **and forced** on `users`, `workspaces`, `workspace_members`, `audit_log` | All four |
| `projectone_api` attributes | `NOBYPASSRLS`, `NOINHERIT` — unchanged from `d7b95c1f4e08` |

The policy set is the STEP-11 generation, not STEP-09's: `workspaces_update_privileged` and `workspace_members_update_privileged` have replaced the earlier role-blind `_same_workspace` update policies, which is what `9f4d2c7a1b83` exists to do.

### Behavioural verification — partial, and why

Structure is not behaviour, so the intent was to prove isolation operationally over the request path. **That could not be completed**, because the request-path credential fails — which is how the password defect was found.

What the attempt did establish, over the privileged connection:

- **`audit_log` enforces a closed action vocabulary.** `ck_audit_log_action_valid` rejected an arbitrary action string, permitting only `workspace.created`, `member.added`, `member.removed`, `member.left`, `ownership.transferred`. An audit trail whose action names cannot be forged into arbitrary values is stronger than one that accepts free text.
- **The schema matches the code's expectations** — `actor_id`, not `actor_user_id`; two wrong guesses were corrected by reading the live schema rather than assuming it.

**All probe rows were removed.** The database now holds exactly what it held before: one user (`step16.confirmed@gmail.com`), zero workspaces, zero memberships, zero audit rows — verified by query, not assumed. Two earlier probe batches under a different prefix were also found and cleaned.

### What remains unproven

~~**Cross-tenant isolation has not been observed against this database at head.**~~ **Closed on 2026-08-03** — see [[#Live verification]]. Isolation is now proven behaviourally over the request-path connection, with a negative control confirming the policies are what enforce it.

**Detail level:** full — expanded by [[STEP-16 Sign Up and Sign In UI]], per [[Execution Protocol]].

## Goal

The provider-agnostic AI Router: BYOK, provider selection, health monitoring, retries and fallback.

## Scope

Routing and abstraction only. Cost governance is STEP-18 and is a hard gate — no AI call reaches a real provider in production until it passes.

## Prerequisites

- [[STEP-16 Sign Up and Sign In UI]] — `Done`, owner-approved 2026-08-03
- [[STEP-12a Trusted Proxy and Per-User Rate Limiting]] — inserted 2026-08-03, runs first
- [[STEP-16a Developer Session Inspector]] — inserted 2026-08-03

## Required Documentation

- [[AI Architecture]]
- [[AI Providers]]
- [[CLAUDE|CLAUDE.md]] §15

## Inherited from earlier steps

Recorded during synchronization, not expansion.

Added by [[STEP-16 Sign Up and Sign In UI]]:

- **The established backend layering is router → service → repository**, with dependency injection through `app/core/dependencies.py`. The AI Router is a *service* with *repositories* per provider; it is not a router in the HTTP sense, and the naming collision is worth avoiding in module names ([[CLAUDE|CLAUDE.md]] §12).
- **Errors are typed and translated centrally.** `app/core/security.py` defines the exception classes, `app/core/errors.py` owns the HTTP mapping in one table. A provider failure gets a new exception type and one entry in that table — never a `try/except` in a route ([[API Conventions]]).
- **Every error body is `{"detail", "request_id"}`.** A provider outage message reaching a user goes through that envelope like everything else.
- **Logging redacts structurally.** A filter on the log handler strips bearer tokens, `Authorization` values, passwords and API keys. **A BYOK provider key is exactly the kind of value that filter exists for** — confirm the redaction patterns cover provider key formats before the first key is logged anywhere, rather than after.
- **No secret is committed.** Provider keys follow [[Environment and Secrets]]; a BYOK key belongs to a workspace and is tenant data, so it is subject to RLS like everything else.
- **`packages/` is still empty.** If the provider abstraction is genuinely framework-agnostic it may belong there, but adding the first shared package is a structural decision — raise it rather than deciding it mid-step ([[CLAUDE|CLAUDE.md]] §8).

## Tasks

1. **Define the provider interface** — one abstraction every provider implements, covering the calls this release actually needs (chat completion at minimum, per [[STEP-23 AI Chat End to End]]). Model it on the capabilities in [[AI Providers]]; do not build for capabilities no scheduled step consumes.
2. **Implement at least two providers** against that interface. Two is the minimum that proves the abstraction is real — a single implementation always fits its own interface.
3. **Build the selection flow** from [[AI Providers]]: user preference → capability → availability → cost → selection. Selection must be *observable* — the decision and its reason are logged, because an unexplained provider choice is a black box ([[CLAUDE|CLAUDE.md]] §15).
4. **Implement retries with a hard ceiling and provider fallback.** Both are [[CLAUDE|CLAUDE.md]] §15a requirements, not enhancements: unbounded retry logic is forbidden anywhere AI spend is involved, and a critical workflow must survive one provider's outage.
5. **Add provider health tracking** so repeated failures take a provider out of rotation rather than being retried indefinitely.
6. **Store BYOK keys as tenant data** — workspace-scoped, RLS-protected in the same migration that creates the table ([[CLAUDE|CLAUDE.md]] §16), encrypted at rest, never returned to a client in full and never logged.
7. **Surface uncertainty honestly.** A failed or degraded call reports what happened; it never returns confident-sounding output over a silent fallback ([[CLAUDE|CLAUDE.md]] §15).

**Explicitly out of scope:** budget ceilings, circuit breakers, spend tracking and anomaly detection — all [[STEP-18 AI Cost Governance Controls]], which is a hard gate before any provider call reaches production. Also out of scope: the BYOK settings UI ([[STEP-19 Settings and BYOK UI]]) and chat itself ([[STEP-23 AI Chat End to End]]).

## Validation

- **Both providers satisfy the interface**, proven by the same test suite running against each rather than by two bespoke suites.
- **Fallback is observed, not assumed** — force the primary provider to fail and confirm the call completes through the secondary, with the switch logged.
- **The retry ceiling is enforced** — a permanently failing provider stops at the limit and does not retry indefinitely. Assert the exact call count.
- **Selection is reproducible and explained** — given the same inputs the same provider is chosen, and the reason is in the log.
- **A BYOK key never appears in a log or an API response**, verified by grepping captured output rather than by review.
- **The keys table has RLS in the migration that creates it**, and a cross-tenant read is proven blocked — following [[RLS Policy Pattern]], with the policies-removed check that STEP-09 established.
- **No provider key is committed**; `.env.example` gains placeholders only.
- Lint, type-check, tests and build pass for `apps/api` in CI.

## Definition of Done

A provider-agnostic AI Router exists with at least two working providers behind one interface; selection follows [[AI Providers]]' documented flow and logs its reasoning; retries are bounded by a hard ceiling and fallback is demonstrated against a forced failure; provider health is tracked; BYOK keys are stored as RLS-protected tenant data, encrypted, and proven absent from logs and responses; and no AI call path reaches production before [[STEP-18 AI Cost Governance Controls]] lands.

**This is a Critical change** ([[CLAUDE|CLAUDE.md]] §21 — AI/agent architecture, database schema, security controls, multi-tenancy). It carries an **owner approval gate**: [[STEP-18 AI Cost Governance Controls]] does not begin until the owner confirms this step.

> [!warning] Cost governance is a gate, not a follow-up
> [[CLAUDE|CLAUDE.md]] §15a is binding on every AI feature, and this step deliberately builds the machinery that *makes calls* before the machinery that *bounds them*. That ordering is only safe because nothing user-facing calls it yet. If any scheduled work would put a real provider call in front of a user before STEP-18 is `Done`, that is a plan problem to raise — not a risk to absorb.

## Credential root cause, 2026-08-03

Investigated at the owner's instruction before any code was written, and recorded because the conclusion changed a documented procedure.

**Where the role is created:** migration `d7b95c1f4e08`, the only place in the repository. It creates `projectone_api` `NOLOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER` and deliberately sets **no password** — a credential in a migration is a credential in source control.

**Where the password is defined:** never in a migration and never in a script. Two places set one, for two different databases — `tests/conftest.py` for the throwaway test database, and the manual out-of-band step in [[Environment Setup]] for the development one.

**The source of truth:** there was none, by design — and that was the defect. The role's password lived only in the database; `REQUEST_DATABASE_URL` lived only in git-ignored `.env`. **Two independent writes with nothing linking them**, so nothing in the repository could detect divergence.

**How it was proven rather than guessed.** The stored SCRAM-SHA-256 verifier was read from `pg_authid` and the `.env` password re-derived against it (PBKDF2 → HMAC "Client Key" → SHA-256). The derivation was first validated against a control role with a known password — reporting `True` for the correct password and `False` for a wrong one — so its verdict was trustworthy. Every plausible variant then failed: as-parsed, URL-unquoted, whitespace-stripped, with a trailing `\r`, lowercased, the admin password, and the conftest test value. The file itself was ruled out too: no BOM, no quoting, no percent-escapes, no trailing whitespace, and `rolvaliduntil` is NULL so nothing had expired.

**Conclusion:** the stored password was a value present in no readable artifact. `.env` was never its source, and a manual `ALTER ROLE` believed to have fixed it on 2026-08-03 had not — a claim accepted without verification at the time, which is the process failure worth recording alongside the technical one.

### The fix: the credential is now generated, never synchronized

`scripts/sync-request-role-credential.py` generates the password, applies it with `ALTER ROLE`, **proves it by opening a new connection as that role** and asserting `rolbypassrls = false`, and only then rewrites `.env`. No human sees or types the value. `--check` verifies agreement without writing.

Two safety properties are deliberate: it **refuses** to touch a role carrying `BYPASSRLS` or `SUPERUSER` (that would mint a request-path credential with no tenant isolation), and it writes `.env` via an atomic rename after verification succeeds — so a failed run leaves the database updated and `.env` untouched, making re-running always safe and always convergent.

## Connection architecture migration, 2026-08-03

**Both connection strings moved to the Supabase session pooler**, by owner decision, after the direct host proved unreachable from both environments.

`db.<project-ref>.supabase.co` publishes an **AAAA record and no A record** — Supabase serves direct connections over IPv6 only, IPv4 being a paid add-on. Verified against three resolvers.

```
postgres.<project-ref>@aws-0-eu-central-1.pooler.supabase.com:5432
projectone_api.<project-ref>@aws-0-eu-central-1.pooler.supabase.com:5432
```

Three details were established by testing, not assumption: the username **must** carry the `<role>.<project-ref>` suffix (bare is rejected); the port **must** be 5432, since transaction mode on 6543 does not support the prepared statements psycopg uses; and the region cannot be inferred from DNS, because every `aws-0-<region>` hostname resolves — it was proven by successful authentication.

**The pooler was not assumed to preserve tenant isolation.** A throwaway probe role confirmed the pooler accepts non-owner roles at all, then every isolation property was re-verified over it. Full detail in [[Environment Setup#The Connection Architecture]].

The application code needed no change: `RequestSessionFactory` already used `SET LOCAL ROLE` and transaction-scoped `set_config`, chosen by [[STEP-10 Authentication Backend]] to stop a caller's identity leaking into the next request on a pooled connection. That decision — made for a different reason — is exactly what pooling requires.

## Live verification

Performed against the development database on 2026-08-03, after the migration above.

| Check | Result |
|---|---|
| `alembic upgrade head` | `a3c07d5e91f4` → **`f1a4c8d29b57`** applied |
| Request-path authentication | ✅ `projectone_api` |
| `rolbypassrls` | ✅ **false** |
| `provider_credentials` RLS | ✅ enabled **and forced** |
| Policies | ✅ 3 — SELECT, INSERT, UPDATE; **no DELETE** |
| Grants to `authenticated` | ✅ `SELECT, INSERT, UPDATE` only |
| `version` column + touch trigger | ✅ present |
| API startup against the pooler | ✅ `/health` 200, `database: healthy` |

### Behavioural RLS — proven over the request path

Two tenants seeded, isolation asserted as `projectone_api` → `SET LOCAL ROLE authenticated`:

| Assertion | Result |
|---|---|
| Alice sees her own credential | ✅ |
| **Alice sees Bob's credential** | ✅ **No** |
| Alice reads Bob's ciphertext | ✅ **No** |
| Alice updates Bob's row | ✅ **0 rows** |
| `DELETE` | ✅ **refused** |

**Negative control:** with RLS disabled, the identical query returned Bob's credential — the breach observed directly. RLS was restored and re-confirmed `enabled=True, forced=True`.

**All probe rows removed**, verified by query: 1 user (the STEP-16 validation account), 0 workspaces, 0 credentials — exactly the prior state.

### Still not run: the pytest isolation suite

`tests/test_provider_credential_isolation.py` (18 tests) remains skipped. It **creates and destroys rows** and its own harness forbids pointing it at anything but a throwaway database, so running it against the development project would be destructive. The behavioural proof above covers the same properties over the same connection; the suite is CI's job, against a service container.

**Unrelated note for the same `.env`:** `PROJECTONE_TRUSTED_PROXIES` is empty, so the API warns at startup. Correct for a bare local API with nothing in front of it; it must be set before `apps/web` proxies to it ([[Infrastructure]]).

## Outcome

Full architectural detail lives in [[AI Router Implementation]]; this records what happened while building it.

### What was built

| Module | Purpose |
|---|---|
| `app/ai/provider.py` | The ABC every provider implements, plus request/response types |
| `app/ai/errors.py` | Failures typed by *retryable vs terminal* |
| `app/ai/health.py` | Availability circuit breaker |
| `app/ai/router.py` | Selection, bounded retries, fallback |
| `app/ai/crypto.py` | AES-256-GCM for keys at rest |
| `app/ai/providers/{openai,anthropic}.py` | Two adapters |
| `app/repositories/provider_credentials.py` | Ciphertext only, over the tenant connection |
| `app/services/provider_credential_service.py` | The only place plaintext exists |
| `app/services/ai_service.py` | Joins credentials to the router |
| `migrations/versions/f1a4c8d29b57_*.py` | The table, its RLS and its grants |

### Defects found and fixed during implementation

Each was caught before it shipped, and each is now guarded by a test:

1. **`touch_row()` would have failed every UPDATE.** The trigger sets `NEW.version = OLD.version + 1`, and the first draft of the migration attached it to a table with no `version` column — so every key rotation and every revocation would have raised *"record new has no field version"*. Found by reading the function rather than assuming its shape. The column was added, along with the `WHEN (OLD.* IS DISTINCT FROM NEW.*)` clause the existing triggers carry. Guarded by `test_the_touch_trigger_maintains_version`.

2. **A cross-tenant key leak in the router's first draft.** `AIRouter` held the key resolver as instance state (`_active_resolver`). The router is constructed once and shared across requests, so two concurrent requests would race and **the loser would resolve a key belonging to the other workspace** — the same class of defect as the pooled-connection claim leak STEP-10 reproduced. Fixed by threading the resolver through as a parameter, which removes the attribute there was to race on. Guarded by `test_one_workspaces_call_never_receives_another_workspaces_key`.

3. **A new required setting broke every existing environment.** Adding `PROJECTONE_BYOK_ENCRYPTION_KEY` as required correctly refused to start without it — and that included the whole test suite and every developer's `.env`. Resolved properly rather than by weakening the requirement: `.env.example` documents it with a generation command, [[Environment Setup]] gained a step, and the eight test call sites share one constant from `conftest.py` so the next required setting is one edit rather than eight.

### Validation performed

Everything not requiring a live database. All observed, not assumed.

| Check | Result |
|---|---|
| `ruff check .` | Clean |
| `ruff format --check .` | 82 files formatted |
| `mypy app/` (strict) | Clean, 49 files |
| `pytest -q` | **212 passed**, 133 skipped (database-backed) |
| Migration module loads, revision chain | `a3c07d5e91f4 -> f1a4c8d29b57 (head)` |
| Migration SQL structure | Balanced, 12 statements, ENABLE+FORCE, 3 policies, no DELETE policy |

Test count rose from 113 to 212. The new suites:

- `test_ai_providers.py` — **40**, one parametrized contract suite run against *both* providers, exactly as the Validation section requires. Adding a third provider is one entry.
- `test_ai_router.py` — **29**, selection, ceilings, fallback, health.
- `test_byok_credentials.py` — **25**, encryption and log redaction.
- `test_ai_service.py` — **5**, tenant scoping.
- `test_provider_credential_isolation.py` — **18**, RLS. *Written, not yet run* — see [[#Live verification handed to the owner]].

### Negative controls

Each defect was introduced deliberately, the failure observed, and the code restored:

| Control | Result |
|---|---|
| Retry ceiling raised to 99 | **3 failed** — exactly the ceiling tests |
| Terminal errors made retryable | **2 failed** — both terminal-error tests |
| Health breaker always reports available | **4 failed** — both selection and tracking tests |
| A key logged in `store()` | **1 failed** — the log-capture test caught it |

All restored; the suite returns to 212 passed.

**One finding worth recording from the fourth control.** The leaked key was logged under the field name `leaked=`, which the redaction filter does not match — so it reached the log unredacted and the test caught it on content rather than on redaction. That is the correct outcome and it confirms what `app/core/logging.py` already says about itself: **the filter is a floor, not a guarantee.** Code must still not pass keys to a logger; the filter exists because the cost of being wrong once is unbounded.

### Deliberately not built

- **No HTTP routes.** The router is reachable only through DI. [[STEP-19 Settings and BYOK UI]] and [[STEP-23 AI Chat End to End]] own the surface, and adding an endpoint here would put a provider call in front of a user before [[STEP-18 AI Cost Governance Controls]] — the gate this step's own warning names.
- **No streaming, embeddings, image generation or tool calling.** No scheduled step consumes them.
- **Not moved to `packages/`.** `app/ai/` is framework-agnostic and could move, but introducing the first shared package is a structural decision for the owner ([[CLAUDE|CLAUDE.md]] §8), and a package with one consumer is indirection without a benefit. The constraint is kept so the option stays open.

### Known limitations

- **Encryption key rotation is unsupported.** Changing `PROJECTONE_BYOK_ENCRYPTION_KEY` makes every stored credential undecryptable and each workspace must re-enter its keys.
- **One deployment-wide encryption key, not per-tenant.** Per-tenant keys need a KMS to be worth anything; storing them beside the ciphertext they protect is theatre. An ADR and infrastructure, not a mid-step improvisation.
- **Health tracking is in-process, per worker** — the same stated approximation as the rate limiter, with the same resolution (a shared store needs its own ADR).
- **Provider costs are hardcoded constants**, not fetched pricing. They make providers comparable; they do not bill.

---

## Navigation

- **Previous:** [[STEP-12a Trusted Proxy and Per-User Rate Limiting]]
- **Next:** [[STEP-18 AI Cost Governance Controls]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[AI Router Implementation]] · [[AI Providers]] · [[RLS Policy Pattern]] · [[DOC-02 Validate the Request-Path Credential at Startup]]
