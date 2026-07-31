# docs/

**Documentation does not live here. It lives in the Obsidian Vault at
[`../ProjectOne Vault/`](../ProjectOne%20Vault/).**

[Chapter 02 - Repository Architecture](../ProjectOne%20Vault/04%20Engineering%20Handbook/Chapter%2002%20-%20Repository%20Architecture.md)
§2.6 designates `docs/` as the single source of truth for architecture, ADRs, the Engineering
Handbook and the Project Bible. In ProjectOne that role is filled by the vault: the vault *is*
`docs/`, held in Obsidian so its cross-links, MOCs and indexes stay navigable.

This file exists so that role is never ambiguous. A second copy of the documentation in this
folder would be a competing source of truth, and a document describing behavior the system no
longer has is worse than no document at all ([`CLAUDE.md`](../CLAUDE.md) §19).

## Where to Go

| You are looking for | Read |
|---|---|
| How to work in this repository | `../ProjectOne Vault/01 Claude OS/Start Here.md` |
| What ProjectOne is and does | `../ProjectOne Vault/03 Project Bible/` |
| Binding engineering standards | `../ProjectOne Vault/04 Engineering Handbook/` |
| Architecture Decision Records | `../ProjectOne Vault/08 ADR/` |
| The build plan | `../ProjectOne Vault/09 Development/Build Plan/Build Plan.md` |

## What May Live Here

Generated documentation artifacts only — API schemas emitted by tooling (e.g. an exported OpenAPI
specification), coverage reports, or similar build output that is produced from code rather than
authored by hand. Anything authored by a human or by Claude belongs in the vault, linked from the
relevant MOC.
