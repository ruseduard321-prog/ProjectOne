---
title: "ADR-005: Async Job Queue and Worker Execution Model"
category: ADR
status: accepted
version: "1.2"
last_updated: 2026-08-17
tags: [adr, decision, backend, infrastructure, security, workflow, jobs]
adr_number: "0005"
---

# ADR-005: Async Job Queue and Worker Execution Model

## Status

**Accepted** — approved by the project owner on 2026-08-17.

This decision is now binding, and [[STEP-30 Async Job Infrastructure]] may build against it ([[CLAUDE|CLAUDE.md]] §7). **Changing the queue technology, the worker's tenancy mechanism, or the cross-tenant dispatch boundary requires a new ADR that supersedes this one** — this note is not amended in place.

### Final review — 2026-08-17

The owner made acceptance conditional on verifying that the cross-tenant dispatch boundary in §5 is explicitly limited to three things: the `jobs` table only, no privileged connection passed to handlers, and the user's RLS context restored before execution.

**Two of the three were already explicit; the third was not, and v1.2 fixes it.**

| Condition | v1.1 | Action |
|---|---|---|
| `jobs` table only | Explicit — §5 constraint 1 | None |
| No privileged connection passed to handlers | Explicit — §5 constraint 3 | Wording tightened to cover *reachable from* and *held open during*, not only *passed to* |
| User RLS context restored before execution | **Not explicit in §5.** Decided in §4, but never stated in §5 as an ordering guarantee | **Added as §5 constraint 4** |

The third was the one worth checking. §4 established that handlers run under an RLS-subject session, and §5 said the privileged connection is closed before handler code runs — but nothing said the tenant session is opened *before the handler's first statement*. Two correct statements in separate sections are not an ordering guarantee, and the gap between them is exactly where a handler could run with neither connection. v1.2 states it as a constraint and requires the step to prove constraints 1, 3 and 4 by test rather than by inspection.

### Owner review — round 1, 2026-08-17

| # | Decision | Outcome |
|---|---|---|
| 1 | The queue is a **PostgreSQL table** in the existing database, claimed with `FOR UPDATE SKIP LOCKED` (§1) | **Accepted** |
| 2 | **No task framework** is adopted; the job contract is written directly (§2) | **Accepted** |
| 3 | The worker is a **second entrypoint of the API application**, not a new app (§3) | **Accepted** |
| 4 | Tenancy reaches the worker as the **enqueuing user's identity**, replayed through the existing RLS session (§4) | **Accepted** |
| 5 | Dispatch is an explicitly **audited cross-tenant service path**, bounded to the `jobs` table alone (§5) | **Accepted** |
| 6 | Delivery is **at-least-once**, bounded by a lease, with duplicate-safety a stated handler obligation (§6) | **Accepted** |
| 7 | Job attempts per enqueue | **Changed: 3 → 2** |
| 8 | Composed ceiling on upstream provider requests per enqueue | **Changed: 90 → 60** |
| 9 | A job whose actor lost workspace membership before execution | **Accepted — fails permanently** (§4, §7) |
| 10 | Deployment shape: one application image, a separate worker process; **hosting deferred to [[STEP-82 Staging Environment and Deployment Pipeline]]** | **Accepted** |

v1.1 applies decisions 7–10 to the body below. Nothing else changed.

§5 remains the decision most deserving of scrutiny at final review: it is a deliberate, bounded exception to the rule that nothing bypasses RLS.

## Context

`WorkflowRunner` executes every step synchronously inside the HTTP request that started it. A multi-minute render therefore cannot be a workflow: the browser would wait for it, and any timeout between the client and the API would abandon a run that is still spending money. [[STEP-31 Workflow Async Execution]], [[STEP-32 Media Processing Pipeline]] and every long-running capability after them are blocked on this. [[Product Coverage Audit]] records background execution as the second-largest foundation gap.

Four facts about the current codebase shape the decision, and each was read rather than assumed:

**1. The engine is already resumable; only the driver is missing.** `WorkflowRunner` persists state after *each* step and `next_step_index` counts only `completed` steps, so a run identified by its id alone can be continued in a process that did not start it. A job handler is therefore "advance run X from wherever it got to" — the queue drives an existing resumable engine rather than becoming one.

**2. RLS context in ProjectOne is a *user*, not a workspace.** `RequestSessionFactory.authenticated_as` opens a transaction, runs `SET LOCAL ROLE authenticated`, and sets `request.jwt.claim.sub` to the verified user id. Every policy written by `9f4d2c7a1b83` resolves through `app_current_user_workspaces_as`, which reads `auth.uid()` and joins `workspace_members`. **A worker has no request, and therefore has no user** — so whatever carries tenancy into the worker is not an implementation detail, it is the tenant boundary itself.

**3. The request-path role fails closed.** `projectone_api` has `rolbypassrls = false` and `rolinherit = false`. A code path that forgot the role switch reads **nothing** rather than everything. This property is worth preserving in the worker precisely because a worker is where such an omission would go unnoticed by every route test in the suite.

**4. A commit discards the RLS identity.** `SET LOCAL ROLE` and `set_config(..., true)` are transaction-scoped, verified against the live database during STEP-10 and relied upon by migration `c8f1a3d54e29`. That migration also established the shape a durable claim must take: **the claim commits before the expensive call**, because a row locked for the duration of an upstream HTTP request is how a cost control becomes a bottleneck. Those two facts together constrain the worker's transaction structure and are the reason §4 below is written as it is.

Two further facts about the repository, not the code:

- **There is no `infrastructure/` directory beyond a `.gitkeep`.** [[CLAUDE|CLAUDE.md]] §9 specifies one; the only deployment artefact that exists is `.github/workflows/ci.yml`. "Deployed alongside the API" currently has nowhere to be written down.
- **There is no queue dependency of any kind** in `apps/api/pyproject.toml` — no broker, no task library, no Redis client. Whatever is chosen is an addition to the §10 stack table.

### Why this needs an ADR

[[CLAUDE|CLAUDE.md]] §39 requires an ADR for technology choices, infrastructure decisions, and changes to the multi-tenancy model. This is all three simultaneously, and §21 makes it Critical independently — a new execution context where RLS can be lost is the definition of a change to the multi-tenancy model. §21's uncertainty rule would resolve toward an ADR even if the classification were arguable.

The four questions are deliberately answered in **one** ADR rather than four, because they are a single coupled choice. Choosing a broker outside PostgreSQL changes how tenancy can travel; choosing a framework changes who owns the retry ceiling; choosing a deployment shape changes what configuration the tenancy mechanism can rely on. Deciding them separately would mean deciding three of them against assumptions about the fourth.

## Decision

### 1. The queue is a PostgreSQL table in the existing database

Jobs are rows in a `jobs` table in the primary Supabase PostgreSQL database. Workers claim work with a conditional `UPDATE` over `SELECT ... FOR UPDATE SKIP LOCKED`, which PostgreSQL serialises: concurrent workers each receive a different row, and none blocks on another's.

**No new infrastructure service, and no new dependency.** `psycopg` is already a runtime dependency and the only client this needs.

Three properties decide it, in order of weight:

- **Transactional enqueue.** A job is written in the *same transaction* as the row that motivates it. A workflow run and its job commit together or neither exists. Every external broker breaks this: the run commits, the broker publish fails, and the run is permanently stranded in `running` with nothing to advance it — or the publish succeeds, the transaction rolls back, and a worker picks up a job for a run that does not exist. Both failure modes require an outbox pattern to fix, which is a PostgreSQL-backed queue with extra steps.
- **The job table is tenant data, and can be RLS-protected like everything else.** A workspace can be shown its own jobs through exactly the mechanism every other tenant table already uses. A broker's internal state is invisible to the database and to the tenant alike.
- **The claim is SQL this project has already written and proven.** `c8f1a3d54e29` implemented a conditional-UPDATE claim for chat turns and verified it against real PostgreSQL with four concurrent callers: one claimed, three observed and did not. The queue's claim is the same pattern with a lease added.

**Polling, not push, initially.** A worker polls on a bounded interval. Latency is bounded by that interval and the interval is configuration, not code. `LISTEN`/`NOTIFY` would reduce it to near-zero and is **deliberately not adopted here**: it is an optimization, ProjectOne has no measurement showing the poll interval matters, and [[CLAUDE|CLAUDE.md]] §17 requires measurement before optimization. It remains available without a superseding ADR, since it changes latency and not architecture.

**The load question is answered at this product's scale, not a hypothetical one.** ProjectOne's jobs are renders, generations and multi-step workflows — work measured in seconds to minutes, at single-digit or low-double-digit concurrency for the foreseeable future. A partial index on the pending states makes each poll an index scan returning almost nothing. The regime where a database-backed queue genuinely hurts is thousands of short jobs per second, which is not this product and would be visible long before it arrived.

### 2. No task framework is adopted

The job contract — enqueue, claim, execute, record outcome — is written directly in `app/jobs/`, in ProjectOne's own code.

Celery, Dramatiq and RQ are rejected below (§Alternatives). The decisive reason is not weight, it is **ownership of the ceilings**. [[CLAUDE|CLAUDE.md]] §15a requires that every retry ceiling and every execution limit be explicit, bounded and stated. A framework brings its own retry semantics, its own backoff defaults, and its own dead-letter behaviour, configured through its own surface — which means the composed ceiling in §7 below would be a product of two numbers ProjectOne owns and one a library's defaults own. `test_no_ai_call_path_bypasses_governance` exists because this project asserts its governance rather than trusting it, and a framework's retry loop is not assertable in that way without wrapping it until nothing of the framework is left.

The contract is genuinely small: one table, one claim statement, one loop, one handler registry. Writing it directly keeps every §15a ceiling and every RLS decision in code the test suite can reach.

### 3. The worker is a second entrypoint of the API application

The worker runs as `python -m app.jobs.worker` from the **same image, same package and same `Settings`** as the API. It is a second process, not a second application.

It is deliberately **not** `apps/worker/`. The worker needs the same services, repositories, session factory and configuration the API has, and [[CLAUDE|CLAUDE.md]] §8 forbids one app depending on another. The alternatives were to duplicate that code, to introduce an app-to-app dependency, or to extract the entire service and repository layer into `packages/` — a large refactor serving a distinction with no benefit, since the two processes will always deploy from the same commit.

**Configuration is validated at worker startup with the same strictness as the API.** STEP-28 made object storage a startup requirement rather than a first-upload surprise; a worker that touches assets and starts without R2 credentials would reproduce exactly the defect that change removed, one layer deeper and less visible. The worker calls the same `get_settings()` and fails the same way, plus whatever it additionally requires.

**`infrastructure/` is created by [[STEP-30 Async Job Infrastructure]]**, recording the **process model** — that one image is run under two commands, what configuration each process requires, and how a worker is started and stopped. This is the first thing in the repository that requires the directory to exist.

**Which platform actually runs them is deferred to [[STEP-82 Staging Environment and Deployment Pipeline]]**, at the owner's decision on 2026-08-17. STEP-30 owes a deployment shape that is *documented and runnable*, not a hosting choice — that is a separate decision, it has no bearing on any code this step writes, and making it now would be choosing a vendor before there is an environment to run in. What STEP-30 must guarantee is that the worker starts from the same image and validates its configuration as strictly as the API, so whatever platform STEP-82 selects inherits a process that fails at deploy rather than at a user's first job.

**One job at a time per worker process.** The codebase is synchronous throughout — sync FastAPI handlers, sync `psycopg`. Concurrency is achieved by running more worker processes, which is also what makes the claim in §1 load-bearing rather than theoretical. An in-process concurrency model would be the first async code in the repository, introduced in the process where a mistake is least observable.

### 4. Tenancy reaches the worker as the enqueuing user's identity

**A job carries the workspace id *and* the id of the user who enqueued it, both required fields.** The worker establishes tenant context by calling the existing `RequestSessionFactory.authenticated_as(user_id)` — the same code path, the same role switch, the same `request.jwt.claim.sub`, subject to the same policies.

The workspace id on the job is not the security mechanism. It is the *attribution* — what the job is for, what the ledger charges, what the operator filters on. **The security mechanism is the user identity replayed through RLS**, exactly as a request would.

Four consequences follow, and all four are intended:

- **A handler never receives a privileged connection.** It receives repositories built over an RLS-subject session, indistinguishable from the ones a route builds. There is no "the worker is internal so it can use elevated access" path; [[CLAUDE|CLAUDE.md]] §16 forbids that for admin tooling and forbids it here for the same reason.
- **A job whose actor lost workspace membership before execution fails permanently.** Accepted by the owner on 2026-08-17. The policies resolve through `workspace_members` at execution time, so a revoked user's job reads nothing and the handler fails loudly — and that failure is classified **terminal**: no retry, dead-lettered on the first attempt (§7). Retrying it would spend the ceiling re-asking a question whose answer will not change, which is the same reasoning that makes a budget refusal terminal. Work authorized by a membership that no longer exists must not silently complete, and it must not silently keep trying either. Stated here because it is a behaviour someone will otherwise report as a bug; the dead-letter record names the cause, so the operator sees revocation rather than a generic failure.
- **A missed role switch fails closed, in the worker too.** This is the whole reason for reusing `authenticated_as` rather than writing a worker-specific session: `rolinherit = false` means the failure mode of forgetting is *reading nothing*, not reading everything.
- **The transaction structure is dictated by fact 4 in the Context.** The claim commits before the handler runs, so the long work executes with no transaction open and no row locked. The handler then opens **short, discrete RLS-scoped transactions** for each unit of database work — the same split across two boundaries that STEP-23 applied across two requests. A single long transaction spanning a multi-minute render would hold a connection, hold locks through an upstream call, and is exactly what `c8f1a3d54e29` rejected.

**System-originated jobs are out of scope and explicitly undecided.** Every job this ADR contemplates originates from a request made by an authenticated user, so an enqueuing user always exists. [[STEP-74 Workflow Scheduling and Triggers]] introduces jobs with no user, and the actor those run as is a decision that step must make with its own ADR. Inventing a service identity now — before there is a caller to shape it — is precisely the speculative architecture [[CLAUDE|CLAUDE.md]] §35 forbids, and a hastily-chosen one would become the platform's most privileged principal.

### 5. Dispatch is an audited cross-tenant service path, bounded to one table

There is one irreducible cross-tenant operation in any queue: **a worker must find the next job before it knows whose job it is.** The dispatch query cannot be RLS-scoped, because the identity that would scope it is the answer the query returns. This is stated here rather than buried, because [[CLAUDE|CLAUDE.md]] §16 requires cross-tenant access to be justified and documented via ADR before it is built.

The exception is bounded by five constraints, all of which the step must implement and prove:

1. **One table.** The dispatcher reads and updates `jobs` and nothing else. It never joins to a tenant table and never returns tenant data — it returns a job id, a workspace id, a user id, a job type and an opaque payload.
2. **Three statements, not a connection.** Claim, extend lease, record outcome. The privileged path is a small, single-purpose repository, in the same shape and for the same stated reason as `AISpendRepository`: a control that must work whether or not any particular caller can see the row.
3. **The handler never sees it.** The dispatcher hands the handler an identity, not a connection. **No privileged connection is passed to, reachable from, or held open during handler code.** It is closed when the claim commits.
4. **The user's RLS context is established before execution begins.** This is the positive half of constraint 3, and it is an *ordering guarantee*, not merely an available mechanism: between the claim committing and the handler's first statement, the worker opens a session through `RequestSessionFactory.authenticated_as(user_id)` (§4). **A handler is never invoked outside a tenant-scoped session.** A job whose identity cannot be established — a revoked membership, a user that no longer exists — fails terminally at this point and never reaches the handler at all (§7).
5. **Every claim is logged** with job id, job type, workspace id, worker id and correlation id — an audited path, per §16, not a raw query that skips RLS because it is internal.
6. **The `jobs` table still carries RLS**, in the same migration that creates it (§13, §16). A workspace reads its own jobs through policy; the dispatcher's privileged access is the exception, and the exception does not remove the rule.

**These six constraints are the boundary, and [[STEP-30 Async Job Infrastructure]] must prove constraints 1, 3 and 4 by test rather than by inspection** — an architectural test that the dispatcher's module reaches no tenant table, and a test that fails if a handler is ever handed a connection that is not RLS-subject. A boundary asserted only in prose is a boundary the next handler's author can cross without noticing.

### 6. Delivery is at-least-once, bounded by a lease

**At-least-once, stated in the job contract's own docstring** rather than implied. A handler author who has to infer the delivery guarantee will infer the convenient one.

A claimed job holds a **lease** with an expiry. A worker executing a long job extends it periodically; a worker that dies stops extending, and the job becomes eligible again once the lease lapses. This is what prevents a crashed worker from holding a job forever — the failure `c8f1a3d54e29` deliberately left unsolved for chat turns, and which a general queue cannot leave unsolved.

**What happens on lease expiry is stated plainly, because it is the sharp edge:** the job becomes claimable while the original worker may still be running it. That is the at-least-once case, it is unavoidable without distributed consensus, and every handler is written to survive it.

**A lease recovery consumes an attempt.** A worker crash-looping on a job that kills the process would otherwise be unbounded — the one shape where "the process died so it does not count" produces an infinite loop with no error to observe.

**The handler obligation is a rule, not a hope.** Duplicate delivery must not duplicate effects. For the workflow handler this is nearly free: `next_step_index` counts completed steps, so a second delivery resumes where the first reached. **It is not free for any handler with an external side effect.** `c8f1a3d54e29`'s finding is the binding precedent: a duplicate that reaches an AI provider is charged twice, and deduplicating the stored result afterwards prevents a duplicate row, never a duplicate bill. Any handler performing a non-idempotent external action must guard it with its own durable claim in the same shape, and the job lease is not a substitute for one.

### 7. Retry, dead-lettering, and the composed ceiling

**Retries are classified before they are counted.** Not every failure deserves a retry, and retrying the wrong one spends money on a settled "no":

- **Terminal — no retry, dead-letter immediately.** Every `GovernanceError` (budget exceeded, spend breaker open, emergency shutdown, execution limit exceeded), every `WorkflowError`, and **every authorization failure — including the revoked-membership case in §4**. A budget refusal retried is the refusal repeated; a tripped ceiling retried is the ceiling not being a ceiling; a revoked membership retried is a permission check re-asked of a database that will keep answering no. This mirrors the `RetryableProviderError` / `TerminalProviderError` split `AIRouter` already applies one layer down.
- **Retryable — bounded, then dead-lettered.** Transient infrastructure failures, unexpected exceptions, and lease recoveries.

**Handlers declare their retry ceiling explicitly.** There is no default that silently permits work — an omitted ceiling is a configuration error at registration, not a job that quietly retries forever.

**The composed ceiling, as arithmetic.** Three retry layers now exist, and [[CLAUDE|CLAUDE.md]] §15a's worst case is reached not by anyone removing a limit but by three reasonable limits multiplying. The product is stated here, and belongs in the code as a named constant with this arithmetic beside it:

| Layer | Ceiling | Source |
|---|---|---|
| Provider attempts per provider | 3 | `DEFAULT_MAX_ATTEMPTS_PER_PROVIDER` |
| Providers in the fallback chain | 2 | `DEFAULT_MAX_PROVIDERS_TRIED` |
| → **upstream requests per `complete()`** | **6** | STEP-17 |
| Chained AI invocations per run execution | 5 | `DEFAULT_MAX_CHAINED_INVOCATIONS` |
| → **upstream requests per run execution** | **30** | 5 × 6 |
| Job attempts per enqueue | **2** | set by the owner, 2026-08-17 |
| → **upstream requests per enqueue** | **60** | 2 × 5 × 6 |

**60 is the accepted ceiling**, reduced from the 90 that v1.0 proposed. The owner's reasoning is the one this ADR should have reached on its own: two attempts is what a retry ceiling is *for* — it absorbs a transient failure and refuses to keep paying for a persistent one. A third attempt buys the case where a fault clears on exactly the second retry, which is rare, and costs 30 more upstream provider requests every time it does not.

It is the true bound, not the expected case: a resumed run does not re-execute completed steps, so the realistic figure is far lower — but a ceiling stated optimistically is not a ceiling. Two adjacent bounds hold independently and are not multiplied away: `ExecutionBudget`'s 300-second wall clock and 500,000-token limits apply per run execution, and `AISpendService`'s per-workspace spend ceiling applies across everything. **The retry ceiling bounds wasted work; the spend ceiling bounds cost.** Both are required, and neither substitutes for the other.

**Raising any layer means recomputing this product.** That is why the number belongs in the code as a named constant with the arithmetic beside it rather than as three unrelated settings — a future change that lifts job attempts from 2 to 4 is a change from 60 to 120, and the person making it should see that before merging it, not after an invoice.

Note that a resumed run receives a **fresh** `ExecutionBudget` — the runner documents this deliberately, so a run paused overnight for approval does not fail on elapsed wall-clock time. That is why job attempts multiply rather than share the run's allowance, and it is why the job attempt ceiling is low.

**A dead-lettered job is an observability event, not a status.** [[CLAUDE|CLAUDE.md]] §26 is explicit that a system which can fail in a way nobody notices is an observability gap. Dead-lettering emits a logged event carrying job id, type, workspace, attempt count and last error; the row records the same, and both are inspectable without attaching a debugger. Correlation ids travel from the enqueuing request into the worker's logs, or an async failure cannot be traced to what caused it.

## Consequences

**What becomes easier**

- Long-running work becomes expressible at all. [[STEP-31 Workflow Async Execution]] onward are unblocked.
- Async execution inherits the tenant model rather than reinventing one — a handler's database access is indistinguishable from a route's, so the isolation guarantees transfer without a second set of proofs.
- The Build Plan gains a deployment home. `infrastructure/` finally exists, and §9's specified structure stops being aspirational.

**What becomes harder, and what this costs**

- **The primary database takes queue load.** Poll frequency and index behaviour become part of the design rather than a later tuning exercise. If job volume ever reaches a regime where this hurts, migrating to a broker is a superseding ADR — made easier, not harder, by the fact that the job contract is ProjectOne's own rather than a framework's.
- **A second process must be deployed, configured and monitored.** Two process types share one image and one configuration surface, but a worker that is not running is a platform where nothing finishes and nothing errors. Worker liveness becomes a §26 monitoring requirement, not an assumption.
- **One documented cross-tenant path now exists.** §5 bounds it tightly, but it exists, and every future reader must be able to find the boundary. That is why it is a numbered decision in an ADR rather than a comment in a repository.
- **A third retry layer is added to a system that already had two.** The 60 in §7 is the honest cost of that. Anyone raising one layer must recompute the product, which is why the arithmetic lives beside the constant.
- **Handler authors inherit an obligation.** Every future handler must be duplicate-safe. Documented in the contract's docstring and enforced by review, since it is not a property a type can carry.

## Scope Boundaries

This ADR records the decisions above and **introduces no others**. Specifically, it does not decide:

- **The `jobs` table's columns, indexes or state vocabulary.** Schema detail belongs to [[STEP-30 Async Job Infrastructure]]'s migration, reviewed under §13.
- **Workflow integration.** STEP-30 ships the infrastructure and proves it on a trivial handler; making workflow runs actually asynchronous is [[STEP-31 Workflow Async Execution]].
- **Scheduling, cron or delayed execution** — [[STEP-74 Workflow Scheduling and Triggers]], which also owns the system-actor question deferred in §4.
- **Notification of job completion** — [[STEP-34 Notifications Domain]] onward. A user watching a job finish is a different problem from a job finishing.
- **`LISTEN`/`NOTIFY` dispatch latency.** Available later without a superseding ADR (§1).
- **Provider-side idempotency keys.** The exactly-once problem `c8f1a3d54e29` names as unachievable without them remains open, and is a capability-layer decision rather than a queue one.
- **Where the worker is hosted, and horizontal worker autoscaling.** Deferred to [[STEP-82 Staging Environment and Deployment Pipeline]] by owner decision (§3). STEP-30 settles the *process model* — one image, two commands, strict startup validation on both — and records it in `infrastructure/`. Which platform runs those processes, and when they scale, is STEP-82's decision and affects no code STEP-30 writes.

## Alternatives Considered

### Redis with a task framework (Celery, Dramatiq, RQ)

The conventional answer, and the one most engineers would reach for. Mature, push-based, near-zero dispatch latency, and retries, dead-lettering and a worker loop arrive for free.

**Rejected because** it loses transactional enqueue — a run and its job can no longer commit atomically, so the stranded-run and orphaned-job failure modes both become real and require an outbox to fix, which reintroduces a PostgreSQL-backed queue underneath the broker. It adds a service to run, secure, pay for and monitor, and a new credential class, for a workload whose throughput requirement is trivially inside what PostgreSQL handles. It places the retry ceiling inside a library's configuration surface rather than ProjectOne's asserted code (§2). And it carries tenancy in a store the database cannot see, so the RLS reuse in §4 would have to be rebuilt as a bespoke mechanism.

The performance advantage is real and irrelevant at this scale: it optimizes dispatch latency in milliseconds for jobs that run for minutes.

### A PostgreSQL-native task library (Procrastinate, pgqueuer)

Genuinely appealing — they keep transactional enqueue and add `LISTEN`/`NOTIFY`, a worker loop and retry handling on top.

**Rejected because** they own the schema and the connection handling, and both collide with commitments this codebase has already made. ProjectOne's two-connection split (`postgres` for migrations, `projectone_api` for everything RLS-subject) is load-bearing security, and a library managing its own connections and its own tables is a third pattern beside it. Their tables would not carry ProjectOne's RLS policies without being fought, and their retry semantics would sit outside the §15a accounting for the same reason as any other framework. The saving is a claim statement and a loop — roughly the smallest part of this step.

### A managed cloud queue (SQS, Cloud Tasks, Cloud Pub/Sub)

Operationally excellent: durable, monitored, and someone else's problem to run.

**Rejected because** it is a hard dependency on a specific cloud vendor, which [[CLAUDE|CLAUDE.md]] §7's provider-independence principle treats as a cost requiring justification, and ProjectOne currently has no such account to depend on. It shares every drawback of the broker option — no transactional enqueue, tenancy outside the database — and adds vendor lock-in on top, in exchange for operational convenience the project does not yet need at a scale it does not yet have.

### A workspace-scoped database claim instead of a user identity (§4)

Carry only the workspace id, add RLS policies that read a workspace claim, and give the worker a role that sets it.

**Rejected because** it is a second, parallel tenant mechanism. Every existing policy resolves through `auth.uid()` and `workspace_members`; adding a workspace-claim path means every current and future policy must be correct under *both*, and a table whose author remembered one but not the other is a silent cross-tenant hole. It also grants a principal that can assert a workspace directly, without a membership proving it is entitled to — which is strictly more powerful than any principal that exists today. Replaying an existing user identity reuses a mechanism that is already written, already tested, and already fails closed.

### Privileged access with an explicit workspace filter in the handler

The `AISpendRepository` shape, generalised: the worker uses the privileged connection everywhere and every query filters on the job's workspace id.

**Rejected because** it makes tenant isolation a property of handler discipline rather than of the database — precisely the inversion [[CLAUDE|CLAUDE.md]] §13 and §16 forbid, where a forgotten `WHERE` clause is a cross-tenant leak that no route test would catch. `AISpendRepository` is a *narrow* exception with a stated reason (a control must see a ceiling the caller cannot hide) and three single-purpose statements; extending that shape to every future handler would make the exception the rule. §5 keeps the privileged path to dispatch alone for exactly this reason.

### Keeping execution synchronous and raising HTTP timeouts

The zero-infrastructure option, worth naming because it is what the platform does today.

**Rejected because** it does not survive contact with the product. A render measured in minutes cannot be held open by a browser, no timeout anywhere in the path can be trusted, and a client that disconnects abandons a run that is still spending money — with no process left to record what happened. It also caps concurrency at the API's worker count, so one long generation degrades every unrelated request.

## Related

- Implements the first task of: [[STEP-30 Async Job Infrastructure]]
- Unblocks: [[STEP-31 Workflow Async Execution]] · [[STEP-32 Media Processing Pipeline]]
- Builds on: [[ADR-001 Technology Stack]] · [[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]]
- Governed by: [[CLAUDE|CLAUDE.md]] §7 · §13 · §15a · §16 · §21 · §39

---

## Navigation

- **Previous:** [[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]]
- **Next:** —
- **Parent:** [[Home]]
- **Related Notes:** [[STEP-30 Async Job Infrastructure]] · [[Workflow Engine]] · [[Infrastructure]] · [[Security Architecture]] · [[Backend Architecture]]
