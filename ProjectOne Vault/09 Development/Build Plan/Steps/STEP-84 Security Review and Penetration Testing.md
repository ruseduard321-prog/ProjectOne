---
title: STEP-84 Security Review and Penetration Testing
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, testing, security, infrastructure]
step_id: STEP-84
step_status: Not Started
detail_level: outline
phase: "Beta Readiness and Release"
---

# STEP-84 — Security Review and Penetration Testing

**Status:** Not Started
**Phase:** Beta Readiness and Release — Observability, staging, recovery, security review, full verification of the beta surface, and the private invite-only free beta itself.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Review the whole product's security surface as it now stands, not as twenty steps each reviewed their own change.

## Why This Step Exists Now

[[Security Architecture]] and [[Release Strategy]] both require security review before release. The surface has grown enormously since STEP-25: third-party OAuth credentials, file uploads, payment integration, AI tool execution and a worker tier all arrived after the last audit.

## Dependencies

- [[STEP-83 Backup, Recovery Objectives and Disaster Drill]]

## Scope

- Full security review across every surface added since STEP-25.
- Dependency vulnerability scanning.
- Tenant isolation verified by attempting cross-tenant access, not by reading policies.
- Credential and secret handling reviewed across every new integration, with the FA-05 redaction rules re-verified.
- Tool-execution and upload surfaces reviewed specifically as injection vectors.

## Out of Scope

- No formal certification — SOC 2 or ISO 27001 audits are separate undertakings.
- No bug bounty programme.

## Surfaces Affected

**All.** Backend, frontend, database, infrastructure.

## Required Tests and Proofs

- Cross-tenant access attempts fail across every domain, enumerated.
- No known high or critical dependency vulnerability remains unaddressed.
- No credential appears in any log, re-proven with the FA-05 negative controls.
- Upload and tool paths resist injection attempts.

## Definition of Done

Every surface added since STEP-25 is security-reviewed, cross-tenant isolation is proven by attempted breach across every domain, dependencies are clean, and findings are recorded with severities.

## Risks and Governance Gates

**Critical.** Findings here may block release. The step is deliberately before verification so remediation has somewhere to land.

## Audit Gaps Closed

Security posture across all post-STEP-25 surfaces

---

## Navigation

- **Previous:** [[STEP-83 Backup, Recovery Objectives and Disaster Drill]]
- **Next:** [[STEP-85 Full Product Verification and Hardening]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
