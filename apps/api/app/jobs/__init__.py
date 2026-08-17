"""Asynchronous job execution: the contract, the registry, and the worker.

Introduced by [[STEP-30 Async Job Infrastructure]] against
[[ADR-005 Async Job Queue and Worker Execution Model]], which the project owner
accepted on 2026-08-17.

The package holds the parts a *handler author* deals with -- the contract, the
registry, the worker loop. The two database repositories live where every other
repository lives, and the split between them is the tenant boundary:

| Module | Connection | Subject to RLS | Purpose |
|---|---|---|---|
| `app/repositories/jobs.py` | tenant | **Yes** | Enqueue and read a workspace's jobs |
| `app/repositories/job_dispatch.py` | privileged | No | Claim, extend lease, record outcome |

The second is the one documented cross-tenant path in the platform, bounded to
the `jobs` table by ADR-005 §5 and asserted by `tests/test_job_boundary.py`.
"""
