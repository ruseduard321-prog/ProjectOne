"""Request and response contracts for the authentication endpoints.

Every external input is validated by a schema before it reaches business logic
(CLAUDE.md §12, §16). Nothing here accepts a user id: identity comes from a
verified token, never from a request body — a `user_id` field on a sign-in
request is an impersonation endpoint with extra steps.
"""

from pydantic import BaseModel, EmailStr, Field


class SignUpRequest(BaseModel):
    """Credentials for registering a new account."""

    email: EmailStr

    # Supabase enforces its own minimum; this is ProjectOne's floor, applied
    # before the request leaves the process. The upper bound is not decoration:
    # the password is hashed upstream, and an unbounded input is free CPU for
    # whoever sends a megabyte of it.
    password: str = Field(min_length=8, max_length=128)


class SignInRequest(BaseModel):
    """Credentials for signing in."""

    email: EmailStr

    # Deliberately *not* length-validated the way sign-up is. A minimum here
    # would reject a short legacy password with a validation error that differs
    # from a wrong-password error — telling an attacker their guess was the
    # wrong shape rather than merely wrong.
    password: str = Field(max_length=128)


class RefreshRequest(BaseModel):
    """A refresh token being exchanged for a new session."""

    refresh_token: str = Field(min_length=1, max_length=2048)


class SessionResponse(BaseModel):
    """The tokens and identity returned by a successful sign-in."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    email: str | None


class SignUpResponse(BaseModel):
    """The outcome of a registration.

    `session` is None when the project requires email confirmation: the account
    exists but is not signed in yet. That is a normal outcome, so it is modelled
    rather than treated as an error.
    """

    user_id: str | None
    email_confirmation_required: bool
    session: SessionResponse | None


class ProfileResponse(BaseModel):
    """The caller's own profile."""

    id: str
    email: str
    display_name: str | None


class MessageResponse(BaseModel):
    """A bare acknowledgement, used where there is nothing else to return."""

    message: str
