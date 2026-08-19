"""Offline tests for how the FA-03 drill obtains its PostgreSQL client tools.

The drill needs a disposable PostgreSQL server and cannot run here, or on any
machine without one -- which is exactly why the part that decides **what gets
executed** deserves tests of its own. That part builds a container command line
and accepts an image reference from the environment, and neither needs a
database, a network, or Docker to verify.

Every test below is pure: it builds argv lists and validates strings. None of
them starts a container, and none of them reaches a registry.

Written after a real incident. On 2026-08-19 the step this replaced hung for 62
minutes fetching packages and run 32271805691 had to be cancelled, taking
FA-03's evidence with it. `--pull never` is the guarantee that cannot happen
again, so it is asserted here rather than assumed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# `scripts/` is not a package and is not on the path for a plain `pytest` run:
# the drills execute as scripts, and `backup_restore_drill` imports its sibling
# `migration_cycle_drill` the same way. Adding the directory is what lets these
# tests import the module under test at all.
_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import backup_restore_drill as drill  # noqa: E402 - the path insert above must run first

# --------------------------------------------------------------------------
# Choosing where the tools come from
# --------------------------------------------------------------------------


def test_the_tools_come_from_path_when_no_image_is_configured(monkeypatch) -> None:
    """An unset variable must leave local behaviour exactly as it was.

    The drill has always run from PATH on a developer machine, and this change
    must not quietly require Docker of anyone who already has a matching client.
    The `mount` argument must not leak into that path either.
    """
    monkeypatch.delenv(drill._CLIENT_IMAGE_VARIABLE, raising=False)

    assert drill._client_image() is None
    assert drill._client_command("pg_dump", None) == ["pg_dump"]
    assert drill._client_command("pg_restore", None, mount="/tmp/drill") == ["pg_restore"]


def test_the_container_command_runs_the_tool_from_the_configured_image() -> None:
    """The image supplies the binary, and the entrypoint is bypassed.

    `postgres:17`'s entrypoint exists to start a server; without `--entrypoint`
    the arguments would reach `docker-entrypoint.sh` instead of `pg_dump`.
    """
    command = drill._client_command("pg_dump", "postgres:17")

    assert command[:3] == ["docker", "run", "--rm"]
    assert command[-3:] == ["--entrypoint", "pg_dump", "postgres:17"]
    assert command[command.index("--network") + 1] == "host"
    # pg_dump writes to stdout, so nothing is mounted for it.
    assert "--volume" not in command


def test_the_client_container_never_downloads_an_image() -> None:
    """`--pull never` is the whole reliability claim of this arrangement.

    Docker has already pulled the image to start the service container, so the
    drill reaches no registry. Without this flag a missing image silently
    reintroduces a network fetch into a required check -- the exact failure this
    replaced, and it cost 62 minutes the day it happened.
    """
    for tool, mount in (("pg_dump", None), ("pg_restore", "/tmp/drill")):
        command = drill._client_command(tool, "postgres:17", mount=mount)

        assert command[command.index("--pull") + 1] == "never"


def test_the_dump_directory_is_mounted_read_only() -> None:
    """`pg_restore` reads the dump and never writes to the host.

    A writable mount would hand a container write access to a runner directory
    for no reason the drill can name (CLAUDE.md 16, least privilege).
    """
    command = drill._client_command("pg_restore", "postgres:17", mount="/tmp/drill")

    assert command[command.index("--volume") + 1] == "/tmp/drill:/tmp/drill:ro"


def test_the_container_drops_privileges_it_does_not_need() -> None:
    """Both containers run with no capabilities and no privilege escalation.

    The single exception is asserted rather than tolerated: only the container
    with a mount gets `DAC_OVERRIDE` back, because it runs as root against a
    dump file the host wrote as another uid with mode 0600. The container that
    writes to stdout touches no host file and keeps nothing.
    """
    dump = drill._client_command("pg_dump", "postgres:17")
    restore = drill._client_command("pg_restore", "postgres:17", mount="/tmp/drill")

    for command in (dump, restore):
        assert command[command.index("--cap-drop") + 1] == "ALL"
        assert command[command.index("--security-opt") + 1] == "no-new-privileges"

    assert "--cap-add" not in dump
    assert restore[restore.index("--cap-add") + 1] == "DAC_OVERRIDE"


# --------------------------------------------------------------------------
# Validating the image reference
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "postgres:latest",  # unpinned: not a version
        "postgres",  # no tag at all
        "library/postgres:17",  # namespaced
        "ghcr.io/example/postgres:17",  # foreign registry
        "example.com/postgres:17",  # foreign registry
        "alpine:3",  # approved shape, wrong image
        "postgres:17 --privileged",  # a second argument smuggled in
        "postgres:17\n",  # trailing newline
        "postgres:17\tx",  # embedded tab
        "postgres:17;id",  # shell metacharacter
        "postgres:17@sha256:deadbeef",  # malformed digest
        "-v/:/host",  # leading dash: would read as a flag
    ],
)
def test_an_unapproved_image_reference_is_refused(value, monkeypatch) -> None:
    """Whatever is accepted here becomes `docker run <value>` in CI.

    The grammar is narrow rather than merely shell-safe. The value is never
    interpolated into a shell, so shell-safety is not the property that matters
    -- naming an image somebody else chose is.
    """
    monkeypatch.setenv(drill._CLIENT_IMAGE_VARIABLE, value)

    with pytest.raises(SystemExit) as raised:
        drill._client_image()

    assert drill._CLIENT_IMAGE_VARIABLE in str(raised.value)


@pytest.mark.parametrize(
    "value",
    [
        "postgres:17",
        "postgres:17.11",
        "postgres:17-bookworm",
        "postgres:17.11-alpine",
        "postgres:17@sha256:" + "a" * 64,
    ],
)
def test_an_approved_image_reference_is_accepted(value, monkeypatch) -> None:
    """The grammar must not be so narrow it rejects the values CI needs.

    A validator nobody can satisfy gets widened in a hurry by whoever hits it
    next, which is how narrow grammars quietly become permissive ones.
    """
    monkeypatch.setenv(drill._CLIENT_IMAGE_VARIABLE, value)

    assert drill._client_image() == value


# --------------------------------------------------------------------------
# Failing loudly when the toolchain cannot run
# --------------------------------------------------------------------------


def test_a_failed_docker_probe_stops_the_drill_with_a_named_reason(monkeypatch) -> None:
    """A broken Docker must stop here, not print an empty line and continue.

    This probe is the first thing that runs the container, so it is where a dead
    daemon and a `--pull never` miss both surface. Printing whatever `--version`
    produced and carrying on would push either of them three steps downstream,
    where it reads like a restore failure instead of a toolchain one.
    """
    monkeypatch.setenv(drill._CLIENT_IMAGE_VARIABLE, "postgres:17")
    monkeypatch.setattr(drill.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(
        drill.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=[],
            returncode=125,
            stdout="",
            stderr="Error response from daemon: No such image: postgres:17",
        ),
    )

    with pytest.raises(SystemExit) as raised:
        drill._require_tooling(drill._client_image())

    message = str(raised.value)
    assert "No such image" in message
    assert "postgres:17" in message


def test_a_missing_docker_binary_is_reported_before_anything_runs(monkeypatch) -> None:
    """Naming the variable that caused the requirement is the whole message.

    "docker: not found" on a machine nobody asked to install Docker is a
    confusing failure; saying which setting asked for it is not.
    """
    monkeypatch.setenv(drill._CLIENT_IMAGE_VARIABLE, "postgres:17")
    monkeypatch.setattr(drill.shutil, "which", lambda name: None)

    with pytest.raises(SystemExit) as raised:
        drill._require_tooling(drill._client_image())

    message = str(raised.value)
    assert "docker" in message
    assert drill._CLIENT_IMAGE_VARIABLE in message
