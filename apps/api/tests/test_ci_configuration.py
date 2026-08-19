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
#: without updating the ruleset strands its gate: the ruleset goes on expecting
#: a context that no longer reports, and GitHub holds every PR waiting for a
#: status that never arrives. The result is a permanently blocked merge, not a
#: silent pass.
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
        "ruleset requires a check with exactly that name. The ruleset would keep "
        "expecting a context nothing reports, and GitHub holds a PR waiting for a "
        "status that never arrives — so this rename blocks every merge until the "
        "ruleset is corrected."
    )


# --------------------------------------------------------------------------
# Triggers, concurrency and job ceilings
# --------------------------------------------------------------------------

#: Every CI job with the ceiling it must declare. GitHub's default is 360
#: minutes, so an unbounded job holds a required check pending for six hours —
#: and a pending required check blocks the merge button the whole time.
JOB_TIMEOUTS = (
    ("governance-docs", 10),
    ("web", 20),
    ("api", 30),
)


def _top_level_block(name: str) -> str:
    """Return one top-level workflow block, comments stripped.

    Comments are documentation, not configuration: a test that read them could
    pass on a promise the workflow does not actually keep.

    Args:
        name: The top-level key, at column zero.

    Returns:
        The block's body, with comment lines removed.
    """
    source = WORKFLOW_PATH.read_text(encoding="utf-8")
    block = re.search(rf"^{name}:\n(?P<body>(?:^ +.*\n|^\s*\n)*)", source, re.MULTILINE)
    assert block is not None, f"No top-level `{name}:` block in {WORKFLOW_PATH.name}"

    return "".join(
        line
        for line in block.group("body").splitlines(keepends=True)
        if not line.lstrip().startswith("#")
    )


def _trigger_sub_block(event: str) -> str:
    """Return one event's sub-block from the `on:` mapping.

    Args:
        event: The trigger name, such as `push` or `pull_request`.

    Returns:
        The event's indented body, empty when the event carries no settings.
    """
    block = re.search(
        rf"^  {event}:\n(?P<body>(?:^    .*\n)*)", _top_level_block("on"), re.MULTILINE
    )
    assert block is not None, f"CI declares no `{event}:` trigger"

    return block.group("body")


def test_push_ci_is_restricted_to_main() -> None:
    """A push to a PR branch must not start a second full pipeline.

    `push` and `pull_request` both fire on a PR-branch push, against the same
    commit, and both report the same required check names — so a pending context
    from either holds the merge button. Concurrency cannot collapse them:
    `github.ref` differs by event, so the two never share a group.
    """
    branches = re.findall(r"^      - (?P<branch>\S+)$", _trigger_sub_block("push"), re.MULTILINE)

    assert branches == ["main"], (
        "CI's `push:` trigger must be restricted to `main` — post-merge validation of the "
        f"squashed commit. Found: {branches or 'no branch filter'}. An unrestricted push "
        "trigger runs the whole pipeline twice for every PR update."
    )


def test_pull_request_ci_is_not_branch_restricted() -> None:
    """The merge gate must keep running for every pull request.

    The duplicate-run fix narrows `push`. Narrowing `pull_request` instead — or
    as well — would remove the gate the fix exists to protect.
    """
    assert re.search(r"^  pull_request:\s*$", _top_level_block("on"), re.MULTILINE), (
        "CI must run on every `pull_request`; that run reports the required checks."
    )
    assert not _trigger_sub_block("pull_request").strip(), (
        "`pull_request:` must carry no branch filter — every PR is validated, without exception."
    )


def test_each_pull_request_gets_its_own_stable_concurrency_group() -> None:
    """Supersede within one PR, never across PRs, never on `main`.

    Keying on `github.ref` is the mistake this replaces: it is
    `refs/pull/<n>/merge` for a pull_request and `refs/heads/<branch>` for a
    push, so the two events never share a group and cannot deduplicate.

    The `|| github.run_id` fallback is what protects `main`. A push to `main` has
    no PR number, and `run_id` is unique per run, so every main validation gets
    its own group and a later push to `main` cannot cancel or replace it through
    this configuration. Without the fallback, main runs would share one group —
    and GitHub keeps at most one *pending* run per group, so a newer merge would
    replace a queued validation outright, which no `cancel-in-progress` setting
    prevents.
    """
    group = re.search(r"^  group: (?P<value>.+)$", _top_level_block("concurrency"), re.MULTILINE)
    assert group is not None, "CI declares no concurrency `group:`"
    value = group.group("value")

    assert "github.event.pull_request.number" in value, (
        "The concurrency group must key on the pull request number, so pushes to one PR "
        f"supersede each other and different PRs never do. Found: {value}"
    )
    assert "github.run_id" in value, (
        "The concurrency group must fall back to `github.run_id`, giving every push to `main` "
        f"a group of its own so no main validation is cancelled or replaced. Found: {value}"
    )
    assert "github.ref" not in value, (
        "The concurrency group must not key on `github.ref`: it differs between the push and "
        f"pull_request events, which is what let duplicate runs coexist. Found: {value}"
    )


def test_only_pull_request_runs_are_cancelled() -> None:
    """A commit on `main` is already permanent and must be validated.

    An unconditional `cancel-in-progress: true` would let the next merge cancel
    the previous merge's validation, leaving a commit on `main` proven by nothing.
    """
    cancel = re.search(
        r"^  cancel-in-progress: (?P<value>.+)$", _top_level_block("concurrency"), re.MULTILINE
    )
    assert cancel is not None, "CI declares no `cancel-in-progress:`"
    value = cancel.group("value")

    assert "github.event_name == 'pull_request'" in value, (
        "`cancel-in-progress` must be conditional on the event being a pull request, so "
        f"superseded PR runs cancel and main validations never do. Found: {value}"
    )


@pytest.mark.parametrize(("job", "minutes"), JOB_TIMEOUTS)
def test_every_ci_job_declares_its_timeout(job: str, minutes: int) -> None:
    """Every job is bounded, so a hung step fails rather than blocking the merge.

    Without `timeout-minutes` GitHub applies 360 minutes. A required check stays
    pending for that whole time while a step hangs, and a pending required check
    holds the merge button — an unbounded job is a merge blocker waiting for a
    slow network. The ceilings leave generous headroom over observed durations.
    """
    source = WORKFLOW_PATH.read_text(encoding="utf-8")

    block = re.search(rf"^  {job}:\n(?P<body>(?:.*\n)*?)(?=^  \S|\Z)", source, re.MULTILINE)
    assert block is not None, f"No `{job}:` job found in {WORKFLOW_PATH.name}"

    declared = re.search(
        r"^    timeout-minutes: (?P<value>\d+)$", block.group("body"), re.MULTILINE
    )
    assert declared is not None, (
        f"The `{job}` job declares no `timeout-minutes`, so GitHub applies its 360-minute "
        "default and a hung step holds a required check pending for six hours."
    )
    assert int(declared.group("value")) == minutes, (
        f"The `{job}` job's timeout is {declared.group('value')} minutes; this suite expects "
        f"{minutes}. Change both together, deliberately."
    )


@pytest.mark.parametrize(
    "step_name",
    ["Verify migrations reverse (FA-02)", "Verify backup and restore (FA-03)"],
)
def test_the_pipeline_still_runs_the_foundation_drills(step_name: str) -> None:
    """FA-02 and FA-03 must keep running on every pull request.

    Both drills live in the `api` job, which runs on `pull_request`. A trigger
    change that narrowed that would remove the only place either drill executes —
    and a drill that stops running fails silently by definition.
    """
    assert f"name: {step_name}" in WORKFLOW_PATH.read_text(encoding="utf-8"), (
        f"The `{step_name}` step is gone from ci.yml. It is the only place this drill runs."
    )


def test_the_trigger_and_concurrency_blocks_are_shaped_as_this_parser_assumes() -> None:
    """Guard the parsers above against a workflow restructure.

    Same reasoning as `test_the_workflow_is_shaped_as_this_parser_assumes`: a
    parser that silently reads nothing turns every assertion above into a vacuous
    pass, which is worse than having no test at all.
    """
    assert _top_level_block("on").strip(), "Parsed no triggers — the `on:` block changed shape"
    assert _top_level_block("concurrency").strip(), "Parsed no concurrency settings"
    assert _trigger_sub_block("push").strip(), "Parsed no `push:` configuration"


# --------------------------------------------------------------------------
# The FA-03 drill's client image (STEP-25a, FA-03)
# --------------------------------------------------------------------------

#: The service container whose image the FA-03 drill's client tools must match.
#: Named rather than positional on purpose — `services:` is a mapping, and a
#: second service added above this one must never become the comparison target.
API_DATABASE_SERVICE = "postgres"

#: The variable naming the image the drill runs `pg_dump`/`pg_restore` from.
CLIENT_IMAGE_VARIABLE = "PROJECTONE_PG_CLIENT_IMAGE"


def _api_service_image(service: str = API_DATABASE_SERVICE, *, source: str | None = None) -> str:
    """Return the image declared by one **named** service of the `api` job.

    Resolved by walking `api:` -> `services:` -> `<service>:` -> `image:`, rather
    than by taking the first `image:` the job happens to contain. The difference
    is not cosmetic: adding a second service container — a cache, a queue — would
    put another `image:` in the same job, and a first-match parser would silently
    start comparing the drill's client against whichever one appeared first.
    `test_the_service_image_parser_resolves_the_named_service` holds that line.

    Args:
        service: The key under `services:` to read.
        source: Workflow text to parse instead of the real file. Used by the
            guard test below to present a shape this repository does not have
            yet, so the parser is tested against the failure it must survive.

    Returns:
        The image reference the named service declares.
    """
    text = source if source is not None else WORKFLOW_PATH.read_text(encoding="utf-8")

    job = re.search(rf"^  {API_JOB}:\n(?P<body>(?:.*\n)*?)(?=^  \S|\Z)", text, re.MULTILINE)
    assert job is not None, f"No `{API_JOB}:` job found in {WORKFLOW_PATH.name}"

    services = re.search(
        r"^    services:\n(?P<body>(?:.*\n)*?)(?=^    \S|\Z)",
        job.group("body"),
        re.MULTILINE,
    )
    assert services is not None, f"The `{API_JOB}` job declares no `services:` block"

    entry = re.search(
        rf"^      {re.escape(service)}:\n(?P<body>(?:.*\n)*?)(?=^      \S|\Z)",
        services.group("body"),
        re.MULTILINE,
    )
    assert entry is not None, (
        f"No `{service}:` service found in the `{API_JOB}` job. The FA-03 drill's client "
        "image is compared against this service specifically — if it was renamed, this "
        "comparison has to be pointed at the new name deliberately."
    )

    image = re.search(r"^        image: (?P<value>\S+)$", entry.group("body"), re.MULTILINE)
    assert image is not None, f"The `{service}` service declares no `image:`"

    return image.group("value")


def test_the_drill_client_image_matches_the_database_service_image() -> None:
    """FA-03's client tools must come from the same image as the server.

    `pg_dump` refuses to dump a server newer than itself, so the drill needs a
    client of at least the service container's major version. Naming one image
    for both is what makes that true by construction instead of by two pins
    somebody has to remember to bump together — and this is what fails when they
    drift, rather than a red drill blaming the backup for a toolchain gap.

    `--pull never` gives this a second edge: the drill can only run an image
    Docker already holds, and the only image it is guaranteed to hold is the one
    the service container started from. A client image naming anything else
    would not be slow, it would simply not exist.
    """
    configured = _api_job_env().get(CLIENT_IMAGE_VARIABLE)

    assert configured == _api_service_image(), (
        f"{CLIENT_IMAGE_VARIABLE} has drifted from the `{API_DATABASE_SERVICE}` service "
        "container's image. The FA-03 drill runs pg_dump/pg_restore from that image with "
        "`--pull never`, so it must name an image the job has already pulled. Bump both "
        "together."
    )


def test_the_service_image_parser_resolves_the_named_service() -> None:
    """A second service must not become the comparison target by being first.

    This repository declares one service today, so the real workflow cannot
    exercise the ambiguity — which is exactly why the parser is pointed at a
    shape it does not have yet. A first-`image:` parser passes every assertion in
    this file right up until someone adds a cache container, and then it starts
    comparing the PostgreSQL client against Redis and reporting drift that is not
    there (or, worse, agreement that is not either).
    """
    two_services = (
        "jobs:\n"
        "  api:\n"
        "    runs-on: ubuntu-latest\n"
        "    services:\n"
        "      cache:\n"
        "        image: redis:7\n"
        "        ports:\n"
        "          - 6379:6379\n"
        "      postgres:\n"
        "        # A comment, at the depth the real workflow uses.\n"
        "        image: postgres:17\n"
        "        env:\n"
        "          POSTGRES_DB: projectone_test\n"
        "\n"
        "    env:\n"
        "      PROJECTONE_ENVIRONMENT: development\n"
        "  web:\n"
        "    runs-on: ubuntu-latest\n"
    )

    assert _api_service_image(source=two_services) == "postgres:17"
    assert _api_service_image("cache", source=two_services) == "redis:7"

    # The failure this guards: `redis:7` is the first `image:` in that job.
    naive = re.search(r"^        image: (?P<value>\S+)$", two_services, re.MULTILINE)
    assert naive is not None and naive.group("value") == "redis:7", (
        "The fixture no longer places a non-PostgreSQL image first, so it no longer "
        "distinguishes a named lookup from a first-match one."
    )


def test_the_service_block_is_shaped_as_this_parser_assumes() -> None:
    """Guard the service parser against a workflow restructure.

    Same reasoning as the other parser guards in this file: a parser that
    silently reads nothing turns the drift assertion above into a vacuous pass.
    An unknown service name must raise rather than return something plausible.
    """
    assert _api_service_image() == "postgres:17", (
        "The `postgres` service image is not what this suite expects. Change it and "
        f"{CLIENT_IMAGE_VARIABLE} together, deliberately."
    )

    with pytest.raises(AssertionError):
        _api_service_image("no-such-service")
