"""API-wide conventions every endpoint inherits.

One place for the decisions that must not be re-made per endpoint: where the
version lives in a URL, and what a request is called in logs and error bodies.
A convention re-decided per router is not a convention (CLAUDE.md §14).
"""

import contextvars

#: The current major version of the public API.
#:
#: **URL prefix, not header negotiation.** A version in the path is visible in
#: an access log, a `curl` command, a browser address bar and an edge routing
#: rule; a version in an `Accept` header is visible in none of them, and a
#: client that forgets it silently receives whatever the server defaults to.
#: The cost is that the version appears in every URL, which is precisely the
#: property that makes it hard to get wrong.
#:
#: v2 does not replace this constant — it is added alongside it, so both can be
#: served while clients migrate. That is what versioning is for, and it is why
#: no route hardcodes the prefix string.
API_VERSION = "v1"

#: The prefix every product route is mounted under.
#:
#: `/health` is deliberately **not** mounted here. It is consumed by
#: orchestrators and uptime checks, not by API clients, and its contract is
#: "the process is ready" rather than a product interface. Versioning it would
#: mean a deploy configuration change every time the API version moves, for a
#: payload whose shape is not a public contract.
API_PREFIX = f"/api/{API_VERSION}"

#: The header carrying a request's correlation id, in and out.
#:
#: Read from the request when a caller (or an upstream proxy) supplies one so a
#: trace survives a hop, generated when they do not, and always echoed back so
#: a user reporting a failure can quote the id from the response they saw.
REQUEST_ID_HEADER = "X-Request-ID"

#: The correlation id of the request being served on this task.
#:
#: A `ContextVar` rather than a module global because the two are not the same
#: thing under concurrency: a global would be shared across every request the
#: worker is handling at once, so a log line would carry whichever id happened
#: to be set last. A context variable is bound per task, which is the scope a
#: request actually has.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default="-",
)


def current_request_id() -> str:
    """Return the correlation id of the request being served.

    Returns `"-"` outside a request — a startup log line has no request to
    correlate to, and a placeholder keeps the log format fixed-width rather
    than making the field conditionally absent.
    """
    return request_id_var.get()
