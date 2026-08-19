"""Tests that every project command in `.claude/commands/` keeps its safety contract.

**Why this file exists.** A project command is prose the harness expands into a
turn, so nothing type-checks it and nothing fails when it drifts. Two mechanical
properties must not drift.

*First, the tool frontmatter.* `allowed-tools` **preauthorizes**; it does not
restrict. A command absent from it is not forbidden -- absence removes that
command's explicit preauthorization and nothing more, and what happens next is
decided by the active Claude Code permission mode: Default may prompt, while Auto
runs without permission prompts, auto-approves local file operations and routes
other actions through its own background safety checks.

**These tests therefore assert only what is checkable in the file: that an
operation is not explicitly preauthorized by the command.** They do not assert,
and must never be described as asserting, that the owner will see a prompt --
that would be a promise about a permission mode this file cannot observe. The
safety question they answer is "is the dangerous thing **denied**, and is nothing
dangerous **broadly preauthorized**". Those are tested separately because they
fail for different reasons.

**These tests do not prove semantic safety.** Pattern matching over a frontmatter
string cannot enumerate every spelling of a destructive command (`git -c ...
push`, an alias, a wrapper script). They prove that the required deny rules are
present and that no broad write pattern is preauthorized. The prose mutation
boundary in each command remains the primary control; these are defense in depth.

*Scope note.* The deny-rule and broad-allow tests are scoped to `/po-build`
deliberately. `/po-fix` predates this contract and preauthorizes `git commit`,
`git push` and `git add`; hardening its frontmatter is a separate task and is not
folded into the change that introduced these tests (CLAUDE.md 29/35). The
universal tests below -- frontmatter fields, no subagents, a declared mutation
boundary -- apply to every command.

*Second, the Build Plan index parser.* `/po-build` resolves a step by parsing the
`## Steps` table, so a row shape its parser mishandles would make it resolve the
wrong step, or silently none. A title cell may carry `[[target|alias]]`, whose
pipe is **not** a cell separator -- a naive `split("|")` turns such a row into
five cells and drops it. `split_table_row` masks those pipes, and
`steps_table_rows` **raises on any row it cannot classify** rather than skipping
it, so a malformed row can never disappear.

**Every list here is derived, never written down**, except the policy constants.

`EXPECTED_SKILL_COUNT` is a deliberate drift alarm, not an architectural
assumption. `/po-build` and `/po-review` *discover* skills by globbing
`.claude/skills/*/SKILL.md`, so routing adapts to an eleventh skill on its own --
but the routing prose still claims a count. This test fails the moment a skill is
added, on purpose. Raising the number after updating that prose is the fix;
deleting the test is not.

**Deliberately not duplicated here:** the required CI check *names* are already
pinned by `test_ci_configuration.py::test_a_required_check_keeps_the_name_the_ruleset_requires`.

Offline and dependency-free: this parses text. It does not shell out and does not
import the application.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pytest

#: The repository root, relative to this file: tests/ -> api/ -> apps/ -> root.
REPO_ROOT = Path(__file__).resolve().parents[3]

COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
BUILD_PLAN = REPO_ROOT / "ProjectOne Vault" / "09 Development" / "Build Plan" / "Build Plan.md"
STEPS_DIR = BUILD_PLAN.parent / "Steps"

#: The step-identifier grammar `/po-build` section 1 documents.
STEP_ID_PATTERN = re.compile(r"^STEP-[0-9]{2}[a-z]?$")

#: Skills present when `/po-build` was written. See the module docstring.
EXPECTED_SKILL_COUNT = 10

#: Deny rules `/po-build` must carry. Presence is asserted; coverage of every
#: possible spelling is explicitly not claimed (see the module docstring).
REQUIRED_DENY_RULES = (
    "Agent",
    "Task",
    "Bash(git merge:*)",
    "Bash(git rebase:*)",
    "Bash(git reset:*)",
    "Bash(git clean:*)",
    "Bash(git stash:*)",
    "Bash(git branch -d:*)",
    "Bash(git branch -D:*)",
    "Bash(git commit --amend:*)",
    "Bash(git push --force:*)",
    "Bash(git push -f:*)",
    "Bash(git push --force-with-lease:*)",
    "Bash(git push --no-verify:*)",
    "Bash(gh pr merge:*)",
    "Bash(gh pr review:*)",
    "Bash(gh api --method POST:*)",
    "Bash(gh api --method PATCH:*)",
    "Bash(gh api --method PUT:*)",
    "Bash(gh api --method DELETE:*)",
    "Bash(gh api -X POST:*)",
    "Bash(./scripts/migrate.sh up:*)",
    "Bash(./scripts/migrate.sh down:*)",
    "Bash(./scripts/migrate.sh status:*)",
)

#: Allow patterns broad enough to admit a destructive variant through an extra
#: flag. A write command must not carry blanket command-level preauthorization;
#: what bounds it is the mutation boundary and the deny rules, not this list.
FORBIDDEN_BROAD_ALLOWS = (
    "Bash(git branch:*)",
    "Bash(git push:*)",
    "Bash(git push origin:*)",
    "Bash(git commit:*)",
    "Bash(git commit -m:*)",
    "Bash(git switch:*)",
    "Bash(git switch -c:*)",
    "Bash(git checkout:*)",
    "Bash(git add:*)",
    "Bash(git add --:*)",
    "Bash(gh pr create:*)",
    "Bash(gh api:*)",
    "Bash(gh api --method GET:*)",
    "Bash(gh:*)",
    "Bash(git:*)",
    "Bash(./scripts/migrate.sh:*)",
    "Bash(./scripts/migrate.sh new:*)",
)

#: Generic file-editing tools. Preauthorizing these would give the command
#: blanket authorization to write anywhere, contradicting its own mutation
#: boundary. What actually bounds an edit is the approved scope envelope, the
#: frozen planned file set and the pre-commit reconciliation -- not this list.
FORBIDDEN_GENERIC_EDIT_TOOLS = ("Edit", "Write", "NotebookEdit")


def _command_files() -> list[Path]:
    """Every project command, discovered rather than listed."""
    files = sorted(COMMANDS_DIR.glob("*.md"))
    assert files, "No project commands found -- has `.claude/commands/` moved?"
    return files


def _po_build() -> Path:
    """The `/po-build` command file, whose frontmatter this suite pins hardest."""
    path = COMMANDS_DIR / "po-build.md"
    assert path.is_file(), "`.claude/commands/po-build.md` is missing"
    return path


def _frontmatter(path: Path) -> str:
    """Return the leading YAML frontmatter block of a command file."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, f"{path.name} has no YAML frontmatter block"
    return match.group(1)


def _field(front: str, name: str) -> str:
    """Return one frontmatter field's value, up to the next top-level key."""
    pattern = rf"^{name}:(.*?)(?=^[a-z][a-z-]*:|\Z)"
    match = re.search(pattern, front, re.DOTALL | re.MULTILINE)
    assert match, f"frontmatter has no `{name}:` field"
    return match.group(1)


def _tool_entries(field_value: str) -> list[str]:
    """Split a tool list into entries, honouring the commas inside `Bash(...)`.

    A `Bash(...)` operand may itself contain a comma, so a plain `split(",")`
    would fragment one entry into two and make a membership test meaningless.
    """
    entries: list[str] = []
    depth = 0
    current = ""
    for character in field_value:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        if character == "," and depth == 0:
            entries.append(current.strip())
            current = ""
            continue
        current += character
    entries.append(current.strip())
    return [entry for entry in entries if entry]


# --- Build Plan index parsing -------------------------------------------------

_WIKI_SPAN = re.compile(r"\[\[[^\]]*\]\]")
_ALIAS_SENTINEL = "\x00"


def split_table_row(line: str) -> list[str]:
    """Split one Markdown table row, honouring `|` inside `[[target|alias]]`.

    Exposed rather than underscore-prefixed because it is unit-tested directly:
    the alias case is the one this parser exists to get right.
    """
    masked = _WIKI_SPAN.sub(lambda m: m.group(0).replace("|", _ALIAS_SENTINEL), line)
    body = masked.strip()
    assert body.startswith("|"), "not a table row"
    cells = body.strip("|").split("|")
    return [cell.strip().replace(_ALIAS_SENTINEL, "|") for cell in cells]


def _steps_table_lines() -> list[str]:
    """Return the `|`-prefixed lines of the `## Steps` table, and only those."""
    text = BUILD_PLAN.read_text(encoding="utf-8")
    section = re.search(r"^## Steps$\n(.*?)(?=^## )", text, re.DOTALL | re.MULTILINE)
    assert section, "The Build Plan has no `## Steps` section -- resolution depends on it."
    return [line for line in section.group(1).splitlines() if line.lstrip().startswith("|")]


def steps_table_rows() -> list[tuple[str, str]]:
    """Return `(step_id, title_cell)` for every step row in the `## Steps` table.

    Every table line is classified as exactly one of header, separator, phase
    heading, or step row. **A line matching none of them raises** -- a malformed
    row must never vanish silently, which is how a naive parser hides an aliased
    title.
    """
    rows: list[tuple[str, str]] = []
    for line in _steps_table_lines():
        cells = split_table_row(line)
        if len(cells) != 4:
            raise ValueError(f"index row does not have four cells: {line!r}")
        if all(cell and set(cell) <= {"-", ":"} for cell in cells):
            continue
        if cells == ["ID", "Title", "Status", "Detail"]:
            continue
        if not cells[0]:
            if cells[1] and not cells[2] and not cells[3]:
                continue
            raise ValueError(f"row has an empty id but is not a phase heading: {line!r}")
        if not cells[1] or not cells[2]:
            raise ValueError(f"step row is missing a title or a status: {line!r}")
        rows.append((cells[0], cells[1]))
    return rows


def _wiki_target(title_cell: str) -> str | None:
    """Return the note a title cell links to, for `[[x]]` and `[[x|alias]]`."""
    match = re.match(r"^\[\[([^\]|]+)(?:\|[^\]]+)?\]\]$", title_cell)
    return match.group(1) if match else None


# --- Universal command contract ----------------------------------------------


@pytest.mark.parametrize("path", _command_files(), ids=lambda p: p.name)
def test_every_command_declares_required_frontmatter(path: Path) -> None:
    front = _frontmatter(path)
    for field in ("description:", "argument-hint:", "allowed-tools:", "disallowed-tools:"):
        assert field in front, f"{path.name} is missing `{field}`"
    assert "disable-model-invocation: true" in front, (
        f"{path.name} must not be model-invocable -- a project command is typed "
        "by the owner (Task Workflow, Project Commands)."
    )


@pytest.mark.parametrize("path", _command_files(), ids=lambda p: p.name)
def test_no_command_permits_subagents(path: Path) -> None:
    denied = _field(_frontmatter(path), "disallowed-tools")
    for tool in ("Agent", "Task"):
        assert tool in denied, f"{path.name} must disallow `{tool}`"


@pytest.mark.parametrize("path", _command_files(), ids=lambda p: p.name)
def test_every_command_declares_a_mutation_boundary(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert re.search(r"^## Mutation boundary\b", text, re.MULTILINE), (
        f"{path.name} declares no mutation boundary section"
    )


# --- `/po-build` frontmatter, pinned ------------------------------------------


def test_po_build_denies_the_required_dangerous_operations() -> None:
    denied = _field(_frontmatter(_po_build()), "disallowed-tools")
    missing = [rule for rule in REQUIRED_DENY_RULES if rule not in denied]
    assert not missing, (
        f"po-build.md is missing deny rules: {missing}. `allowed-tools` only "
        "preauthorizes -- absence from it removes explicit preauthorization but "
        "does not block the operation, so an explicit deny is what makes it "
        "unreachable. Defense in depth, not a proof of safety."
    )


def test_po_build_does_not_broadly_preauthorize_a_write_command() -> None:
    allowed = _field(_frontmatter(_po_build()), "allowed-tools")
    offending = [pattern for pattern in FORBIDDEN_BROAD_ALLOWS if pattern in allowed]
    assert not offending, (
        f"po-build.md broadly preauthorizes: {offending}. A wildcarded write "
        "command can absorb an extra destructive flag without matching any deny "
        "rule. Branch creation, commit, push, PR creation and migration "
        "generation must not carry blanket command-level preauthorization "
        "(CLAUDE.md 20/20a)."
    )


def test_po_build_does_not_preauthorize_generic_file_edits() -> None:
    entries = _tool_entries(_field(_frontmatter(_po_build()), "allowed-tools"))
    offending = [tool for tool in FORBIDDEN_GENERIC_EDIT_TOOLS if tool in entries]
    assert not offending, (
        f"po-build.md preauthorizes generic file editing: {offending}. That is "
        "blanket authorization to write anywhere, which contradicts the command's "
        "own mutation boundary. This asserts only that the command does not "
        "explicitly preauthorize it -- not that any prompt will occur."
    )


def test_po_build_still_preauthorizes_the_fixed_governance_regeneration() -> None:
    """The one intentional preauthorized write: exact, fixed, idempotent commands."""
    entries = _tool_entries(_field(_frontmatter(_po_build()), "allowed-tools"))
    assert "Bash(./scripts/sync-governance-docs.sh --check)" in entries, (
        "po-build.md must keep the governance sync check preauthorized -- it is "
        "the fixed exception the command's mutation boundary declares."
    )


def test_skill_count_is_pinned_so_an_eleventh_fails_loudly() -> None:
    skills = sorted(SKILLS_DIR.glob("*/SKILL.md"))
    assert len(skills) == EXPECTED_SKILL_COUNT, (
        f"Found {len(skills)} skills, expected {EXPECTED_SKILL_COUNT}. Routing "
        "globs and already adapts -- but the commands' prose still claims a "
        "count. Update that prose deliberately, then raise EXPECTED_SKILL_COUNT. "
        "Do not delete this test."
    )


# --- Build Plan index ---------------------------------------------------------


def test_the_steps_table_parses_completely() -> None:
    lines = _steps_table_lines()
    assert len(lines) > 50, "The `## Steps` table shape has changed."
    rows = steps_table_rows()
    assert rows, "The `## Steps` table yielded no step rows."


def test_the_row_parser_handles_wiki_aliases() -> None:
    plain = "| STEP-31 | [[STEP-31 Workflow Async Execution]] | Not Started | full |"
    aliased = "| STEP-79 | [[STEP-79 Domain Screen Blueprints|Plans]] | Not Started | outline |"
    heading = "| | **Platform Substrate** | | |"

    assert split_table_row(plain) == [
        "STEP-31",
        "[[STEP-31 Workflow Async Execution]]",
        "Not Started",
        "full",
    ]
    assert split_table_row(aliased) == [
        "STEP-79",
        "[[STEP-79 Domain Screen Blueprints|Plans]]",
        "Not Started",
        "outline",
    ], "An alias pipe was read as a cell separator -- the defect this parser fixes."
    assert split_table_row(heading) == ["", "**Platform Substrate**", "", ""]
    assert _wiki_target("[[STEP-79 Domain Screen Blueprints|Plans]]") == (
        "STEP-79 Domain Screen Blueprints"
    )


def test_every_index_step_id_matches_the_documented_grammar() -> None:
    bad = [sid for sid, _ in steps_table_rows() if not STEP_ID_PATTERN.match(sid)]
    assert not bad, (
        f"Index ids outside `/po-build`'s documented grammar: {bad}. Widen the "
        "grammar in `.claude/commands/po-build.md` section 1 first, or the "
        "command will reject or mis-resolve these steps."
    )


def test_index_step_ids_are_unique() -> None:
    ids = [sid for sid, _ in steps_table_rows()]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicates, (
        f"Duplicate ids in the index: {duplicates}. `/po-build` refuses an "
        "ambiguous row rather than guessing."
    )


def test_every_index_row_resolves_to_an_existing_step_note() -> None:
    problems: list[str] = []
    for step_id, title in steps_table_rows():
        target = _wiki_target(title)
        if target is None:
            problems.append(f"{step_id}: title is not a single wiki-link ({title!r})")
        elif not (STEPS_DIR / f"{target}.md").is_file():
            problems.append(f"{step_id}: no note at Steps/{target}.md")
    assert not problems, "Index rows that do not resolve: " + "; ".join(problems)


def test_every_step_note_path_is_shell_safe() -> None:
    """Every resolved note path must survive `/po-build` section 2's classifier.

    All step notes contain spaces today, so quoting is mandatory rather than
    incidental. A quote, backslash or control character in a title would make the
    path unrepresentable under the command's fixed quoting discipline, and the
    command stops instead of resolving it.
    """
    unsafe = re.compile(r"""[\x00-\x1f\x7f'"\\]""")
    steps_root = str(STEPS_DIR.resolve()) + "/"
    problems: list[str] = []
    for step_id, title in steps_table_rows():
        target = _wiki_target(title)
        if target is None:
            continue
        if unsafe.search(target):
            problems.append(f"{step_id}: unsafe character in {target!r}")
        if unicodedata.normalize("NFC", target) != target:
            problems.append(f"{step_id}: {target!r} is not NFC-normalized")
        if not str((STEPS_DIR / f"{target}.md").resolve()).startswith(steps_root):
            problems.append(f"{step_id}: {target!r} escapes the Steps directory")
    assert not problems, "Step note paths `/po-build` could not pass to git: " + "; ".join(problems)
