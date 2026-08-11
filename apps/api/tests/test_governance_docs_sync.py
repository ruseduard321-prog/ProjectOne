"""Tests that the generated root governance documents match their canonical sources.

**Why this file exists.** `CLAUDE.md` and `AGENTS.md` at the repository root are
generated from canonical sources in `ProjectOne Vault/00 Governance/`. Two
copies exist because they serve different consumers — the Claude Code harness
reads only the root `CLAUDE.md`, OpenAI Codex reads only the root `AGENTS.md`,
and every wiki-link in the vault resolves only to the vault copy.

Generation is what makes drift impossible, but only if something notices when
the generated copy is stale. `sync-governance-docs.sh --check` is that check,
and before this file nothing ran it: a contributor who edited a canonical source
and forgot to regenerate produced a root file silently describing older rules
than the vault — and the root file is the one the agents actually read.

**The document list is derived, never written down.** Hardcoding the two pairs
here would reproduce the defect one level up: a third governed document would be
added to the config, not to this copy, and these tests would keep passing while
the new file drifted. `_documents()` reads the config, so a new entry is covered
the moment it is introduced.

Offline and dependency-free: this parses JSON and compares text. It deliberately
does not shell out to the sync scripts — CI runs `pytest` on a runner that has
`bash`, but a contributor on Windows PowerShell may not, and a test that only
runs on some platforms is a test that stops being trusted.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

#: The repository root, relative to this file: tests/ -> api/ -> apps/ -> root.
REPO_ROOT = Path(__file__).resolve().parents[3]

#: The configuration both sync scripts read.
CONFIG_PATH = REPO_ROOT / "scripts" / "sync-governance-docs.config.json"


def _documents() -> list[dict[str, object]]:
    """Return the document entries from the sync configuration.

    Read from the config rather than listed here, so this suite tracks
    `sync-governance-docs.config.json` automatically.
    """
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    documents = config["documents"]

    assert documents, "The sync config defines no documents — has its shape changed?"

    return list(documents)


def _render(source: str, document: dict[str, object]) -> str:
    """Apply the config's strip rules to a source document.

    A faithful reimplementation of the transformation both sync scripts perform.
    Keeping a second implementation is deliberate: it means this test fails when
    a script's behaviour drifts from the documented rules, rather than agreeing
    with whatever the script happens to do today.
    """
    lines = source.replace("\r\n", "\n").split("\n")

    # 1. Drop a leading YAML frontmatter block.
    if document.get("stripFrontmatter"):
        if lines and lines[0] == "---":
            for index in range(1, len(lines)):
                if lines[index] == "---":
                    lines = lines[index + 1 :]
                    break

    # 2. Drop a blockquote callout and its continuation lines.
    marker = str(document.get("stripCalloutStartsWith") or "")
    if marker:
        kept: list[str] = []
        in_callout = False
        for line in lines:
            if not in_callout and line.startswith(marker):
                in_callout = True
                continue
            if in_callout:
                if line.startswith(">"):
                    continue
                if line == "":
                    in_callout = False
                    continue
            kept.append(line)
        lines = kept

    # 3. Drop a trailing heading and everything after it.
    heading = str(document.get("stripFromHeading") or "")
    if heading:
        kept = []
        for line in lines:
            if line == heading:
                break
            kept.append(line)
        lines = kept

    # Trim leading blank lines, then trailing blank lines and any dangling
    # "---" separator left behind by removing a trailing section.
    start = 0
    while start < len(lines) and lines[start] == "":
        start += 1

    last = len(lines) - 1
    while last >= start and lines[last] in ("", "---"):
        last -= 1

    return "\n".join(lines[start : last + 1]) + "\n"


def _document_ids() -> list[str]:
    """Test ids that name the document, so a failure reads clearly."""
    return [str(document["name"]) for document in _documents()]


@pytest.mark.parametrize("document", _documents(), ids=_document_ids())
def test_generated_document_matches_its_canonical_source(document: dict[str, object]) -> None:
    """Each root document must equal what the sync scripts would generate.

    The assertion that catches an edited canonical source that was never
    regenerated — which leaves the agents reading a root file older than the
    vault it claims to mirror.
    """
    source_path = REPO_ROOT / str(document["source"])
    target_path = REPO_ROOT / str(document["target"])

    assert source_path.is_file(), f"Canonical source missing: {document['source']}"
    assert target_path.is_file(), f"Generated document missing: {document['target']}"

    expected = _render(source_path.read_text(encoding="utf-8"), document)
    actual = target_path.read_text(encoding="utf-8").replace("\r\n", "\n")

    assert actual == expected, (
        f"{document['target']} is stale — it no longer matches {document['source']}. "
        "The root file is generated; edit the canonical source and regenerate with "
        "`./scripts/sync-governance-docs.sh` (or `.\\scripts\\sync-governance-docs.ps1`). "
        "Never edit the root copy directly."
    )


@pytest.mark.parametrize("document", _documents(), ids=_document_ids())
def test_generated_document_warns_against_editing_it(document: dict[str, object]) -> None:
    """Each generated file must carry its do-not-edit notice.

    The strip rules remove the vault-only callout, so the HTML comment is what
    tells someone reading the root file that their edits will be overwritten.
    Losing it turns a generated file into one that looks hand-maintained.
    """
    target = (REPO_ROOT / str(document["target"])).read_text(encoding="utf-8")

    assert "GENERATED" in target, (
        f"{document['target']} has lost its 'this file is GENERATED' notice. "
        "Without it, the next reader edits the generated copy and loses the work."
    )
    assert str(document["source"]) in target, (
        f"{document['target']} does not name its canonical source. A reader who "
        "cannot find the source will edit the generated file instead."
    )


def test_every_configured_source_is_inside_the_governance_folder() -> None:
    """Canonical sources live in `00 Governance/`, not scattered across the vault.

    One predictable location is what makes "where is the real file?" answerable
    without consulting the config. A source added elsewhere is a second source of
    truth forming (CLAUDE.md §19).
    """
    for document in _documents():
        source = str(document["source"])

        assert source.startswith("ProjectOne Vault/00 Governance/"), (
            f"Canonical source {source!r} is outside `ProjectOne Vault/00 Governance/`. "
            "Governed documents belong in one folder so they stay findable."
        )


def test_every_configured_target_is_at_the_repository_root() -> None:
    """Generated mirrors sit at the root, where the agent harnesses read them.

    `CLAUDE.md` and `AGENTS.md` are auto-loaded from the root by their
    respective tools. A target in a subdirectory would generate a file nothing
    reads — which is worse than no file, because it looks like it works.
    """
    for document in _documents():
        target = str(document["target"])

        assert "/" not in target and "\\" not in target, (
            f"Generated target {target!r} is not at the repository root. The agent "
            "harnesses only auto-load root-level files."
        )
