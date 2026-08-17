---
title: STEP-29 Asset Management UI
category: Development/Build Step
status: draft
version: "2.0"
last_updated: 2026-08-17
tags: [engineering, workflow, build-step, frontend, design-system]
step_id: STEP-29
step_status: In Progress
detail_level: full
phase: "Platform Substrate"
---

# STEP-29 — Asset Management UI

**Status:** In Progress — implementation began 2026-08-17 on `step-29-asset-management-ui`
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, and enough notification to make an asynchronous run visible.
**Detail level:** full — expanded 2026-08-17 against `main` @ `1a5f1e3`, with [[STEP-28 Asset Upload and Download]] merged and its routes readable in code.

> [!note] Expanded late, and by this step rather than its predecessor
> [[Execution Protocol#The Loop]] item 11 makes expansion the *preceding* step's obligation, while its context is loaded. STEP-28's completion record does not record doing it, so this note was still `outline` when STEP-29 was selected. Recorded rather than quietly corrected: a loop item that can be skipped without anything noticing is worth seeing once.

## Objective

Let a user upload, browse, preview and delete a project's assets from the product.

## Why This Step Exists Now

[[Projects]] requires assets to be organised and reviewable, and STEP-28 made that buildable: every route this step needs already exists and is proven against a real bucket. Until now the project detail screen could record that an asset was *intended* — it renders a list and a metadata-only form — but no file has ever reached it. Two strings on that screen currently tell the user so, and this step is what makes them false.

## Dependencies

- [[STEP-28 Asset Upload and Download]] — `Done`, merged as `2eeff40` via PR #19 on 2026-08-16.
- [[STEP-26 Product Design System Foundation]] — `Done`, under [[ADR-003 Design Token Architecture]] (`Accepted`).

## Inherited from earlier steps

Recorded during synchronization, not expansion.

Added by [[STEP-28 Asset Upload and Download]]:

- **The backend is finished. This step adds no route, no schema and no migration.** `POST .../assets/upload`, `GET .../assets/{id}/download` and `DELETE .../assets/{id}` all exist and are tested. Any scope here that appears to need a backend change is a signal to re-read, not to widen.
- **The upload endpoint takes `multipart/form-data`**, and D4 of that step chose it *for this step by name*: "a browser's file input posts `multipart/form-data` natively, so [[STEP-29 Asset Management UI]] sends a `FormData` and nothing else." Honouring that is the cheapest part of this step; the transport question below is about how the `FormData` crosses the Next.js boundary, not about the wire format.
- **The per-asset ceiling is 100 MB**, and D2 words it as the *initial* limit. It is the number the UI must be honest about, both in what it tells the user before an upload and in what it does with a 413.
- **A signed URL lives 15 minutes** (D3) and is a bearer capability — anyone holding it reads the object, with no further authentication. That single fact drives [[#D3 — When is a signed URL minted? — **Resolved**]].
- **`storage_path` is opaque.** Never parse, split, strip, prefix or render it. Non-null means "this asset has bytes"; null means it does not. That boolean is the only thing the UI may read from it.
- **Refusal messages never echo the filename**, by rule in `asset_content.py`. The UI must not reintroduce what the API deliberately withheld by pasting the filename back beside the error.
- **No listing operation exists in the storage contract.** The asset table is the only index of what exists in storage, so `GET .../assets` is the only enumeration available and the UI must not imply a filesystem view.

Added by [[STEP-26 Product Design System Foundation]]:

- **No component and no screen was touched by STEP-26.** It shipped the token layer in `globals.css` and the fonts in `layout.tsx`, and nothing else. **This step is the first real consumer of the §7.1 contracts** — which is why the Risks section below is about the contracts rather than about the feature.

## What expansion found that the outline did not anticipate

Five facts came out of reading the merged code rather than the plan. Each changes the shape of the work, so they are recorded here rather than discovered mid-implementation.

**1. A Server Action cannot carry this step's payload.** Every write in `apps/web` today goes through a Server Action. Next.js caps a Server Action body at **1 MB** by default — `next/dist/server/app-render/action-handler.js:519`, which also applies the cap to multipart parsing as `fieldSize` — against an API that accepts 100 MB. The established pattern does not reach the established ceiling. Resolved as [[#D1 — How do the bytes cross the Next.js boundary? — **Resolved**]].

**2. A Server Action also cannot report progress.** `useActionState` exposes pending or not-pending, and nothing between. The Scope below says "upload control with **progress**", and no amount of care inside the existing pattern produces a percentage. This is the same finding as item 1 seen from the user's side, and it is why D1 resolves toward a transport that has an event for it.

**3. `apiRequest` cannot send a `FormData`.** `lib/api.ts` hardcodes `Content-Type: application/json` and `JSON.stringify(body)` on every request. The multipart path needs its own function beside it rather than a widened `body` parameter — a single function that sometimes serialises and sometimes does not is the kind of conditional a reader has to hold in their head at every call site.

**4. There is no dialog contract to consume, but the tokens for one already exist.** §7.1 lists eight components and none of them is a dialog. Yet `--radius-lg` is documented as "Dialogs, panels", `--shadow-lg` as "Dialogs" and `--color-surface-raised` as "Dropdowns, dialogs" — the token layer anticipated a dialog that was never built, because STEP-26 built no components at all. So the confirmation control is a *new contract*, not a workaround, and §9a rule 2 (trap focus, close on `Escape`, return focus to the opener) is the nearest binding precedent. Resolved as [[#D4 — What shape is the delete confirmation? — **Resolved**]].

**5. The web test suite has no DOM, deliberately.** `vitest` runs in a node environment; the suite uses `renderToStaticMarkup`, and `dashboard-screen.test.tsx` argues in its own header why RTL plus jsdom were rejected ([[CLAUDE|CLAUDE.md]] §28). Static rendering cannot drive hook state, so two of this step's four required proofs — "all four async states render" and "keyboard reachability and focus order" — are not automatable as the suite stands. This shapes the component decomposition rather than the dependency list; see Task 2 and [[#Risks and Governance Gates]] R1.

## Scope

- Upload control with real byte-level progress and failure handling, for files up to the API's 100 MB ceiling.
- Asset list per project, using the [[Design System]] contracts from STEP-26.
- Preview for the kinds that can be previewed; an honest fallback for those that cannot.
- Delete with confirmation, through a new shared `ConfirmDialog` whose contract is added to [[Design System]] §7.1 in the same change.
- Loading, empty, error and success states as [[CLAUDE|CLAUDE.md]] §11 and [[Design System]] §10 require.

## Out of Scope

- No bulk operations, no folders, no tagging, no search.
- No inline editing of asset content.
- **No backend change of any kind.** No new route, no new field on `AssetResponse`, no migration. [[#D2 — How is preview decided without a MIME type? — **Resolved**]] closes the one place this was tempting.
- **No [[Dashboard]] *Upload Files* quick action** — [[#D6 — Does the Dashboard quick action ship here? — **Resolved**]]. This narrows the Audit Gaps Closed line the outline carried; see that section.
- **No chunked or resumable upload.** Inherited from STEP-28's exclusion. One request, one body, bounded by the ceiling.
- **No image transformation or thumbnailing** — [[STEP-32 Media Processing Pipeline]]. A preview renders the original bytes or it does not render.
- **No client-side re-implementation of the server's format allowlist.** The `accept` attribute is a picker hint only; see Task 2.

## Surfaces Affected

**Frontend:** the project detail screen, a new shared confirmation component, a new same-origin upload route handler, and the server-only API client. **Backend:** none. **Database:** none.

## Required Documentation

A candidate list, not a reading list ([[Execution Protocol#Context Discipline]] rule 2). Each entry names the question it would answer; skip any whose question does not arise.

| Document | The question it answers | Likely needed |
|---|---|---|
| `apps/web/src/lib/api.ts` | How does a request reach the API, and what does it hardcode? | **Yes** — already read during expansion; Task 1 modifies it |
| `apps/web/src/app/(app)/projects/[projectId]/page.tsx` | What does the screen render today? | **Yes** — the step rewrites its Assets section |
| `apps/web/src/app/(app)/projects/actions.ts` | What is the `FormState` contract and how are API errors mapped? | **Yes** — `toFormState` gains two status codes |
| [[Design System]] §7.1, §9.1, §9a, §10 | What contract must a new shared component satisfy? | **Yes** — Task 3 adds a contract to §7.1 |
| `apps/web/src/app/session/expired/route.ts` | What does a route handler look like in this codebase? | **Yes** — the only existing one, and Task 1's precedent |
| `apps/api/app/services/asset_content.py` | Which formats are accepted, and what does each refusal say? | **Yes** — for `accept` hints and error wording |
| `apps/web/src/components/settings/SettingsForm.tsx` | How does an existing client form handle error focus and announcement? | Only for the pattern; do not restate it in a new component |
| [[STEP-28 Asset Upload and Download]] | Why 100 MB, why 15 minutes? | Already captured above under Inherited — re-read only if a decision is questioned |
| [[Table - assets]] | — | **No.** No schema change, and `AssetResponse` is the contract the UI sees |
| [[Security Architecture]] | — | **No.** The relevant rules are the token boundary and the bearer-capability TTL, both already known |

## Tasks

### 1. Transport: a same-origin upload route handler

The bytes must reach the API without the access token reaching the browser, and with an event the UI can count progress from ([[#D1 — How do the bytes cross the Next.js boundary? — **Resolved**]]).

- Add a route handler under `apps/web/src/app/api/` mirroring the API's own path shape, following `app/session/expired/route.ts` as the local precedent for the file convention.
- The handler resolves the session server-side exactly as a Server Action does — `requireProfile()` / `resolveAccessToken()` — so **the httpOnly cookie stays httpOnly and no token is ever serialised to the client**. This is the whole reason the browser does not talk to the API directly, and the reason a direct-to-bucket upload was rejected outright.
- Forward the multipart body to `POST .../assets/upload`. Prefer streaming the request body over buffering it; a 100 MB upload buffered in the Next process is memory the route does not need to hold.
- Add `uploadAsset()` to `lib/api.ts` **beside** `apiRequest`, not through it — `apiRequest` hardcodes JSON serialisation, and a conditional inside it would make every existing call site harder to read for the benefit of one new one.
- Map the API's refusals through unchanged. 413, 415, 429 and 404 each already carry a `public_message` written to be shown; the handler must not replace them with a generic failure, and must not append the filename the API deliberately omitted.

### 2. Upload control

- A Client Component owning a file input and an `XMLHttpRequest`, with the reason for `"use client"` stated in its own docstring (§7.1 rule 3). XHR rather than `fetch` for one reason worth writing down: `upload.onprogress` exists and `fetch` has no equivalent that is safe to rely on.
- **Split presentation from state.** The component owning the XHR holds progress, error and success; a pure presentational component receives them as props. This is §11 separation, and it is also the only way the state proofs in [[#Required Tests and Proofs]] are testable in a suite with no DOM (see R1).
- All four §10 states: an indeterminate state while the request opens, a determinate bar once bytes are moving, `role="alert"` on failure with focus moved to it, and an announced success naming what was added.
- **Refuse locally what the server would refuse anyway** — a file over 100 MB should not be uploaded for ninety seconds in order to be rejected. State the ceiling in the control's hint text before a file is chosen, not only in the error after.
- `accept` is derived from the chosen kind as a **picker hint only**. The server is the sole authority on format; the client copy exists so the file dialog is not a list of everything. Record that at the definition, in the way `lib/projects.ts` already records why `ASSET_KINDS` is mirrored.
- On success, `revalidatePath` the project route so the new asset appears in the server-rendered list rather than being pushed into client state.

### 3. `ConfirmDialog`, and its contract

The screen deletes assets today with a single unconfirmed click. The step requires confirmation, and §7.1 has no dialog to consume ([[#D4 — What shape is the delete confirmation? — **Resolved**]]).

- Build it as a **shared** component in `components/shell/`, not a one-off inside the projects feature — a second consumer is certain, and §39's rule-of-three starts by not making the first copy hard to find.
- **Add its contract to [[Design System]] §7.1 in the same change**, with its public interface and its required states, exactly as this step's Risks section instructs. A component that exists in code and not in §7.1 is the drift that section exists to prevent.
- Behaviour is fixed by §9a rule 2, the nearest binding precedent: trap focus while open, close on `Escape`, **return focus to the control that opened it**.
- Native `<dialog>` unless something concrete rules it out — it brings the focus trap, the `Escape` handler and the backdrop without a dependency (§28).
- The confirming action is `intent="danger"`, names the asset being deleted, and is never the default-focused control.

### 4. Asset list, rows and preview

- `AssetList` and `AssetRow` are **Server Components** (§7.1 rule 3). Only the preview control and the dialog need the client.
- A row shows the human-readable `assets.name`, its kind label, and its creation date. **It never shows `storage_path`** — the only thing read from that column is whether it is null.
- **An asset with a null `storage_path` is a first-class state, not an error.** It was recorded through the metadata-only form and has no bytes. It renders as "no file attached" with no preview control, and never as a broken preview.
- Preview is decided by `kind` alone ([[#D2 — How is preview decided without a MIME type? — **Resolved**]]): `image` → `<img>`, `video` → `<video controls>`, `audio` → `<audio controls>`, `document` → **no inline preview**, offering a download link and a plain sentence saying preview is not available for this type. That fallback is the "degrades honestly" proof.
- Every preview element carries the accessible name the asset already has. An `<img>` whose `alt` is empty is a defect here, not a decoration.

### 5. Lazy signed URLs

- A signed URL is minted **on user action only** — never for every asset at render time ([[#D3 — When is a signed URL minted? — **Resolved**]]).
- Add a Server Action returning `{ url, expires_in_seconds }` for one asset, reusing the existing `FormState` conventions in `actions.ts`.
- **A signed URL must never appear in the server-rendered HTML** of the project page, and never in a `revalidatePath`-cached render. It is a bearer capability with a 15-minute life; baking one into a cacheable document hands it to whoever the cache serves next.
- Handle expiry honestly: a preview left open past 15 minutes will fail, and the failure must offer a working retry that re-mints (§10 rule 4 — a retry that does not re-run the operation is worse than none).

### 6. Wire into the project screen, and correct the copy

- Replace the Assets section of `app/(app)/projects/[projectId]/page.tsx` with the upload control and the new list.
- **Two strings are now false and must go** — [[CLAUDE|CLAUDE.md]] §19 treats documentation drift as a bug, and product copy asserting an absent capability is the same defect one layer out:
  - line 154: `"…Uploading files is not available yet."` in the `EmptyState` description.
  - line 219: `"Records the asset. File upload is not available yet."` as the `AssetKindField` hint.
- **The metadata-only *Add asset* form stays** ([[#D5 — Does the metadata-only form survive? — **Resolved**]]). Its hint is rewritten to say what it actually does — record an asset that does not have a file yet — so the two controls are not two spellings of the same thing.
- Any new `SettingsForm` call site added here is already covered by `form-boundary.test.ts`, whose `CALL_SITES` array names this file. Adding a call site needs no test change; adding a *file* with one does.

### 7. Tests

Every proof in [[#Required Tests and Proofs]], plus:

- Presentational components tested directly with `renderToStaticMarkup` over a props matrix — the decomposition in Task 2 is what makes this possible without adding jsdom.
- A source-level assertion, in the style of `form-boundary.test.ts`, that `storage_path` is never rendered and never parsed anywhere in `apps/web`.
- An assertion that no signed URL reaches the server-rendered markup of the project page.
- Follow the existing suite's conventions. **No new test dependency is added by this step**; R1 records why, and what the honest long-term answer is.

### 8. Documentation

- Add the `ConfirmDialog` contract to [[Design System]] §7.1, and record any §7.1 contract that did not survive contact with a real screen (that finding is this step's stated purpose, not a side effect).
- Update this note's Validation, Manual Test Checklist and Step Completion Record, and the [[Build Plan]] index row, together.
- Expand [[STEP-30 Async Job Infrastructure]] to full detail, per [[Execution Protocol#The Loop]] item 11 — the item this step's own predecessor missed.

## Decisions

Seven decisions this step could not take alone. **All seven were resolved by the project owner on 2026-08-17**, before implementation began, against a written plan. Recorded here rather than guessed at ([[CLAUDE|CLAUDE.md]] §34), and recorded with the reasoning so a later session sees why the rule exists rather than only that it does.

### D1 — How do the bytes cross the Next.js boundary? — **Resolved**

**Decision: a same-origin route handler in `apps/web`, called from the client with `XMLHttpRequest`.**

The API accepts 100 MB; a Next.js Server Action accepts 1 MB by default and reports no progress. Three shapes were put to the owner:

- **(a) Server Action with `experimental.serverActions.bodySizeLimit` raised to 100mb.** Matches every existing write path, smallest new surface. Costs: no progress beyond a spinner, and the file buffers in the Next process as well as the API's.
- **(b) Route handler plus client XHR.** ← **chosen**
- **(c) Direct browser-to-bucket upload with a signed PUT.** ← **rejected outright**

**Why it went this way.** The Scope says "progress", and (a) cannot produce a number — a user uploading a 60 MB video would watch an indeterminate spinner for a minute with no way to distinguish progress from a hang. (b) is the only shape with an event to count. The cost is one route and one client component, and the token boundary is unchanged: the handler reads the httpOnly cookie server-side exactly as a Server Action does.

**(c) was rejected on security, not effort.** It needs a backend endpoint this step has no mandate for, and it routes bytes around `asset_content.py` entirely — the magic-byte check STEP-28 built precisely because a declared type and an extension are both strings a client chooses. Accepting bytes no one sniffed would undo that step's central proof.

**No ADR.** This is a transport choice inside one application, using framework capabilities already in the §10 stack — an execution decision, not one that constrains how the system is built ([[CLAUDE|CLAUDE.md]] §39).

### D2 — How is preview decided without a MIME type? — **Resolved**

**Decision: preview is decided by `kind` alone. `AssetResponse` does not gain a MIME type.**

`AssetResponse` carries `id, project_id, name, kind, storage_path, created_by, created_at` — no MIME type and no size — so per-kind is the granularity actually available. The alternative was adding the stored canonical MIME type to the response, which `validate_upload` already returns and the service could persist.

**Why it went this way.** That alternative is a **public API contract change** — Critical under [[CLAUDE|CLAUDE.md]] §21 — sitting inside a step whose Surfaces Affected says "Backend: none". Four kinds map cleanly onto four rendering strategies, and the only thing a MIME type would buy today is distinguishing PDF from a hypothetical second document format that does not exist. [[STEP-32 Media Processing Pipeline]] is the step with a real need for per-format metadata; if it wants this field, it can justify it on its own terms rather than inheriting it from a UI convenience.

### D3 — When is a signed URL minted? — **Resolved**

**Decision: lazily, on user action. Never eagerly at render.**

Eager minting would issue one API call per asset on every page load, burn the 15-minute TTL while the user reads the page, and place a bearer capability into HTML that Next may cache.

**Why it went this way.** The last of those is the decisive one. STEP-28's D3 chose fifteen minutes specifically to bound what a leaked URL is worth, and rendering one into a cacheable document is a leak with extra steps. Lazy minting costs image thumbnails in the list — a real UX loss, accepted — and buys a URL that is always fresh, one request per actual intent, and no capability in any cached render.

### D4 — What shape is the delete confirmation? — **Resolved**

**Decision: a new shared `ConfirmDialog`, with its contract added to [[Design System]] §7.1 in the same change.**

The alternative was a two-step inline confirm, which adds no shared component and no focus-trap surface.

**Why it went this way.** This step's own Risks section says a contract that does not survive contact with a real screen is a finding for [[Design System]] rather than something to work around here — and "no dialog contract exists" is exactly that finding. The token layer already names dialogs in three places (§4.2, §4.3, §6.2) while §7.1 defines none, because STEP-26 shipped no components at all. Building the component and leaving §7.1 silent would preserve the gap for the next step to rediscover.

The cost is honest: a dialog brings §9a rule 2's focus-trap, `Escape` and focus-return obligations, and R1 means those are verified through the rendered accessibility tree rather than automatically — which §9.2 already names as the standard for dialog work.

### D5 — Does the metadata-only form survive? — **Resolved**

**Decision: yes. Both controls ship, with wording that distinguishes them.**

`POST .../assets` records an asset with no bytes, and the API's own docstring defends it: an asset can be planned before it exists.

**Why it went this way.** Removing it is a scope reduction nobody asked for, and it would delete a capability a user of the current screen already has. The genuine risk is two controls that look like two ways to do one thing; that is a copy problem with a copy solution, and Task 6 owns it.

### D6 — Does the Dashboard quick action ship here? — **Resolved**

**Decision: no. Out of scope for STEP-29.**

The outline's Audit Gaps Closed line named the [[Dashboard]] *Upload Files* quick action, while Surfaces Affected said project asset surfaces only. The two disagreed and the owner settled it toward the narrower reading.

**Why it went this way.** Uploads are per-project and there is no workspace-level upload destination, so an honest Dashboard action would link to `/projects` to pick one first — which is a navigation link wearing an upload label. Shipping it would also mean editing `dashboard-screen.test.tsx:435`, which currently asserts `"Upload Files"` is *absent*, to assert the opposite. Changing an existing test's meaning to accommodate a contested addition is the sequence worth stopping at.

**Consequence recorded:** the Audit Gaps Closed line below is narrowed accordingly, and the Dashboard gap stays open against a later step rather than being silently claimed here.

### D7 — Is this step Critical? — **Resolved**

**Decision: not Critical under [[CLAUDE|CLAUDE.md]] §21. Ordinary review before merge.**

The §21 trigger list is schema, authentication, authorization, security controls, billing, public API contract, infrastructure, AI/agent architecture, the Memory System, multi-tenancy/RLS, or a breaking change. This step touches none: no backend, no schema, no contract change, no new permission, and the token boundary is preserved rather than moved.

**Why the question was asked at all.** §21 says uncertainty defaults to Critical, and two things here are adjacent to the list — a new route handler that handles a session token, and a surface that renders bearer capabilities. Both were examined. The handler reads the same cookie through the same helpers a Server Action already uses and grants no access that did not already exist; D3 keeps capabilities out of rendered HTML entirely. Adjacent is not the same as touching, and the classification is recorded so a reviewer can disagree with the reasoning rather than only with the conclusion.

**This changes nothing about the merge gate.** Claude opens the Pull Request; the owner merges it ([[CLAUDE|CLAUDE.md]] §20a). Non-Critical describes the review depth required, not the existence of a review.

## Required Tests and Proofs

- **Upload failure surfaces an actionable message rather than a silent no-op** — one proof per refusal class: 413 oversize, 415 type/extension/content mismatch, 429 rate limit, and a transport failure with no response at all.
- **A refusal never echoes the filename**, preserving the rule the API enforces on its side.
- **All four async states render** — loading, empty, error, success — for both the upload control and the asset list, and **empty is never rendered when the true state is error** (§10 rule 2).
- **Keyboard reachability and focus order on every interactive control**, including the dialog's focus trap, its `Escape` close, and focus returning to the control that opened it.
- **A preview of an unsupported kind degrades honestly instead of erroring** — a `document` renders the fallback and a download link, not a broken `<img>`.
- **An asset with a null `storage_path` renders as "no file attached"**, with no preview control and no error.
- **`storage_path` is never rendered and never parsed** anywhere in `apps/web`.
- **No signed URL appears in the project page's server-rendered markup.**
- **A file above the 100 MB ceiling is refused before it is uploaded**, not after.

## Validation

Observed, not assumed ([[Execution Protocol#The Loop]] item 8).

1. **Done.** `eslint . --max-warnings=0` and `tsc --noEmit` clean on `apps/web`, run locally on 2026-08-17.
2. **Done.** Full web suite green locally: **324 passed, 26 files**, against a **261 / 22** baseline measured on this branch before any test was written — **+63 tests in 4 new files**. No skips, none before and none added.
3. **Done.** `next build` compiles and the new endpoint is registered as a dynamic route: `ƒ /api/workspaces/[workspaceId]/projects/[projectId]/assets/upload`. A production build is what would catch a server/client boundary violation that `tsc` accepts, so it is run as validation rather than assumed from a green typecheck.
4. **Done.** Each proof in [[#Required Tests and Proofs]] exists as a named test and was read individually — see the [[#Manual Test Checklist]], which ties each one to the test establishing it.
5. **Not done — requires a running API and a browser.** The upload path driven end to end with real files of each previewable kind, one over the ceiling, and one whose extension lies about its content. Claude cannot observe this: the machine it works on has no running API. See the [[#Manual Test Checklist]].
6. **Not done — requires a browser.** Keyboard-only pass over the Assets section, and the dialog verified through the rendered accessibility tree per [[Design System]] §9.2.
7. **Not done.** Required CI green on the Pull Request — no Pull Request has been opened.

## Manual Test Checklist

The change is entirely user-visible, so this is the load-bearing half of validation — R1 means the interaction proofs cannot all be automated in the current suite.

**Established by automated proof**, which is stronger than a manual pass: a manual check happens once, these re-run on every Pull Request. Each is ticked against the test that establishes it rather than against a recollection of having tried it.

- [x] An over-ceiling file is refused before any byte is sent. — `AssetUpload` checks `MAX_UPLOAD_BYTES` before opening the request; the ceiling and its wording are asserted in `asset-surface.test.tsx`
- [x] A refusal is shown with the API's own message and never names the file. — `upload-route.test.ts` *"never adds a filename to a refusal the API left out"*, and `asset-surface.test.tsx` *"never echoes a filename it was not given"*
- [x] All four async states render. — `asset-surface.test.tsx`, five `UploadStatus` cases plus the list's empty state
- [x] An asset with no file reads "No file attached" and offers no preview. — `asset-surface.test.tsx` *"says plainly when an asset has no file, and offers no preview"*
- [x] A PDF offers a link rather than a broken preview pane. — `asset-surface.test.tsx` *"labels the control for a document asset as Get link"*
- [x] No signed URL appears in server-rendered markup. — `asset-surface.test.tsx` *"puts no signed URL into server-rendered markup"*
- [x] `storage_path` is never rendered or taken apart. — `asset-surface.test.tsx`, one rendering proof and one source-level proof across all five components
- [x] An expired preview offers a retry that genuinely re-mints. — the retry calls the same `load` as the first attempt; the failure branch is asserted in `AssetPreview`
- [x] A lost session during upload answers 401 rather than redirecting into a sign-in page. — `upload-route.test.ts`

**Requires a browser and a running API.** These are the items R1 names, plus the ones that need real bytes. **None has been performed** — Claude cannot reach a browser or a running API from this machine, verified rather than assumed.

- [ ] Upload a real image; progress advances through determinate percentages and the asset appears without a full page reload.
- [ ] Upload a real video of tens of megabytes; the percentage moves smoothly rather than jumping from 0 to 100.
- [ ] Upload a file whose extension disagrees with its content; the API's 415 is displayed.
- [ ] Preview an image, a video and an audio asset; each renders from a freshly minted URL.
- [ ] Leave a preview open past 15 minutes, then act on it; the failure is honest and *Try again* recovers.
- [ ] Delete an asset; the dialog traps focus, closes on `Escape`, and returns focus to the trigger.
- [ ] Traverse the entire Assets section with the keyboard alone; tab order follows visual order and no control is unreachable.
- [ ] Disconnect the network mid-upload; the error is actionable.
- [ ] View the page source of a loaded project page in the browser; no signed URL is present.

## Definition of Done

A user can upload, see, preview and delete project assets, with every async state defined and accessibility preserved.

Additionally, per [[Execution Protocol#Step Completion]]:

- [x] Every decision resolved and recorded in this note — D1 through D7 settled by the owner on 2026-08-17, before implementation.
- [x] `ConfirmDialog`'s contract present in [[Design System]] §7.1, with the reason the gap existed recorded beside it.
- [x] The two false strings on the project screen removed — the `EmptyState` description and the `AssetKindField` hint both now describe what the screen does.
- [x] [[STEP-30 Async Job Infrastructure]] expanded to full detail.
- [x] Status synchronized between this note and the [[Build Plan]] index.
- [ ] **Manual checklist complete** — nine items established by automated proof; nine require a browser and a running API and have not been performed.
- [ ] **Required CI green on the Pull Request** — no Pull Request has been opened.

## Implementation Record

**Not merged. No Pull Request has been opened, and nothing has been pushed** — the owner asked for review before delivery.

**What shipped**, as five new components, one new route, and edits to five existing files:

| File | What it does |
|---|---|
| `app/api/workspaces/[workspaceId]/projects/[projectId]/assets/upload/route.ts` | **New.** Streams a browser's multipart body to the API, carrying the session |
| `components/projects/AssetUpload.tsx` | **New.** The `XMLHttpRequest` upload, its progress and its failures |
| `components/projects/UploadStatus.tsx` | **New.** The four states, drawn from a prop so they can be asserted without a DOM |
| `components/projects/AssetList.tsx`, `AssetRow.tsx` | **New.** Server Components: the list, the empty state, one row |
| `components/projects/AssetPreview.tsx` | **New.** Mints a URL on click and renders per kind |
| `components/shell/ConfirmDialog.tsx` | **New.** Shared native-`<dialog>` confirmation, contract in [[Design System]] §7.1 |
| `lib/api.ts` | `uploadAsset`, `assetDownloadUrl`, `ApiAssetDownload`, extracted `decodeResponse` |
| `lib/projects.ts` | Ceiling, `accept` hints, preview mode, `AssetUrlResult`, upload path |
| `app/(app)/projects/actions.ts` | `assetDownloadUrlAction` |
| `app/(app)/projects/[projectId]/page.tsx` | Wired up; both false strings removed |
| `components/projects/AssetKindField.tsx` | Optional `onChange`, so the picker's `accept` can follow the chosen kind |

**Scope held.** No backend file was touched, no migration exists, no dependency was added, and `AssetResponse` is unchanged — D2's alternative would have been a public API contract change.

### What implementation found that expansion did not

**1. `apiRequest` needed a shared decoder, not a wider signature.** The plan said to add `uploadAsset` beside it. Doing so would have duplicated the error-envelope decoding, so that decoding was extracted to `decodeResponse` and both call it. A refusal now looks identical whichever function sent the request, which is the property that would otherwise have drifted.

**2. TypeScript's DOM library has not adopted `duplex`.** Streaming a request body requires `duplex: "half"`, which the runtime implements and `RequestInit` does not declare — so the literal failed the excess-property check. Resolved with a declared `StreamingRequestInit` interface rather than a cast, because `any` is forbidden ([[CLAUDE|CLAUDE.md]] §35) and an erased field would lose the reason it is there.

**3. The upload route must stay out of the proxy's matcher, and that is load-bearing.** `proxy.ts` answers a session-less request with a 307 to sign-in. An `XMLHttpRequest` follows a redirect transparently, so an unauthenticated upload would have reported success carrying a sign-in page. The handler refuses with a 401 and the error envelope instead. Asserted in `upload-route.test.ts`.

**4. `FormField` and `AssetKindField` both survived contact with a non-`SettingsForm` caller** — the finding R2 predicted, resolved in their favour. Both already accept explicit `error` and `disabled` props for exactly this case, so the upload form reuses them rather than reimplementing labelled inputs.

**5. There is no shared contract for a file input or a progress indicator**, and none was added. A native `<progress>` element already carries the right semantics, and the file input has one caller. Recording the absence rather than writing a speculative contract, per §7.1's own rule that a contract for an unbuilt domain reads as a decision.

## Risks and Governance Gates

**Not Critical** ([[#D7 — Is this step Critical? — **Resolved**]]), and the ordinary review-before-merge gate applies unchanged. Claude opens the Pull Request; the owner merges it.

**R1 — Two required proofs are not automatable in the current suite.** The web suite runs in node with no DOM, by a decision `dashboard-screen.test.tsx` argues in its own header. Static rendering cannot drive hook state or dispatch a keypress, so "all four async states" and "focus order" cannot be fully proven by `vitest` as things stand.

*Mitigation:* decompose so the presentational half takes state as props and is statically renderable across a props matrix — better design regardless (§11) — and carry the interaction proofs on the manual checklist, which §9.2 already names as the standard for dialog work. **No test dependency is added by this step.** Adding jsdom is the honest long-term answer and deserves to be its own decision with its own reasoning, not two dev dependencies arriving inside a UI step ([[CLAUDE|CLAUDE.md]] §28, §29).

**R2 — First real consumer of the STEP-26 contracts.** Stated in the outline and unchanged by expansion, except that expansion found the first failure before implementation started: §7.1 defines no dialog, no file input and no progress indicator. D4 routes the dialog finding back into [[Design System]] as the outline instructed. Expect at least one more, and route it the same way rather than working around it here.

**R3 — A capability rendered into a cached document.** A 15-minute bearer URL in a server-rendered page that Next may cache is the most consequential failure available in this step, because nothing about it looks wrong. D3 is the design answer; the markup assertion in Task 7 and the page-source check on the manual list are what keep it true.

**R4 — A duplicated format allowlist drifting from the server's.** The `accept` hint mirrors `ALLOWED_TYPES`, and a mirror is a second copy. Bounded by making it a picker hint with no authority: if it drifts, a user sees a slightly wrong file dialog and the server still refuses correctly. Recorded at the definition so the next reader knows which copy decides.

**R5 — Double buffering on a large upload.** Under D1 a 100 MB upload passes through the Next process as well as the API's. Streaming the body in Task 1 bounds it; the coupling itself is the one STEP-28's D2 already recorded between the ceiling and the transport, and it is a signal to revisit the transport rather than the number.

## Audit Gaps Closed

Asset download / preview — *Missing, P1*

> [!note] Narrowed from the outline
> The outline also claimed the [[Dashboard]] *Upload Files* quick action. [[#D6 — Does the Dashboard quick action ship here? — **Resolved**]] puts it out of scope, so that gap stays open against a later step rather than being claimed by a step that does not close it.

---

## Navigation

- **Previous:** [[STEP-28 Asset Upload and Download]]
- **Next:** [[STEP-30 Async Job Infrastructure]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]] · [[Design System]]
