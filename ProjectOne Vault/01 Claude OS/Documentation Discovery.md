---
title: Documentation Discovery
category: Claude OS
status: stable
version: "1.2"
last_updated: 2026-08-01
tags: [governance, documentation, ai]
aliases: []
---

# Documentation Discovery

How Claude finds the right documentation for a task — without reading the whole vault.

## The Rule

**Never read the whole vault.** The vault is large and growing; reading everything for every task doesn't produce better answers, it produces slower ones and wastes context that should be spent on the actual work. Read narrowly and precisely instead.

## The Discovery Sequence

1. **Identify the task.** What domain does it touch — frontend, backend, database, AI/agents, security, design, process? Name it before searching for anything.
2. **Search the vault.** Use the relevant MOC ([[Architecture MOC]], [[Engineering Handbook MOC]], [[AI MOC]], [[Security MOC]], [[Design MOC]], etc.) or an index ([[Global Index]], [[Alphabetical Index]], [[Category Index]]) to locate candidate notes. Follow wiki-links from there rather than opening folders at random.
3. **Read only the minimum relevant documents.** Stop once the task's actual questions are answered — see [[Reading Priority]] for which categories of document to check and in what order. Do not read adjacent notes "just in case."
4. **Stop if required documentation is missing.** If a schema, API contract, or architectural detail the task depends on isn't documented anywhere findable, stop before implementing anything and tell the user **exactly what is missing** — name the specific document, decision, or detail that doesn't exist, not a vague "documentation is incomplete" (per [[CLAUDE|CLAUDE.md]] §6 step 0, Sections 33–34). A missing document is a reason to pause, not a reason to invent one.

## Build Plan Execution Applies This Strictly

For build-plan steps, [[Execution Protocol#Context Discipline]] is this sequence with explicit limits: a document is read only when a **named unknown** requires it, one architecture document is read at a time, established code outranks documentation describing a pattern the repository already implements, and documentation that is only an *output* of the step is opened when it is written, not before.

That section does not replace these rules — it is the same principle with the loopholes closed. Step 4 above is untouched: missing documentation still stops the work.

## Why This Order

Identifying the domain first prevents an unfocused search. Searching via MOCs/indexes instead of folder-browsing keeps discovery fast even as the vault grows. Reading only what's minimally relevant preserves context for the actual implementation work. Stopping on missing documentation is what keeps Claude from fabricating architecture — see [[CLAUDE|CLAUDE.md]] Section 34.

---

## Navigation

- **Previous:** [[Start Here]]
- **Next:** [[Reading Priority]]
- **Parent:** [[Home]]
- **Related Notes:** [[Reading Priority]] · [[CLAUDE|CLAUDE.md]] · [[Global Index]]
