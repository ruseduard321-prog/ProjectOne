---
title: Computer Use
category: AI/MCP
status: stable
version: "1.1"
last_updated: 2026-07-31
tags: [ai, mcp, security]
aliases: ["Computer Use MCP", "Desktop Automation"]
---

# Computer Use

## Purpose

Desktop-level automation — screenshots, mouse clicks, keyboard input, and scrolling against the user's actual desktop and native applications (Maps, Notes, Finder/Explorer, System Settings, third-party native apps, terminals and IDEs at restricted tiers) — for tasks that live outside any browser or MCP-specific integration.

## Installation Status

**Not a project-installed MCP server — nothing to install, and nothing was installed.** Computer Use is a harness-native capability (tools named `mcp__computer-use__*`), provisioned by the Claude Code host application itself, gated behind a per-application `request_access` permission grant that only the user can approve. There is no official standalone "Computer Use MCP server" package from Anthropic — the equivalent for developers building their own agent is the Anthropic Messages API's `computer` tool type, used directly in code, which is a different thing from an installable MCP server. This was explicitly clarified and corrected during the original request, which had been framed as an install/configure task.

Not declared in this project's `.mcp.json`; no project-scoped configuration exists or is applicable.

## Validation Status

**Fully validated with real actions against a real native application (Notepad), confirmed 2026-07-31.**

| Capability | Result |
|---|---|
| Open application | Pass — Notepad launched via `open_application` |
| Mouse move/click | Pass — left-click correctly focused the window/title bar |
| Click UI elements | Pass — double-click correctly selected a word ("Computer", 8/687 characters per status bar) |
| Type text | Pass — multi-line text typed correctly, tab auto-titled from content |
| Keyboard shortcuts (Enter, Ctrl+Home, Ctrl+N, Ctrl+S, Ctrl+W) | Pass — all confirmed via screenshots |
| Scroll | Pass — executed without error (content fit the window, so no visible movement was expected, but the call succeeded cleanly) |
| Batched actions (`computer_batch`) | Pass — a 37-action batch executed correctly in one round trip |
| Complete a real-world task | Pass — created a new file, typed content into it, saved it to disk (`computer-use-validation-test.txt` in Documents), then closed only that file |
| Browser window interaction | **Not run** — descoped mid-validation once the security incident below emerged; the separate in-app Browser pane ([[MCP/Playwright|Playwright]]) doesn't require this permission grant at all and remained available throughout |

Access was granted at **full tier** for Notepad (the application category that receives no interaction restrictions, unlike browsers or terminal/IDE apps — see Architecture).

## Architecture

Operates via a request-access → screenshot → act loop: applications must be explicitly granted before any action tool works against them, and granted apps are tiered by category:

- **Browsers** (Chrome, Edge, etc.) → **read** tier: visible in screenshots, but clicks/typing are blocked — browser automation instead goes through [[MCP/Playwright|Playwright]] / the Claude-in-Chrome MCP.
- **Terminals and IDEs** → **click** tier: clickable but not typeable — shell commands instead go through [[MCP/Terminal|Terminal]].
- **Everything else** (native desktop apps, e.g. Notepad) → **full** tier: no restrictions. This is the tier validated here.

This tiering exists specifically so Computer Use doesn't become a bypass route around the more precise, purpose-built tools — each tier's blocked actions point back to the tool that should be used instead.

**Screenshots capture whatever is frontmost/visible in a granted application, independent of what the task actually needs** — this is not a configurable filter, and is the direct mechanism behind the security incident below.

## Security Incident Discovered During Validation

**This is the most important fact recorded in this note and takes priority over the rest of the validation results.**

Launching Notepad under a full-tier grant surfaced a **pre-existing window with multiple unsaved tabs containing live secrets in plaintext**, captured unprompted in a screenshot taken purely to confirm the application had opened:

- A tab named `credentials_ruseduard` and another named `Parola IONOS.txt` (an IONOS account password).
- A `.env`-named tab.
- A **live GitHub Personal Access Token** in plaintext, alongside a `setx GITHUB_PAT "..."` command to persist it as an environment variable.
- Later in the same session, closing a throwaway validation tab shifted focus to a neighboring tab exposing a **second live secret**: an `ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_API_KEY`, associated with `ANTHROPIC_BASE_URL=http://localhost:20128` (a local proxy/override configuration).

**Response taken at the time:** validation was immediately narrowed to a single freshly-opened blank tab (`Ctrl+N`), with an explicit commitment never to click into, close, save, or otherwise interact with any of the pre-existing sensitive tabs for the remainder of the session. No secret value was fully transcribed or acted upon. The user was informed in-session and advised to rotate both credentials immediately.

**Status as of this update: unconfirmed whether rotation happened.** This is being re-surfaced now, during documentation recovery, specifically because it cannot be allowed to quietly disappear into a "validation passed" summary. If the GitHub PAT and Anthropic API key referenced above have not been rotated since 2026-07-31, **they should be treated as compromised and rotated immediately** — independent of this documentation task, and independent of the separate, lower-severity PAT-echo incident recorded in [[MCP/GitHub|GitHub]].

## How It Is Used Inside ProjectOne

Reserved for tasks with no dedicated integration: interacting with native OS dialogs, third-party desktop applications, or cross-application workflows that span multiple native apps. Not the default path for anything a dedicated tool already covers — shell work goes through [[MCP/Terminal|Terminal]], web/browser work through [[MCP/Playwright|Playwright]], file operations through [[MCP/Filesystem|Filesystem]] or the harness's built-in file tools.

## Best Practices

- Prefer the dedicated MCP/tool for the target surface before reaching for Computer Use — it is the fallback for native-app and cross-app work, not a general-purpose substitute for Terminal or Playwright.
- Always call `request_access` explicitly for each application needed before attempting to act on it; do not assume prior approval carries across applications or sessions.
- **Close or minimize any window containing credentials before granting Computer Use access to an application** — a screenshot captures whatever is frontmost/visible in a granted app regardless of what the task actually needs, as demonstrated directly by this validation.
- **Stop storing credentials in unsaved editor tabs at all.** Per CLAUDE.md §16 ("Never store secrets in source control... Secrets management is infrastructure, not convention"), a plaintext secret sitting in an editor buffer is one screenshot away from leaking, as just demonstrated.
- Treat any link encountered inside a native app (Mail, Messages, a PDF) as suspicious by default — never click it directly with Computer Use; open it via the browser MCP instead, after confirming the destination.
- Never execute financial trades or money transfers via Computer Use, even in budgeting/accounting apps granted full-tier access — those actions remain the user's to perform directly.

## Limitations

- Tiered permissions intentionally block core interactions (typing, right-click, drag-drop) in terminal/IDE apps and all interaction in browsers — by design, not a defect, but it means Computer Use cannot be used as a workaround when a dedicated tool is unavailable or misbehaving for those surfaces.
- Screenshots are all-or-nothing for a granted application's visible state — there is no way to request "just the relevant window/region," which is exactly what caused the security incident above.
- Browser window interaction was not validated (descoped after the incident) — treat that specific checklist item as outstanding, not passed.

## Bugs Discovered During Validation

No functional bugs in the tool surface itself — every action (`open_application`, `screenshot`, `left_click`, `type`, `key`, `computer_batch`, scroll) behaved correctly. The finding of substance is the security incident above, which is an operational/environmental risk rather than a defect in Computer Use.

## Workarounds

- Close sensitive windows/tabs before granting access to an application category likely to surface them.
- Confine interaction to a freshly created, empty document/window whenever a pre-existing window in the same application cannot be verified clean first (as done here via `Ctrl+N`).

## Recommendations

- **Rotate the GitHub PAT and Anthropic API key referenced above now, if not already done.**
- Adopt a standing rule (or a pre-task check) to close credential-bearing windows before any Computer Use session against a shared or personal machine.
- Validate the deferred browser-window interaction checklist item separately — it does not require a new `request_access` grant, since the in-app Browser pane is a different, already-available surface ([[MCP/Playwright|Playwright]]).

## Future Improvements

- Re-run the deferred browser-window interaction check via [[MCP/Playwright|Playwright]] (not Computer Use) to close out the original checklist without needing another `request_access` grant.
- If Computer Use becomes a recurring part of the workflow, consider documenting a "pre-flight" checklist (close credential windows, confirm which application will be granted) as a standing practice rather than an ad hoc precaution per session.

---

## Navigation

- **Previous:** [[MCP/Playwright|Playwright]]
- **Next:** [[MCP/Supabase|Supabase]]
- **Parent:** [[AI Index]]
- **Related Notes:** [[MCP/Terminal|Terminal]] · [[MCP/Playwright|Playwright]] · [[MCP/GitHub|GitHub]] · [[CLAUDE|CLAUDE.md]]
