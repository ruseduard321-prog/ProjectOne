"""Authentication router.

Validates input, calls the service, returns a response — nothing else
(CLAUDE.md §12).

**No error translation happens here.** `AuthError` and its subclasses are
mapped to status codes by the handlers in `app.core.errors`, registered once
for the whole application. This router previously owned that mapping in a
`_reject` helper; STEP-12 moved it, because a mapping that each router must
remember to apply is a mapping that a future router silently omits — and an
uncaught `AuthError` is a 500 where a 401 was meant.

The one exception below is deliberate and is not a translation: sign-up turns a
rejected registration into a 400 with a *different, generic* message, which is
a decision about this endpoint rather than about the error type.
"""

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import AccessTokenDep, AuthServiceDep, CurrentUserDep
from app.core.security import CredentialsRejectedError
from app.repositories.supabase_auth import AuthSession
from app.schemas.auth import (
    MessageResponse,
    ProfileResponse,
    RefreshRequest,
    SessionResponse,
    SignInRequest,
    SignUpRequest,
    SignUpResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_response(session: AuthSession) -> SessionResponse:
    """Convert a service-layer session into its response shape."""
    return SessionResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_in=session.expires_in,
        user_id=session.user_id,
        email=session.email,
    )


@router.post(
    "/sign-up",
    response_model=SignUpResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
)
def sign_up(request: SignUpRequest, auth_service: AuthServiceDep) -> SignUpResponse:
    """Register an identity and provision its ProjectOne profile.

    Returns 201 with a session, or 201 with `email_confirmation_required` when
    the project requires confirmation and no session was issued.
    """
    try:
        session = auth_service.sign_up(request.email, request.password)
    except CredentialsRejectedError as error:
        # 400, not 401: nothing was being authenticated. The message is
        # deliberately generic — "User already registered" would turn this
        # endpoint into an account-enumeration oracle.
        #
        # Caught here rather than in a handler because it is endpoint-specific:
        # the same exception from `sign_in` correctly means 401, and a
        # handler cannot tell the two apart. Every other `AuthError` falls
        # through to `app.core.errors`.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration could not be completed",
        ) from error

    if session is None:
        return SignUpResponse(
            user_id=None,
            email_confirmation_required=True,
            session=None,
        )

    return SignUpResponse(
        user_id=session.user_id,
        email_confirmation_required=False,
        session=_to_response(session),
    )


@router.post("/sign-in", response_model=SessionResponse, summary="Sign in")
def sign_in(request: SignInRequest, auth_service: AuthServiceDep) -> SessionResponse:
    """Exchange an email and password for a session."""
    return _to_response(auth_service.sign_in(request.email, request.password))


@router.post("/sign-out", response_model=MessageResponse, summary="Sign out")
def sign_out(access_token: AccessTokenDep, auth_service: AuthServiceDep) -> MessageResponse:
    """Revoke the session behind the supplied token.

    Requires a bearer token because it revokes *that* session upstream. A
    client-side discard would leave the token valid until it expired, which is
    not what signing out means.
    """
    auth_service.sign_out(access_token)

    return MessageResponse(message="Signed out")


@router.post("/refresh", response_model=SessionResponse, summary="Refresh a session")
def refresh(request: RefreshRequest, auth_service: AuthServiceDep) -> SessionResponse:
    """Exchange a refresh token for a new session."""
    return _to_response(auth_service.refresh(request.refresh_token))


@router.get("/me", response_model=ProfileResponse, summary="The caller's profile")
def read_me(user: CurrentUserDep, auth_service: AuthServiceDep) -> ProfileResponse:
    """Return the profile of the authenticated caller.

    Also the endpoint that proves identity reaches the database: the row comes
    back keyed to the verified `sub` claim, and is provisioned on first use if
    the identity predates this API.
    """
    profile = auth_service.profile_for(user)

    return ProfileResponse(
        id=str(profile.id),
        email=profile.email,
        display_name=profile.display_name,
    )
