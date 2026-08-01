---
title: "{{METHOD}} {{/api/v1/path}}"
category: API Endpoint
status: draft
version: "0.1"
last_updated: "{{date}}"
tags: [api, backend]
method: "{{GET|POST|PATCH|DELETE}}"
path: "{{/api/v1/...}}"
---

# {{METHOD}} {{/api/v1/path}}

> Every endpoint inherits the conventions in [[API Conventions]] — version prefix, error envelope, correlation id, logging. Document only what is **specific to this endpoint**; do not restate the shared contract.

## Description

What it does, and the problem it solves.

## Authentication

Required? Which permission, if any — see [[Authorization Model]]. State the role that suffices, not the role that happens to be used in testing.

## Request

```json
{}
```

Note any field deliberately **absent** — an endpoint that does not accept a `user_id` because identity comes from the token is worth saying out loud.

## Response

```json
{}
```

Status on success: `{{200|201|204}}`.

## Errors

Only the statuses this endpoint can actually return, and what causes each. The shared envelope and the generic 401/403/422 behaviour are in [[API Conventions]] — list them here only when this endpoint does something specific with one.

| Status | Cause |
|--------|-------|
|        |       |

## Rate Limiting

Default is **none** — limits apply to the unauthenticated auth endpoints only ([[API Conventions]]). State a limit here only if this endpoint has one, with the reason it needs one.

## Notes

Anything a future reader would otherwise have to reconstruct from the code: why a status code was chosen over the obvious alternative, what is deliberately not validated, what a soft delete actually removes.

---

## Navigation

- **Parent:** [[Backend MOC]]
- **Related Notes:** [[API Conventions]] · [[API Architecture]] · [[Authorization Model]]
