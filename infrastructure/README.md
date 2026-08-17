# ProjectOne Infrastructure

Deployment configuration, the process model, and the operational notes that go
with them. CLAUDE.md §9 has specified this directory since STEP-01; until
STEP-30 nothing in the repository needed it, so it held a `.gitkeep` and nothing
else.

[[ADR-005 Async Job Queue and Worker Execution Model]] §3 is what changed that:
ProjectOne now runs **two processes**, and "deployed alongside the API" had
nowhere to be written down.

## What lives here

| File | What it records |
|---|---|
| [`process-model.md`](process-model.md) | The two processes, what each requires, and how each is started and stopped |

## What deliberately does not live here yet

**Which platform runs these processes.** Hosting, orchestration and worker
autoscaling are deferred to [[STEP-82 Staging Environment and Deployment
Pipeline]] by the project owner's decision on 2026-08-17 (ADR-005 §3, §Scope
Boundaries).

That deferral is narrow and worth stating precisely, because "deployment is
deferred" would be the wrong reading. STEP-30 owes a deployment shape that is
**documented and runnable** — one image, two commands, strict startup validation
on both — so that whatever platform STEP-82 selects inherits processes that fail
at deploy rather than at a user's first job. Choosing the vendor now would be
choosing one before there is an environment to run in.

**Infrastructure as code.** CLAUDE.md §28a requires each environment's
configuration to be owned by infrastructure-as-code rather than edited in a
dashboard. There is no environment to codify yet; the first is STEP-82's, and
the templates belong there.

**Secrets.** They are never committed (CLAUDE.md §16). `apps/api/.env.example`
and `apps/web/.env.example` are the templates; real values are injected at
runtime per environment.
