"""Request logging, and the rule that no credential ever reaches a log.

Two things live here, and the second is the reason the first is not simply a
call to `logging.basicConfig`:

1. A formatter that stamps every line with the request's correlation id, so a
   user-reported failure is findable without reproducing it (CLAUDE.md §25).
2. A **redacting filter** that removes credential-shaped values from any record
   passing through it, whoever emitted it.

**Why the filter exists rather than a convention.** "Do not log the
`Authorization` header" is a rule that holds exactly until someone debugging an
auth problem logs the request headers, and it fails silently and permanently at
that moment — the token is in the log file, and nothing turns red. Enforcing it
in the pipeline means the convenience change a future engineer makes produces a
redacted line instead of a leaked credential (CLAUDE.md §16, §25).

The filter is a floor, not a licence: code should still not pass tokens to a
logger. It exists because the cost of being wrong once is unbounded.
"""

import logging
import re
import sys
from typing import Any

from app.core.api import current_request_id

# Identifies the root handler installed by `configure_logging`, so re-running it
# replaces its own handler rather than clearing every handler on the root logger
# -- including ones the test suite depends on.
_HANDLER_NAME = "projectone.stdout"

# A connection URI's inline password: `scheme://user:<secret>@host`.
#
# Named rather than inlined below so its negative-control test can remove
# exactly this rule and prove the leak returns without it (FA-05). A redaction
# test that still passes with the rule deleted is testing nothing.
#
# Only the password is replaced. Scheme, user and host survive, because an
# operator reading a connection failure needs to know *which* connection failed
# -- deleting the whole URI trades a leak for a mystery.
#
# `[^:@/\s]+` for the password: it cannot span a host separator, so the pattern
# cannot run past the end of one URI and swallow the rest of the line. The
# negative lookahead leaves an already-redacted URI alone, keeping redaction
# idempotent.
_URI_PASSWORD = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^:@/\s]+:)(?!\[REDACTED\])[^:@/\s]+@")

# Credential-shaped environment variables in `KEY=value` form, which is how
# settings appear when a config object is logged or a startup failure dumps its
# environment. `PROJECTONE_BYOK_ENCRYPTION_KEY` is the case the audit found
# unmatched.
#
# Anchored on the *suffix* of the name rather than a list of known variables, so
# a variable added next year is covered without anyone remembering to add it
# here.
#
# `_URL`/`_DSN` values are deliberately *excluded* from this rule and left to
# `_URI_PASSWORD`, which runs first. Both would redact the credential, but this
# one would flatten the whole value to `[REDACTED]`, discarding the host and
# user that make a connection failure diagnosable. The lookahead skips any value
# already carrying a redaction marker -- which, after `_URI_PASSWORD` has run,
# is exactly the URL and DSN cases.
_KEY_SHAPED_ENV = re.compile(
    r"(?i)\b([A-Z][A-Z0-9_]*_(?:KEY|SECRET|TOKEN|PASSWORD|PASS|CREDENTIALS?)\s*=\s*)"
    r"(?!\[REDACTED\])\S+"
)

# `*_URL` / `*_DSN` in `KEY=value` form, kept separate from `_KEY_SHAPED_ENV`
# because its lookahead is different: the value is skipped when it *contains* a
# redaction marker anywhere, not only when it starts with one. After
# `_URI_PASSWORD` has run, a connection URL reads
# `postgresql://user:[REDACTED]@host/db` -- already safe, and worth keeping in
# that form. This rule exists for the remaining case: a `*_URL` value that
# carries a credential in some shape `_URI_PASSWORD` does not recognise.
_KEY_SHAPED_URL = re.compile(r"(?i)\b([A-Z][A-Z0-9_]*_(?:URL|DSN)\s*=\s*)(?!\S*\[REDACTED\])\S+")

#: Patterns whose *values* are replaced wherever they appear in a log message.
#:
#: Matched on the rendered message rather than on argument names, because the
#: leak this guards against is a dict or a header mapping being formatted into
#: a message — at which point the structure that would have named the field is
#: already gone.
#:
#: Each pattern keeps the label and replaces what follows it, so a redacted line
#: still says *that* a token was present. A line with the evidence silently
#: deleted is harder to debug than one that says "there was a token here".
#:
#: **Order is load-bearing.** `_URI_PASSWORD` runs before `_KEY_SHAPED_URL` so
#: that `DATABASE_URL=postgresql://user:secret@host/db` keeps its host and user
#: rather than collapsing to `DATABASE_URL=[REDACTED]`. Each rule has a
#: negative-control test that removes it and asserts the leak returns.
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    # FA-05. A failed `psycopg.connect(...)` renders the source line holding the
    # DSN into its traceback, so a routine connection error wrote a live
    # database password into the log. First, so later rules see a URI whose
    # password is already gone.
    (_URI_PASSWORD, r"\1[REDACTED]@"),
    # `Authorization: Bearer <token>` and the bare `Bearer <token>` form, in
    # header dumps, f-strings and repr() output alike. Runs first so the scheme
    # survives redaction -- a line reading `Bearer [REDACTED]` still says what
    # kind of credential was present.
    (
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"),
        "Bearer [REDACTED]",
    ),
    # An Authorization header whose scheme is something else, or absent.
    #
    # The negative lookahead is what stops this undoing the rule above: without
    # it, `Authorization: Bearer [REDACTED]` matches again and collapses to
    # `Authorization: [REDACTED]`, losing the scheme the previous pattern
    # deliberately preserved. Already-redacted values are left alone.
    (
        re.compile(
            r"(?i)(['\"]?authorization['\"]?\s*[:=]\s*)(['\"]?)"
            r"(?!\[REDACTED\]|Bearer \[REDACTED\])[^'\",}\s][^'\",}]*"
        ),
        r"\1\2[REDACTED]",
    ),
    # Token- and password-shaped keys in dict/JSON/kwargs renderings.
    (
        re.compile(
            r"(?i)(['\"]?(?:access_token|refresh_token|api[_-]?key|apikey|password|secret)"
            r"['\"]?\s*[:=]\s*)(['\"]?)[^'\",}\s][^'\",}]*"
        ),
        r"\1\2[REDACTED]",
    ),
    # Credential-shaped environment variables. Last, so the rules above have
    # already handled the informative cases -- a `DATABASE_URL` whose password
    # this pattern would otherwise flatten along with its host.
    (_KEY_SHAPED_ENV, r"\1[REDACTED]"),
    (_KEY_SHAPED_URL, r"\1[REDACTED]"),
)


def redact(text: str) -> str:
    """Return `text` with credential-shaped values replaced.

    Exposed rather than kept private so it is directly testable: the assertion
    that a token never reaches a log is only worth as much as the test behind
    it, and testing through a whole logging pipeline tests the pipeline instead
    of the rule.
    """
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)

    return text


class RedactingFilter(logging.Filter):
    """Strips credential-shaped values from every record that passes.

    Attached to the handler rather than to a logger, so it applies to records
    from third-party libraries too — `httpx` and `uvicorn` both log request
    detail, and neither knows about ProjectOne's rules.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact the record in place and always admit it.

        Returns True unconditionally: this filter censors, it does not drop.
        Discarding a record because it contained a token would lose the event
        as well as the credential, and the event is usually the interesting
        part of an auth failure.
        """
        # Render first, then redact. `record.msg % record.args` is where a
        # header dict becomes a string, so redacting the parts separately would
        # miss anything that only looks like a credential once formatted.
        record.msg = redact(record.getMessage())
        record.args = None

        if record.exc_text:
            record.exc_text = redact(record.exc_text)

        return True


class RequestIdFilter(logging.Filter):
    """Attaches the current correlation id to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Bind `request_id` onto the record and always admit it."""
        # Set unconditionally rather than only when absent: a caller-supplied
        # `request_id` extra would otherwise be able to claim a different
        # request's id, which is precisely what this field must not allow.
        record.request_id = current_request_id()

        return True


def configure_logging(level: int = logging.INFO) -> None:
    """Install the application's logging pipeline.

    Idempotent: called from the application factory, which tests call many
    times per session. Re-running it replaces the handler rather than stacking
    another one, so a test suite does not end up printing every line 90 times.

    Args:
        level: The threshold for the root logger.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s",
        )
    )
    # Order matters. `RequestIdFilter` binds the attribute the formatter needs;
    # `RedactingFilter` rewrites the message. Both run before formatting, so
    # neither can be skipped by a handler that formats early.
    handler.addFilter(RequestIdFilter())
    handler.addFilter(RedactingFilter())
    # Marks this handler as ours, so re-running this function replaces it
    # without touching handlers installed by anyone else -- see below.
    handler.set_name(_HANDLER_NAME)

    root = logging.getLogger()
    root.setLevel(level)

    # Remove only the handler *this function* installed, never every handler on
    # the root logger.
    #
    # Clearing them all was indiscriminate: the application factory calls this,
    # and pytest's `caplog` attaches its capturing handler to the root logger,
    # so building an app inside a test silently destroyed the fixture's ability
    # to see any log record. Whether that happened depended on whether the
    # client fixture ran before or after `caplog` attached, which varies by
    # interpreter -- the assertion-rewriting tests passed on 3.14 and failed on
    # CI's 3.12 for exactly this reason.
    #
    # Removing by name keeps the idempotence this function needs (no stacked
    # duplicate handlers across the many factory calls a suite makes) without
    # taking anything that is not ours.
    for existing in list(root.handlers):
        if existing.get_name() == _HANDLER_NAME:
            root.removeHandler(existing)

    root.addHandler(handler)

    # uvicorn installs its own handlers on these and would otherwise emit a
    # second, unredacted copy of every access line it produces.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    """Return a module logger.

    A thin wrapper so call sites import from here rather than from `logging`
    directly — which keeps the pipeline above the only way a line is emitted.
    """
    return logging.getLogger(name)


def log_context(**fields: Any) -> str:  # noqa: ANN401 - arbitrary log fields by design
    """Render structured fields into a single, redacted message fragment.

    Returns `key=value` pairs. Redaction is applied here as well as in the
    filter, deliberately: two independent applications of the same rule, so a
    handler misconfiguration cannot be the single point of failure for a
    credential leak.
    """
    return redact(" ".join(f"{key}={value}" for key, value in fields.items()))
