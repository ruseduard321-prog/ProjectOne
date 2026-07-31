---
title: Prompt Standards
category: AI/Prompts
status: draft
version: "0.1"
last_updated: 2026-07-30
tags: [ai, prompt, documentation]
aliases: []
---

# Prompt Standards

Operating standards for every system prompt used in ProjectOne, expanding on [[CLAUDE|CLAUDE.md]] Section 31 (Prompt Engineering Rules).

## Versioning

Every production prompt is versioned and stored in [[06 AI/Prompts]] using [[Prompt Template]]. A prompt change is a behavior change to the feature it powers — same Definition of Done as code (Section 22).

## Review

Prompt changes are reviewed with the same rigor as code changes — see [[CLAUDE|CLAUDE.md]] Section 21.

## Anti-Sprawl

Prefer the smallest prompt change that achieves the goal. Overlapping near-duplicate prompts are maintainability debt, exactly like duplicated code (Section 31).

## Cost Awareness

Every prompt's model selection is deliberate — capability, latency, and cost — per [[CLAUDE|CLAUDE.md]] Section 15a (AI Cost Governance).

---

## Navigation

- **Parent:** [[06 AI/Prompts]]
- **Related Notes:** [[Prompt Template]] · [[CLAUDE|CLAUDE.md]]
