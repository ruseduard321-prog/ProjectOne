---
title: Database MOC
category: MOC
status: stable
version: "1.0"
last_updated: 2026-07-30
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
- [[Table - users]] — application-side profile, keyed to Supabase Auth
- [[Table - workspaces]] — the tenant boundary
- [[Table - workspace_members]] — user ↔ workspace membership and role

## Cross-References

- [[Authentication and Authorization]] — row-level security for workspace isolation
- [[Backend Architecture]] — database access layer
- [[Backup and Disaster Recovery]] — backup policy for stored data

---

## Navigation

- **Parent:** [[Home]]
- **Related MOCs:** [[Backend MOC]] · [[Security MOC]] · [[Architecture MOC]]
