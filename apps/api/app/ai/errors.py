"""Provider failures, typed by what the router should do about them.

The hierarchy is organised around **one question**: is retrying this call
plausibly going to help? That is the only distinction the router acts on, so it
is the distinction the types encode. Organising instead by HTTP status or by
vendor error code would produce a taxonomy the router has to interpret, and an
interpretation living in a `match` statement is one every new provider can get
subtly wrong.

    ProviderError                     (base -- never raised directly)
    +-- RetryableProviderError        retry, then fall back
    |   +-- ProviderTimeoutError
    |   +-- ProviderUnavailableError
    |   +-- ProviderRateLimitedError
    +-- TerminalProviderError         do not retry; fall back if possible
        +-- ProviderAuthenticationError
        +-- ProviderRequestError

## Why terminal errors still fall back

A rejected credential is terminal *for that provider* and says nothing about the
next one -- a workspace whose OpenAI key has been revoked can still be served by
Anthropic. What terminal means is "do not try this provider again with this
request", not "give up".

`ProviderAuthenticationError` is the case that makes this concrete, and it is
also the one where retrying is actively harmful: a wrong key retried three times
is three chances to trip the provider's own abuse detection on the workspace's
account.
"""


class ProviderError(Exception):
    """Base class for every provider failure.

    Never raised directly -- the router branches on the two subclasses below,
    and an error that is neither is a bug in a provider adapter rather than a
    third case to handle.

    Carries a `public_message` like every other error in this codebase
    (`app.core.security`), so the HTTP layer never has to decide what is safe to
    show a user. Vendor error text can quote request content back, and request
    content is the user's own prompt -- which may be exactly what they would not
    want echoed into an error surface (CLAUDE.md §24).
    """

    #: What a client is told. Deliberately generic: the specific cause goes to
    #: the log, where it is a debugging aid rather than a disclosure.
    public_message = "The AI provider could not complete this request"

    def __init__(self, message: str, provider: str | None = None) -> None:
        """Record the internal cause and which provider produced it.

        Args:
            message: The internal detail. Logged, never returned to a client.
            provider: Which provider failed, when known. Optional because a
                failure can occur before any provider is chosen.
        """
        super().__init__(message)
        self.provider = provider


class RetryableProviderError(ProviderError):
    """The call failed for a reason that may not recur.

    A timeout, a 503, a rate limit. The router retries these up to its hard
    ceiling and then falls back (CLAUDE.md §15a -- the ceiling is not optional,
    and "retry until it works" is the forbidden shape).
    """


class ProviderTimeoutError(RetryableProviderError):
    """The provider did not answer within the configured timeout."""

    public_message = "The AI provider took too long to respond"


class ProviderUnavailableError(RetryableProviderError):
    """The provider is unreachable or returned a server error."""

    public_message = "The AI provider is temporarily unavailable"


class ProviderRateLimitedError(RetryableProviderError):
    """The provider refused the call because *its* rate limit was hit.

    Distinct from ProjectOne's own `RateLimitExceededError`, and the two must
    not be conflated: that one means the caller has spent their allowance here,
    this one means the workspace's own upstream account is throttled. The remedy
    differs -- ours is to wait, this one's is to fall back to another provider
    the workspace is not currently throttled on.
    """

    public_message = "The AI provider is rate limiting this workspace"


class TerminalProviderError(ProviderError):
    """The call failed for a reason retrying cannot fix.

    The router does not retry these. It still falls back, because terminal is
    scoped to the provider that raised it -- see the module docstring.
    """


class ProviderAuthenticationError(TerminalProviderError):
    """The provider rejected the credential.

    Almost always a revoked, mistyped or wrong-provider BYOK key. Terminal by
    design: retrying a rejected credential cannot succeed, and repeating it
    risks the workspace's upstream account being flagged.

    **The key itself never appears in this error.** The message says which
    provider rejected it, never what was sent.
    """

    public_message = "The stored API key for this provider was rejected"


class ProviderRequestError(TerminalProviderError):
    """The provider rejected the request as malformed or unsupported.

    A context window exceeded, an unknown model name, an unsupported parameter.
    Retrying an identical request produces an identical rejection, so the router
    moves on rather than spending the ceiling on a certainty.
    """

    public_message = "The request could not be processed by the AI provider"


class NoProviderAvailableError(ProviderError):
    """Selection found no provider able to serve the request.

    Deliberately **not** a subclass of either branch: nothing was attempted, so
    "retryable" is not a meaningful property of it. Raised when every candidate
    was filtered out -- no configured key, no matching capability, or every
    provider marked unhealthy.

    This is the honest answer to an impossible request, and it is surfaced as
    one. Returning a degraded or canned response here is precisely the
    "confident-sounding output" CLAUDE.md §15 forbids.
    """

    public_message = "No AI provider is currently available for this workspace"


class AllProvidersFailedError(ProviderError):
    """Every candidate provider was tried and every one failed.

    Distinct from `NoProviderAvailableError`, which means none was *eligible*.
    This one means the fallback chain ran to exhaustion, which is a different
    operational signal: the first is usually a configuration problem, the second
    is usually an outage.
    """

    public_message = "Every available AI provider failed to complete this request"
