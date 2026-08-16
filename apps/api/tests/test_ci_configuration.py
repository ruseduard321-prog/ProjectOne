"""Tests that CI supplies every setting the API refuses to start without.

**Why this file exists.** STEP-17 made `PROJECTONE_BYOK_ENCRYPTION_KEY`
required. Every developer machine has it in `apps/api/.env`, which
`SettingsConfigDict(env_file=".env")` reads automatically, so the full local
suite passed. CI has no `.env` — the variable was simply absent — and the API
could not start there. The gap was invisible to every other test in this
directory, because they construct `Settings` directly with keyword arguments
and so never exercise the environment at all.

That is the failure mode being closed: a required setting is added, local
development keeps working because of a file that is deliberately not committed,
and the pipeline breaks on a push instead of in the change that caused it.

**The required-field list is derived, never written down.** Hardcoding the
names here would reproduce the original defect one level up: the next required
setting would be added to `Settings`, not to the copy, and this test would keep
passing while CI broke. `_required_setting_names` reads the model — and, since
STEP-28, also `STARTUP_REQUIRED_STORAGE_VARIABLES`, because a variable enforced
by `get_settings()` rather than by a required field is invisible to the model
alone. Either way a new requirement fails this test the moment it is
introduced, and the failure names the variable and the file to fix.

Offline and dependency-free: this parses text and inspects a pydantic model.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core.config import STARTUP_REQUIRED_STORAGE_VARIABLES, Settings

#: The workflow, relative to this file: tests/ -> api/ -> apps/ -> repo root.
WORKFLOW_PATH = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"

#: The job whose environment must satisfy `Settings`. The `web` job runs a
#: different application with different configuration, so it is not in scope.
API_JOB = "api"


def _api_job_env() -> dict[str, str]:
    """Return the `env:` mapping of the `api` job, parsed from the workflow.

    Parsed with a regex rather than a YAML library on purpose. PyYAML is not a
    dependency, and adding one so a single test can read a flat `KEY: value`
    block would be a new dependency for a one-off need (CLAUDE.md §28). The
    block this reads is exactly that shape, and `test_the_workflow_is_shaped_as_this_parser_assumes`
    below fails loudly if it ever stops being — so the shortcut cannot rot into
    a test that silently reads nothing.

    Returns:
        Variable names mapped to their literal values, unquoted.
    """
    source = WORKFLOW_PATH.read_text(encoding="utf-8")

    # The `api` job starts at two-space indentation and runs until the next key
    # at that same level, or the end of the file.
    job = re.search(
        rf"^  {API_JOB}:\n(?P<body>(?:.*\n)*?)(?=^  \S|\Z)",
        source,
        re.MULTILINE,
    )
    assert job is not None, f"No `{API_JOB}:` job found in {WORKFLOW_PATH.name}"

    # Within it, the job-level `env:` block at four spaces. `steps:` also
    # carries `env:` blocks, at deeper indentation, which this must not pick up:
    # a variable set on one step is not set for the job.
    block = re.search(
        r"^    env:\n(?P<body>(?:^      \S.*\n|^\s*(?:#.*)?\n)*)",
        job.group("body"),
        re.MULTILINE,
    )
    assert block is not None, f"No job-level `env:` block found in the `{API_JOB}` job"

    parsed: dict[str, str] = {}
    for line in block.group("body").splitlines():
        entry = re.match(r"^      (?P<key>[A-Za-z_][A-Za-z0-9_]*): (?P<value>.*)$", line)
        if entry:
            parsed[entry.group("key")] = entry.group("value").strip().strip("'\"")

    return parsed


def _required_setting_names() -> set[str]:
    """Return every variable the API refuses to start without.

    **Two sources, because the API has two ways of requiring a variable**, and
    reading only the first would make this test quietly incomplete:

    1. Fields with no default. A field's alias wins when it has one:
       `SUPABASE_URL` is read under that exact name, not under the prefix.
    2. `STARTUP_REQUIRED_STORAGE_VARIABLES` — checked by `get_settings()` rather
       than by pydantic, because a storage-free `Settings` must stay
       constructable for tests while a storage-free *deployment* must not start
       (STEP-28).

    Both are derived from `app/core/config.py`; neither is written down here.
    That is the whole design of this file: a copy of the list is how the next
    required setting gets added to the model and forgotten here, which is the
    STEP-17 failure this exists to prevent.
    """
    prefix = Settings.model_config["env_prefix"]

    field_required = {
        field.alias or f"{prefix}{name}".upper()
        for name, field in Settings.model_fields.items()
        if field.is_required()
    }

    return field_required | set(STARTUP_REQUIRED_STORAGE_VARIABLES)


def test_ci_supplies_every_required_setting() -> None:
    """CI must set every variable the API will not start without.

    The assertion that would have caught the STEP-18 pipeline failure before it
    was pushed: `PROJECTONE_BYOK_ENCRYPTION_KEY` became required and the
    workflow was never updated to match.
    """
    missing = _required_setting_names() - _api_job_env().keys()

    assert not missing, (
        f"The `{API_JOB}` job in {WORKFLOW_PATH.name} does not set {sorted(missing)}. "
        "These are required by app/core/config.py, so the API cannot start in CI. "
        "Add a non-secret placeholder to the job's `env:` block — do not give the "
        "setting a default in config.py, which would weaken it for production too."
    )


def test_the_ci_encryption_key_is_the_one_the_test_suite_uses() -> None:
    """CI's BYOK key must be the same constant as the test fixture.

    Two independently-valid keys would both work, which is exactly why they
    would drift. Pinning them together means the value CI validates is the value
    the suite exercises, and `TEST_BYOK_KEY` stays the single definition.
    """
    from tests.conftest import TEST_BYOK_KEY

    configured = _api_job_env().get("PROJECTONE_BYOK_ENCRYPTION_KEY")

    assert configured == TEST_BYOK_KEY, (
        "CI's PROJECTONE_BYOK_ENCRYPTION_KEY has drifted from tests.conftest.TEST_BYOK_KEY. "
        "Keep one definition so CI cannot validate a key the suite never uses."
    )


def test_the_ci_encryption_key_is_valid_but_obviously_not_a_secret() -> None:
    """CI's key must parse as AES-256 and be self-evidently a fixture.

    Both halves matter. Invalid, and the API exits at startup with the very
    error this fix exists to remove. Indistinguishable from a real key, and a
    reader cannot tell a committed placeholder from a leaked credential — so the
    value decodes to readable ASCII that says what it is (CLAUDE.md §16).
    """
    from app.ai.crypto import parse_encryption_key

    configured = _api_job_env()["PROJECTONE_BYOK_ENCRYPTION_KEY"]

    # Raises CredentialEncryptionError if it is not base64 or not 32 bytes,
    # which is the same check `get_settings()` runs at startup.
    key = parse_encryption_key(configured)

    assert key == b"test-byok-key-32-bytes-long-xxxx", (
        "CI's encryption key should decode to a string that announces itself as a "
        "test fixture. A random-looking value here is indistinguishable from a "
        "committed secret."
    )


def test_no_required_setting_is_given_a_default_to_satisfy_ci() -> None:
    """The BYOK key must stay required in `Settings`.

    The tempting fix for a missing variable in CI is a default in config.py.
    That would start the API in *every* environment without a configured key —
    a single hardcoded encryption key shared by every deployment, which is not
    encryption (CLAUDE.md §16). This asserts the tempting fix was not taken.
    """
    field = Settings.model_fields["byok_encryption_key"]

    assert field.is_required(), (
        "byok_encryption_key has acquired a default. A default encryption key is a "
        "hardcoded one shared by every deployment. Supply the value per environment "
        "instead — see the `api` job's `env:` block for how CI does it."
    )


def test_the_startup_required_storage_list_is_not_empty() -> None:
    """Emptying the list must not become the way to silence this file.

    `STARTUP_REQUIRED_STORAGE_VARIABLES` is both the requirement and the thing
    that reports the requirement, which is efficient and slightly dangerous: a
    future change that clears it would make `test_ci_supplies_every_required_setting`
    pass vacuously *and* remove the startup check, with no test objecting.

    The equivalent of `test_no_required_setting_is_given_a_default_to_satisfy_ci`
    for a requirement that lives outside the model.
    """
    assert STARTUP_REQUIRED_STORAGE_VARIABLES, (
        "STARTUP_REQUIRED_STORAGE_VARIABLES is empty, so the API no longer refuses to "
        "start without object storage and this file no longer checks that CI supplies "
        "it. If storage genuinely became optional again, say so in the step note — do "
        "not clear the list to make a pipeline green."
    )


def test_the_workflow_is_shaped_as_this_parser_assumes() -> None:
    """Guard the regex parser against a workflow restructure.

    Without this, moving the `env:` block or renaming the job would make
    `_api_job_env()` return an empty mapping — and an empty mapping would make
    the drift assertions above pass vacuously while CI was broken again. A
    parser this test depends on has to fail loudly rather than quietly.
    """
    assert WORKFLOW_PATH.is_file(), f"{WORKFLOW_PATH} not found — has the workflow moved?"

    env = _api_job_env()

    assert env, f"Parsed no variables from the `{API_JOB}` job — the workflow shape has changed"
    assert env.get("PROJECTONE_ENVIRONMENT") == "development", (
        "Expected the `api` job to run as `development`; the parser may be reading the wrong block."
    )


@pytest.mark.parametrize(
    "variable",
    [
        "SUPABASE_SECRET_KEY",
        "DATABASE_URL",
        "REQUEST_DATABASE_URL",
        # All four storage variables, not only the two secrets. An account id or
        # a bucket name is not a credential, but a committed workflow pointed at
        # a *real* bucket is still a real bucket that CI can write to.
        "PROJECTONE_R2_ACCOUNT_ID",
        "PROJECTONE_R2_BUCKET",
        "PROJECTONE_R2_ACCESS_KEY_ID",
        "PROJECTONE_R2_SECRET_ACCESS_KEY",
    ],
)
def test_ci_credentials_are_placeholders_not_real_ones(variable: str) -> None:
    """No value in the workflow may be a real credential.

    The workflow is committed, so anything here is public. CI is entitled to a
    throwaway container and nothing else — a real Supabase key or a real
    connection string in this file would be a credential leak, not a
    convenience (CLAUDE.md §16, §28a).
    """
    value = _api_job_env()[variable]

    assert "supabase.com" not in value, (
        f"{variable} in CI points at a real Supabase host. CI must use the throwaway "
        "service container, never a project holding real data."
    )
    assert any(marker in value for marker in ("ci-throwaway", "ci_placeholder", "127.0.0.1")), (
        f"{variable} in CI does not look like a placeholder. Every value in a committed "
        "workflow is public."
    )


# --------------------------------------------------------------------------
# Required-check names (FA-08)
# --------------------------------------------------------------------------

#: The check names the `Protect main` ruleset requires, verified against the
#: ruleset API on 2026-08-15 during STEP-25a.
#:
#: The ruleset matches on the literal string, so these names are part of the
#: repository's merge protection rather than cosmetic labels. Renaming a job
#: without updating the ruleset silently removes its gate: the ruleset goes on
#: requiring a check that no longer reports, and GitHub treats an absent check
#: as nothing to wait for.
REQUIRED_CHECK_NAMES = (
    "governance docs (sync check)",
    "web (lint, typecheck, test, build)",
    "api (lint, format, typecheck, test)",
)


@pytest.mark.parametrize("check_name", REQUIRED_CHECK_NAMES)
def test_a_required_check_keeps_the_name_the_ruleset_requires(check_name: str) -> None:
    """Each required check's job still declares the name the ruleset matches.

    **FA-08.** The audit found `governance docs (sync check)` reporting drift
    without blocking it; the owner made it a required check on 2026-08-11. This
    test guards the half that can regress silently afterwards — a job rename.

    It cannot verify the ruleset itself, which lives in repository settings
    rather than in the tree. What it can do is fail when the workflow stops
    offering a name the ruleset was configured against, which is the direction
    the breakage actually travels.
    """
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert f"name: {check_name}" in workflow, (
        f"No job in ci.yml declares `name: {check_name}`, but the `Protect main` "
        "ruleset requires a check with exactly that name. A required check that "
        "never reports does not block a merge — it is simply never waited for, "
        "so this rename would remove the gate rather than fail loudly."
    )
