---
title: STEP-85 Staging Environment and Deployment Pipeline
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, testing, security, infrastructure]
step_id: STEP-85
step_status: Not Started
detail_level: outline
phase: "Verification and Release Hardening"
---

# STEP-85 — Staging Environment and Deployment Pipeline

**Status:** Not Started
**Phase:** Verification and Release Hardening — Observability, staging, deployment, full-product verification and the beta itself.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Provision staging and build the deployment path with rollback.

## Why This Step Exists Now

[[CLAUDE|CLAUDE.md]] §28a requires strict environment isolation and staging parity, and [[Deployment Strategy]] requires staged deployment with rollback. The audit found no repository evidence of either, and no release can happen without them.

## Dependencies

- [[STEP-84 Observability and Alerting]]

## Scope

- Staging environment mirroring production configuration shape.
- Deployment pipeline for API, web and worker.
- Rollback to the last known stable version.
- Post-deployment health checks.
- Infrastructure as code, per [[Infrastructure]] — no manual dashboard configuration ([[CLAUDE|CLAUDE.md]] §28a).

## Out of Scope

- No production launch — that is [[STEP-89 Private Beta Release]].
- No blue-green or canary sophistication beyond rollback.

## Surfaces Affected

**Infrastructure:** staging, pipelines, IaC. **CI:** deployment stages.

## Required Tests and Proofs

- A deployment rolls back successfully, proven by performing one.
- Staging configuration shape matches production.
- No secret is present in any committed configuration.
- Health checks fail a bad deployment rather than passing it through.

## Definition of Done

Staging exists with production parity, deployments are automated with proven rollback and health gating, and all configuration is infrastructure as code.

## Risks and Governance Gates

**Critical** — infrastructure and deployment configuration. Environment isolation failures are how development credentials reach production data.

## Audit Gaps Closed

**Staging environment**, **Production deployment & rollback** — *Missing, P0 release prerequisites*

---

## Navigation

- **Previous:** [[STEP-84 Observability and Alerting]]
- **Next:** [[STEP-86 Backup, Recovery Objectives and Disaster Drill]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
