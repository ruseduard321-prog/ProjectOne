---
name: architecture-reviewer
description: Reviews changes that introduce, alter, or reverse architectural structure. Triggers on new ADRs and ADR status changes; on a Superseded ADR with no named successor; on normative edits to the body of an already-Accepted ADR (for inspection — not on mechanical link/typo fixes); on a framework, database engine, load-bearing runtime dependency, ADR-governed dependency or established-stack member being added, removed or replaced, and on adapter or provider boundaries created, collapsed or bypassed — but not on minor helper, development or tooling dependencies, version bumps or lockfile diffs; on a new independently launched process, worker, scheduler, consumer or execution substrate even when it creates no new top-level module; on infrastructure changes that alter deployment topology, the process model, an ownership boundary or runtime architecture — but not on other infrastructure/ edits; and on new top-level modules, cross-app dependencies, or folder restructuring that changes ownership. Critical — may block the change.
classification: critical
---

# Architecture Reviewer

Source of truth: `ProjectOne Vault/06 AI/Skills/Architecture Reviewer.md` (reasoning, scope, escalation rules). This file only operationalizes it — do not restate the *why* here; update the vault note instead and keep this in sync.

Shared execution model: `ProjectOne Vault/06 AI/Skill Contract.md`.

## Trigger Conditions

Fires on changes that **introduce, alter, or reverse architectural structure**. A path match alone never fires this skill — every path below carries a semantic condition.

**ADR lifecycle and content** — `ProjectOne Vault/08 ADR/`

- New ADR added, or `status` changed (`Draft`→`Review`→`Accepted`/`Rejected`; `Accepted`→`Deprecated`/`Superseded`).
- `Superseded` naming no successor ADR, or a successor that does not exist. **`Deprecated` requires no successor** — not a finding.
- **Normative body of an `Accepted` ADR edited** — `Decision`, `Consequences`, `Scope Boundaries`, `Alternatives Considered`, or a `Context` statement a `Decision` rests on. Fires for inspection; check 1 classifies the edit.
- **Not a trigger:** `Navigation` blocks, `Related` link lists, frontmatter `version`/`last_updated`, typo and broken-link fixes leaving every normative section untouched (→ `documentation-keeper`). Mixed diff → the normative hunk decides. Genuinely unclear → escalate, do not guess.

**Dependency and stack boundary** — `apps/api/pyproject.toml`, `apps/web/package.json`

- Dependency **added, removed or replaced**, where it is: a framework or database engine; major/load-bearing at runtime; named or governed by an Accepted ADR; part of the established technology stack; creating or moving a provider/runtime capability boundary; or creating, collapsing or bypassing an adapter boundary protecting replaceability.
- **Adapter boundary collapsed or bypassed** — a provider client widened beyond the layer keeping it replaceable, e.g. `boto3` beyond `apps/api/app/storage/providers/` (ADR-004; `tests/test_storage_boundary.py` asserts the boundary). No manifest diff required.
- **Not a trigger:** adding or removing a minor helper, development or tooling dependency, or a mechanical manifest cleanup, that changes no architectural capability — landing outside the literal §10 table is not by itself architectural; a version change alone; a lockfile-only diff (`apps/web/package-lock.json`).
- `security-reviewer` owns every dependency's package safety, version, lockfile and supply-chain risk, additions included, and fires independently. Both fire on one dependency change only where it carries **both** architectural and security implications.

**New runtime service or process** — any location, including existing directories

- A worker, scheduler, consumer, daemon, or process launched/supervised independently of an existing one.
- A new execution substrate (queue, scheduler, background-task mechanism, event consumer), **even with no new dependency and no new top-level module**.
- Signals, **none sufficient alone**: `__main__` entrypoint *plus* a supervised loop or `SIGTERM`/`SIGINT` lifecycle; a new command in the canonical process/deployment model's process table; a new long-lived background thread or scheduled executor owning work outside a request.
- **Not a trigger:** one-shot CLI/CI scripts that run to completion (`apps/api/scripts/`, `scripts/`), whatever entrypoint mechanics they carry.

**Infrastructure that changes architecture** — `infrastructure/`

- Deployment topology; the process model (process table, a process's command, or its startup requirements); an ownership boundary moving between apps/packages/processes/environments; a new environment, runtime boundary, or IaC introducing either.
- **Not a trigger:** any other `infrastructure/` change — runbooks, failure-mode notes, inspection commands, prose (→ `security-reviewer` for secrets/posture; `code-reviewer` for owner-review routing).

**Repository structure**

- New top-level module or package; new dependency between `apps/` and `packages/`; folder reshape changing ownership boundaries (not a plain rename).

**Explicit request** — "review this architecture", "does this need an ADR", "is this a new service".

## Check Sequence

Run in order; stop and report immediately on the first Critical finding rather than continuing silently past it:

1. **ADR lifecycle gate** — new architecture has a corresponding ADR that is `Accepted`, not `Draft`/`Review`, before being treated as production work. `Superseded` names an existing successor; `Deprecated` requires none. If the diff edits an ADR, compare before and after and classify:
    - **Decision change** (materially changes or reverses the accepted `Decision`, its constraints, `Scope Boundaries`, or architectural `Consequences`) → not amendable in place; requires the owner-controlled §7 lifecycle, normally a superseding ADR naming and linking this one. **BLOCK** with that remedy.
    - **Clarification** (wording, examples or references, decision's meaning unchanged) → stays a documentation change; `documentation-keeper` owns its mechanical correctness; this check clears.
    - **Unclear** → escalate and ask; resolve in neither direction.
    - Normative edit to a `Draft`/`Review` ADR → the lifecycle working; clears.
2. **Stack boundary** — the established stack and the ADR-governed dependency set under §10/§28 are unchanged, or an ADR justifies the change: a dependency added, removed or replaced where it is a framework or database engine, load-bearing at runtime, ADR-governed, part of the established stack, or carrying a capability/adapter boundary. A dependency change altering no architectural capability (minor helper, dev/tooling package, manifest cleanup) clears without an ADR, addition or removal alike.
3. **Dependency direction** — apps depend on shared packages, never the reverse; no circular imports.
4. **Folder ownership** — the change lands in the folder that owns that responsibility.
5. **Modularity/replaceability** — no unjustified hard-coupling between major systems (AI, Backend, Frontend, Database, Infrastructure).
6. **Provider independence** — no unjustified hard lock-in to an external AI/cloud/third-party service.
7. **Silent-drift check** — implemented shape matches what was proposed/approved; any divergence is flagged, not accepted as a fait accompli.
8. **Process and deployment shape** — a new independently launched process, execution substrate, or deployment-topology change is settled by an `Accepted` ADR and recorded in the repository's canonical process/deployment model (currently `infrastructure/process-model.md`; if that record moves or is renamed, follow the canonical record, not the path), makes no app depend on another (§8), and creates no runtime boundary no environment can own (§28a).

## Output Format

**PASS** — one line per check confirming it was evaluated and cleared, or "not applicable to this diff."

**BLOCK** — for each failed check: the check name, the specific CLAUDE.md section violated (cite §number), and what's missing (e.g. "draft an ADR before this proceeds past prototype/spike scope").

## Escalation

Stop and ask rather than deciding when:
- Whether a change constitutes "new architecture" needing an ADR is genuinely unclear.
- Two plausible module placements both seem defensible with no way to break the tie from existing conventions.
- Whether an ADR edit touches a normative section at all, or is purely mechanical, can't be settled from the diff — ask in either direction, never guess.
- Whether a normative ADR edit changes the accepted decision's meaning or only clarifies wording is ambiguous (check 1's "unclear") — a question for the ADR's approver, not this skill.
- Whether an added, removed or substituted dependency is load-bearing, or whether a substitution is like-for-like inside an existing boundary, can't be determined from the manifest alone.
- Whether a new entrypoint is a deployed service or a one-shot utility can't be determined from the change alone.

## Handoff

- Schema/migration mechanics → `database-engineer` skill.
- Security architecture specifics (RLS, auth), secrets/posture under `infrastructure/`, and every dependency's package safety, version, lockfile and supply-chain risk → `security-reviewer` skill. It fires on those independently, additions included; both skills fire on one dependency change only where it carries both architectural and security implications.
- AI/agent-specific architecture → `ai-systems-engineer` skill.
- Runtime performance consequences of an approved structure → `performance-reviewer` skill.
- Implementation once an ADR is Accepted → `full-stack-engineer` skill. It implements job/workflow/storage code that changes feature behavior *inside* an approved substrate; this skill decides whether the substrate itself is permitted.
- Infrastructure/deployment configuration routed to owner review as Critical under §21, and placement/naming/coverage of what was built → `code-reviewer` skill.
- Mechanical correctness of an ADR or vault note (frontmatter, links, Navigation, index membership), and a clarifying ADR edit once check 1 has cleared it → `documentation-keeper` skill.
