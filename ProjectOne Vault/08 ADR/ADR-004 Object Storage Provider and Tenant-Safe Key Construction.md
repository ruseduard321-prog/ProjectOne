---
title: "ADR-004: Object Storage Provider and Tenant-Safe Key Construction"
category: ADR
status: accepted
version: "1.0"
last_updated: 2026-08-15
tags: [adr, decision, backend, infrastructure, security, storage]
adr_number: "0004"
---

# ADR-004: Object Storage Provider and Tenant-Safe Key Construction

## Status

**Accepted** — approved by the project owner on 2026-08-15.

This decision is now binding, and [[STEP-27 Storage Provider Abstraction]] and later steps may build against it ([[CLAUDE|CLAUDE.md]] §7). **Changing ProjectOne's primary object-storage provider requires a new ADR that supersedes this one** — this note is not amended in place.

### What the owner approved

[[STEP-27 Storage Provider Abstraction]] was `Blocked` because no canonical object-storage provider decision existed. The owner resolved that block on 2026-08-15:

| # | Decision | Outcome |
|---|---|---|
| 1 | ProjectOne's canonical storage architecture is the **vendor-neutral `StorageProvider` boundary** | **Accepted** |
| 2 | **Cloudflare R2 (Standard)** is the initial production adapter | **Accepted** |
| 3 | The adapter uses R2's **S3-compatible API** | **Accepted** |
| 4 | R2-specific SDK types, configuration and errors stay **below the adapter boundary** | **Accepted** |
| 5 | **No caller may construct or supply a raw object key** | **Accepted** |
| 6 | Workspace isolation remains ProjectOne's responsibility **at the path-construction layer** | **Accepted** |
| 7 | Changing the primary storage provider is an **ADR-level decision** | **Accepted** |

## Context

Everywhere else in ProjectOne the workspace boundary is enforced by the database. [[CLAUDE|CLAUDE.md]] §16 mandates Row Level Security on every tenant-scoped table, and a repository that forgot its filter would still be safe because the database refuses the row.

**Object storage has no equivalent.** A bucket is a flat key space, and an object key is just a string. Whatever isolation exists is the isolation the application constructs. This is why the provider choice and the key convention are decided together in one ADR rather than separately: choosing a vendor without settling who owns key construction would leave the actual tenant boundary undecided.

The audit names file storage as the product's single largest blocker — video, publishing, asset review and the media agent chain all sit behind it. The abstraction is settled before there are callers, for the same reason [[AI Providers]] was: provider independence is far cheaper to establish before anything depends on it.

### Why this needs an ADR

[[CLAUDE|CLAUDE.md]] §39 requires an ADR for technology choices, infrastructure decisions and changes to the multi-tenancy model. This is all three at once, and §21 makes it Critical independently. It is not operational policy under §39's exemption, and §21's uncertainty rule would resolve toward an ADR even if the classification were arguable.

## Decision

### 1. The canonical architecture is the boundary, not the vendor

ProjectOne's storage architecture is the **vendor-neutral `StorageProvider` interface**. Cloudflare R2 is an implementation detail *behind* that interface, not an architectural commitment in front of it.

This distinction is the entire point of the decision. Selecting R2 does **not** make ProjectOne's storage architecture R2-specific, and no code above the adapter boundary may assume R2, S3, or any successor.

### 2. Cloudflare R2 (Standard) is the initial production adapter

Accessed through R2's **S3-compatible API**, using `boto3` — the AWS SDK for Python, which Cloudflare's own presigned-URL documentation lists as a supported client for R2.

### 3. R2-specific detail stays below the boundary

No `boto3` type, no `botocore` exception, no bucket name, no endpoint URL and no R2 credential may appear in a signature, a return type, or a raised exception above `app/storage/providers/`. Callers see `bytes`, `str`, and the storage module's own dataclasses and error types.

This is enforced by an executable architectural test, not by convention alone — see [[STEP-27 Storage Provider Abstraction]].

### 4. Callers never construct object keys

**A caller supplies a workspace identifier and a logical name. It never supplies a path, a key, or any part of one.** Key construction happens inside the storage layer and nowhere else.

The corollary is that there is no API by which a caller *could* pass a raw key, because an interface that accepts one cannot be made safe by documentation.

### 4a. What is persisted is a locator, not a key

Recorded at owner review on 2026-08-15, as a clarification of §4 rather than a new decision.

The rule "callers never construct object keys" is only half a rule if the *persisted* value is a key. A file is stored in one request and served in another, so something is written to `assets.storage_path` — and had that been the constructed `ws/<uuid>/<name>`, the code reading it back would have had to parse it into a logical name, because no method accepts a key. Caller-side raw-path handling would return through the schema, and the column would record S3 addressing semantics that outlive the provider.

**`put` therefore returns `StoredObject.locator`, which is the logical name**, and that is what is persisted. With the `workspace_id` already on the row it is exactly what `get`, `signed_url` and `delete` accept, so retrieval is a lookup rather than a parse. The constructed key never leaves the storage layer.

A locator is not a capability: two workspaces legitimately persist the same string, and isolation comes from the workspace id supplied with it.

### 5. Workspace isolation is the path layer's responsibility

Because R2 has no RLS equivalent, the key convention **is** the tenant boundary. A defect in it is a cross-tenant data leak with no second line of defence.

Two properties are therefore required of any key convention adopted under this ADR:

- **Every key is unambiguously attributable to exactly one workspace**, and no workspace can construct a key that resolves into another workspace's namespace.
- **Prefix containment is not sufficient on its own.** A naive `f"{workspace_id}/{name}"` makes `ws-1` a prefix of `ws-10`, so any operation reasoning about ownership by prefix comparison is wrong by construction. The convention must make this case safe, and the step must prove it.

### 6. One private bucket

A single private bucket, with workspace separation expressed in the key structure. **Not one bucket per workspace** — per-tenant buckets trade a well-tested string-construction problem for a provisioning problem, add an unbounded resource to manage, and collide with per-account bucket limits as tenancy grows.

No object is publicly readable. Access to bytes is granted through **presigned URLs with a bounded lifetime**, which R2 supports through the S3-compatible API.

### 7. Changing provider is an ADR-level decision

Adding a second adapter is not — the boundary exists precisely so that a further S3-compatible adapter (AWS S3, MinIO, Backblaze) can be added without a new architectural decision. **Changing which provider is primary** does require a superseding ADR.

## Rationale

Recorded as the owner stated it, with vendor-specific facts verified against current Cloudflare documentation on 2026-08-15:

- **ProjectOne is expected to become media/video heavy.** Storage economics are dominated by egress at that profile, not by at-rest cost.
- **R2 Standard has no Internet egress charge.** Cloudflare's pricing documentation states egress (data transfer to Internet) is free, and that "There are no charges for egress bandwidth for any storage class." Storage is billed per GB-month with Class A/B operation charges.
- **R2 provides an S3-compatible API**, which is what makes the adapter portable: the same adapter shape reaches S3, MinIO and Backblaze.
- **R2 supports presigned object URLs** through that API, with expiry configurable from 1 second to 7 days (604,800 seconds).
- **R2 supports future prefix/object-scoped temporary credentials**, recognised here as a possible future defence-in-depth mechanism.
- **Separating storage from Supabase avoids unnecessary provider concentration.** [[ADR-001 Technology Stack]] already records Supabase concentrating database, auth, storage and realtime as a known consequence; keeping media out of it limits blast radius.
- **Supabase Storage remains a valid alternative and was seriously considered.** It is not chosen, and — decisively — choosing it would **not** have removed the need for application-level tenant-safe keys: server-side S3 access keys bypass Supabase Storage's RLS. The obligation in §5 above is therefore provider-independent.

## Consequences

- **The key convention carries the entire isolation burden.** R2 has no RLS. This is the accepted cost of the decision, and it is why [[STEP-27 Storage Provider Abstraction]] treats hostile-identifier, traversal, encoded-separator and prefix-confusion tests as required proofs rather than optional coverage.
- **A new credential class enters the system** — an R2 access key pair and endpoint, handled per [[Environment and Secrets]] using `SecretStr`, never committed and never logged.
- **`boto3` becomes a backend dependency.** It is confined to `app/storage/providers/` and is not importable above the boundary, which the architectural test asserts.
- **Presigned URL lifetime is bounded by R2 at 7 days.** Any future requirement for longer-lived access needs a different mechanism, not a longer expiry.
- **Portability is retained but not free.** Provider independence holds only while the interface stays vendor-neutral; the architectural test is what keeps that true over time rather than at the moment of writing.

## Scope Boundaries

This ADR records the decision above and **introduces no additional architectural decisions**. Specifically, it does not decide:

- **Temporary prefix/object-scoped R2 credentials.** Recognised as a possible future defence-in-depth mechanism. **This does not expand [[STEP-27 Storage Provider Abstraction]]'s scope**, which does not require them.
- **Upload endpoints, UI, quotas, lifecycle rules, or media processing** — [[STEP-28 Asset Upload and Download]] and [[STEP-33 Storage Quotas and Lifecycle]] own these.
- **A second adapter.** Provider independence is proven by the boundary and its test, not by writing two implementations before either has a caller.

## Alternatives Considered

### AWS S3

The de-facto standard, with the widest tooling and the same S3 API. **Rejected because** egress is billed per GB, which is the dominant cost at ProjectOne's expected media profile, and the portability advantage over R2 is nil — both speak the same API, so the adapter is identical either way.

### Supabase Storage

Bundled with infrastructure ProjectOne already runs, and the only option offering RLS-backed object policies as a genuine second isolation line. **Rejected because** it deepens the provider concentration [[ADR-001 Technology Stack]] already flags as a consequence, it is the weakest option for large video, and its headline security advantage does not survive the access pattern ProjectOne needs: server-side S3 access keys bypass its RLS, so application-level tenant-safe keys would still be mandatory.

### Local filesystem

Excellent for tests, and genuinely useful as a future test double. **Rejected as a production choice** because it has no native presigned-URL mechanism, no durability story and no horizontal scalability ([[CLAUDE|CLAUDE.md]] §7).

---

## Navigation

- **Previous:** [[ADR-003 Product Visual Language and Token Semantics]]
- **Next:** [[ADR-005 Async Job Queue and Worker Execution Model]]
- **Parent:** [[Home]]
- **Related Notes:** [[STEP-27 Storage Provider Abstraction]] · [[ADR-001 Technology Stack]] · [[Environment and Secrets]] · [[Backend Architecture]] · [[Infrastructure]]
