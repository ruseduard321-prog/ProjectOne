---
title: AI Router Implementation
category: Architecture
status: stable
version: "1.0"
last_updated: 2026-08-03
tags: [ai, backend, architecture, security, standards]
aliases: ["AI Router", "Provider Abstraction", "BYOK"]
---

# AI Router Implementation

**How ProjectOne routes an AI call to a provider**, established by [[STEP-17 AI Router and Provider Abstraction]] and binding from that point on.

[[AI Providers]] specifies *what* this layer must do — BYOK, selection, health monitoring, retries, fallbacks, provider replacement. This note records *how* it is built and which decisions are now settled.

> [!warning] No user-facing path reaches a provider yet
> [[STEP-18 AI Cost Governance Controls]] is a **hard gate**. This step deliberately builds the machinery that *makes calls* before the machinery that *bounds spend*, which is only safe because nothing user-facing calls it. Putting a real provider call in front of a user before STEP-18 is `Done` is a plan problem to raise, not a risk to absorb.

## The Layering

```
routers/          (none yet - STEP-19 and STEP-23 add them)
    v
AIService         joins a workspace's credentials to the router
    v
AIRouter          selection, retries, fallback, health
    v
AIProvider        one abstract method per capability
    v
OpenAIProvider / AnthropicProvider
```

The naming collision is worth stating: **`AIRouter` is a service, not an HTTP router.** It lives in `app/ai/`, not `app/routers/`, and follows the established router → service → repository layering as the *service* tier.

`app/ai/` imports no FastAPI, no psycopg and no vendor SDK. That constraint is deliberate — it is what would let the package move to `packages/` if a second application ever needs it. **It has not been moved**: introducing the first shared package is a structural decision belonging to the owner ([[CLAUDE|CLAUDE.md]] §8), and a package with one consumer is indirection without a benefit.

## The Provider Contract

An **abstract base class**, not a `Protocol`. A Protocol is structurally satisfied by any object with the right shape, so a provider missing `name` would be accepted silently and fail when first selected — in production, on a real request. An ABC fails at import, which is the only time this mistake is cheap.

| Member | Purpose |
|---|---|
| `name` | Stable identifier. A **wire value**: it keys BYOK rows, so renaming orphans stored credentials. |
| `capabilities` | Answers the selection flow's capability check. |
| `cost_per_1k_tokens` | Indicative USD, for the cost stage only. Not billing input. |
| `complete(request, api_key)` | **Exactly one attempt.** |

**`complete` makes one attempt and never retries.** A provider retrying internally would multiply the router's ceiling by its own count, and the real spend limit would be a product nobody wrote down ([[CLAUDE|CLAUDE.md]] §15a).

**The key is a per-call parameter, never instance state.** A provider object is shared across tenants; holding a key on it would put one tenant's credential where another tenant's request could reach it.

### What the abstraction actually absorbs

Two providers is the minimum that proves an interface is real — a single implementation always fits its own interface. Anthropic differs from OpenAI in four ways, and each is contained in its adapter:

| | OpenAI | Anthropic |
|---|---|---|
| Credential | `Authorization: Bearer` | `x-api-key` |
| System prompt | a `role: system` message | **top-level `system` field** |
| Response text | `choices[0].message.content` | `content[]` text blocks |
| Usage | `prompt_tokens` / `completion_tokens` | `input_tokens` / `output_tokens` |

The system-prompt difference is the load-bearing one: **Anthropic rejects a `system` role inside `messages`**, so a request built naturally for OpenAI is invalid there. The router must hand the *identical* `CompletionRequest` to either, so `_split_system` reconciles it. That is the concrete justification for the interface existing at all.

Written against the HTTP APIs rather than vendor SDKs. `httpx` is already a runtime dependency, so this adds nothing to the dependency surface, while each SDK would add its transitive tree, its own retry logic fighting the router's ceiling, and its own release cadence ([[CLAUDE|CLAUDE.md]] §28).

## Errors Are Typed by What To Do About Them

```
ProviderError
├── RetryableProviderError    → retry, then fall back
│   ├── ProviderTimeoutError
│   ├── ProviderUnavailableError
│   └── ProviderRateLimitedError
└── TerminalProviderError     → do not retry; still fall back
    ├── ProviderAuthenticationError
    └── ProviderRequestError
```

Organised around **one question — is retrying plausibly going to help?** — because that is the only distinction the router acts on. A taxonomy by HTTP status would need interpreting, and interpretation in a `match` statement is something every new provider can get subtly wrong.

**Terminal errors still fall back.** Terminal means "do not try *this provider* again with this request", not "give up": a workspace whose OpenAI key was revoked can still be served by Anthropic.

`ProviderRateLimitedError` is distinct from the API's own `RateLimitExceededError` and must not be conflated. That one means the caller has spent their allowance *here*; this one means the workspace's own upstream account is throttled, and the remedy is a different provider rather than waiting.

> [!important] The 429 ordering is load-bearing
> A naive "4xx is terminal" check classifies throttling as terminal and never retries a condition that is purely temporal. Both adapters check 429 before the generic 4xx branch, and the shared contract suite asserts it for every provider.

## Selection

[[AI Providers]]' documented flow, and **the order is the contract**:

**preference → capability → availability (health) → cost → selection**

Cost is last deliberately: a cheap provider that cannot do the job, is down, or has no key is not a candidate at any price.

- **BYOK is a hard filter.** No key, no call. Checked before health so an unconfigured workspace does not read as an outage.
- **A preference ranks among survivors; it is not an override.** Preferring an unhealthy provider does not resurrect it.
- **Ties break on name.** Without it, two equally-priced providers order by dictionary insertion — making the choice depend on import order and turning a reproducible decision into a coin flip nobody can debug.

`select()` returns the whole ordered chain plus a `SelectionReason`, which records what was considered and why each candidate was rejected. Returned rather than only logged, so a caller can surface it and a test can assert on it: **a provider choice explainable only by reading log output is a black box** ([[CLAUDE|CLAUDE.md]] §15).

## Two Ceilings, and Neither Is Optional

| Limit | Bounds | Default |
|---|---|---|
| `max_attempts_per_provider` | Retries against one provider | 3 |
| `max_providers_tried` | How far the fallback chain runs | 2 |

**Six upstream calls, absolute, per `complete()`.** They multiply rather than overlap. Both are constructor parameters so a deployment can lower them, both are refused below 1 at construction, and there is no "retry until success" branch anywhere to find.

**This is not the spend ceiling.** Budget limits, spend tracking and anomaly detection are [[STEP-18 AI Cost Governance Controls]]'. What lives here bounds *runaway execution*; what lives there bounds *money*. Conflating them would put budget enforcement in a class whose failure mode is "try the next provider" — far too soft for a budget.

**A fallback is disclosed on the response.** `CompletionResponse.served_after_fallback` plus `provider` and `model` mean a caller can always attribute an answer honestly. A silent fallback is exactly the "confident-sounding output" [[CLAUDE|CLAUDE.md]] §15 forbids.

## Provider Health

A circuit breaker on **availability**, not spend. Three states, and the third is what makes recovery possible:

| State | Meaning | Selection |
|---|---|---|
| `HEALTHY` | Under the failure threshold | Eligible |
| `UNHEALTHY` | Threshold reached, cooldown running | **Skipped** |
| `RECOVERING` | Cooldown elapsed, unproven | Eligible — one probe |

Without `RECOVERING`, an unhealthy provider would need a success to recover and would never be selected to make one — out of rotation until the process restarts.

Three **consecutive** failures opens it (any success resets the run, so a provider failing every other call cannot hover under the threshold forever); 30 seconds of cooldown closes it.

> [!note] In-process, per worker — a stated limitation
> N workers each track health independently, so a provider must fail the threshold *per worker*. This mirrors the rate limiter's approximation ([[ADR-002 Trusted Proxy and Client Address Resolution]] Future Evolution) and has the same resolution: a shared store is a new infrastructure dependency requiring its own ADR.
>
> The approximation errs safely — it makes the breaker **slower to open, never slower to close**. A healthy provider is never wrongly skipped.

## BYOK Credentials

`provider_credentials`, created with its RLS policies in the same migration (`f1a4c8d29b57`), per the standing rule in [[RLS Policy Pattern]].

**A stored provider key is the most sensitive tenant data in the system so far**: it authorizes spend on an account ProjectOne does not own, so a leak is a direct financial loss for the customer. It therefore gets two independent controls.

### RLS, following the pattern exactly

| Command | Rule |
|---|---|
| SELECT | Live membership — so an ordinary member can make AI calls |
| INSERT | **`owner` or `admin` only** |
| UPDATE | **`owner` or `admin` only**, with `WITH CHECK` |
| DELETE | **No policy, no grant** — removal is a soft delete |

Reads are membership-scoped while writes are role-scoped, and the asymmetry is deliberate: requiring owner/admin to *read* would mean only admins could use AI at all, while a key authorizes spend and so belongs with the roles controlling billing-adjacent settings.

### Encryption at rest

AES-256-GCM, keyed by `PROJECTONE_BYOK_ENCRYPTION_KEY` from the environment — never in the database, never in source control.

- **GCM, authenticated.** Tampered ciphertext fails to decrypt rather than decrypting to garbage that then gets sent to a provider as a credential.
- **A fresh nonce per encryption**, prepended to the ciphertext. Nonce reuse is GCM's one catastrophic failure, and there is no code path that can supply one.
- **Required, no default.** A default would be a hardcoded key shared by every deployment, which is not encryption. The API refuses to start without a valid one.

Encryption is **defence in depth behind RLS, not a substitute**: RLS stops one tenant reading another's row; encryption stops a leaked backup or a future admin path from yielding a *usable* credential.

### Where plaintext exists

Exactly two places: `ProviderCredentialService.key_for` and the adapter it hands the key to. The repository holds ciphertext and never decrypts, so a repository result cannot be logged into a leak. `CredentialSummary` — what a settings screen sees — has **no field capable of carrying a key**, which is stronger than remembering to exclude one in a serializer.

The router resolves keys through a **callable, one provider at a time**, so a fallback that never happens never decrypts the credential it did not need.

> [!warning] The key resolver is a parameter, never instance state
> The router is constructed once and shared across requests. Holding a request-scoped resolver on `self` would let two concurrent requests race, and the loser would resolve a key belonging to the **other workspace** — the same class of defect as the pooled-connection claim leak [[RLS Policy Pattern]] records. Caught during implementation and prevented structurally.

## Known Limitations

Stated so the next reader does not assume otherwise:

- **Encryption key rotation is not supported.** Changing `PROJECTONE_BYOK_ENCRYPTION_KEY` makes every stored credential undecryptable, and each workspace must re-enter its keys. A re-encryption path is unbuilt.
- **One deployment-wide encryption key**, not per-tenant. Per-tenant keys need a key management service to be worth anything — storing them in the same database as the ciphertext they protect is theatre. That is an ADR and infrastructure, not something to improvise.
- **No streaming, embeddings, image generation or tool calling.** No scheduled step consumes them; adding one later is one method and one implementation per provider, while removing a speculative one is a breaking change.
- **No HTTP routes.** [[STEP-19 Settings and BYOK UI]] and [[STEP-23 AI Chat End to End]] own those.
- **Costs are hardcoded constants**, not fetched pricing. They exist to make providers comparable, not to bill.

---

## Navigation

- **Previous:** [[Authorization Model]]
- **Next:** [[Web Session Handling]]
- **Parent:** [[Architecture MOC]]
- **Related Notes:** [[AI Providers]] · [[AI Architecture]] · [[RLS Policy Pattern]] · [[API Conventions]] · [[Environment and Secrets]] · [[Security Architecture]]
