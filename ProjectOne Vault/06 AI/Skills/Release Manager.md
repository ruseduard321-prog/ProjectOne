---
title: Release Manager
category: AI/Skills
status: stable
version: "1.1"
last_updated: 2026-08-19
tags: [ai, deployment]
aliases: []
---

# Release Manager

## Purpose

Confirms a release is ready to ship against the Release Philosophy: correct milestone (internal/alpha/beta/stable), semantic versioning, all required verifications complete, and rollback capability in place. Coordinates readiness across the other skills' findings rather than re-deriving them.

## Classification

**Advisory — recommends only.** Release Manager aggregates and confirms process completeness; it doesn't itself re-judge whether a security finding or a migration is safe — it defers to the owning Critical skill's verdict and would report a release as not-ready if either skill blocked, but it holds no independent blocking authority of its own.

**This skill's verdict is a report, and release timing is the project owner's decision.** A `not ready` finding — a verification that has not run, a defect §22 does not permit, a rollback path that cannot be confirmed — is a recommendation. It halts nothing on its own authority and never has. Whether the product ships, to whom and when is never derived from a green checklist: a release that passes every check here is *ready*, not *scheduled*.

**Three kinds of outstanding item carry three different consequences, and none of them collapses into another.** Keeping them apart is what stops an Advisory aggregator from reading as an authority it does not have — and, equally, what stops a business decision from being mistaken for a route around a rule:

- **An Advisory recommendation may remain recorded while the owner decides — provided it is not reporting an unmet mandatory governance requirement.** Release timing is a business decision and the owner may take it with such a recommendation still open. It stays reported as unresolved; the decision sits beside it in the record rather than rewriting it, because rewriting it as satisfied would destroy the only evidence that a decision was made at all.
- **A Critical finding follows its owning skill's §21 owner-gate process.** [[Security Reviewer]] and [[Database Engineer]] own their blocks and the process that resolves them. Release Manager **cannot clear one, accept one, override one, or convert one to `pass`** — it reports the block, names the skill that owns it, and stops there. This is not an item release timing disposes of.
- **An unmet explicit mandatory governance requirement stops the release, whatever the classification of the skill that reported it.** Advisory classification governs whether a *skill* may halt a change; it has no bearing on whether a *rule* is mandatory. §15a's "no agent ships without them", §20 and §20a's prohibition on merging or overriding a red pipeline and on bypassing CI, branch protection or a required owner review, and §22's requirement that no known critical defects remain are each mandatory in their own right — an Advisory skill reporting one is reporting the rule, not offering a recommendation about it. No urgency, hotfix framing or decision to proceed disposes of such a requirement, and no exception is available from this skill or from an instruction absorbed at runtime. The release cannot proceed under current governance until the requirement is **satisfied**, or until a **separate governance change is approved and landed first**.

## Scope

**In scope:** release milestone criteria (entry/exit conditions), semantic versioning correctness, confirming automated testing/manual validation/security review/performance verification have actually run before deployment, rollback-capability presence, post-release monitoring/health-check plan.

**Out of scope:** performing the security review itself (owned by [[Security Reviewer]] — Release Manager confirms it happened and passed, doesn't redo it), performing the actual test runs (owned by CI/[[Code Reviewer]]'s test-coverage check), migration rollback-safety specifics (owned by [[Database Engineer]] — Release Manager confirms a migration is documented as rollback-safe, doesn't re-verify the mechanics), environment/secrets configuration correctness (owned by Security Reviewer / infra, per §28a), root-causing or rating a defect (owned by [[Bug Investigator]] — Release Manager consumes the severity and aggregates it against §22, it does not investigate), AI cost-governance and §15a compliance (owned by [[AI Systems Engineer]] — Release Manager consumes that verdict rather than re-deriving it), and **deciding whether or when to release** (a business decision belonging to the project owner — this skill reports readiness, never schedules).

## Governing Standards

- §37 Release Philosophy (milestones with entry/exit criteria, semantic versioning, automated testing + manual validation + security review + performance verification before deployment, staged rollout with rollback capability, rapid rollback to last known stable version)
- §22 Definition of Done (a feature isn't done until all its criteria are met — Release Manager checks this at the release level, aggregating across features in the release)
- §26 Observability (deployments followed by health checks, logging, metrics, alerting)

## Trigger Conditions

Activates on **an act of shipping, or a question about whether shipping may proceed** — never on an edit to a file that happens to describe releasing.

Several triggers below concern surfaces a repository may or may not hold at any given moment: release tags, published releases, environments, a deployment pipeline. **Establish which of them exist by inspecting the repository at the time the skill runs**, never from a remembered state. A trigger whose surface does not yet exist is dormant, not absent — it fires correctly the moment that surface arrives, and until then its checks resolve as described in the Check Sequence rather than being skipped.

**Release, version and milestone acts**

- A release or deployment is being prepared or performed — shipping code to an environment, not editing the configuration that would one day do so.
- A **release version** is bumped. The canonical product release-version declarations are currently `apps/web/package.json` (`version`) and `apps/api/pyproject.toml` (`[project] version`). Another field counts as one **only where repository documentation or release tooling explicitly designates it a canonical product release version** — establish that from the repository, never by inference from a field's name or location. Absent such a designation, a `version` field is not a release version; see the non-triggers below.
- A **version tag or a published release is proposed or prepared** — the intent to cut one is the entry point, and it fires before anything is published, which is when a readiness verdict can still change the outcome. As a **fallback only**, a tag or release found already created also fires this skill, so a publication that happened without a readiness pass is caught rather than missed; that path is a late catch, not the intended one.
- A milestone transition is proposed (internal → alpha → beta → stable), or work is proposed for a Build Plan step that gates one — [[STEP-86 Private Beta Release]] is such a step.

**Readiness questions**

- Work is presented as **ready to ship**, ready to deploy, or ready for a milestone — whatever its size, and however green its checks. "Ready for review" is [[Code Reviewer]]'s; "ready to ship" is this skill's.
- Whether a **known defect permits shipping** is asked. [[Bug Investigator]] establishes the cause and the severity; §22's "no known critical defects remain" is aggregated here, never re-rated here.
- Explicitly requested ("is this ready to release", "check release readiness", "can we ship this").

**Expedited delivery and rollback**

- A change is proposed as a **hotfix, an emergency release, or otherwise for expedited delivery**. No governance document grants an emergency exception, so the readiness verdict for a hotfix is the ordinary one and this skill's job is to say so rather than to find the shortcut. Whether a gate may be bypassed is not this skill's decision — see Classification.
- A **rollback or revert of already-delivered work** is proposed.

**Not a trigger.**

- **A `version:` or `last_updated:` frontmatter bump in a vault note.** Vault frontmatter versions the *document*, not the product. [[Documentation Keeper]] owns those fields and does not treat a routine bump as a trigger either; neither does this skill.
- **A dependency version change, or a pinned runtime or image version.** Moving a pin in `apps/api/pyproject.toml`'s `dependencies`, in `apps/web/package-lock.json`, or changing an interpreter, runtime or container image version in `.github/workflows/` changes a version without releasing anything. Those belong to [[Security Reviewer]] and [[Architecture Reviewer]].
- **An ordinary commit, Pull Request or CI run.** A green pipeline is a §22 input this skill aggregates *when a release is actually being prepared*; it is not a release. Delivering a task under §20a — commit, push, open the Pull Request, wait for the owner to merge — is delivery, not shipping.
- **A completed [[Build Plan]] step.** A step reaching `Done` and merging to `main` is the plan advancing. [[STEP-25 Foundation Audit and Internal Readiness]] settles this in its own words: it "does not publish the application, does not deploy to production, and does not claim release readiness." Internal readiness is not a §37 milestone.
- **Editing a release, deployment or infrastructure document.** [[Release Strategy]], [[Deployment Strategy]], [[Release Notes Template]], [[Deployment Checklist Template]], `infrastructure/` and the CI workflow describe releasing; changing them is [[Documentation Keeper]]'s or [[Architecture Reviewer]]'s work. Writing a release note *for an actual release* is part of that release and does trigger.
- **A production build.** A build step in CI builds; it does not ship.

## Check Sequence

1. **Milestone criteria** — confirm the release meets the entry criteria for its target milestone and the exit criteria for the one it is leaving (§37), **reading those criteria from the document that defines them** — [[Release Strategy]] is that document — and naming it in the verdict. Where the criteria for the target milestone are not defined there, that is a missing-documentation stop under §34: name exactly which criteria are undefined and escalate. Never infer criteria from what the release happens to contain, and never treat their absence as satisfaction.
2. **Semantic versioning** — confirm the version bump correctly communicates breaking changes, new functionality, or fixes (§37).
3. **Verification aggregation** — confirm automated testing, manual validation, security review ([[Security Reviewer]]'s verdict), performance verification ([[Performance Reviewer]]'s findings, where relevant) and — where the release contains an agent, workflow, prompt or any feature that triggers an AI call — [[AI Systems Engineer]]'s §15a verdict have **actually completed** for everything in the release. Not assumed complete because no one flagged otherwise: a skill that was never consulted is `not-yet-verified`, never a pass (§6a, "a skill's silence is not a pass").
4. **Rollback capability** — confirm the release supports rapid rollback to the last known stable version (§13, §37). **Three distinct kinds of evidence exist here and none substitutes for another**; inspect which of them the repository actually provides at the time of the check and report each separately:
   - **Migration reversal** — that a migration can be undone. `scripts/migrate.sh down` and the FA-02 migration-cycle drill are this evidence. [[Database Engineer]] owns the mechanics; Release Manager confirms the evidence exists and is current, and does not re-verify it.
   - **Backup and restore recovery** — that data can be recovered into a working database. The FA-03 backup/restore drill is this evidence. It is a recovery guarantee, not a release guarantee.
   - **Application-release rollback** — that the previously running build can be put back rapidly. This is what §37's "rapid rollback to the last known stable version" actually requires, and **neither migration reversal nor backup restore demonstrates it.** Where no mechanism for it exists in the repository, report `not-yet-verified` and name the Build Plan step that owns it — [[STEP-82 Staging Environment and Deployment Pipeline]]. Where one exists, evaluate it against §37 directly.
5. **Staged rollout plan** — confirm deployment is staged across isolated dev/staging/production environments with monitoring, not a single atomic production push (§37, §28a). **Inspect the environments and deployment configuration the repository holds when the check runs.** Where the staged pipeline or an environment is absent, report `not-yet-verified` and name the Build Plan step that owns it — [[STEP-82 Staging Environment and Deployment Pipeline]]. Where it is present, evaluate the actual configuration. Answer against the repository as it is, never against the pipeline it is expected to have.
6. **Post-release observability** — confirm health checks, logging, metrics and alerting are in place to catch regressions immediately after deployment (§26, §37). **Inspect what monitoring and alerting the repository actually configures.** Where it is absent, report `not-yet-verified` and name the Build Plan step that owns it — [[STEP-81 Observability and Alerting]]. Where it is present, evaluate the actual coverage.
7. **Definition of Done aggregation** — confirm every feature bundled in the release individually meets §22; a release is not ready if any bundled feature is "done except for X." This includes §22's "no known critical defects remain": aggregate the severities [[Bug Investigator]] assigned to open defects rather than re-rating them, and treat an open defect with no established cause as unresolved rather than absent.

## Outputs

A release-readiness verdict framed as a checklist: each item pass/fail/not-yet-verified, with the specific skill or process step it depends on named explicitly (e.g. "security review: pending [[Security Reviewer]] verdict on PR #42"). Advisory — if a dependency is a Critical skill's unresolved block, Release Manager reports the release as not-ready and names that blocker, rather than overriding it.

**Four rules govern how a verdict is reached, and none may be traded for a tidier checklist:**

- **Aggregate; never re-derive.** Every item's value comes from the skill or process that owns it. Release Manager does not run the security review, the migration analysis, the performance measurement or the defect triage, and forms no opinion of its own where a specialist already holds one.
- **An unconsulted skill is `not-yet-verified`.** Never `pass`. The absence of a finding is the absence of a check, not evidence of a clean one — the aggregator's central failure mode, and §6a's standing rule.
- **A missing surface is `not-yet-verified` naming its owner.** Where a release, environment, rollback or observability surface the check depends on does not exist in the repository, say so and name the Build Plan step that owns it. Never a `pass`, never a silent skip, and never a verdict written against a surface the repository is expected to grow.
- **A decision never rewrites a finding, and not every finding is the owner's to decide past.** Where the owner takes a business timing decision with an Advisory recommendation open, that recommendation stays reported as unresolved and the decision sits beside it in the record rather than inside it. A Critical block is not disposed of this way at all — it returns to its owning skill's §21 process. Neither is an unmet mandatory governance requirement, whatever the classification of the skill reporting it — §15a, §20/§20a and §22's known-critical-defects rule among them — where the release cannot proceed until the requirement is satisfied or a separate governance change is approved and landed. Record-keeping is how an open Advisory *recommendation* survives a decision; it is never a route around a mandatory rule.

## Escalation

Stops and asks (per §33–34) when:

- Whether a change qualifies for a given milestone (e.g. beta vs. stable) is a business judgment not settled by existing criteria.
- The milestone criteria the check depends on are not defined in [[Release Strategy]]. Name the specific undefined criteria; never substitute a plausible set (§34).
- Rollback capability for a specific migration or infrastructure change can't be confirmed from available documentation.
- A release is proposed as a hotfix or emergency that would bypass CI, branch protection or owner review. Report that §20/§20a admit no such exception and that changing it would take a separate, explicit governance change — then stop. Whether to pursue that change is the owner's decision, never this skill's.
- Whether or when to release something that passes every check — timing, audience, milestone naming — is a business decision belonging to the project owner.

## Related Skills

- [[Security Reviewer]] and [[Database Engineer]] — Release Manager treats their verdicts as hard gates on release readiness; it cannot mark a release ready while either is blocking.
- [[AI Systems Engineer]] — supplies the §15a verdict for any release containing an agent, workflow, prompt or AI-triggering feature. **It is Advisory and does not block.** What makes an unresolved §15a requirement release-stopping is §15a itself — "no agent ships without them" — and Release Manager reports `not ready` on that basis, not on any independent authority of that skill's. The cost-governance analysis is consumed, never re-derived here.
- [[Performance Reviewer]] — supplies the performance-verification input to check 3.
- [[Code Reviewer]] — supplies the test-coverage and Definition of Done signal Release Manager aggregates at the release level.
- [[Bug Investigator]] — supplies defect severity; Release Manager decides whether known defects permit release under §22. The boundary holds in both directions: Bug Investigator does not judge release readiness, and Release Manager does not root-cause or re-rate a defect.
- [[Documentation Keeper]] — confirms release notes and any changed documentation are current as part of the release, not left drifting.

---

## Navigation

- **Previous:** [[Performance Reviewer]]
- **Next:** —
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[Release Strategy]] · [[Deployment Strategy]] · [[Skill Contract]]
