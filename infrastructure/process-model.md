# Process Model

ProjectOne runs **two processes from one image**. This document records what
each is, what it requires, and how it is started and stopped.

Settled by [[ADR-005 Async Job Queue and Worker Execution Model]] §3 and built by
[[STEP-30 Async Job Infrastructure]].

## The two processes

| Process | Command | Serves |
|---|---|---|
| **API** | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | HTTP requests |
| **Worker** | `python -m app.jobs.worker` | The `jobs` queue |

Both run from `apps/api`, from the **same image, same package and same
`Settings`**. The worker is a second *process*, not a second *application*: it
needs the services, repositories and session factory the API already has, and
CLAUDE.md §8 forbids one app depending on another. `apps/worker/` was considered
and rejected on those grounds (ADR-005 §3).

The practical consequence is that the two always deploy from the same commit. A
worker running older code than the API is not a state this model can reach, so
no handler-version negotiation exists or is needed.

**[[STEP-31 Workflow Async Execution]] made the worker load-bearing for a user
feature**, not only for an infrastructure probe. Starting a workflow run,
approving a step and continuing a stopped one all enqueue and answer `202`; the
run itself executes in the worker. **A deployment with no worker running is a
deployment where workflows are accepted and never happen** — visible to a user as
runs that stay `pending` forever, and visible in the logs as nothing at all.
Worker liveness was already a monitoring requirement ([[STEP-81 Observability and
Alerting]]); it is now a monitoring requirement with a user-facing failure behind
it.

## Configuration

**One configuration surface, validated identically by both processes.** Both
call `get_settings()`, which exits naming any missing or malformed variable
rather than starting in a broken state.

That includes object storage. STEP-28 made `PROJECTONE_R2_*` a startup
requirement rather than a first-upload surprise, and a worker that touches assets
and started without those credentials would reproduce exactly the defect that
change removed — one layer deeper, and far less visible, because a worker's
failure is not in front of a user (ADR-005 §3).
`tests/test_job_worker.py::TestWorkerStartupConfiguration` asserts this per
variable, as a subprocess, which is the only way to observe what a deploy would.

Two settings exist for the worker specifically, both optional and both with safe
defaults. See `apps/api/.env.example` for the full documentation:

| Variable | Default | Bounds |
|---|---|---|
| `PROJECTONE_JOB_LEASE_SECONDS` | `60` | ≥ 5 |
| `PROJECTONE_JOB_POLL_INTERVAL_SECONDS` | `1.0` | > 0 |

## Running the worker

```bash
cd apps/api
python -m app.jobs.worker
```

It logs `job_worker_started` with its worker id, its lease and its poll interval,
then claims one job at a time.

**Concurrency is more worker processes, never more threads.** The codebase is
synchronous throughout, and `SELECT ... FOR UPDATE SKIP LOCKED` is what makes
extra processes actually help: two workers polling at the same instant receive
different jobs rather than queueing behind one another. The only background
thread a worker starts is a lease heartbeat, which runs no job work.

## What each process costs the database

There is **no application-side connection pool.** Every database session is a fresh connection that closes with the block that opened it, so sizing a pool is not the question — how many connections exist at once is.

Both processes connect as the same `projectone_api` login through `REQUEST_DATABASE_URL`, so they compete for the server's `max_connections` rather than for a pool. Budget accordingly:

| Process | Concurrent request-role connections | Plus |
|---|---|---|
| **API** | one per in-flight request, for that request's life | one privileged connection per in-flight AI call |
| **Worker** | **one per process**, and only while a step is doing database work | one privileged connection per in-flight AI call |

**A worker runs one job at a time** (ADR-005 §3), and the only thread it starts is the lease heartbeat, which runs no job work. So `N` workers cost at most `N` request-role connections, and a worker calling an AI provider holds **no** request-role connection at all while the call is in flight — steps read through session-per-call readers rather than holding one open (`app/workflows/execution.py`). `tests/test_workflows_api.py::TestTheProviderCallHoldsNoTenantConnection` measures that against `pg_stat_activity` rather than asserting it in prose.

Scaling workers is therefore linear and predictable, and the number to watch when adding them is the API's concurrent request count, not the worker's.

## Stopping the worker

`SIGTERM` or `SIGINT` asks the loop to stop **after the current job**, then the
process exits 0.

Draining rather than killing is deliberate. A job interrupted mid-flight is
recoverable — its lease lapses and another worker takes it — but that recovery
costs one of the job's two attempts, and spending an attempt on an orderly deploy
is avoidable waste.

A deployment platform should therefore allow a termination grace period at least
as long as the longest expected job, and treat a worker still running at the end
of it as one whose job will be recovered by its lease rather than as an error.

## Failure modes an operator should know

| Symptom | Meaning | Where it is logged |
|---|---|---|
| Worker exits 1 shortly after start | Configuration is invalid; the message names the variable | stderr, before logging is configured |
| Worker exits 1 after running | Ten consecutive dispatch failures — the database is unreachable | `job_dispatch_failed`, then `job_worker_stopped` |
| Jobs accumulate in `pending` | No worker is running | Nothing — see below |
| A job is `dead_lettered` | Terminal refusal, or attempts exhausted | `job_dead_lettered`, with the cause |
| `job_outcome_discarded` | A worker finished a job whose lease it had lost | Expected under at-least-once; not an error |

**"No worker is running" logs nothing, by construction**, and that is the one
failure mode this document cannot close on its own. A platform where nothing
finishes and nothing errors is CLAUDE.md §26's central case, so **worker liveness
is a monitoring requirement** — recorded here, owned by
[[STEP-81 Observability and Alerting]]. Until then it is a known, stated gap
rather than an assumption.

## Inspecting the queue

Every job's state, attempt count, last error and dead-letter status is a column
on `public.jobs`, readable by the workspace that owns it through RLS. The
correlation id of the enqueuing request travels with the job and is bound into
every line the worker logs while running it, so an asynchronous failure is
traceable back to the request that caused it.

## What this document does not decide

Hosting, orchestration, autoscaling and environment provisioning — all deferred
to [[STEP-82 Staging Environment and Deployment Pipeline]] by owner decision
(ADR-005 §3). What is settled here is the process model those decisions will be
made against.
