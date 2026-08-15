"""FA-07 — audit retention is bounded, configurable, and tested.

CLAUDE.md §16 requires audit logs to be retained on a **stated** schedule and
disclosed as a bounded legal exception to user erasure. The audit found no
retention, purge, prune or expiry mechanism for `audit_log` at all: the
exception to deletion was unbounded, and growing.

The owner set the window on 2026-08-15 — **90 days, configurable before public
release** — and was explicit that remediation must define the deletion
behaviour *and* test it. A policy no test exercises is a comment.

**Boundary dates are the substance here.** "Older than 90 days" is exactly the
kind of rule that ships with an off-by-one nobody notices, because both the
correct and the incorrect version delete *something*. These tests pin the
boundary in both directions: a row one second past the window goes, a row one
second inside it stays.

Offline. The cutoff arithmetic and the SQL targeting are what can be wrong, and
neither needs a database to verify — the deletion is exercised against a
disposable database by the isolation suite, never against shared data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import SecretStr

from app.core.config import Environment, Settings
from app.repositories.audit import AuditRepository
from app.services.audit_service import AuditService
from tests.test_auth_endpoints import TEST_BYOK_KEY


def _settings(**overrides: object) -> Settings:
    """Build settings with retention overrides applied.

    Constructed here rather than through `test_auth_endpoints.make_settings`,
    which takes no arguments: widening a helper shared by several test modules
    so this one can vary a single field would change those modules' blast radius
    for no benefit (CLAUDE.md §29).
    """
    return Settings(
        environment=Environment.DEVELOPMENT,
        SUPABASE_URL="https://project.test",
        SUPABASE_SECRET_KEY=SecretStr("unused"),
        DATABASE_URL=SecretStr("postgresql://unused/db"),
        REQUEST_DATABASE_URL=SecretStr("postgresql://unused/db"),
        byok_encryption_key=SecretStr(TEST_BYOK_KEY),
        _env_file=None,
        **overrides,  # type: ignore[arg-type]
    )


# --------------------------------------------------------------------------
# The window itself
# --------------------------------------------------------------------------


def test_the_default_retention_window_is_ninety_days() -> None:
    """The owner's decision of 2026-08-15, asserted rather than assumed."""
    assert _settings().audit_retention_days == 90


def test_the_retention_window_is_configurable() -> None:
    """Configurable before public release, per the owner's decision.

    Hard-coding 90 would satisfy the letter of the finding and none of its
    intent: the window has to be adjustable without a code change when the
    compliance position firms up (CLAUDE.md §28a).
    """
    assert _settings(audit_retention_days=30).audit_retention_days == 30


def test_retention_can_be_disabled_for_a_deployment_that_must_keep_everything() -> None:
    """Zero means keep forever — a legal hold, not an accident.

    Some deployments will be under an obligation to retain. That must be
    expressible, and it must be explicit rather than achieved by setting the
    window to a very large number.
    """
    settings = _settings(audit_retention_days=0)

    assert settings.audit_retention_days == 0
    assert AuditService.retention_cutoff(settings) is None


# --------------------------------------------------------------------------
# The cutoff, at the boundary
# --------------------------------------------------------------------------


def test_the_cutoff_is_the_window_before_now() -> None:
    """90 days back from now, within a tolerance that cannot hide an error."""
    before = datetime.now(UTC)
    cutoff = AuditService.retention_cutoff(_settings())
    after = datetime.now(UTC)

    assert cutoff is not None
    assert before - timedelta(days=90) <= cutoff <= after - timedelta(days=90)


def test_a_row_older_than_the_window_is_past_the_cutoff() -> None:
    """One second past 90 days is deleted. The direction that must not be timid."""
    cutoff = AuditService.retention_cutoff(_settings())
    assert cutoff is not None

    older = datetime.now(UTC) - timedelta(days=90, seconds=1)

    assert older < cutoff


def test_a_row_inside_the_window_is_not_past_the_cutoff() -> None:
    """One second inside 90 days is kept. The direction that must not be greedy.

    Deleting a row a user or auditor still expects to find is the worse of the
    two failures: an over-retained row is a disclosure problem, a prematurely
    deleted one is unrecoverable.
    """
    cutoff = AuditService.retention_cutoff(_settings())
    assert cutoff is not None

    newer = datetime.now(UTC) - timedelta(days=89, hours=23, minutes=59)

    assert newer > cutoff


def test_a_shorter_window_moves_the_cutoff_forward() -> None:
    """The configured value is what the cutoff is derived from, not a constant."""
    short = AuditService.retention_cutoff(_settings(audit_retention_days=1))
    long = AuditService.retention_cutoff(_settings(audit_retention_days=365))

    assert short is not None
    assert long is not None
    assert short > long


# --------------------------------------------------------------------------
# What the purge targets
# --------------------------------------------------------------------------


def test_the_purge_statement_deletes_only_rows_older_than_the_cutoff() -> None:
    """The SQL is parameterised on the cutoff and filters on `created_at`.

    Asserted on the statement because the failure being guarded is a `DELETE`
    whose WHERE clause is wrong or absent — which no amount of downstream
    testing catches once it has run.
    """
    statement = AuditRepository.purge_statement()

    normalised = " ".join(statement.split()).lower()

    assert normalised.startswith("delete from public.audit_log")
    assert "where created_at < %s" in normalised


def test_the_purge_statement_is_not_an_unfiltered_delete() -> None:
    """**The regression that must never ship.**

    A `DELETE FROM audit_log` with no predicate destroys the entire trail for
    every tenant. This is the assertion standing between a retention feature
    and that outcome.
    """
    statement = " ".join(AuditRepository.purge_statement().split()).lower()

    assert "where" in statement, "the purge statement has no WHERE clause"
    assert "truncate" not in statement, (
        "TRUNCATE bypasses RLS and row-level filtering entirely — it must never "
        "appear in a retention purge"
    )


def test_the_purge_is_refused_when_retention_is_disabled() -> None:
    """A disabled window must delete nothing, not everything.

    The dangerous reading of `audit_retention_days = 0` is "keep nothing". It
    means "keep everything", and the two differ by the entire audit log.
    """
    assert AuditService.retention_cutoff(_settings(audit_retention_days=0)) is None


def test_a_negative_window_is_rejected_rather_than_treated_as_a_cutoff() -> None:
    """A negative window would place the cutoff in the future — deleting all rows.

    Rejected at settings construction, so a typo in configuration fails at
    startup rather than at the first purge (CLAUDE.md §24).
    """
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _settings(audit_retention_days=-1)


# --------------------------------------------------------------------------
# The disclosure this makes true
# --------------------------------------------------------------------------


def test_the_retention_window_is_reported_for_disclosure() -> None:
    """§16 requires the exception to be disclosed as bounded, not merely bounded.

    The value has to be readable by the code that tells a user how long their
    audit trail is kept, or the disclosure drifts from the behaviour.
    """
    settings = _settings()

    assert AuditService.retention_disclosure(settings) == (
        "Audit events are retained for 90 days, then permanently deleted."
    )


def test_the_disclosure_states_indefinite_retention_when_that_is_the_truth() -> None:
    """A deployment keeping everything must say so, not stay silent."""
    disclosure = AuditService.retention_disclosure(_settings(audit_retention_days=0))

    assert "indefinitely" in disclosure.lower()


def test_the_purge_reports_how_many_rows_it_deleted() -> None:
    """A purge that runs silently cannot be monitored (CLAUDE.md §26).

    The count is what an operator checks when asking whether retention is
    working, and what an alert fires on when it changes sharply. Exercised
    through a stub repository so the contract is asserted without a database.
    """

    class StubRepository:
        """Records the cutoff it was given and reports a fixed deletion count."""

        def __init__(self) -> None:
            self.cutoff: datetime | None = None

        def purge_older_than(self, cutoff: datetime) -> int:
            self.cutoff = cutoff
            return 7

    repository = StubRepository()
    service = AuditService(repository)  # type: ignore[arg-type]

    deleted = service.purge_expired(_settings())

    assert deleted == 7
    assert repository.cutoff is not None, "the purge ran without a cutoff"


def test_a_disabled_window_purges_nothing_and_touches_no_rows() -> None:
    """The end-to-end shape of the "keep everything" case.

    Not merely that the cutoff is None — that the repository is never asked to
    delete, so a disabled window cannot reach a DELETE statement at all.
    """

    class ExplodingRepository:
        """Fails the test if anything asks it to delete."""

        def purge_older_than(self, cutoff: datetime) -> int:
            raise AssertionError(f"purge attempted with retention disabled (cutoff={cutoff})")

    service = AuditService(ExplodingRepository())  # type: ignore[arg-type]

    assert service.purge_expired(_settings(audit_retention_days=0)) == 0
