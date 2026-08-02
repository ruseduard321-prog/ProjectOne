"""Per-user rate limiting for authenticated routes.

Separate from the middleware limiter by necessity, not by preference. ASGI
middleware runs *before* FastAPI resolves dependencies, so at the moment
`RateLimitMiddleware` executes there is no verified identity to key on -- the
token has not been checked yet. A limiter wanting a `user_id` there would have
to verify the token itself, duplicating auth logic into a second place nobody
would think to audit when the first one changed (ADR-002 §2).

So the split follows how the two classes genuinely differ:

- **Public routes** are limited in middleware, keyed on the resolved client
  address, refusing before any work happens -- the entire point of limiting an
  endpoint reachable without a credential.
- **Authenticated routes** are limited here, keyed on the `user_id` the
  *validated* auth context produced.

The identity is never read from a header, a body field, or an unverified claim.
It arrives through the same `get_current_user` dependency every other
authenticated route uses, so a caller cannot influence which bucket they are
counted against -- the property that makes the limit real rather than
decorative.

**In-process and per-worker**, like the middleware limiter beside it: N workers
permit up to N times each configured allowance. That approximation was stated
openly in STEP-12 and is unchanged here -- this step fixes *what is counted*,
not *where counts live*. ADR-002 §Future Evolution records the migration path
to a shared store and the Availability First posture Foundation adopts if that
store is ever unreachable.
"""

import time
import uuid
from collections import deque
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends

from app.core.dependencies import CurrentUserDep
from app.core.logging import get_logger, log_context
from app.core.security import RateLimitExceededError

logger = get_logger(__name__)


class UserRateLimiter:
    """Sliding-window request counts, keyed by verified user and scope.

    The counter logic mirrors `RateLimitMiddleware` deliberately: two limiters
    that drifted in their window semantics would leave one of them wrong in a
    way only a load test would ever surface.
    """

    def __init__(self) -> None:
        """Start with no recorded traffic."""
        self._hits: dict[tuple[str, str], deque[float]] = {}

    def clear(self) -> None:
        """Discard all recorded traffic.

        Exists for tests. Without it, one test exhausting an allowance leaks
        that state into every test running afterwards in the same process, and
        the failure surfaces in whichever test happens to run next rather than
        in the one that caused it.
        """
        self._hits.clear()

    def check(self, user_id: uuid.UUID, scope: str, limit: int, window_seconds: int) -> None:
        """Record a request and refuse it if the allowance is spent.

        Args:
            user_id: The **verified** caller, from the auth context.
            scope: What the allowance protects. Distinct scopes never share a
                bucket, so exhausting one route cannot lock a user out of an
                unrelated one.
            limit: Requests permitted per user per window.
            window_seconds: Width of the sliding window.

        Raises:
            RateLimitExceededError: when the allowance is already spent.
        """
        now = time.monotonic()
        # `user:` namespacing matches ADR-002 §1. The two limiters share no
        # storage today; a key ambiguous about what it identifies is a defect
        # waiting for the first refactor that makes them share it.
        key = (f"user:{user_id}", scope)
        cutoff = now - window_seconds
        hits = self._hits.setdefault(key, deque())

        while hits and hits[0] <= cutoff:
            hits.popleft()

        # Idle keys are dropped so the dict does not grow once per user and
        # never shrink -- the same leak the middleware limiter avoids, and more
        # pressing here: the key space is every user who ever signs in.
        if not hits:
            del self._hits[key]
            self._hits[key] = hits

        if len(hits) >= limit:
            # The identity *class*, never the user id. Which bucket filled is
            # the diagnostic; a user identifier in a log line is personal data
            # under Privacy and Data Protection, and this line is emitted on
            # exactly the traffic most likely to be automated.
            logger.warning(
                log_context(
                    event="rate_limit_exceeded",
                    scope=scope,
                    identity="user",
                    limit=limit,
                    window_seconds=window_seconds,
                )
            )

            raise RateLimitExceededError(window_seconds)

        hits.append(now)


#: The process-wide limiter.
#:
#: A module global rather than a `Depends`-constructed instance because the
#: counters *are* the state: a per-request instance would start empty each time
#: and limit nothing. Reached through `get_user_rate_limiter` so a test can
#: override it via `app.dependency_overrides` rather than patching this module.
_limiter = UserRateLimiter()


def get_user_rate_limiter() -> UserRateLimiter:
    """Return the process-wide per-user limiter."""
    return _limiter


UserRateLimiterDep = Annotated[UserRateLimiter, Depends(get_user_rate_limiter)]


def limit_by_user(scope: str, limit: int, window_seconds: int) -> Callable[..., None]:
    """Build a dependency limiting a route to `limit` requests per verified user.

    A factory because a FastAPI dependency takes no arguments of its own -- the
    allowance is captured at import time, in the route declaration, which is
    where it belongs and where a reviewer will actually see it:

        @router.post(
            "/expensive",
            dependencies=[Depends(limit_by_user("ai", 20, 60))],
        )

    Args:
        scope: Bucket name. Routes sharing a scope share an allowance, which is
            what makes "20 AI calls a minute across every AI route" expressible
            rather than requiring one bucket per path.
        limit: Requests permitted per user per window.
        window_seconds: Width of the sliding window.

    Returns:
        A dependency raising `RateLimitExceededError` when the allowance is
        spent, translated to 429 by `app.core.errors`.
    """

    def dependency(
        user: CurrentUserDep,
        limiter: UserRateLimiterDep,
    ) -> None:
        limiter.check(user.id, scope, limit, window_seconds)

    return dependency
