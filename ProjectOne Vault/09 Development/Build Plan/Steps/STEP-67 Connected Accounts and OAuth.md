---
title: STEP-67 Connected Accounts and OAuth
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, publishing, backend]
step_id: STEP-67
step_status: Not Started
detail_level: outline
phase: "Distribution"
---

# STEP-67 — Connected Accounts and OAuth

**Status:** Not Started
**Phase:** Distribution — Channels, connected accounts and the publishing path that turns finished content into published content.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Let a workspace connect a platform account and hold its credentials safely.

## Why This Step Exists Now

[[Settings]] names Connected Accounts as a core section and [[User Journey]] step 2 has users connecting platforms at onboarding. Nothing can be published anywhere without this, and it is the most security-sensitive step in the roadmap.

## Dependencies

- [[STEP-66 Channels Domain]]

## Scope

- OAuth connect flow for at least one platform.
- Encrypted token storage reusing the BYOK credential patterns from STEP-19.
- Token refresh and revocation.
- Explicit scope display — the user sees what access they are granting.
- Disconnect that genuinely revokes.

## Out of Scope

- No publishing yet — the next step.
- No platform-specific API beyond authentication.

## Surfaces Affected

**Backend:** OAuth flows, credential service. **Database:** connected-account credentials with RLS. **Frontend:** Settings Connected Accounts section. **Infrastructure:** platform app registration.

## Required Tests and Proofs

- Tokens are encrypted at rest, never logged, and never returned to a client.
- Refresh works and a revoked token is handled honestly.
- Disconnect revokes upstream, not merely locally.
- Cross-tenant credential access is impossible.
- The credential redaction rules from FA-05 hold for these new secrets.

## Definition of Done

A workspace connects a platform account through OAuth, with encrypted storage, working refresh, genuine revocation on disconnect, and no credential reaching a log or a client.

## Risks and Governance Gates

**Critical, and the highest security risk in the roadmap.** Third-party credentials with write access to a user's public presence. FA-05 was a plaintext-credential leak; this step must not reintroduce that class of defect for a more dangerous secret.

## Audit Gaps Closed

**Connected accounts / OAuth** — *Missing, P1, no step*; [[Settings]] Connected Accounts

---

## Navigation

- **Previous:** [[STEP-66 Channels Domain]]
- **Next:** [[STEP-68 Publishing Execution]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
