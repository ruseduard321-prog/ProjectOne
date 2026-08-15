"""FA-05 — the rule that a connection-URI password never reaches a log.

Separate from `test_api_conventions.py`, which owns the *conventions* every
endpoint inherits. What is under test here is a single security control and the
specific defect the STEP-25 audit found in it: `redact()` covered bearer tokens
and `key=value` credential shapes, and did not cover a PostgreSQL connection URI
carrying an inline password. A failed `psycopg.connect(...)` renders the source
line holding that URI into the traceback, so a routine connection error wrote a
live database password into the application log.

Every credential in this file is unmistakably fake. A test that leaked a real
one while proving nothing leaks would be its own finding.

**Negative controls are the point.** A redaction test that still passes with the
redaction rule removed is testing nothing, so the tests that matter here assert
the un-redacted form *fails* — the same standard STEP-09 set for RLS.
"""

import logging

import psycopg
import pytest

from app.core.logging import RedactingFilter, log_context, redact

#: Unmistakably fake, and distinctive enough that a substring search for it
#: cannot collide with anything else the rendered output might contain.
FAKE_DB_PASSWORD = "totally-fake-pw-do-not-use-9Z8Y7X"
FAKE_DATABASE_URL = (
    f"postgresql://projectone_api:{FAKE_DB_PASSWORD}@db.example.test:5432/projectone"
)


# --------------------------------------------------------------------------
# Connection-URI passwords
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        FAKE_DATABASE_URL,
        f"connection failed: {FAKE_DATABASE_URL}",
        f'DATABASE_URL="{FAKE_DATABASE_URL}"',
        f"psycopg.connect('{FAKE_DATABASE_URL}')",
        # The drivered form SQLAlchemy and Alembic use.
        f"postgresql+psycopg://projectone_api:{FAKE_DB_PASSWORD}@db.example.test:5432/one",
        # Non-PostgreSQL schemes leak identically and cost nothing to cover.
        f"redis://default:{FAKE_DB_PASSWORD}@cache.example.test:6379/0",
    ],
)
def test_a_connection_uri_password_is_redacted(line: str) -> None:
    """The FA-05 defect itself: an inline URI password must not survive."""
    result = redact(line)

    assert FAKE_DB_PASSWORD not in result, result
    assert "[REDACTED]" in result


def test_a_redacted_uri_still_identifies_the_connection() -> None:
    """Redaction must not cost the diagnostic value of the line.

    An operator reading a connection failure needs to know *which* connection
    failed. Removing the whole URI would hide the host and the user along with
    the password, turning a debuggable error into a mystery — the same reason
    the bearer-token rule preserves the scheme.
    """
    result = redact(f"could not connect: {FAKE_DATABASE_URL}")

    assert FAKE_DB_PASSWORD not in result
    assert "postgresql://" in result
    assert "projectone_api" in result
    assert "db.example.test:5432" in result


def test_a_uri_without_a_password_is_left_alone() -> None:
    """No password, nothing to redact — the line must survive intact.

    Guards against a pattern greedy enough to mangle every URL in the logs.
    """
    assert redact("connecting to postgresql://reader@db.example.test:5432/app") == (
        "connecting to postgresql://reader@db.example.test:5432/app"
    )
    assert redact("GET https://api.example.test/v1/items") == (
        "GET https://api.example.test/v1/items"
    )


# --------------------------------------------------------------------------
# Key-shaped credentials the audit found unmatched
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "leaked"),
    [
        (
            "PROJECTONE_BYOK_ENCRYPTION_KEY=dGVzdC1mYWtlLWtleS1ub3QtcmVhbC0wMDAw",
            "dGVzdC1mYWtlLWtleS1ub3QtcmVhbC0wMDAw",
        ),
        (f"DATABASE_URL={FAKE_DATABASE_URL}", FAKE_DB_PASSWORD),
        ("SUPABASE_SERVICE_ROLE_KEY=fake-service-role-key-000", "fake-service-role-key-000"),
        ("SOME_TOKEN=fake-token-value-000", "fake-token-value-000"),
        ("ADMIN_PASSWORD=fake-password-value-000", "fake-password-value-000"),
        ("STRIPE_SECRET=fake-secret-value-000", "fake-secret-value-000"),
    ],
)
def test_key_shaped_credentials_are_redacted(line: str, leaked: str) -> None:
    """`*_KEY`, `*_SECRET`, `*_TOKEN`, `*_PASSWORD`, `*_URL` in KEY=value form.

    The environment-variable rendering, which is how these appear when a config
    object is logged or a startup failure dumps its settings.
    """
    result = redact(line)

    assert leaked not in result, result
    assert "[REDACTED]" in result


def test_a_database_url_keeps_its_host_while_losing_its_password() -> None:
    """`DATABASE_URL=<uri>` must not flatten to `[REDACTED]`.

    Both the URI rule and the key-shaped rule would remove the credential, but
    flattening the whole value discards the host and user an operator needs to
    diagnose the failure. The URI rule runs first and the `*_URL` rule skips a
    value already carrying a marker, so the informative form survives.
    """
    result = redact(f"DATABASE_URL={FAKE_DATABASE_URL}")

    assert FAKE_DB_PASSWORD not in result
    assert "db.example.test:5432" in result, result
    assert "projectone_api" in result, result


def test_an_opaque_url_value_is_still_fully_redacted() -> None:
    """A `*_URL` carrying a credential the URI rule cannot parse is not trusted.

    The host-preserving path above depends on `_URI_PASSWORD` having recognised
    the value. When it has not, there is no structure to preserve and the whole
    value goes.
    """
    result = redact("SOME_URL=opaque-fake-credential-000")

    assert "opaque-fake-credential-000" not in result
    assert "[REDACTED]" in result


def test_a_key_shaped_line_keeps_its_variable_name() -> None:
    """Which credential was present is the debuggable half; keep it."""
    result = redact("PROJECTONE_BYOK_ENCRYPTION_KEY=dGVzdC1mYWtlLWtleS1ub3QtcmVhbA==")

    assert "PROJECTONE_BYOK_ENCRYPTION_KEY" in result
    assert "dGVzdC1mYWtlLWtleS1ub3QtcmVhbA" not in result


def test_ordinary_key_value_pairs_are_not_redacted() -> None:
    """Only credential-shaped keys. A pattern that eats `method=GET` is useless."""
    assert redact("method=GET path=/v1/workspaces status=200") == (
        "method=GET path=/v1/workspaces status=200"
    )
    assert "workspace_id=abc-123" in redact("workspace_id=abc-123")


# --------------------------------------------------------------------------
# The end-to-end reproduction, and the regression it guards
# --------------------------------------------------------------------------


def test_a_failed_connection_does_not_log_its_password(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The audit's own reproduction, inverted into a regression test.

    STEP-25 attached `RedactingFilter` to a handler, called `logger.exception()`
    on a failed `psycopg.connect(...)`, and found the plaintext password in the
    emitted record — the traceback renders the source line holding the URI.
    This asserts that path is now closed, through the real filter, on a real
    connection failure to a host that does not resolve.
    """
    logger = logging.getLogger("test.fa05.connection")

    with caplog.at_level(logging.ERROR, logger=logger.name):
        caplog.handler.addFilter(RedactingFilter())
        try:
            try:
                psycopg.connect(FAKE_DATABASE_URL, connect_timeout=1)
            except Exception:
                logger.exception("database connection failed for %s", FAKE_DATABASE_URL)
        finally:
            caplog.handler.filters = [
                existing
                for existing in caplog.handler.filters
                if not isinstance(existing, RedactingFilter)
            ]

    rendered = "\n".join(
        [record.getMessage() for record in caplog.records]
        + [caplog.handler.format(record) for record in caplog.records]
    )

    assert rendered, "the probe logged nothing, so it proved nothing"
    assert FAKE_DB_PASSWORD not in rendered, rendered


def test_log_context_redacts_a_connection_uri() -> None:
    """`log_context` applies the same rule, deliberately independently.

    Two applications of one rule, so a handler misconfiguration is not the
    single point of failure for a credential leak.
    """
    result = log_context(event="connect_failed", dsn=FAKE_DATABASE_URL)

    assert FAKE_DB_PASSWORD not in result
    assert "event=connect_failed" in result


# --------------------------------------------------------------------------
# Negative controls
# --------------------------------------------------------------------------


def test_the_uri_pattern_is_load_bearing() -> None:
    """Remove the URI rule and the leak returns — so the rule is what stops it.

    Without this, a future refactor could delete the pattern and leave the
    suite green, which is precisely the failure mode the audit found.
    """
    from app.core import logging as logging_module

    surviving = tuple(
        entry
        for entry in logging_module._REDACTIONS
        if entry[0] is not logging_module._URI_PASSWORD
    )

    assert len(surviving) == len(logging_module._REDACTIONS) - 1, (
        "the URI-password pattern is not in the redaction set"
    )

    text = FAKE_DATABASE_URL
    for pattern, replacement in surviving:
        text = pattern.sub(replacement, text)

    assert FAKE_DB_PASSWORD in text, (
        "the password was redacted without the URI pattern, so the pattern proves nothing"
    )


def test_the_key_shaped_pattern_is_load_bearing() -> None:
    """The same control for the `KEY=value` rule."""
    from app.core import logging as logging_module

    surviving = tuple(
        entry
        for entry in logging_module._REDACTIONS
        if entry[0] is not logging_module._KEY_SHAPED_ENV
    )

    assert len(surviving) == len(logging_module._REDACTIONS) - 1

    text = "PROJECTONE_BYOK_ENCRYPTION_KEY=dGVzdC1mYWtlLWtleS1ub3QtcmVhbA=="
    for pattern, replacement in surviving:
        text = pattern.sub(replacement, text)

    assert "dGVzdC1mYWtlLWtleS1ub3QtcmVhbA" in text, (
        "redacted without the key-shaped pattern, so the pattern proves nothing"
    )


def test_the_url_shaped_pattern_is_load_bearing() -> None:
    """The same control for the `*_URL` / `*_DSN` rule.

    Uses a value `_URI_PASSWORD` cannot parse, so this rule is the only thing
    standing between the credential and the log.
    """
    from app.core import logging as logging_module

    surviving = tuple(
        entry
        for entry in logging_module._REDACTIONS
        if entry[0] is not logging_module._KEY_SHAPED_URL
    )

    assert len(surviving) == len(logging_module._REDACTIONS) - 1

    text = "SOME_URL=opaque-fake-credential-000"
    for pattern, replacement in surviving:
        text = pattern.sub(replacement, text)

    assert "opaque-fake-credential-000" in text, (
        "redacted without the URL pattern, so the pattern proves nothing"
    )


# --------------------------------------------------------------------------
# The existing rules must survive the new ones
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "expected_fragment"),
    [
        ("Authorization: Bearer fake.jwt.value", "Bearer [REDACTED]"),
        ("{'authorization': 'Basic ZmFrZTpmYWtl'}", "[REDACTED]"),
        ('{"password": "fake-hunter2"}', "[REDACTED]"),
        ("api_key=fake_key_abcdefghijklmnop", "[REDACTED]"),
    ],
)
def test_existing_redactions_are_not_degraded(line: str, expected_fragment: str) -> None:
    """The new patterns must not re-redact an already-redacted line.

    This is the defect the bearer rule's negative lookahead was written to
    avoid: a second pass collapsing `Bearer [REDACTED]` into `[REDACTED]`,
    losing the scheme the first rule deliberately preserved.
    """
    result = redact(line)

    assert expected_fragment in result
    for leaked in ("fake.jwt.value", "ZmFrZTpmYWtl", "fake-hunter2", "fake_key_abcdefghijklmnop"):
        assert leaked not in result


def test_redaction_is_idempotent() -> None:
    """Redacting twice equals redacting once, for every rule in the set."""
    lines = [
        FAKE_DATABASE_URL,
        "Authorization: Bearer fake.jwt.value",
        "PROJECTONE_BYOK_ENCRYPTION_KEY=dGVzdC1mYWtl",
        '{"password": "fake-hunter2"}',
    ]

    for line in lines:
        once = redact(line)
        assert redact(once) == once, line
