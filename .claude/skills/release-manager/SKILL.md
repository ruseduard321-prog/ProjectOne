---
name: release-manager
description: Confirms release readiness against milestone criteria, semantic versioning, aggregated verification (testing, security review, performance review, AI cost governance) and rollback capability. Triggers on an act of shipping or a question about whether shipping may proceed — a release or deployment being prepared or performed; a release version bumped in a canonical product release-version declaration, currently apps/web/package.json and apps/api/pyproject.toml, plus any other field that repository documentation or release tooling explicitly designates as a canonical product release version; a version tag or release being proposed or prepared (and, as a fallback, one found already created); a milestone transition (internal/alpha/beta/stable); work presented as ready to ship; whether a known defect permits shipping; a hotfix, emergency or expedited release; a proposed rollback of already-delivered work; and explicit readiness requests. Not triggered by vault frontmatter version bumps, dependency or runtime version pins, ordinary commits/PRs/CI runs, a completed Build Plan step, edits to release or infrastructure documents, or a production build. Advisory — aggregates other skills' verdicts, does not independently block.
classification: advisory
---

# Release Manager

Source of truth: `ProjectOne Vault/06 AI/Skills/Release Manager.md` (reasoning, scope, escalation rules). This file only operationalizes it — do not restate the *why* here; update the vault note instead and keep this in sync.

Shared execution model: `ProjectOne Vault/06 AI/Skill Contract.md`.

## Trigger Conditions

Fires on **an act of shipping, or a question about whether shipping may proceed** — not on editing a file that describes releasing. Where a trigger names a surface (tags, releases, environments, a deployment pipeline), **inspect the repository to establish whether it exists**; if it does not, the trigger is dormant and the relevant check resolves per the Check Sequence.

**Release, version and milestone acts**
- A release or deployment is being prepared or performed — shipping to an environment, not editing config that would one day do so.
- A release version is bumped. Canonical declarations are currently `apps/web/package.json` (`version`) and `apps/api/pyproject.toml` (`[project] version`). Another field counts only where repository documentation or release tooling explicitly designates it a canonical product release version; otherwise it is not one.
- A version tag or published release is **proposed or prepared** (`git tag`, `gh release`). Fallback only: one found already created.
- A milestone transition is proposed (internal → alpha → beta → stable), or work is proposed for a gating Build Plan step (e.g. STEP-86 Private Beta Release).

**Readiness questions**
- Work presented as ready to ship / deploy / reach a milestone, whatever its size and however green its checks. "Ready for review" → `code-reviewer`; "ready to ship" → here.
- Whether a known defect permits shipping. Severity comes from `bug-investigator`; §22 is aggregated here.
- Explicit request ("is this ready to release", "check release readiness", "can we ship this").

**Expedited delivery and rollback**
- A change proposed as a hotfix, emergency release, or for expedited delivery. §20/§20a admit no exception; report the ordinary verdict and escalate.
- A rollback or revert of already-delivered work is proposed.

**Not a trigger**
- A `version:` or `last_updated:` frontmatter bump in a vault note → `documentation-keeper`.
- A dependency version change, or a pinned interpreter/runtime/container-image version (`apps/api/pyproject.toml` dependencies, `apps/web/package-lock.json`, versions in `.github/workflows/`) → `security-reviewer` / `architecture-reviewer`.
- An ordinary commit, Pull Request or CI run, and §20a task delivery.
- A Build Plan step reaching `Done` or merging to `main`.
- Edits to release, deployment or infrastructure documents and templates → `documentation-keeper` / `architecture-reviewer`. A release note written for an actual release does trigger.
- A production build.

## Check Sequence

1. **Milestone criteria** — release meets entry criteria for its target milestone and exit criteria for the one it is leaving. Read them from `Release Strategy` and name it in the verdict. Criteria not defined there → escalate under §34, naming which are undefined. Never infer criteria from the release's contents.
2. **Semantic versioning** — version bump correctly communicates breaking changes, new functionality, or fixes.
3. **Verification aggregation** — automated testing, manual validation, security review (`security-reviewer`), performance verification (`performance-reviewer`, where relevant), and `ai-systems-engineer`'s §15a verdict where the release contains an agent, workflow, prompt or AI-triggering feature, have actually completed. A skill never consulted is `not-yet-verified`, never `pass`.
4. **Rollback capability** — three separate kinds of evidence; report each on its own and never substitute one for another:
   - *Migration reversal* — `scripts/migrate.sh down`, FA-02 cycle drill. Mechanics owned by `database-engineer`; confirm the evidence exists and is current, do not re-verify.
   - *Backup/restore recovery* — FA-03 drill. A recovery guarantee, not a release guarantee.
   - *Application-release rollback* — putting the previously running build back, which is what §37 requires. Absent → `not-yet-verified`, naming STEP-82. Present → evaluate against §37.
5. **Staged rollout plan** — inspect the environments and deployment configuration present. Absent → `not-yet-verified`, naming STEP-82. Present → evaluate the actual configuration. Never answer against an expected pipeline.
6. **Post-release observability** — inspect the monitoring and alerting configured. Absent → `not-yet-verified`, naming STEP-81. Present → evaluate actual coverage.
7. **Definition of Done aggregation** — every bundled feature individually meets §22, none "done except for X", including "no known critical defects remain": aggregate `bug-investigator`'s severities rather than re-rating them; an open defect with no established cause is unresolved, not absent.

## Output Format

A release-readiness checklist: each item pass/fail/not-yet-verified, naming the specific skill or process step it depends on (e.g. "security review: pending security-reviewer verdict on PR #42"). If a Critical skill (`security-reviewer` or `database-engineer`) is blocking, the release is reported not-ready with that blocker named — this skill never overrides a Critical block.

Four rules, never traded for a tidier checklist:
- Aggregate; never re-derive. Each item's value comes from the owning skill or process.
- An unconsulted skill is `not-yet-verified`, never `pass`.
- A missing surface is `not-yet-verified` naming its owning Build Plan step — never `pass`, never a silent skip.
- A decision never rewrites a finding, and not every finding is the owner's to decide past. Record an open Advisory recommendation beside the decision, never inside it.

Three outcomes, kept distinct in the output. Classify by **what the finding reports**, not by the classification of the skill that reported it:
- **Advisory recommendation open, reporting no mandatory requirement** → may remain recorded while the owner takes the business release-timing decision.
- **Critical finding open** → its owning skill's §21 owner-gate process. Never cleared, accepted, overridden or marked `pass` here.
- **Unmet explicit mandatory governance requirement** — §15a ("no agent ships without them"), §20/§20a (a red pipeline never merged or overridden; CI, branch protection and required owner review never bypassed), §22 (no known critical defects remain), and any other rule stated as mandatory → the release cannot proceed under current governance until the requirement is satisfied, or until a separate governance change is approved and landed. Applies whether the reporting skill is Advisory or Critical.

## Escalation

Stop and ask rather than deciding when:
- Whether a change qualifies for a given milestone is a business judgment not settled by existing criteria.
- The milestone criteria the check depends on are not defined in `Release Strategy`. Name which; never substitute a plausible set.
- Rollback capability for a specific migration or infrastructure change can't be confirmed from available documentation.
- A hotfix or emergency release is proposed that would bypass CI, branch protection or owner review. State that §20/§20a admit no exception and that changing it requires a separate governance change, then stop.
- Whether or when to release something that passes every check — timing, audience, milestone naming.

## Handoff

- Unresolved security or migration blockers → reported as-is from `security-reviewer` / `database-engineer`, never re-adjudicated.
- §15a / AI cost-governance verdict → `ai-systems-engineer`. Advisory and non-blocking; an unresolved §15a requirement makes this skill report `not ready` because of §15a, not because that skill blocks. Never re-derived here.
- Performance verification input → `performance-reviewer` skill.
- Test-coverage / Definition of Done signal → `code-reviewer` skill.
- Defect severity for §22's "no known critical defects remain" → `bug-investigator` supplies it; aggregated here, never root-caused or re-rated here.
- Release notes / documentation currency → `documentation-keeper` skill.
