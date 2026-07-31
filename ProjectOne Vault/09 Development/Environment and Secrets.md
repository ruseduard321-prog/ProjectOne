---
title: Environment and Secrets
category: Development
status: stable
version: "1.1"
last_updated: 2026-07-31
tags: [engineering, security, configuration, documentation]
aliases: ["Environment Configuration", "Secrets Policy", "Feature Flags"]
---

# Environment and Secrets

How ProjectOne configures itself across environments, where secrets live, and how incomplete work reaches production safely. This note is the operational detail behind [[CLAUDE|CLAUDE.md]] §28a; it does not restate the rules there, it says how they are actually implemented.

Established by [[STEP-05 Environment and Secrets]], deliberately **before the first real credential exists** ([[STEP-07 Supabase Provisioning]]) — so the first secret lands in a system already built to protect it rather than one retrofitted around it.

**Approved by the project owner on 2026-07-31** as a Critical change ([[CLAUDE|CLAUDE.md]] §21 — security controls). The policies below are settled: changing them is a deliberate decision requiring owner review again, not an implementation detail a later step may quietly revise. The three decisions explicitly reviewed were the required `environment` variable with no default, the per-app `.gitignore` negation, and documenting the feature-flag convention without building its mechanism.

## The Three Environments

`development`, `staging`, `production`. Strictly isolated: separate credentials, separate data, separate AI provider keys. A user record, an API key or a database in one never appears in another.

The set is closed and enforced in code — both apps reject any other value at startup. A fourth environment is a deliberate change to both applications and this note, not something a deploy can introduce by typing a new string into a variable.

| | development | staging | production |
|---|---|---|---|
| **Purpose** | Local machines | Pre-release verification | Real users |
| **Data** | Disposable, synthetic | Synthetic, production-*shaped* | Real user data |
| **Credentials** | Per-developer | Staging-only | Production-only, least privilege |
| **AI provider keys** | Own keys, low budget ceiling | Own keys, own ceiling | Own keys, own ceiling ([[CLAUDE\|CLAUDE.md]] §15a) |
| **Configuration shape** | — | Mirrors production | Canonical |

**Parity is by design.** Staging mirrors production's configuration *shape* (not scale), so a change verified in staging is meaningful evidence about production. Divergence between the two is a bug in the environment setup, not an accepted quirk.

**Never copy production data into staging or development to debug something.** That silently moves real user data into a lower-trust environment and defeats the isolation this table describes ([[CLAUDE|CLAUDE.md]] §16).

## Configuration Is Read Once, At Startup

Both apps parse and validate their entire configuration when the process starts. A missing or malformed required variable **stops the process** with a message naming the variable and pointing at the template.

This is deliberate. The alternative — reading `process.env` or `os.environ` wherever a value is needed — turns a misconfiguration into a runtime error hours later, in a request handler, usually in production, usually as something that reads like an unrelated bug.

| | `apps/api` | `apps/web` |
|---|---|---|
| Module | `app/core/config.py` | `src/lib/env.ts` |
| Mechanism | pydantic-settings `BaseSettings` | Hand-written validation |
| Prefix | `PROJECTONE_` | `NEXT_PUBLIC_PROJECTONE_` |
| Access | Injected via `get_settings()` | Import `env` |
| On failure | Exits non-zero before serving | Build/start fails |

The web app validates in plain TypeScript rather than with a schema library: the rules are a handful of string checks, and a dependency for that is added supply-chain surface for no gain ([[CLAUDE|CLAUDE.md]] §28). Revisit if the config grows genuinely complex.

**Never read `process.env` or `os.environ` outside these two modules.** That bypasses validation and reintroduces the untyped access they exist to remove.

### Required vs optional

A field with no default is **required** — the app will not start without it. `environment` is required in both apps specifically because defaulting it would let a production deploy that forgets the variable start anyway, in the wrong mode, silently. Failing loudly is the safer failure.

Optional fields carry defaults chosen to be *safe*, not convenient.

## Secrets

- **Never in source control, never hardcoded, never logged** ([[CLAUDE|CLAUDE.md]] §16, [[Chapter 09 - Security Standards]]). A secret committed once is committed forever — rotate it rather than trying to erase it.
- **`.env` files are git-ignored; `.env.example` templates are committed.** Templates name every required variable and carry only placeholders. They are the contract a new machine reads, so an added variable belongs in the template in the same change.
- **Real secrets are injected at runtime** by the platform's secrets manager, scoped per environment, never baked into an image or a build.

### The `NEXT_PUBLIC_` trap

Anything prefixed `NEXT_PUBLIC_` is **inlined into the browser bundle at build time and is readable by anyone using the site**. It is not configuration-with-extra-steps; it is publication.

Only non-secret values may carry that prefix. A secret the browser appears to need is a design error: it belongs behind an API route or in `apps/api`, never in the bundle. Service-role keys and AI provider keys in particular must never appear in `apps/web` in any form.

### Ignore rules are per-app, and that matters

`apps/web/.gitignore` (from `create-next-app`) has its own `.env*` rule that **wins over the repository root**, because git applies the rule nearest the file. The root's `!**/.env.example` negation alone left `apps/web/.env.example` ignored — the template would have been silently missing from every fresh clone.

Both files now carry the negation. **When adding a new app, verify its template is actually trackable** rather than assuming the root rule reaches it:

```
git check-ignore -v apps/<name>/.env.example
```

No output means trackable. Output naming a rule means it is being ignored and the app needs its own negation.

## Configuration Changes Behavior, Not Code Paths

There is **no environment-conditional business logic** in either app. No `if (environment === 'production')` branching what the code does.

The distinction: configuration supplies *values* (a URL, a budget ceiling, a key) that code uses uniformly. It does not select between implementations. Environment-conditional branches mean production runs code that no other environment ever executes — which is to say, code that was never really tested before it reached users.

Verified per step: a grep for `NODE_ENV ===`-style branching must return no business-logic hits.

## Feature Flags

Flags are how incomplete or gradually-rolled-out work reaches production safely. **No flag mechanism is implemented yet** — nothing is incomplete enough to need one. The convention is fixed now so the first flag follows it instead of inventing one under deadline.

Every flag has, without exception:

| Property | Rule |
|---|---|
| **Owner** | A named person. Not "the team". |
| **Default** | **Off**, unless on is explicitly justified in writing. |
| **Removal date** | An actual date. A flag with no removal plan is technical debt the moment it is created. |
| **Scope** | What it gates, in one sentence. |

**Flags are removed, not left behind.** Once a flag is fully on or fully off everywhere and no longer branching, delete it and the dead side of the branch. Stale flags accumulate into a configuration surface nobody understands, where the combination that is actually running in production is unknown.

**Flags are not a substitute for the approval gates in [[CLAUDE|CLAUDE.md]] §15.** An autonomous agent action that would otherwise need user approval does not become exempt by hiding behind a flag.

When the first flag is needed, it is implemented as configuration through the modules above — not as a new mechanism, and not as environment branching.

## Adding a Variable

1. Add it to the app's `.env.example` with a **placeholder** and a comment saying what it is.
2. Add it to the config module — with a default if genuinely optional, without one if required.
3. If required, confirm the app refuses to start without it and that the error names it.
4. Add it to every environment's real configuration before the code that reads it deploys.
5. If it is a secret, confirm it is injected by the secrets manager and appears in no log.

Step 4 sequencing matters: a required variable that reaches production before its value does takes the service down at startup.

---

## Navigation

- **Previous:** [[Environment Setup]]
- **Next:** —
- **Parent:** [[Development MOC]]
- **Related Notes:** [[Environment Setup]] · [[Infrastructure]] · [[Chapter 09 - Security Standards]] · [[Security Architecture]] · [[CLAUDE|CLAUDE.md]]
