---
title: "ADR-001: Technology Stack"
category: ADR
status: review
version: "1.0"
last_updated: 2026-07-31
tags: [adr, decision, architecture, frontend, backend, database, ai]
adr_number: "0001"
---

# ADR-001: Technology Stack

## Status

**Review** — awaiting project owner acceptance.

Per [[CLAUDE|CLAUDE.md]] §7, implementation may only begin once this ADR reaches `Accepted`. [[STEP-03 Web App Skeleton]] does not start while this remains in `Review`.

## Context

ProjectOne is an AI Operating System for content businesses, intended to scale from its first user to thousands of concurrent users **without a rewrite** ([[CLAUDE|CLAUDE.md]] §3). The repository skeleton now exists ([[STEP-01 Repository Bootstrap]]) but contains no application code, so this is the last moment at which the stack can be chosen cheaply — every subsequent step assumes one.

A stack is already named in [[CLAUDE|CLAUDE.md]] §10 and referenced throughout the Engineering Handbook. It has never been recorded as a decision: nothing states what it was chosen *over*, or what obligations it creates. An undocumented default is not a decision, and the vault's own rule is that if it isn't written down, it isn't settled ([[Start Here]]). This ADR closes that gap and becomes the first entry in `08 ADR/`.

The forces at play:

- **Capability requirements, not technology preferences, come first.** [[Frontend Architecture]], [[Backend Architecture]] and [[Database Architecture]] deliberately name no vendor — they specify what the system must *do*. The stack is accountable to those requirements.
- **AI workloads are the differentiator and the highest-risk surface** ([[CLAUDE|CLAUDE.md]] §30). Long-running, streaming, provider-variable calls shape the backend more than CRUD does.
- **Multi-tenancy is architectural, not a feature** ([[CLAUDE|CLAUDE.md]] §16). Workspace isolation must be enforceable at the database layer via Row Level Security, not by application discipline.
- **Solo-owner velocity is a real constraint.** The stack must be operable by a very small team without a dedicated platform engineer.
- **Provider independence is binding** ([[CLAUDE|CLAUDE.md]] §7). No hard lock-in to a single AI provider, cloud vendor or third-party service where avoidable.

## Decision

ProjectOne adopts the following stack. This matches [[CLAUDE|CLAUDE.md]] §10 exactly; no layer diverges from it.

| Layer | Technology | Governing standard |
|---|---|---|
| Frontend framework | **Next.js (App Router)** | [[Chapter 05 - NextJS Architecture]] |
| UI library | **React** | [[Chapter 04 - React Standards]] |
| Frontend language | **TypeScript, strict mode** | [[Chapter 03 - TypeScript Standards]] |
| Styling | **Tailwind CSS + ProjectOne [[Design System]]** | [[Design System]] |
| Backend language | **Python** | [[Chapter 06 - FastAPI Architecture]] |
| Backend framework | **FastAPI** | [[Chapter 06 - FastAPI Architecture]] |
| Database | **Supabase / PostgreSQL** | [[Chapter 07 - Database Standards]] |
| AI layer | **Provider-agnostic AI Router, BYOK-capable** | [[AI Providers]], [[AI Architecture]] |
| Infrastructure | **Cloud-first, infrastructure as code** | [[Infrastructure]] |

Binding consequences of the choice:

1. **Server Components are the default** on the frontend; Client Components require a browser-API, interactive-state, animation or event-handler justification ([[CLAUDE|CLAUDE.md]] §11).
2. **`any` is forbidden** and strict mode is never relaxed ([[CLAUDE|CLAUDE.md]] §35).
3. **Every tenant-scoped table ships with its RLS policy in the same migration that creates it** ([[CLAUDE|CLAUDE.md]] §16). A table without RLS is an incomplete migration.
4. **No AI provider SDK is called directly from feature code.** All model access goes through the AI Router ([[AI Providers]]).
5. **Adding a framework, database engine or major dependency outside this table requires a new ADR** ([[CLAUDE|CLAUDE.md]] §10, §28).

### Implementation languages (resolved)

**Frontend: TypeScript, strict mode. Backend: Python.** Confirmed by the project owner on 2026-07-31 and now stated explicitly in the canonical documentation rather than inferred from the framework choice.

An earlier revision of this ADR flagged an ambiguity: [[CLAUDE|CLAUDE.md]] §10 listed *"Language | TypeScript (strict mode)"* as a single unqualified row while also mandating FastAPI, a Python framework — two rows that could not both hold system-wide. That is closed. §10 now carries separate **Frontend language** and **Backend language** rows, and the two owning handbook chapters state their scope directly: [[Chapter 03 - TypeScript Standards]] §3.1 scopes TypeScript to the frontend, [[Chapter 06 - FastAPI Architecture]] names Python as the backend language.

The specific Python version is not settled here — it belongs to [[STEP-04 API App Skeleton]].

### Why two languages

The split (TypeScript frontend, Python backend) is deliberate and is the decision's main cost. Python is where the AI ecosystem actually lives — provider SDKs, evaluation tooling and orchestration libraries land there first and are best maintained there. Since AI is ProjectOne's differentiator, the backend is placed where that ecosystem is strongest, and the cost of a second language is paid knowingly rather than discovered later. Contract drift between the two is the risk this creates; it is mitigated by generating TypeScript types from FastAPI's OpenAPI schema (see Consequences).

## Alternatives Considered

### Option A — Next.js full-stack (TypeScript everywhere, no separate backend)

Use Next.js Route Handlers and Server Actions as the entire backend; drop FastAPI. One language, one deployable, one type system end to end, and no cross-language contract to maintain.

**Rejected because** it puts the AI layer in the weaker ecosystem. ProjectOne's differentiator is agents, workflows, memory and provider routing ([[CLAUDE|CLAUDE.md]] §15) — work that is long-running, retry-heavy and orchestration-shaped. Python's AI tooling is materially ahead of Node's, and serverless request/response handlers are an awkward host for workflows that must be *deterministic, observable, resumable and versioned* ([[Workflow Engine]]). Choosing this would optimize for early convenience at the cost of the platform's core surface — precisely the trade [[CLAUDE|CLAUDE.md]] §5 forbids ("never optimize only for speed of delivery").

### Option B — Self-managed PostgreSQL (or a non-Supabase managed instance)

Run PostgreSQL directly on a cloud provider; build authentication, storage and realtime in-house on top of it.

**Rejected because** it front-loads months of undifferentiated platform work with no user-visible value, contradicting "create measurable value before adding features" ([[CLAUDE|CLAUDE.md]] §39). Supabase supplies auth, storage, realtime and — critically — first-class Row Level Security, which is exactly the mechanism [[CLAUDE|CLAUDE.md]] §16 mandates for tenant isolation. The lock-in risk is smaller than it appears: the substrate is standard PostgreSQL, so the data layer stays portable even if the surrounding services are later replaced. Revisit if Supabase's limits become the binding constraint, which is a scaling problem worth having.

### Option C — Django or Rails backend

A batteries-included framework: ORM, admin, auth and migrations in one opinionated package, with less assembly than FastAPI.

**Rejected because** the batteries largely duplicate what Supabase already provides (auth, migrations, admin), while the framework's synchronous, request/response-shaped core fits ProjectOne's dominant workload poorly. AI calls are long-running and streaming; FastAPI's async-native model and Pydantic validation match "validate every external input using schemas before it enters business logic" ([[CLAUDE|CLAUDE.md]] §12) without fighting the framework. Django's ORM would also compete with Supabase for ownership of the schema, splitting a responsibility that must have exactly one owner ([[Chapter 02 - Repository Architecture]] §2.10).

### Option D — A single AI provider SDK called directly (no router abstraction)

Integrate one provider's SDK throughout the codebase and skip the routing layer.

**Rejected because** it violates provider independence ([[CLAUDE|CLAUDE.md]] §7) on day one and makes the fallback requirement unimplementable — critical workflows must survive a single provider's outage ([[CLAUDE|CLAUDE.md]] §15). It also forecloses BYOK, a stated platform capability. The router's cost is one indirection layer; the cost of retrofitting one across a mature codebase is far higher.

## Consequences

### Easier

- Each layer has a written standard already ([[Engineering Handbook MOC]] Chapters 3–7), so implementation steps inherit conventions instead of inventing them.
- RLS-based tenant isolation is available from the first migration rather than being retrofitted ([[CLAUDE|CLAUDE.md]] §16).
- Server Components keep the client bundle small by default ([[CLAUDE|CLAUDE.md]] §11).
- FastAPI's async model suits streaming AI responses and long-running workflow steps without special handling.
- The AI Router makes model selection an engineering decision with a paper trail ([[CLAUDE|CLAUDE.md]] §15) rather than a hardcoded default.

### Harder

- **Two languages, two toolchains.** Lint, test, type-check and CI must be maintained for both; contributors need both. Accepted knowingly — see *Why two languages*.
- **The frontend/backend contract is now cross-language** and can drift silently — nothing in the type system connects a FastAPI response model to the TypeScript that consumes it. See *OpenAPI contract* below for the committed mitigation.
- **Two deployment targets** with separate environments and secrets ([[CLAUDE|CLAUDE.md]] §28a).
- **Supabase concentrates several concerns** (database, auth, storage, realtime). Mitigated by standard PostgreSQL underneath, but auth and storage migrations would be real work.

### OpenAPI contract

Choosing two languages creates one hard requirement: **the frontend/backend contract must be generated, never hand-maintained.**

**Decided here:** TypeScript types for the API contract are generated from FastAPI's OpenAPI schema. Hand-written TypeScript interfaces mirroring backend response models are not acceptable — a hand-copied contract is a duplicate definition that drifts the moment one side changes, which [[CLAUDE|CLAUDE.md]] §35 forbids ("never duplicate logic").

**Deferred to implementation:** this is recorded as an obligation, not scheduled as work. It is implemented **when the API layer is built** — the step that first defines real endpoint contracts is the step that wires up generation. No new Build Plan step is created for it and no step ordering changes; the [[Build Plan]] is not expanded on the strength of this ADR.

Deliberately not decided here — these are implementation details for whichever step picks this up, and fixing them now would be speculative design against a codebase that does not exist ([[CLAUDE|CLAUDE.md]] §29/§35):

- the generator tool
- whether generated types live in `apps/web` or a shared package under `packages/`
- whether generation runs in CI, as a pre-commit step, or on demand
- how drift is detected (for example, CI failing when regenerated output differs from what is committed)

**The obligation stands regardless of where it lands:** a step that ships a typed frontend call against a hand-written interface has not satisfied this ADR.

### Obligations this creates

- **Provider independence** ([[CLAUDE|CLAUDE.md]] §7): AI access flows through the router; critical workflows define a fallback provider ([[AI Providers]]); no feature code imports a provider SDK directly.
- **Cloud portability**: infrastructure as code, avoiding vendor-proprietary primitives where a portable equivalent exists ([[Infrastructure]]).
- **Cost governance** ([[CLAUDE|CLAUDE.md]] §15a): budget ceilings, circuit breakers, retry caps and execution limits are requirements of the AI layer from its first line, not later hardening. [[STEP-18 AI Cost Governance Controls]] implements them.
- **Generated API contract** (see *OpenAPI contract* above): TypeScript types for API responses are generated from FastAPI's OpenAPI schema, never hand-written, from the moment the first real endpoint exists.
- **This ADR is revisited, not quietly amended**, if any layer changes. Superseding requires a new ADR that names this one ([[CLAUDE|CLAUDE.md]] §7).

### Not decided here

Deliberately out of scope, to keep this ADR about the stack: the specific hosting provider, the CI provider, the AI providers behind the router, the package manager and monorepo tooling, and the testing frameworks. Each is settled by its own step or ADR when it becomes concrete — recording them now would be the speculative over-design [[CLAUDE|CLAUDE.md]] §29/§35 forbids.

## Related

- Governing rules: [[CLAUDE|CLAUDE.md]] §7 (ADR lifecycle, provider independence) · §10 (stack table) · §28 (dependency rules)
- Requirements: [[Frontend Architecture]] · [[Backend Architecture]] · [[Database Architecture]] · [[API Architecture]]
- Standards: [[Chapter 03 - TypeScript Standards]] · [[Chapter 04 - React Standards]] · [[Chapter 05 - NextJS Architecture]] · [[Chapter 06 - FastAPI Architecture]] · [[Chapter 07 - Database Standards]]
- AI layer: [[AI Architecture]] · [[AI Providers]] · [[Workflow Engine]]
- Build steps: [[STEP-02 Stack Confirmation ADR]] (this ADR) · [[STEP-03 Web App Skeleton]] · [[STEP-04 API App Skeleton]]

---

## Navigation

- **Previous:** —
- **Next:** —
- **Parent:** [[Global Index]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[Design System]] · [[Infrastructure]]
