---
title: STEP-10 Authentication Backend
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-01
tags: [engineering, workflow, build-step, security,backend]
step_id: STEP-10
step_status: Not Started
detail_level: outline
---

# STEP-10 — Authentication Backend

**Status:** Not Started
**Detail level:** outline — expanded to full detail by [[STEP-09 Row Level Security Policies]], per [[Execution Protocol]].

## Goal

Sign-up, sign-in, sign-out, session and token handling in `apps/api`, with identity reaching the RLS policies from STEP-09.

## Scope

Backend only — no UI. MFA and OAuth providers are in scope per [[Authentication and Authorization]]; decide during expansion whether they ship here or in a follow-on step.

## Prerequisites

- [[STEP-09 Row Level Security Policies]] — `Done`

## Required Documentation

- [[Authentication and Authorization]]
- [[Security Architecture]]
- [[Chapter 09 - Security Standards]]
- [[Table - users]] — specifically [[Table - users#Relationship to Supabase Auth]]

## Inherited from earlier steps

Recorded during synchronization, not expansion — these are constraints this step must resolve, not its task list.

> [!warning] Blocker to clear here: the Supabase REST API returns 401
> `SUPABASE_URL` and `SUPABASE_SECRET_KEY` are configured and validated, but REST calls with the provided `sb_secret_...` key return 401 while direct PostgreSQL access works ([[STEP-07 Supabase Provisioning#Outcome]]). Nothing has used REST so far, so it has blocked nothing.
>
> **This step is the deadline.** Supabase Auth's admin API is HTTP, so the first real consumer of those two variables is almost certainly here. Resolve it before building on them — most likely the key must be enabled for the REST role in the dashboard, or a different key type is required.

Two schema facts from [[STEP-08 Users and Workspaces Schema]] that this step owns:

- **`public.users.id` holds the same value as `auth.users.id`, with no foreign key between them.** The link is a convention right now, enforced by nothing. This step decides how it is established on sign-up and how it is kept honest — a trigger on `auth.users`, an application-side upsert, or an explicit FK if the coupling to Supabase's schema is judged acceptable.
- **`public.users.email` is denormalized from `auth.users.email`.** This step owns keeping the copy in step with the authoritative value when a user changes their address.

## Tasks

Not yet expanded. [[STEP-09 Row Level Security Policies]] writes this section, when the surrounding code exists and the tasks can be accurate rather than imagined.

## Validation

Not yet expanded.

## Definition of Done

Not yet expanded.

---

## Navigation

- **Previous:** [[STEP-09 Row Level Security Policies]]
- **Next:** [[STEP-11 Authorization and RBAC]]
- **Parent:** [[Build Plan]]
