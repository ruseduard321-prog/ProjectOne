---
title: Database MOC
category: MOC
status: stable
version: "1.2"
last_updated: 2026-08-08
tags: [moc, database, documentation]
aliases: ["Database Map of Content"]
---

# Database — Map of Content

## Product Bible

- [[Database Architecture]] — core domains, integrity, versioning, soft deletion

## Engineering Handbook

- [[Chapter 07 - Database Standards]] — naming, migrations, indexing, Row Level Security

## Implemented Schema

What actually exists in the database, as opposed to the intended model above.

- [[Schema Overview]] — current tables, migration history, what is still outstanding
- [[Table Conventions]] — the standard column set, trigger and naming rules every table follows
- [[RLS Policy Pattern]] — the tenant-isolation pattern every new tenant-scoped table copies
- [[Table - users]] — application-side profile, keyed to Supabase Auth
- [[Table - workspaces]] — the tenant boundary
- [[Table - workspace_members]] — user ↔ workspace membership and role
- [[Table - audit_log]] — who changed what, append-only
- [[Table - security_event_log]] — authentication events, append-only, no tenant read path
- [[Table - provider_credentials]] — workspace AI provider keys (BYOK), encrypted at rest
- [[Table - ai_spend_records]] — the AI spend ledger, append-only
- [[Table - ai_budgets]] — spend ceilings, running totals and the spend breaker
- [[Table - ai_shutdown_switches]] — emergency stop for AI spend, at three scopes
- [[Table - projects]] — a content project and its lifecycle state
- [[Table - assets]] — a file or document belonging to one project
- [[Table - workflow_runs]] — a workflow run and its step history

## Cross-References

- [[Authentication and Authorization]] — row-level security for workspace isolation
- [[Backend Architecture]] — database access layer
- [[Backup and Disaster Recovery]] — backup policy for stored data

---

## Navigation

- **Parent:** [[Home]]
- **Related MOCs:** [[Backend MOC]] · [[Security MOC]] · [[Architecture MOC]]
