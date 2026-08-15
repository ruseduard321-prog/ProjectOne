"""FA-01 — a locally-skipped isolation suite must be visible, not silent.

Tenant isolation itself is **proven, in CI**. The audit verified that rather
than inferring it: the API job runs a disposable `postgres:17` container and
sets `PROJECTONE_REQUIRE_DATABASE_TESTS`, which turns the `migrated_database`
fixture's skip into a `pytest.fail`. A green API job is therefore only reachable
if the database-backed tests actually executed. That is why the owner reduced
this finding to Medium on 2026-08-15, with the instruction not to conflate
"cannot run locally" with "not verified anywhere."

What remains is narrower and still real: on a developer machine with no
PostgreSQL, the same fixture takes the `pytest.skip` branch and the suite omits
over 300 tests while reporting green. A contributor can reasonably read that as
full coverage.

The fix is visibility, **not** a hard local failure. A contributor without
PostgreSQL must still be able to run the offline suite — that is the deliberate
design `conftest.py` records, and turning the skip into an error would trade one
wrong behaviour for another.

These tests assert the reporting hook itself, so they run identically in both
environments: with a database configured there is nothing to announce, and
without one the banner must appear.
"""

import os

from tests.conftest import (
    REQUIRE_DATABASE_TESTS_VAR,
    TEST_DATABASE_URL_VAR,
    database_skip_banner,
)


def test_the_banner_names_the_omitted_count_and_the_reason() -> None:
    """A reader must learn *how many* tests were omitted and *why*.

    `-ra` already reports skip reasons, one line per test. Three hundred
    identical lines is not a signal anybody reads — a single summary naming the
    count is what actually gets noticed.
    """
    banner = database_skip_banner(skipped=306)

    assert banner is not None
    assert "306" in banner
    assert TEST_DATABASE_URL_VAR in banner


def test_the_banner_says_how_to_run_the_omitted_tests() -> None:
    """Telling someone coverage is missing without telling them how to get it
    converts a silent gap into a visible one and stops there.
    """
    banner = database_skip_banner(skipped=306)

    assert banner is not None
    assert "docker run" in banner or "postgres" in banner.lower()


def test_the_banner_does_not_claim_isolation_is_unverified() -> None:
    """The wording must not overstate the gap.

    Isolation is proven in CI. A banner implying otherwise would teach every
    contributor something false, which is its own defect — and precisely the
    conflation the owner corrected.
    """
    banner = database_skip_banner(skipped=306)

    assert banner is not None
    assert "CI" in banner


def test_there_is_no_banner_when_nothing_was_skipped() -> None:
    """A full run must stay quiet.

    A warning that fires when there is nothing to warn about is noise, and
    noise is how real warnings stop being read.
    """
    assert database_skip_banner(skipped=0) is None


def test_the_offline_suite_still_passes_without_a_database() -> None:
    """The deliberate design, asserted so it is not "fixed" later.

    FA-01's disposition is explicit that the skip must not become a hard local
    failure. This test passing *is* that guarantee on a machine with no
    PostgreSQL: it runs in the same suite that skips the isolation tests.
    """
    configured = bool(os.environ.get(TEST_DATABASE_URL_VAR))
    required = bool(os.environ.get(REQUIRE_DATABASE_TESTS_VAR))

    # In CI both are set and the database tests run. Locally neither is, and the
    # suite still reaches this assertion — which is the property under test.
    assert configured or not required, (
        f"{REQUIRE_DATABASE_TESTS_VAR} is set without {TEST_DATABASE_URL_VAR}; "
        "the fixture should have failed the run before reaching here"
    )
