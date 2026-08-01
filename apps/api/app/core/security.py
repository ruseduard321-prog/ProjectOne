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


class IdentityProviderError(AuthError):
    """Supabase Auth was unreachable or returned an unexpected response."""

    public_message = "The identity provider is unavailable"
