"""Errors raised by the authentication layer.

Typed rather than stringly-typed so routers can translate a cause into a status
code without inspecting messages (CLAUDE.md §24). Every one of these carries a
message safe to return to a client: the detail that would help an attacker
distinguish "expired" from "wrong signature" stays in the log, not the response.
"""


class AuthError(Exception):
    """Base class for every authentication failure.

    Routers catch this one type and return 401. Subclasses exist so logs and
    tests can be specific about *why* without the response body ever being.
    """

    #: What a client is told. Deliberately identical across subclasses.
    public_message = "Not authenticated"


class InvalidTokenError(AuthError):
    """The token is missing, malformed, expired, or fails signature checks.

    One class covers all of those on purpose. Telling a caller which of them
    happened tells an attacker whether a token was ever valid, whether it has
    merely expired, and whether the signing key is right — a free oracle for
    refining an attack. The distinction is preserved in the log message, which
    is where it is useful and not exploitable.
    """


class SigningKeyUnavailableError(AuthError):
    """The signing keys could not be fetched from Supabase.

    Separate from `InvalidTokenError` because it is *our* fault, not the
    caller's: the token may well be valid and unverifiable. It still surfaces as
    401 rather than 500 — an unverifiable token must never be honoured — but
    conflating the two in logs would hide a Supabase outage behind what looks
    like a wave of bad credentials.
    """


class CredentialsRejectedError(AuthError):
    """Supabase rejected a sign-up or sign-in attempt."""

    public_message = "Invalid credentials"


class AuthorizationError(Exception):
    """The caller is authenticated but may not perform this action.

    Deliberately **not** an `AuthError` subclass. Every `AuthError` is mapped to
    401 by the routers, and folding authorization into that hierarchy would make
    a permission failure indistinguishable from a credential failure -- telling
    a user their session is broken when it is fine, and prompting a client to
    throw away a perfectly valid token and re-authenticate in a loop.

    401 means "I do not know who you are." 403 means "I know exactly who you are
    and the answer is still no." Conflating them is a correctness bug before it
    is a security one.
    """

    #: What a client is told. Names neither the required permission nor the
    #: caller's actual role: a 403 that explains precisely which role would have
    #: worked is a map of the permission model handed to whoever probes it.
    public_message = "You do not have permission to perform this action"


class LastOwnerError(Exception):
    """The action would leave a workspace with no owner.

    Deliberately **not** an `AuthorizationError`, because it is not one: the
    caller has every permission required and the request is refused anyway. An
    owner leaving their own workspace holds `LEAVE_WORKSPACE`; what stops them
    is the state of the workspace, not their role.

    Mapping it to 403 would tell an owner they lack a permission they demonstrably
    have, and no amount of re-authenticating or role-changing would fix it. It is
    a **409 Conflict** -- the request conflicts with the resource's current state,
    and the caller resolves it by transferring ownership first.

    The database enforces this independently, via
    `trg_workspace_members_protect_last_owner`. This exception exists so the
    answer is legible rather than a raw constraint violation.
    """

    #: Unlike the authorization messages, this one is deliberately specific and
    #: actionable. It leaks nothing -- the caller is an owner of the workspace
    #: and already knows who is in it -- and withholding the reason here would
    #: leave them unable to work out what to do next.
    public_message = "The last owner cannot leave. Transfer ownership to another member first."


class WorkspaceAccessError(AuthorizationError):
    """The caller is not a live member of the workspace they addressed.

    Distinct from a role being insufficient, and it must **not** be distinct in
    the response. A 404-versus-403 difference here reveals whether a workspace
    id exists at all, turning any endpoint taking a workspace id into an
    existence oracle. Both surface identically to the client; only the log
    knows which happened.
    """


class IdentityProviderError(AuthError):
    """Supabase Auth was unreachable or returned an unexpected response."""

    public_message = "The identity provider is unavailable"


class RateLimitExceededError(Exception):
    """The caller has spent their allowance for a route.

    Deliberately **not** an `AuthError` and not an `AuthorizationError`. The
    caller's credentials are valid and their permissions sufficient; only their
    request rate is not. Mapping it to 401 would send a correct client into a
    token-refresh loop over a condition refreshing cannot fix, and 403 would
    tell them to change a role that is already correct.

    Raised by the per-user limiter, which runs as a dependency because ASGI
    middleware executes before any identity is verified (ADR-002 §2). The
    middleware limiter answers its own 429 directly, since it runs outside the
    handler chain by definition -- the two responses are deliberately identical
    in shape so a caller cannot tell which limiter refused them.
    """

    #: Identical to the middleware limiter's message. A difference between the
    #: two would reveal whether the endpoint treated the caller as
    #: authenticated, which is information a refusal must not carry.
    public_message = "Too many requests. Try again shortly."

    def __init__(self, retry_after_seconds: int) -> None:
        """Record how long the caller should wait.

        Args:
            retry_after_seconds: Window width, surfaced as `Retry-After`.
        """
        super().__init__(self.public_message)
        self.retry_after_seconds = retry_after_seconds
