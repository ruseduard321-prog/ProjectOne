---
title: Reading Priority
category: Claude OS
status: stable
version: "1.0"
last_updated: 2026-07-31
tags: [governance, documentation, ai]
aliases: []
---

# Reading Priority

The order to read documentation in, once [[Documentation Discovery]] has identified which documents are relevant. Read in this order; stop as soon as the task's questions are answered — later steps are conditional, not mandatory.

## Reading Order

1. **[[Start Here]]** — always first, every task, no exception.
2. **ADRs** (`08 ADR/`) — *if relevant.* Check whether a formal decision already governs this area before reading anything else architectural; an Accepted ADR overrides general architecture docs for its specific scope.
3. **Architecture** — [[Architecture MOC]] and the specific domain MOC it points to ([[Backend MOC]], [[Frontend MOC]], [[Database MOC]], [[AI MOC]], [[Security MOC]]). Establishes how the system is shaped before touching a feature.
4. **Feature documentation** — the relevant note(s) in `03 Project Bible/01 Features/` (via [[Features MOC]]) for what the feature is supposed to do and why.
5. **API / Database / Design System** — *only if needed.* [[API Architecture]], [[Database Architecture]], [[Design System]] — read only the one(s) the task actually touches, not all three by default.
6. **Development notes** — *only if needed.* [[Development MOC]], [[Environment Setup]], or prior process notes, when the task is about *how* work gets done rather than *what* to build.

## Why This Order

Governance and settled decisions (ADRs) outrank general architecture, which outranks feature-level detail, which outranks implementation specifics — this mirrors [[CLAUDE|CLAUDE.md]]'s own source-of-truth hierarchy. Reading top-down means Claude never implements against feature-level detail that a higher-priority document has already overridden.

---

## Navigation

- **Previous:** [[Documentation Discovery]]
- **Next:** [[Task Workflow]]
- **Parent:** [[Home]]
- **Related Notes:** [[Documentation Discovery]] · [[Architecture MOC]] · [[CLAUDE|CLAUDE.md]]
