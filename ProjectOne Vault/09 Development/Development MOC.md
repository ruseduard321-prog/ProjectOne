---
title: Development MOC
category: MOC
status: stable
version: "1.4"
last_updated: 2026-08-03
tags: [moc, engineering, documentation]
aliases: ["Development Map of Content"]
---

# Development — Map of Content

Practices, standards and process documentation for day-to-day engineering work.

## Engineering Handbook

- [[Chapter 01 - Development Philosophy]] — core engineering values
- [[Chapter 02 - Repository Architecture]] — repo structure and ownership
- [[Chapter 10 - Testing Standards]] — unit, integration, E2E, performance
- [[Chapter 11 - Code Review Standards]] — review checklist and approval process

## Product Bible — Delivery

- [[Testing Strategy]]
- [[Release Strategy]]
- [[Deployment Strategy]]

## Collaboration Process

- [[Branch and Pull Request Workflow]] — how work reaches `main`: protected branch, one task per branch, PR with green CI, squash merge. Binding on every contributor, human or agent.
- [[AGENTS|AGENTS.md]] — the concise adapter pointing OpenAI Codex at ProjectOne's canonical sources

## Build Execution

- [[Build Plan]] — the step index taking ProjectOne from empty repository to first public release (26 planned, plus inserted steps)
- [[Execution Protocol]] — the rules Claude follows on *"Implement the next step."*
- [[Foundation Audit Findings]] — the prioritised record of what STEP-25 found across the Foundation build: what is sound, what is defective, and what could not be proven

## Documentation Tasks

Standalone documentation corrections that are not Build Plan steps — no code, no release dependency, and no slot in the build sequence.

- [[DOC-01 Align ADR Template with CLAUDE.md]] — the ADR template's status vocabulary diverges from [[CLAUDE|CLAUDE.md]] §7 (missing `Review` and `Rejected`)
- [[DOC-02 Validate the Request-Path Credential at Startup]] — `REQUEST_DATABASE_URL` is checked for presence, never for whether it actually authenticates; a mismatch surfaces on the first tenant request rather than at boot

## Environment & Tooling

- [[Environment Setup]] — current local development environment and AI operating capability status, as verified by direct validation
- [[Environment and Secrets]] — the dev/staging/production split, configuration loading, secret handling and the feature-flag convention

## Templates for Development Work

- [[Bug Report Template]]
- [[Sprint Planning Template]]
- [[Release Notes Template]]
- [[Deployment Checklist Template]]

---

## Navigation

- **Parent:** [[Home]]
- **Related MOCs:** [[Engineering Handbook MOC]] · [[Architecture MOC]]
