"""Cross-cutting request middleware.

Three concerns every endpoint inherits without declaring anything: a
correlation id, a request log line, and rate limiting. Each is here rather than
in a router because a convention a route has to opt into is a convention some
route will eventually forget (CLAUDE.md §14).
"""

import json
import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.api import REQUEST_ID_HEADER, request_id_var
from app.core.logging import get_logger, log_context

logger = get_logger(__name__)

_NextCall = Callable[[Request], Awaitable[Response]]

#: Characters a caller-supplied correlation id may contain.
#:
#: An id from a request header is untrusted input that lands in every log line
#: this request produces (CLAUDE.md §16). Unvalidated, it is a log-injection
#: vector: a newline lets a caller forge log entries, and unbounded length lets
#: them flood the log. Anything failing this check is replaced rather than
#: rejected — the request is fine, only its proposed id is not.
_ID_ALPHABET = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
_ID_MAX_LENGTH = 128


def _sanitize_request_id(supplied: str | None) -> str:
    """Return a safe correlation id, honouring the caller's when it is valid."""
    if supplied is None:
        return str(uuid.uuid4())

    if 0 < len(supplied) <= _ID_MAX_LENGTH and set(supplied) <= _ID_ALPHABET:
        return supplied

    return str(uuid.uuid4())


async def _stamp_request_id(response: Response, request_id: str) -> Response:
    """Ensure a JSON error body carries the correlation id.

    The handlers in `app.core.errors` already add it, and this changes nothing
    for the responses they produce. It exists for the errors that never reach a
    handler at all:

    - Starlette answers an unmatched route with its own 404, inside the router
      rather than through the application's exception handlers.
    - The rate limiter below returns its 429 directly from middleware, which by
      definition runs outside the handler chain.

    Without this, "every error body carries a request id" would be true of most
    errors — and the exceptions would be exactly the two a user is most likely
    to report, since a 404 and a 429 are both things that happen to callers who
    then ask why.

    Success responses are left alone: a request id belongs in the header there,
    and rewriting a 200 body would corrupt any non-object payload (a list, as
    `GET /workspaces` returns) for no benefit.
    """
    if response.status_code < status.HTTP_400_BAD_REQUEST:
        return response

    if not response.headers.get("content-type", "").startswith("application/json"):
        return response

    # Streaming responses have no materialised body; `BaseHTTPMiddleware` wraps
    # everything as one, so the body is drained and rebuilt rather than read.
    body = b"".join([section async for section in response.body_iterator])  # type: ignore[attr-defined]

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Not something this middleware understands. Returned untouched rather
        # than replaced: a body it cannot parse is still the answer the caller
        # is owed, and swallowing it would turn a legible error into a blank.
        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    if isinstance(payload, dict) and "request_id" not in payload:
        payload["request_id"] = request_id

    return JSONResponse(
        content=payload,
        status_code=response.status_code,
        headers={
            # Content-Length is dropped deliberately: the body just changed
            # length, and a stale header is a truncated response.
            key: value
            for key, value in response.headers.items()
            if key.lower() != "content-length"
        },
    )


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Binds a correlation id to the request and logs its outcome.

    Outermost of the three, so the id exists before anything else can log —
    including the rate limiter's refusal, which is a line worth correlating.
    """

    async def dispatch(self, request: Request, call_next: _NextCall) -> Response:
        """Bind an id, serve the request, log it, echo the id back."""
        request_id = _sanitize_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = request_id_var.set(request_id)
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            # Logged before re-raising so the failure carries a correlation id.
            # Starlette's own handler produces the 500; this only ensures the
            # id is in the log next to the traceback rather than absent from it.
            duration_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                log_context(
                    method=request.method,
                    path=request.url.path,
                    status="500",
                    duration_ms=f"{duration_ms:.1f}",
                )
            )
            request_id_var.reset(token)
            raise

        duration_ms = (time.perf_counter() - started) * 1000

        # The query string is deliberately excluded. `request.url.path` is the
        # path alone; logging the full URL would capture query parameters, and
        # CLAUDE.md §16 forbids personal or sensitive data reaching a log
        # through one. Headers are excluded for the same reason — that is where
        # `Authorization` lives.
        logger.info(
            log_context(
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=f"{duration_ms:.1f}",
            )
        )

        response = await _stamp_request_id(response, request_id)
        response.headers[REQUEST_ID_HEADER] = request_id
        request_id_var.reset(token)

        return response


class RateLimitRule:
    """How many requests a client may make to a path within a window."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        """Record the allowance.

        Args:
            limit: Requests permitted per client per window.
            window_seconds: The width of the sliding window, in seconds.
        """
        self.limit = limit
        self.window_seconds = window_seconds


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Refuses a client that exceeds a path's allowance.

    **In-process, per-worker.** The counters live in this worker's memory, so N
    workers permit up to N times the configured limit. That is stated rather
    than hidden: the purpose here is to stop credential stuffing and runaway
    clients from reaching Supabase unthrottled, and a limit that is approximate
    across workers still does that. A globally exact limit needs shared state
    (Redis), which is a new infrastructure dependency and therefore an ADR
    (CLAUDE.md §10, §28) — not something to introduce inside a conventions step.

    Supabase applies its own limits upstream regardless, so this is a second
    layer rather than the only one.
    """

    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        rules: dict[str, RateLimitRule],
    ) -> None:
        """Install the middleware with a path-keyed rule table.

        Args:
            app: The ASGI application being wrapped.
            rules: Rules keyed by exact request path. A path with no rule is
                not limited — limiting everything by default would throttle
                `/health`, and an unreachable health check reports an outage
                that the check itself caused.
        """
        super().__init__(app)
        self._rules = rules
        # Keyed by (client, path) so exhausting the sign-in allowance does not
        # also lock the caller out of sign-up: they are separate protections of
        # separate things.
        self._hits: dict[tuple[str, str], deque[float]] = {}

    def _client_key(self, request: Request) -> str:
        """Return the identity a limit is counted against.

        The peer address, never a header. `X-Forwarded-For` is caller-supplied
        and trivially spoofed, so counting against it would let an attacker
        reset their own allowance by changing one header — a rate limiter that
        the attacker controls. When ProjectOne runs behind a proxy that
        terminates client connections, the correct fix is to configure the
        trusted-proxy handling at that layer, not to trust the header here.
        """
        client = request.client

        return client.host if client is not None else "unknown"

    def _is_allowed(self, key: tuple[str, str], rule: RateLimitRule, now: float) -> bool:
        """Record a hit and report whether it was within the allowance."""
        cutoff = now - rule.window_seconds
        hits = self._hits.setdefault(key, deque())

        while hits and hits[0] <= cutoff:
            hits.popleft()

        # Empty deques are dropped so an idle key does not occupy memory
        # forever. Without this, the dict grows once per distinct client
        # address and never shrinks — a slow leak that only shows up in
        # production, where the address space is large.
        if not hits:
            del self._hits[key]
            self._hits[key] = hits

        if len(hits) >= rule.limit:
            return False

        hits.append(now)

        return True

    async def dispatch(self, request: Request, call_next: _NextCall) -> Response:
        """Serve the request unless its allowance is exhausted."""
        rule = self._rules.get(request.url.path)

        if rule is None:
            return await call_next(request)

        now = time.monotonic()
        key = (self._client_key(request), request.url.path)

        if not self._is_allowed(key, rule, now):
            # Logged at warning: a client hitting a limit on an auth endpoint is
            # either broken or probing, and both are worth seeing. The path is
            # logged; the body — which holds the credentials being tried — is
            # not.
            logger.warning(
                log_context(
                    event="rate_limit_exceeded",
                    path=request.url.path,
                    limit=rule.limit,
                    window_seconds=rule.window_seconds,
                )
            )

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many requests. Try again shortly."},
                headers={"Retry-After": str(rule.window_seconds)},
            )

        return await call_next(request)
