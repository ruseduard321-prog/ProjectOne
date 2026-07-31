---
title: Playwright
category: AI/MCP
status: stable
version: "1.0"
last_updated: 2026-07-31
tags: [ai, mcp, testing]
aliases: ["Playwright MCP", "Browser MCP"]
---

# Playwright / Browser Automation

## Purpose

Interactive, real-browser validation of frontend work — navigating pages, filling forms, clicking, capturing screenshots, and inspecting console/network activity — so UI changes can be confirmed working in an actual browser rather than asserted from reading code, per CLAUDE.md's UI-testing requirement.

## Installation Status

**Already available — nothing installed.** A Playwright installation already exists at the harness level: browser binaries are cached at `~/AppData/Local/ms-playwright` (Chromium build 1234, plus `chromium_headless_shell`, `ffmpeg`, and `winldd`). This backs the harness's own Browser pane tool surface. No `playwright`/`@playwright/test`/`playwright-core` npm package exists in the project or globally — confirmed via `npm ls` and `where playwright`.

**Browser coverage:** Chromium only. **Firefox and WebKit are not installed** — no corresponding directories exist under the Playwright browser cache. Installing them was deliberately not attempted during validation (a non-trivial download/disk-write action outside the scope of validating what already exists); see Recommendations.

## Validation Status

**Validated 2026-07-31.** Full 24-item checklist executed against a demo page served from a disposable temp directory via a local Node HTTP server (not `file://` — see Limitations), fully cleaned up afterward (browser tabs closed, server process killed, port freed, scratch directory deleted).

| Capability | Result |
|---|---|
| Playwright installation present | Pass |
| Browser installation (Chromium) | Pass — Firefox/WebKit not installed |
| Launch browser | Pass |
| Open local HTML page | Pass, via local HTTP server (see Limitations for `file://` caveat) |
| Open external website | Pass |
| Navigate between pages | Pass |
| Click buttons | Pass (verified via DOM state, not just tool response) |
| Fill text inputs | Pass |
| Select dropdowns | Pass |
| Tick checkboxes | Pass |
| Read page content | Pass |
| Wait for dynamic elements | Pass |
| Capture screenshots | Pass |
| Tracing/video capability | **Not exposed** — no trace/video-start tool in this toolset, despite `ffmpeg` being cached |
| Console log capture | Pass, with a duplication bug (see Bugs) |
| JavaScript error capture | **Fail** — uncaught exceptions are not captured |
| Network request inspection | Pass |
| Multiple tabs | Pass |
| File download support | **Unverifiable** — no download-event API, no default Downloads folder present |
| File upload support | **Fail** — no upload tool in this toolset |
| Mobile device emulation | **Partial/misleading** — viewport resize only, no UA/touch emulation |
| Viewport resizing | Pass |
| Cookies/local storage access | Pass |
| Cleanup after execution | Pass |

## Architecture

The harness's Browser pane (`mcp__Claude_Browser__*` tools) is a Playwright-backed automation layer built into Claude Code itself — distinct from, and not listed in, this project's `.mcp.json` (which only configures the `filesystem` server). It manages its own Chromium instance and browser cache independently of any project-level dependency.

## How It Is Used Inside ProjectOne

The standard tool for manually validating frontend changes in a real browser before calling UI work done — matches CLAUDE.md's requirement to start a dev server and exercise the golden path and edge cases in a browser, not just assert correctness from code or type checks.

## Best Practices

- **Serve local pages over HTTP, not `file://`,** when testing anything outside the project directory — spin up a throwaway static server for temp-directory validation work. `file://` paths outside the project render as static, non-interactive snapshots that block every inspection/interaction tool.
- **Verify state via direct DOM/JS reads** (the `javascript_tool`), not just a tool call's "success" response — several operations report success trivially but need independent confirmation of real effect.
- **Don't rely on console-message capture for correctness/error assertions** — add explicit `try/catch` + `console.error()` in test pages if a failure path needs to be asserted on, since uncaught exceptions don't surface.
- **Treat the mobile viewport preset as visual/layout testing only**, not a substitute for genuine responsive or touch-interaction testing.
- Always clean up spawned local servers and scratch directories explicitly — nothing auto-expires them.

## Limitations

- `file://` navigation to paths outside the project renders as a static snapshot — no `read_page`, `get_page_text`, `screenshot`, or `computer` actions work against it.
- No JS runtime-error capture — `window.onerror`/uncaught-exception events are invisible to `read_console_messages`, including with an errors-only filter.
- No file-upload tool in this toolset (exists on the separate `claude-in-chrome` MCP, not here). Attempting to set a file input's value via `form_input` correctly fails with a browser-security `InvalidStateError` — this toolset has no CDP-level `setInputFiles()` equivalent.
- File-download support cannot be verified through this interface — no download-event tracking API exists.
- "Mobile device emulation" is a viewport resize only: `navigator.userAgent`, `maxTouchPoints`, and `ontouchstart` all remain desktop values after switching to the mobile preset.
- No tracing or video-recording tool exposed, despite `ffmpeg` being present in the underlying Playwright cache — the capability likely exists at the engine level but isn't surfaced through this MCP interface.
- Only Chromium is installed; no cross-browser coverage without an explicit install step.

## Bugs Discovered During Validation

- **Console messages are duplicated** — every `console.log`/`console.warn` call was recorded twice in `read_console_messages`.
- Tab-state confusion observed once during validation (a `navigate` call reported success against a tab that `read_page`/`screenshot` then couldn't find "no site is open") — traced to a stray auto-opened preview tab from a prior file-write hook, resolved by explicitly closing extra tabs and re-navigating. Not reproduced as a standalone defect once tab state was made explicit.

## Workarounds

- Route local-file testing through a throwaway local HTTP server instead of `file://` for any page outside the project directory.
- Don't use this toolset to validate upload/download flows; treat those as out of scope for this surface (see Recommendations).
- When encountering "no site is open" errors, check `tabs_context` for stray tabs before assuming a navigation failure.

## Recommendations

- Use this capability for **interactive, exploratory validation** of frontend changes — that's what it's good at and what CLAUDE.md's UI-testing requirement calls for.
- **Do not treat it as a substitute for an automated test suite.** For ProjectOne's Testing Standards (Engineering Handbook Chapter 10 / CLAUDE.md §18 — unit tests, automated E2E for critical user journeys, CI-run regression suites), use the **official `@playwright/test` npm package** as a real dev dependency in the relevant `apps/` package, run via `npx playwright test` in CI. That gives genuine device emulation, file upload/download APIs, tracing, video, and true cross-browser (Chromium/Firefox/WebKit) coverage that this harness surface doesn't provide. This would be a new project dependency (CLAUDE.md §28) and a testing-infrastructure decision — scoped separately, not assumed here.
- If cross-browser manual validation becomes a real need, install Firefox/WebKit browser binaries deliberately (`npx playwright install firefox webkit`) rather than assuming Chromium-only coverage is sufficient.

## Future Improvements

- Evaluate `@playwright/test` adoption for `apps/` once there is real frontend code to test against (per Recommendations above).
- Re-validate JS-error and console-capture behavior if/when the harness's Browser pane toolset is updated — the missing uncaught-exception capture is a real gap for debugging workflows.

---

## Navigation

- **Previous:** [[MCP/Terminal|Terminal]]
- **Next:** [[MCP/Computer Use|Computer Use]]
- **Parent:** [[AI Index]]
- **Related Notes:** [[MCP/Computer Use|Computer Use]] · [[Chapter 10 - Testing Standards]] · [[Testing Strategy]] · [[CLAUDE|CLAUDE.md]]
