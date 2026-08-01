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
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
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

    root = logging.getLogger()
    root.setLevel(level)

    for existing in list(root.handlers):
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
