---
title: STEP-28 Asset Upload and Download
category: Development/Build Step
version: "2.4"
last_updated: 2026-08-16
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-28
step_status: Done
detail_level: full
phase: "Platform Substrate"
---

# STEP-28 — Asset Upload and Download

**Status:** Done — merged to `main` as `2eeff40`; every Validation item satisfied, see [[#Step Completion Record]]
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, and enough notification to make an asynchronous run visible.
**Detail level:** full — expanded 2026-08-16 against `main` @ `115aeea`, with [[STEP-27 Storage Provider Abstraction]] merged and its contract readable in code.

## Objective

Give assets real bytes: an upload path that validates and stores, and a retrieval path that serves them back safely.

## Why This Step Exists Now

`assets.storage_path` is null on every row any route can currently create. Until an upload exists, the asset table records intentions rather than content.

## Dependencies

- [[STEP-27 Storage Provider Abstraction]] — `Done`, merged as `8e29e47` under [[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]] (`Accepted`).

## Inherited from earlier steps

Recorded during synchronization, not expansion.

Added by [[STEP-27 Storage Provider Abstraction]]:

- **The storage contract is fixed and vendor-neutral.** `StorageProvider` (`app/storage/provider.py`) exposes exactly **put, get, signed URL, delete**. There is no listing operation, so any scope here that assumed one needs a different design rather than a new call.
- **This step supplies the `logical_name`, never a path.** No storage method accepts a key, prefix or bucket — `app/storage/keys.py` constructs every key from a workspace id plus a validated logical name. Upload validation therefore covers *file content and size*; **path safety is already guaranteed upstream and must not be re-implemented here**.
- **Persist `StoredObject.locator` into `assets.storage_path`, and pass it back verbatim.** The locator *is* the logical name, so retrieval is `provider.signed_url(asset.workspace_id, asset.storage_path, ttl)` — using the two columns as they are. **Never parse, split, strip or prefix a persisted value**, and never reconstruct `ws/<uuid>/...`: the full object key is internal to the storage layer and is not what is stored. A locator is not a capability — isolation comes from the workspace id supplied alongside it, so two workspaces legitimately persist the same string.
- **No migration.** The locator fits `assets.storage_path` (`text`, `char_length <= 1024`) as-is.
- **Logical names are restricted to `[A-Za-z0-9._-]`.** A user-supplied filename will frequently not satisfy this (spaces, non-ASCII, multiple dots are all common), so this step owns deriving a safe logical name from an uploaded filename — and `assets.name` remains where the human-readable original belongs.
- **Signed-URL expiry is bounded at 7 days** by the backend, and `expires_in` is a required argument with no default — the retrieval path must choose it explicitly.
- **Storage configuration is currently optional** (`PROJECTONE_R2_*`, all-four-or-none). **This is the step that makes it required**, since it introduces the first real caller; until then `build_storage_provider()` raises `StorageNotConfiguredError` at the point of use.
- **Erasure registration is genuinely new work.** STEP-27 added a store but no caller, so nothing was registered with `data_ownership_service.py`. Deleting a workspace's objects is therefore this step's obligation, as the Scope below already states.

## What expansion found that the outline did not anticipate

Three facts came out of reading the merged code rather than the plan. They change the shape of the work, so they are recorded here rather than discovered mid-implementation.

**1. `AssetStore` is already registered — the gap is object deletion, not registration.** `data_ownership_service.py` already contains an `AssetStore` in `REGISTERED_STORES`, and it soft-deletes asset *rows* today. Its own docstring names this step's obligation exactly: *"The bytes live outside PostgreSQL and no storage backend exists yet; when one does, the step that adds it is responsible for erasing from it too."* So Task 6 is not "register a store" — it is extending erasure to reach the objects.

**2. `ExportableStore.erase()` cannot reach a storage provider.** The Protocol is `erase(connection: psycopg.Connection, workspace_id: uuid.UUID) -> int` — a database connection and nothing else, implemented by ten stores. Deleting objects requires a `StorageProvider`, which that signature cannot supply. This is a contract decision, not an implementation detail; **resolved by the owner on 2026-08-16** — see [[#Decisions]] D1.

**3. Object deletion must be row-driven, because the contract has no listing.** There is deliberately no way to enumerate a workspace's objects. Erasure must therefore read `storage_path` from the asset rows and delete each one individually. A row whose `storage_path` is null has no object and is skipped. **This makes the asset table the only index of what exists in storage** — which is precisely why Task 5's orphan handling matters beyond tidiness.

## Scope

- Upload endpoint with size, MIME and extension validation.
- Retrieval through signed URLs, never a public bucket path.
- `storage_path` populated on the asset row.
- Orphan handling in both directions: a failed upload leaves neither a row pointing at nothing nor an object with no row.
- Registration with the erasure path in `data_ownership_service.py` — a new store holding user data owes deletion coverage ([[CLAUDE|CLAUDE.md]] §16).

## Out of Scope

- No image transformation, thumbnailing or transcoding — [[STEP-32 Media Processing Pipeline]].
- No quota enforcement — [[STEP-33 Storage Quotas and Lifecycle]].
- No upload UI — [[STEP-29 Asset Management UI]].
- **No chunked or resumable upload.** The contract takes `data: bytes`. A single-request upload bounded by the size ceiling is this step; resumable transport is a later step if a real file size demands it.

  > [!warning] Not to be confused with `multipart/form-data`
  > This exclusion is about **S3-style multipart / resumable transfer** — splitting one large object across several requests that can be retried independently. That is out of scope.
  >
  > The endpoint *does* accept `multipart/form-data` ([[#Decisions]] D4), which is an unrelated thing wearing a confusingly similar name: one request, one body, several labelled parts. The two are compatible, and the wire format is not what the ceiling constrains.
- **No hard removal of rows.** Erasure stays a soft delete of the row (`deleted_at`), exactly as `data_ownership_service.py` already documents. Only the *object* is removed for good.

## Surfaces Affected

**Backend:** asset routes, service, storage integration, erasure registration, configuration validation. **Database:** none (column exists, no migration). **Frontend:** none.

## Required Documentation

A candidate list, not a reading list ([[Execution Protocol#Context Discipline]] rule 2). Each entry names the question it would answer; skip any whose question does not arise.

| Document | The question it answers | Likely needed |
|---|---|---|
| `app/storage/provider.py`, `keys.py`, `errors.py` | What exactly may a caller pass, and what is raised? | **Yes** — already read during expansion; re-read only the method being called |
| `app/services/data_ownership_service.py` | What contract must an erasure extension satisfy? | **Yes** — Task 6 modifies it |
| `app/routers/projects.py`, `app/schemas/project.py` | Where do asset routes live, and what shape do they return? | **Yes** — the upload route joins them |
| [[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]] | Why may a caller not construct a key? | Only if tempted to touch key construction — which is out of scope |
| [[API Architecture]] | What is the standard error envelope for a 4xx? | Only if `app/core/errors.py` does not already show it — prefer the code (rule 9) |
| [[Table - assets]] | What constrains `kind`, `name`, `storage_path`? | Only for a constraint the migration does not state plainly |
| [[Security Architecture]] | — | **No.** Upload validation rules here are §16 and the key module's, both already known |

## Tasks

### 1. Make storage configuration required

`build_storage_provider()` raises `StorageNotConfiguredError` at the point of use today, which was correct while nothing called it. This step introduces the first real caller, so a deployment missing `PROJECTONE_R2_*` must fail at startup rather than at a user's first upload.

- Extend the existing startup configuration validation so all four `PROJECTONE_R2_*` variables are required, preserving the all-four-or-none rule already in `Settings`.
- Keep `StorageNotConfiguredError` — it stays the correct error for a programmatic call in a context that legitimately has no storage (tests).
- Update `apps/api/.env.example` to move the storage block from optional to required, with the same placeholder discipline the file already uses.

### 2. Derive a safe, unique logical name

The upload carries a filename; the storage layer accepts `[A-Za-z0-9._-]{1,200}`. This task owns the gap, and it has a correctness requirement beyond sanitisation.

- **Uniqueness is mandatory, not cosmetic.** `put` overwrites an existing key silently, and the key is `ws/<workspace>/<logical_name>`. Two uploads of `photo.png` in one workspace would therefore destroy the first file. Derive the logical name from a value that is unique per asset — the asset row's `id` is already a UUID and is the natural source.
- Sanitise the original filename's extension only, against the same allowlist; reject or drop anything outside it rather than attempting clever transliteration.
- **`assets.name` keeps the human-readable original**, unchanged. The user sees the name they chose; storage sees a name it can hold.
- Never echo the rejected filename in an error ([[CLAUDE|CLAUDE.md]] §24; `InvalidLogicalNameError` already models this with `public_message`).

### 3. Upload endpoint

- Add the route beside the existing asset routes in `app/routers/projects.py`. The router validates and delegates; all logic lives in the service ([[CLAUDE|CLAUDE.md]] §12).
- Enforce, in this order — cheapest rejection first, and each independently:
  - **Size ceiling of 100 MB per asset** ([[#Decisions]] D2), refused without reading the whole body into memory where the framework allows it. Define it as a named constant, not a literal at the check site — [[STEP-33 Storage Quotas and Lifecycle]] will need to reference it.
  - **Declared MIME type** against an allowlist derived from `AssetKind`.
  - **Extension** against the same allowlist.
  - **Content sniffing** — the magic bytes must agree with the declared type. A `.png` whose content is a PE executable is refused. This is what makes the "extension lies about its content" proof real rather than nominal.
- Authorization: the caller must hold the permission that already governs asset creation. Do not invent a new permission; reuse what `add_asset` requires.
- Return the existing `AssetResponse` shape, now with `storage_path` populated.

### 4. Retrieval endpoint

- Return a **signed URL**, never bytes proxied through the API and never a public bucket path.
- `expires_in` is explicit at the call site — no default exists in the contract, deliberately. **This step passes 15 minutes** ([[#Decisions]] D3), as a named constant carrying its reasoning: long enough for a browser to fetch an asset it is about to display, short enough that a leaked URL stops working before it is useful.
- Call `provider.signed_url(asset.workspace_id, asset.storage_path, ttl)` using the two columns verbatim. **No parsing, splitting or prefixing** of the persisted value.
- An asset whose `storage_path` is null has no bytes; return a 404-shaped answer rather than a signed URL to nothing.
- Cross-tenant access must fail **at the route layer**, before the storage call — RLS already refuses the row, and the route must not turn a missing row into a signed URL for someone else's object.

### 5. Orphan handling in both directions

The asset table is the only index of what exists in storage (see [[#What expansion found that the outline did not anticipate]] item 3), so a mismatch between row and object is not self-healing.

- Decide and implement one explicit ordering. The recommended shape: **create the row first, upload second, then update `storage_path`** — so a crash mid-upload leaves a row with a null `storage_path` (visible, harmless, retryable) rather than an object no row knows about.
- On upload failure after the row exists, either roll the row back or leave it with a null `storage_path`; never leave it pointing at a locator that was not stored.
- On a storage success whose row update then fails, delete the just-stored object before returning the error — `delete` is idempotent, so this is safe to attempt.
- A database transaction cannot span the storage call. State plainly in the service docstring where the boundary is and what each side guarantees.

### 6. Extend erasure to the objects

- **Widen the erasure contract so a store can reach a `StorageProvider`** ([[#Decisions]] D1). All ten `ExportableStore` implementations move to the widened signature; the nine with no external bytes ignore the new argument. **No deletion path outside the registry** — the owner rejected that shape explicitly.
- Read the workspace's asset rows, take every non-null `storage_path`, and call `provider.delete(workspace_id, storage_path)` for each. Row-driven, because the contract has no listing.
- `delete` is idempotent, so a partially completed erasure is safe to re-run.
- **The row soft-delete stays exactly as it is.** Only object removal is added.
- A storage failure mid-erasure must not silently report success. The per-store count in `ErasureResult` is what makes an erasure auditable; extend that honesty rather than swallowing an error to keep the transaction green.

### 7. Tests

Every proof in [[#Required Tests and Proofs]], plus:

- Unit tests for logical-name derivation, including the collision case two uploads of the same filename would otherwise cause.
- A test that the configuration is genuinely required — startup fails without it.
- Follow the existing suite's fixture conventions; database-backed tests will skip locally and run in CI against the disposable `postgres:17` container, as every prior step's did.

### 8. Documentation

- Update [[Table - assets]] to record that `storage_path` is now populated, and by what.
- Record the upload/retrieval contract wherever the API surface is documented, following what STEP-23 and STEP-20 did for theirs.
- Update this note's status and the [[Build Plan]] index row together.

## Decisions

Four decisions this step could not take alone. **D1, D2 and D3 were resolved by the project owner on 2026-08-16**, before implementation began; **D4 surfaced during implementation** and was resolved by the owner the same day, before the endpoint it governs was written. Recorded here rather than guessed at ([[CLAUDE|CLAUDE.md]] §34), and recorded with the reasoning so a later session sees why the rule exists rather than only that it does.

### D1 — How does erasure reach a storage provider? — **Resolved**

**Decision: extend the erasure flow so asset deletion can reach `StorageProvider`. No out-of-band deletion path.**

`ExportableStore.erase(connection, workspace_id)` has no provider parameter and ten implementations. Three shapes were put to the owner:

- **(a) Widen the contract** — `erase` gains access to a provider. Uniform and honest, but touches all ten stores. **← chosen**
- **(b) Handle objects outside the registry** — `DataOwnershipService.erase_workspace` deletes objects before delegating. **← explicitly rejected**
- **(c) Construct `AssetStore` with a provider** — requires `REGISTERED_STORES` to stop being a module-level tuple of zero-argument instances. Not adopted.

**Why it went this way.** The registry's whole value is that a store absent from it is *visible* rather than invisible — an erasure result reporting `"assets": 0` is a number a reader can question, while a deletion path living outside the registry is one nobody knows to look for. Shape (b) would have reintroduced exactly that blind spot, and it is the shape every later store with external bytes would then have copied. The nine stores with nothing outside PostgreSQL ignore the widened argument; that is a small, uniform cost paid once.

**This remains a shared-contract change and therefore Critical** ([[CLAUDE|CLAUDE.md]] §21) — the owner's decision settles the *design*, not the merge gate. Review before merge still applies. No ADR was required: this is a contract change internal to one service, not a technology or architecture choice that constrains how the system is built ([[CLAUDE|CLAUDE.md]] §39).

### D2 — What is the upload size ceiling? — **Resolved**

**Decision: 100 MB per asset, as the initial limit.**

No source document set one, and it is not derivable from the schema. 100 MB comfortably covers the images, audio and documents an early workspace uploads while staying well below the memory pressure a single-request `data: bytes` upload implies.

**"Initial" is load-bearing.** The contract this step implements reads the whole body, so this ceiling and the absence of multipart upload are the same decision seen twice. A genuine need for larger media is a signal to revisit the transport ([[#Out of Scope]]), not to raise the number alone. [[STEP-33 Storage Quotas and Lifecycle]] owns per-workspace totals; this is per-asset only.

### D3 — What is the signed-URL TTL for a download? — **Resolved**

**Decision: 15 minutes.**

The backend bounds expiry at 7 days and supplies no default, deliberately — the choice belongs at the call site where the sensitivity of the object is known. 15 minutes is long enough for a browser to fetch an asset it is about to display, and short enough that a URL leaked through a referrer header, a shared screenshot or a log stops working before it is useful.

A signed URL is a bearer capability: anyone holding it can read the object, with no further authentication. Minutes rather than days is what keeps that exposure bounded.

### D4 — What wire format does the upload endpoint use? — **Resolved**

**Decision: `multipart/form-data`, adding `python-multipart` as a dependency.**

Not anticipated by expansion. It surfaced during implementation because FastAPI's `UploadFile` and `Form` require `python-multipart`, which is not in the [[CLAUDE|CLAUDE.md]] §10 stack table — so the transport choice and a new dependency turned out to be the same question. **Resolved by the project owner on 2026-08-16**, before the endpoint was written.

The alternative was a raw request body with the metadata in query parameters, which needs no dependency at all. It was rejected on the client side of the contract: a browser's file input posts `multipart/form-data` natively, so [[STEP-29 Asset Management UI]] sends a `FormData` and nothing else, while a raw body would force every client — the UI included — to hand-build a request. Paying one small, framework-native dependency to keep the public API conventional was judged the better trade.

**No ADR.** `python-multipart` is FastAPI's own documented prerequisite for uploads and ships inside `fastapi[standard]`; adopting it is using the chosen framework rather than adding to the stack ([[CLAUDE|CLAUDE.md]] §28). The dependency line records the reasoning where a reader meets it.

## Required Tests and Proofs

- An upload above the 100 MB ceiling is refused, proven by response body.
- A disallowed MIME type is refused, including one whose extension lies about its content.
- A cross-tenant download attempt fails through the route layer, not merely at the policy.
- Deleting a workspace removes its stored objects, not only its rows.
- **Two uploads of the same filename in one workspace produce two retrievable objects** — the collision Task 2 exists to prevent, asserted directly rather than assumed.
- **A failed upload leaves no row pointing at a locator that was not stored**, and no stored object with no row.

## Validation

Observed, not assumed ([[Execution Protocol#The Loop]] item 8).

1. **Done.** `ruff`, `ruff format --check` and `mypy` clean on `apps/api`, locally and in CI.
2. **Done.** Full API suite green locally: `695 passed, 338 skipped`, against a `618 / 321` baseline. Every skip is a database-backed test, as expected; no new skips beyond them.
3. **Done.** Each proof in [[#Required Tests and Proofs]] exists as a named test and was read individually — see the [[#Manual Test Checklist]], which ties each one to the test establishing it.
4. **Done.** The upload and download paths were driven end to end against the real `projectone-dev` bucket by `tests/test_asset_storage_live.py`, with nothing doubled: the route stores the bytes, the derived locator round-trips through `assets.storage_path`, and the signed URL is fetched over plain HTTP carrying no credentials. **Run by the project owner on 2026-08-16 and reported passing** — see the attestation in the completion record below.
5. **Done.** Erasure proven against a real object: `test_erasing_the_workspace_makes_the_object_unreachable` confirms the object exists, runs the real `AssetStore.erase` with a live provider, and asserts the object is then unreadable. Same run, same attestation.
6. **Done.** CI green on PR #19 and again on the merge commit: `1032 passed, 1 skipped`, with the `api` job's disposable `postgres:17` container running every database-backed test.

## Step Completion Record

Merged to `main` as **`2eeff40`** via **PR #19**, squash-merged by the project owner on 2026-08-16.

> [!warning] The commit subject on `main` understates what it contains
> `main`'s commit reads *"feat(step-28): enforce storage configuration at startup (#19)"* — the subject of the branch's **first** commit, which GitHub used for the squash. The commit actually carries **the whole step**: 28 files, +3116/−115, including the upload and download routes, the content validator, the logical-name derivation and the widened erasure contract.
>
> Recorded here because the history cannot be corrected — the commit is published, and Section 20 forbids rewriting it. A reader searching `main` for when upload arrived will not find it by subject; this note is the pointer.

**What shipped:** three new modules (`app/storage/logical_names.py`, `app/services/asset_content.py`, `app/services/asset_storage_service.py`), two new routes on `app/routers/projects.py`, the widened `ExportableStore.erase`, storage error handling in `app/core/errors.py`, and four new test modules carrying 94 tests.

**What is verified:** everything in [[#Required Tests and Proofs]], each against a real PostgreSQL database in CI. The collision proof, both orphan directions, the route-layer cross-tenant refusal, the extension-lies refusal and the object-level erasure all pass.

**The live gap, and how it was closed.** Everything above runs through
`RecordingStorageProvider`, an in-memory double — correct for CI, since live
vendor credentials must never become a routine pipeline dependency, but it left
Validation items 4 and 5 unmet: no byte in this step had reached Cloudflare.

`tests/test_asset_storage_live.py` closes that. Three opt-in tests behind three
gates (`PROJECTONE_RUN_R2_INTEGRATION_TESTS=1`, R2 configured, a real
PostgreSQL), refusing to run against any bucket but `projectone-dev`, with
teardown that deletes every object created and verifies the deletion.

> [!important] This result is attested by the project owner, not observed by Claude
> **The project owner ran the module on 2026-08-16 and reported all three tests
> passing.** Claude did not observe the run: the machine it works on has no
> container runtime and no PostgreSQL, so the tests skip there — verified
> directly rather than assumed.
>
> Recorded this way deliberately. Items 4 and 5 are marked `Done` on the
> owner's report, which is a different kind of evidence from the CI totals cited
> above, and a later reader should be able to tell which is which. Re-running
> the module is what turns the attestation back into an observation.

**What the live run establishes that CI cannot:** the logical name derived from
a database-issued UUID is one R2 actually accepts; the locator survives the
round trip through `assets.storage_path` unaltered; the workspace id reaches the
provider from the right source; the signed URL works for a client holding no
credentials; and `AssetStore.erase` removes real bytes rather than only rows.
Each of those would pass every doubled test while failing in production.

## Manual Test Checklist

No frontend ships in this step, so the checklist is API-level and is **not** "not applicable": the behaviour is user-visible through the API contract.

Four of the five are now established by **automated proofs against a real database**, which is a stronger guarantee than a manual pass: a manual check is performed once, while these re-run on every Pull Request. Each is ticked against the test that establishes it rather than against someone's recollection of having tried it.

- [x] Upload a real file to a project; the response carries a populated `storage_path`. — `test_an_upload_populates_the_storage_path`
- [x] Retrieve it; the signed URL returns the same bytes. — `test_a_download_returns_a_signed_url` with `test_the_uploaded_bytes_are_what_was_stored`
- [x] **Let a signed URL pass its 15-minute expiry; it stops working.** — Established in two halves; see the note below.
- [x] Upload a file whose extension disagrees with its content; it is refused with a usable message that does not echo the filename. — `test_a_file_whose_extension_lies_about_its_content_is_refused` and `test_a_refusal_never_echoes_the_filename`
- [x] Attempt a download as a member of a different workspace; refused at the route. — `test_a_cross_tenant_download_fails_at_the_route`, which also asserts no URL was signed

> [!note] Expiry is proven in two halves, and deliberately not in one
> No single test establishes this, because the honest version of "one test" would sleep fifteen minutes to re-derive something already known. Two tests compose instead:
>
> - **The value reaches the signature.** `test_the_signed_url_carries_the_fifteen_minute_lifetime` asserts the response advertises 900 seconds *and* that R2 signed the URL for 900 seconds — so a client cannot be told one lifetime while the URL carries another.
> - **R2 enforces a lifetime.** [[STEP-27 Storage Provider Abstraction]]'s `test_storage_r2_integration.py` issues a one-second URL, uses it, waits, and is refused by Cloudflare.
>
> Together: this step hands R2 fifteen minutes, and R2 enforces what it is handed. Stated as a composition rather than a single claim, because a reader is entitled to know that no test has watched *this* URL expire — and that the alternative is a quarter-hour sleep in the suite.
>
> `RecordingStorageProvider` cannot help here at all: it issues these URLs and does not implement expiry, so a test asserting one had expired would be the double agreeing with itself.

## Definition of Done

A user can upload a file to a project and retrieve it, with validation enforced, isolation proven through the route layer, and erasure covering the new store.

Additionally, per [[Execution Protocol#Step Completion]]:

- [x] Every decision resolved and recorded in this note — D1, D2 and D3 settled by the owner on 2026-08-16 before implementation; D4 settled the same day, during it.
- [x] Required CI green — `1032 passed, 1 skipped` on the merge commit, with every database-backed test running against the disposable `postgres:17` container. No review conversations were opened.
- [x] **Owner approval obtained** — the project owner merged PR #19 themselves on 2026-08-16. `main` is protected, so the merge *is* the approval act for a Critical change.
- [x] Status synchronized between this note and the [[Build Plan]] index.
- [x] **Manual checklist complete** — four items established by automated proof against a real database, the fifth by the two-test composition described above.
- [x] **Live storage proof executed** — `tests/test_asset_storage_live.py`, run against `projectone-dev` and reported passing by the project owner on 2026-08-16. Attested rather than observed; see [[#Step Completion Record]].

## Risks and Governance Gates

**Critical** — public API contract, tenant data boundary, and a new store subject to §16 deletion obligations. Upload endpoints are also a classic injection surface; validation is the step, not a detail of it. D1 adds a shared-contract change to that list.

**Owner approval is required before merge** ([[CLAUDE|CLAUDE.md]] §21). D1's design gate is already satisfied — the owner settled it on 2026-08-16 — but that is a decision about *shape*, not a merge approval, and the review gate stands unchanged.

Specific risks:

- **Silent overwrite.** Addressed by Task 2; the collision proof is what confirms it.
- **Cross-tenant object access.** The key module makes a traversal unconstructable, but a route returning a signed URL for a row it should not have read would bypass that entirely — hence the route-layer proof.
- **An erasure that reports success while leaving bytes behind.** The most consequential failure available here, because it looks like compliance.

## Audit Gaps Closed

File upload path — *Missing, P0*; Asset download / preview — *Missing, P1*

---

## Navigation

- **Previous:** [[STEP-27 Storage Provider Abstraction]]
- **Next:** [[STEP-29 Asset Management UI]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]] · [[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]]
